import logging
from datetime import datetime

from bson import ObjectId
from mm_base6 import Service
from mm_concurrency import AsyncTaskRunner, async_synchronized_by_arg_value
from mm_result import Result
from mm_std import utc_delta, utc_now

from app.core.blockchains import aptos, evm, starknet
from app.core.constants import Naming
from app.core.db import NamingProblem
from app.core.types import AppCore

logger = logging.getLogger(__name__)


class NameService(Service):
    core: AppCore

    @async_synchronized_by_arg_value(index=1)
    async def check_next_naming(self, naming: Naming) -> None:
        if not self.core.state.check_namings:
            return
        # self.logger.debug("check_next_naming called: %s", naming)

        # first check accounts that were never checked
        need_to_check = await self.core.db.account_name.find(
            {"naming": naming, "checked_at": None}, limit=self.core.settings.limit_naming_workers
        )
        if len(need_to_check) < self.core.settings.limit_naming_workers:
            need_to_check += await self.core.db.account_name.find(
                {"naming": naming, "checked_at": {"$lt": utc_delta(minutes=-1 * self.core.settings.check_name_interval)}},
                "checked_at",
                limit=self.core.settings.limit_naming_workers - len(need_to_check),
            )
        if not need_to_check:
            return

        runner = AsyncTaskRunner(self.core.settings.limit_naming_workers, name="check_names")
        for an in need_to_check:
            runner.add(str(an.id), self.check_account_name(an.id))
        await runner.run()

    async def check_account_name(self, id: ObjectId) -> Result[str | None]:
        account_name = await self.core.db.account_name.get(id)

        # self.logger.debug("check_account_name called: %s / %s", account_naming.naming, account_naming.account)

        match account_name.naming:
            case Naming.ENS:
                urls = self.core.services.network.get_rpc_urls(account_name.network)
                if not urls:
                    return Result.err("no_rpc_urls")
                res = await evm.get_ens_name(urls, account_name.account, proxies=self.core.state.proxies)
            case Naming.ANS:
                res = await aptos.get_ans_name(account_name.account, proxies=self.core.state.proxies)
            case Naming.STARKNET_ID:
                res = await starknet.get_starknet_id(account_name.account, proxies=self.core.state.proxies)
            case _:
                return Result.err("not_implemented")

        if res.is_err():
            # logger.debug("check_account_name: %s", res.err)
            await self.core.db.naming_problem.insert_one(
                NamingProblem(
                    id=ObjectId(),
                    network=account_name.network,
                    naming=account_name.naming,
                    account=account_name.account,
                    message=res.unwrap_err(),
                )
            )
            return res

        name = res.unwrap() or ""
        await self.core.db.group_name.update_one(
            {"group": account_name.group, "naming": account_name.naming},
            {"$set": {f"names.{account_name.account}": name, f"checked_at.{account_name.account}": utc_now()}},
        )
        await self.core.db.account_name.set(id, {"name": name, "checked_at": utc_now()})

        return res

    async def calc_oldest_checked_time(self) -> dict[Naming, datetime | None]:
        res: dict[Naming, datetime | None] = {}
        for naming in list(Naming):
            res[naming] = None
            if not await self.core.db.account_name.exists({"naming": naming, "checked_at": None}):
                name = await self.core.db.account_name.find_one({"naming": naming}, "checked_at")
                if name:
                    res[naming] = name.checked_at
        return res
