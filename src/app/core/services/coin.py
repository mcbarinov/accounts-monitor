import logging
from datetime import datetime

import pydash
import tomlkit
from mm_base6 import Service
from mm_base6.core.utils import toml_dumps
from mm_concurrency import async_synchronized
from mm_mongo import MongoDeleteResult
from mm_std import replace_empty_dict_entries
from mm_web3 import Network, NetworkType
from pydantic import BaseModel

from app.core.db import Coin
from app.core.types import AppCore

logger = logging.getLogger(__name__)


class ImportCoinItem(BaseModel):
    network: Network
    symbol: str
    decimals: int
    token: str | None = None
    notes: str = ""

    @property
    def id(self) -> str:
        return f"{self.network.value}__{self.symbol}".lower()

    def to_db(self) -> Coin:
        return Coin(
            id=self.id, network=self.network, symbol=self.symbol, decimals=self.decimals, token=self.token, notes=self.notes
        )


class CoinCheckStats(BaseModel):
    class Stats(BaseModel):
        oldest_checked_time: datetime | None
        never_checked_count: int  # how many accounts have never been checked
        all_count: int  # how many accounts exist

    coins: dict[str, Stats]  # coin_id -> Stats


class CoinService(Service):
    core: AppCore

    def __init__(self) -> None:
        super().__init__()
        self.coins: list[Coin] = []

    @async_synchronized
    async def import_from_toml(self, toml_str: str) -> int:
        try:
            count = 0
            coins = [ImportCoinItem(**n) for n in tomlkit.loads(toml_str)["coins"]]  # type:ignore[arg-type,union-attr]
            for c in coins:
                if not await self.core.db.coin.exists({"_id": c.id}):
                    await self.core.db.coin.insert_one(c.to_db())
                    count += 1
            return count  # noqa: TRY300
        except Exception:
            logger.exception("Failed to import coins from TOML")
            return -1
        finally:
            await self.load_coins_from_db()

    def export_as_toml(self) -> str:
        coins = []
        for c in self.get_coins():
            coin = replace_empty_dict_entries(
                {"network": c.network, "symbol": c.symbol, "decimals": c.decimals, "token": c.token, "notes": c.notes}
            )
            coins.append(coin)
        return toml_dumps({"coins": coins})

    async def load_coins_from_db(self) -> None:
        self.coins = await self.core.db.coin.find({}, "_id")

    def get_coins(self) -> list[Coin]:
        return self.coins

    def get_coins_map(self) -> dict[str, Coin]:
        return {c.id: c for c in self.get_coins()}

    def explorer_token_map(self) -> dict[str, str]:  # coin_id -> explorer_token
        result: dict[str, str] = {}
        for coin in self.get_coins():
            if coin.token is not None:
                result[coin.id] = coin.network.explorer_token(coin.token)
            else:
                result[coin.id] = coin.network.explorer_token("")
                if result[coin.id].endswith("token/"):
                    result[coin.id] = result[coin.id].removesuffix("token/")
                if result[coin.id].endswith("coin/"):
                    result[coin.id] = result[coin.id].removesuffix("coin/")
        return result

    def get_coins_by_network_type(self) -> dict[NetworkType, list[Coin]]:
        coins = self.get_coins()
        coins_by_network_type: dict[NetworkType, list[Coin]] = {n: [] for n in NetworkType}
        for c in coins:
            coins_by_network_type[c.network.network_type].append(c)
        return coins_by_network_type

    def get_coin(self, id: str) -> Coin:
        res = pydash.find(self.coins, lambda c: c.id == id)
        if res is None:
            raise ValueError(f"Coin with id {id} not found")
        return res

    @async_synchronized
    async def delete(self, id: str) -> MongoDeleteResult:
        await self.core.db.group_balance.delete_many({"coin": id})
        await self.core.db.account_balance.delete_many({"coin": id})
        await self.core.db.group.update_many({"coins": id}, {"$pull": {"coins": id}})
        res = await self.core.db.coin.delete(id)
        await self.load_coins_from_db()
        return res

    async def calc_coin_check_stats(self) -> CoinCheckStats:
        result = CoinCheckStats(coins={})
        for coin in self.get_coins():
            oldest_checked_time = None
            never_checked_count = await self.core.db.account_balance.count({"coin": coin.id, "checked_at": None})
            if never_checked_count == 0:
                account_balance = await self.core.db.account_balance.find_one({"coin": coin.id}, "checked_at")
                if account_balance:
                    oldest_checked_time = account_balance.checked_at
            result.coins[coin.id] = CoinCheckStats.Stats(
                oldest_checked_time=oldest_checked_time,
                never_checked_count=never_checked_count,
                all_count=await self.core.db.account_balance.count({"coin": coin.id}),
            )

        return result
