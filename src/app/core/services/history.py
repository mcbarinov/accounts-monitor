import re
from datetime import datetime
from decimal import Decimal
from typing import cast

import pydash
from bson import ObjectId
from deepdiff import DeepDiff
from mm_base6 import Service
from mm_mongo import MongoInsertOneResult
from pydantic import BaseModel

from app.core.db import History
from app.core.services.group import GroupAccountsInfo
from app.core.types import AppCore


class Diff(BaseModel):
    class BalanceChanges(BaseModel):
        old_value: Decimal
        new_value: Decimal
        old_checked_at: datetime | None
        new_checked_at: datetime | None

    # balance_changed: dict[str, dict[str, tuple[Decimal, Decimal]]]  # coin -> address -> (old_value, new_value)
    balance_changed: dict[str, dict[str, BalanceChanges]]  # coin -> address -> BalanceChanges


# Helper to extract keys from DeepDiff paths.
def extract_keys(path: str) -> list[str]:
    # DeepDiff paths look like "root['network']['ticker']['address']"
    return re.findall(r"\['([^']+)']", path)


class HistoryService(Service):
    core: AppCore

    async def create(self, group_id: ObjectId) -> MongoInsertOneResult:
        group = await self.core.db.group.get(group_id)
        group_balances = await self.core.db.group_balance.find({"group": group_id})
        balances = {b.coin: b.balances for b in group_balances}
        balances_checked_at = {b.coin: b.checked_at for b in group_balances}
        group_namings = await self.core.db.group_name.find({"group": group_id})
        names = {n.naming: n.names for n in group_namings}
        names_checked_at = {n.naming: n.checked_at for n in group_namings}
        return await self.core.db.history.insert_one(
            History(
                id=ObjectId(),
                group=group,
                balances=balances,
                balances_checked_at=balances_checked_at,
                names=names,
                names_checked_at=names_checked_at,
            )
        )

    async def get_balances_diff(self, history_id: ObjectId) -> Diff:
        history = await self.core.db.history.get(history_id)
        group = await self.core.db.group.get(history.group.id)

        group_balances: dict[str, dict[str, Decimal]] = {}
        group_balances_checked_at: dict[str, dict[str, datetime]] = {}
        for gb in await self.core.db.group_balance.find({"group": group.id}):
            group_balances[gb.coin] = gb.balances
            group_balances_checked_at[gb.coin] = gb.checked_at

        history_balances = history.balances
        dd = DeepDiff(history_balances, group_balances, ignore_order=True)
        balances_changed: dict[str, dict[str, Diff.BalanceChanges]] = {}

        # Process values_changed for balance differences.
        for path, change in dd.get("values_changed", {}).items():
            keys = extract_keys(path)
            if len(keys) != 2:
                continue
            coin, address = keys
            balances_changed.setdefault(coin, {})[address] = Diff.BalanceChanges(
                old_value=Decimal(change["old_value"]),
                new_value=Decimal(change["new_value"]),
                old_checked_at=pydash.get(history.balances_checked_at, f"{coin}.{address}"),
                new_checked_at=pydash.get(group_balances_checked_at, f"{coin}.{address}"),
            )

        return Diff(balance_changed=balances_changed)

    async def get_history_group_accounts_info(self, history_id: ObjectId) -> GroupAccountsInfo:
        history = await self.core.db.history.get(history_id)

        balances = history.balances

        coins_sum: dict[str, Decimal] = {}
        for coin, coin_balances in balances.items():
            if coin_balances:
                coins_sum[coin] = cast(Decimal, sum(coin_balances.values()))

        return GroupAccountsInfo(
            coins_sum=coins_sum,
            balances=balances,
            names=history.names,
            coins_map=self.core.services.coin.get_coins_map(),
        )
