import asyncio
import logging
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import cast
from zipfile import ZipFile

import aiofiles
import pydash
import tomlkit
from bson import ObjectId
from mm_base6 import Service, UserError
from mm_base6.core.utils import toml_dumps
from mm_concurrency import async_synchronized
from mm_mongo import MongoDeleteResult
from mm_std import parse_lines
from mm_web3 import Network, NetworkType
from pydantic import BaseModel

from app.core import utils
from app.core.constants import Naming
from app.core.db import AccountBalance, AccountName, Coin, Group, GroupBalance, GroupName
from app.core.types import AppCore

logger = logging.getLogger(__name__)


@dataclass
class ProcessAccountBalancesResult:
    inserted: int
    deleted: int


@dataclass
class ProcessAccountNamingsResult:
    inserted: int
    deleted: int


class ImportGroupItem(BaseModel):
    name: str
    network_type: NetworkType
    notes: str
    coins: str
    namings: str
    accounts: str


class GroupAccountsInfo(BaseModel):
    coins_map: dict[str, Coin]  # coin_id -> Coin
    coins_sum: dict[str, Decimal]  # coin -> sum(balance)
    balances: dict[str, dict[str, Decimal]]  # coin -> account -> balance
    names: dict[Naming, dict[str, str]]  # naming -> account -> name

    def get_balance(self, coin: str, account: str) -> Decimal | None:
        return self.balances.get(coin, {}).get(account, None)

    def get_name(self, naming: Naming, account: str) -> str | None:
        return self.names.get(naming, {}).get(account, None)

    def explorer_address(self, coin: str, account: str) -> str:
        network = Network(coin.split("__")[0])
        return network.explorer_account(account)


class GroupService(Service):
    core: AppCore

    async def get_group_accounts_info(self, group: ObjectId) -> GroupAccountsInfo:
        balances: dict[str, dict[str, Decimal]] = {}
        for gb in await self.core.db.group_balance.find({"group": group}):
            balances[gb.coin] = gb.balances

        coins_sum: dict[str, Decimal] = {}
        for coin, coin_balances in balances.items():
            if coin_balances:
                coins_sum[coin] = cast(Decimal, sum(coin_balances.values()))

        namings: dict[Naming, dict[str, str]] = {}
        for gn in await self.core.db.group_name.find({"group": group}):
            namings[gn.naming] = gn.names

        return GroupAccountsInfo(
            coins_sum=coins_sum, balances=balances, names=namings, coins_map=self.core.services.coin.get_coins_map()
        )

    async def create_group(
        self, name: str, network_type: NetworkType, notes: str, namings: list[Naming], coin_ids: list[str]
    ) -> Group:
        # Check if the namings are consistent with the network type
        for naming in namings:
            if not naming.is_consistent(network_type):
                raise UserError(f"Naming {naming.name} is not consistent with the network type {network_type.value}")
        # Check if the coins are consistent with the network type
        for coin_id in coin_ids:
            if self.core.services.coin.get_coin(coin_id).network.network_type != network_type:
                raise UserError(f"Coin {coin_id} is not consistent with the network type {network_type.value}")

        new_group = Group(id=ObjectId(), name=name, network_type=network_type, notes=notes)
        await self.core.db.group.insert_one(new_group)
        for naming in namings:
            await self.add_naming(new_group.id, naming)
        for coin in coin_ids:
            await self.add_coin(new_group.id, coin)
        return new_group

    async def export_as_toml(self) -> str:
        groups = []
        for group in await self.core.db.group.find({}):
            obj = group.model_dump()
            obj = pydash.omit(obj, "_id")
            obj["coins"] = tomlkit.string("\n".join(obj["coins"]), multiline=True)
            obj["namings"] = tomlkit.string("\n".join(obj["namings"]), multiline=True)
            obj["accounts"] = tomlkit.string("\n".join(obj["accounts"]), multiline=True)
            groups.append(obj)

        return toml_dumps({"groups": groups})

    @async_synchronized
    async def import_from_toml(self, toml: str) -> int:
        known_coins = [c.id for c in self.core.services.coin.get_coins()]
        count = 0
        for data in utils.toml_loads(toml)["groups"]:  # type:ignore[union-attr]
            group = ImportGroupItem(**cast(dict[str, object], data))
            if not await self.core.db.group.exists({"name": group.name}):
                coin_ids = [c.strip() for c in group.coins.split("\n") if c.strip()]
                unknown_coins = [c for c in coin_ids if c not in known_coins]
                if unknown_coins:
                    raise ValueError(f"unknown coins: {unknown_coins}")
                namings = [Naming(n.strip()) for n in group.namings.split("\n") if n.strip()]
                accounts = [a.strip() for a in group.accounts.split("\n") if a.strip()]
                if group.network_type.lowercase_address():
                    accounts = [a.lower() for a in accounts]

                created_group = await self.create_group(group.name, group.network_type, group.notes, namings, coin_ids)
                await self.update_accounts(created_group.id, accounts)
                count += 1
        return count

    @async_synchronized
    async def import_from_zip(self, archive: Path) -> int:
        def unzip(source: Path) -> None:
            with ZipFile(source, "r") as zip_file:
                zip_file.extractall(path=archive.parent)

        await asyncio.to_thread(unzip, archive)

        result = 0
        network_types = [n.value for n in NetworkType]
        for network_type_dir in await asyncio.to_thread(archive.parent.iterdir):
            if network_type_dir.is_dir() and network_type_dir.name in network_types:
                for file in await asyncio.to_thread(network_type_dir.iterdir):
                    if file.is_file() and file.name.endswith(".txt"):
                        network_type = NetworkType(network_type_dir.name)
                        group_name = file.name.removesuffix(".txt")
                        if await self.core.db.group.exists({"name": group_name}):
                            continue

                        async with aiofiles.open(file) as f:
                            addresses = parse_lines(await f.read())
                            invalid_address = utils.find_invalid_address(network_type, addresses)
                            if invalid_address is not None:
                                raise UserError(f"Invalid address: {invalid_address}, for network_type: {network_type}")

                            namings = [n for n in Naming if n.is_consistent(network_type)]
                            networks = [n for n in Network if n.network_type == network_type]
                            coins = await self.core.db.coin.find({"network": {"$in": networks}})
                            coin_ids = [c.id for c in coins]

                            created_group = await self.create_group(
                                name=group_name, network_type=network_type, namings=namings, coin_ids=coin_ids, notes=""
                            )
                            await self.update_accounts(created_group.id, addresses)

        archive.unlink()
        return result

    async def delete_group(self, id: ObjectId) -> MongoDeleteResult:
        await self.core.db.account_balance.delete_many({"group": id})
        await self.core.db.account_name.delete_many({"group": id})
        await self.core.db.group_name.delete_many({"group": id})
        await self.core.db.group_balance.delete_many({"group": id})
        return await self.core.db.group.delete(id)

    async def update_accounts(self, id: ObjectId, accounts: list[str]) -> None:
        logger.debug("update_accounts", extra={"group_id": id, "accounts length": len(accounts)})
        group = await self.core.db.group.get(id)
        if group.network_type.lowercase_address():
            accounts = [a.lower() for a in accounts]
        await self.core.db.group.set(id, {"accounts": accounts})
        await self.process_account_balances(id)
        await self.process_account_names(id)

    async def update_coins(self, id: ObjectId, coin_ids: list[str]) -> None:
        logger.debug("update_coins", extra={"group_id": id, "coin_ids": coin_ids})
        group = await self.core.db.group.get(id)
        # Check if the coins are consistent with the network type
        for coin_id in coin_ids:
            if self.core.services.coin.get_coin(coin_id).network.network_type != group.network_type:
                raise UserError(f"Coin {coin_id} is not from the network type {group.network_type.value}")

        # Add new coins
        new_coins = [coin_id for coin_id in coin_ids if coin_id not in group.coins]
        for coin_id in new_coins:
            await self.add_coin(id, coin_id)

        # Delete coins that are not in the list
        delete_coins = [coin_id for coin_id in group.coins if coin_id not in coin_ids]
        for coin_id in delete_coins:
            await self.remove_coin(id, coin_id)

        if len(new_coins) > 0 or len(delete_coins) > 0:
            await self.process_account_balances(id)

    async def update_namings(self, id: ObjectId, namings: list[Naming]) -> None:
        logger.debug("update_namings", extra={"group_id": id, "namings": namings})
        group = await self.core.db.group.get(id)
        # Check if the namings are consistent with the network type
        for naming in namings:
            if not naming.is_consistent(group.network_type):
                raise UserError(f"Naming {naming.name} is not from the network type {group.network_type.value}")

        # Add new namings
        new_namings = [naming for naming in namings if naming not in group.namings]
        for naming in new_namings:
            await self.add_naming(id, naming)

        # Delete namings that are not in the list
        delete_namings = [naming for naming in group.namings if naming not in namings]
        for naming in delete_namings:
            await self.remove_naming(id, naming)

        if len(new_namings) > 0 or len(delete_namings) > 0:
            await self.process_account_names(id)

    @async_synchronized
    async def add_coin(self, group_id: ObjectId, coin_id: str) -> None:
        logger.debug("add_coin", extra={"group_id": group_id, "coin_id": coin_id})
        if not await self.core.db.coin.exists({"_id": coin_id}):
            raise UserError(f"Coin {coin_id} not found")
        group = await self.core.db.group.get(group_id)
        coin = self.core.services.coin.get_coin(coin_id)
        if coin.network.network_type != group.network_type:
            raise UserError(f"Coin {coin_id} is not from the network {group.network_type.value}")
        if coin_id in group.coins:
            raise UserError(f"Coin {coin_id} already in group {group.name}")

        await self.core.db.group.push(group_id, {"coins": coin_id})
        await self.core.db.group_balance.insert_one(GroupBalance(id=ObjectId(), group=group_id, coin=coin_id))
        if len(group.accounts) > 0:
            insert_many = [
                AccountBalance(id=ObjectId(), group=group_id, network=coin.network, coin=coin_id, account=account)
                for account in group.accounts
            ]
            await self.core.db.account_balance.insert_many(insert_many)

    @async_synchronized
    async def remove_coin(self, group_id: ObjectId, coin_id: str) -> None:
        logger.debug("remove_coin", extra={"group_id": group_id, "coin_id": coin_id})
        await self.core.db.account_balance.delete_many({"group": group_id, "coin": coin_id})
        await self.core.db.group_balance.delete_one({"group": group_id, "coin": coin_id})
        await self.core.db.group.pull(group_id, {"coins": coin_id})

    async def remove_naming(self, group_id: ObjectId, naming: Naming) -> None:
        logger.debug("remove_naming", extra={"group_id": group_id, "naming": naming})
        await self.core.db.account_name.delete_many({"group": group_id, "naming": naming})
        await self.core.db.group_name.delete_one({"group": group_id, "naming": naming})
        await self.core.db.group.pull(group_id, {"namings": naming.value})

    @async_synchronized
    async def add_naming(self, group_id: ObjectId, naming: Naming) -> None:
        logger.debug("add_naming", extra={"group_id": group_id, "naming": naming})
        group = await self.core.db.group.get(group_id)
        if naming in group.namings:
            raise UserError(f"Naming {naming.value} already in group {group.name}")
        if naming.network_type != group.network_type:
            raise UserError(f"Naming {naming.value} is not from the network {group.network_type.value}")

        await self.core.db.group.push(group_id, {"namings": naming.value})
        await self.core.db.group_name.insert_one(GroupName(id=ObjectId(), group=group_id, naming=naming))
        if len(group.accounts) > 0:
            insert_many = [
                AccountName(id=ObjectId(), group=group_id, network=naming.network, naming=naming, account=account)
                for account in group.accounts
            ]
            await self.core.db.account_name.insert_many(insert_many)

    @async_synchronized
    async def process_account_balances(self, id: ObjectId) -> ProcessAccountBalancesResult:
        """Create account balances for all coins and accounts in the group.
        And delete balances for accounts that are not in the group."""
        logger.debug("process_account_balances", extra={"group_id": id})
        group = await self.core.db.group.get(id)
        inserted = 0
        for coin_id in group.coins:
            known_accounts = [
                a["account"]
                async for a in self.core.db.account_balance.collection.find(
                    {"group": id, "coin": coin_id}, {"_id": False, "account": True}
                )
            ]
            new_accounts = [account for account in group.accounts if account not in known_accounts]
            if len(new_accounts) > 0:
                insert_many = [
                    AccountBalance(id=ObjectId(), group=id, network=coin_id.split("__")[0], coin=coin_id, account=account)
                    for account in new_accounts
                ]
                await self.core.db.account_balance.insert_many(insert_many)
                inserted += len(new_accounts)
        deleted = (
            await self.core.db.account_balance.delete_many({"group": id, "account": {"$nin": group.accounts}})
        ).deleted_count

        return ProcessAccountBalancesResult(inserted=inserted, deleted=deleted)

    @async_synchronized
    async def process_account_names(self, id: ObjectId) -> ProcessAccountNamingsResult:
        """Create account names for all namings and accounts in the group.
        And delete docs for accounts that are not in the group."""
        logger.debug("process_account_names", extra={"group_id": id})
        group = await self.core.db.group.get(id)
        inserted = 0
        for naming in group.namings:
            known_accounts = [
                a["account"]
                async for a in self.core.db.account_name.collection.find(
                    {"group": id, "naming": naming}, {"_id": False, "account": True}
                )
            ]
            new_accounts = [account for account in group.accounts if account not in known_accounts]
            if len(new_accounts) > 0:
                insert_many = [
                    AccountName(id=ObjectId(), group=id, network=naming.network, naming=naming, account=account)
                    for account in new_accounts
                ]
                await self.core.db.account_name.insert_many(insert_many)
                inserted += len(new_accounts)

        deleted = (await self.core.db.account_name.delete_many({"group": id, "account": {"$nin": group.accounts}})).deleted_count
        return ProcessAccountNamingsResult(inserted, deleted)

    async def reset_group_balances(self, id: ObjectId) -> None:
        await self.core.db.group_balance.update_many({"group": id}, {"$set": {"balances": {}}})
        await self.core.db.account_balance.update_many(
            {"group": id}, {"$set": {"balance": None, "balance_raw": None, "checked_at": None}}
        )
