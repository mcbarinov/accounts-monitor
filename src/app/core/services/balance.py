import logging
import time
from decimal import Decimal

from bson import ObjectId
from mm_base6 import Service
from mm_concurrency import AsyncTaskRunner, async_synchronized_by_arg_value
from mm_result import Result
from mm_std import utc_delta, utc_now
from mm_web3 import Network, NetworkType, random_node, random_proxy

from app.core.blockchains import aptos, evm, solana, starknet
from app.core.db import Coin, RpcMonitoring
from app.core.types import AppCore

logger = logging.getLogger(__name__)


class BalanceService(Service):
    core: AppCore

    @async_synchronized_by_arg_value(index=1)
    async def check_next_network(self, network: Network) -> int:
        # logger.debug("Checking next network", extra={"network": network})
        if not self.core.state.check_balances:
            return -1
        # first check accounts that were never checked
        need_to_check = await self.core.db.account_balance.find(
            {"network": network, "checked_at": None}, limit=self.core.settings.limit_network_workers
        )
        # next check accounts that were checked more than 5 minutes ago
        if len(need_to_check) < self.core.settings.limit_network_workers:
            need_to_check += await self.core.db.account_balance.find(
                {
                    "network": network,
                    "checked_at": {"$lt": utc_delta(minutes=-1 * self.core.settings.check_balance_interval)},
                },
                "checked_at",
                limit=self.core.settings.limit_network_workers - len(need_to_check),
            )
        if not need_to_check:
            return 0

        runner = AsyncTaskRunner(self.core.settings.limit_network_workers, name="check_balances")
        for ab in need_to_check:
            runner.add(str(ab.id), self.check_account_balance(ab.id))
        await runner.run()
        return len(need_to_check)

    async def _request_balance(self, network: Network, coin: Coin, account: str) -> Result[int]:
        res: Result[int] = Result.err("not started yet")

        for _ in range(5):
            start_at = time.perf_counter()
            urls = self.core.services.network.get_rpc_urls(network)
            if not urls:
                return Result.err(f"rpc url not found for {network}")

            # print("rpc_urls", rpc_urls)
            rpc_url = random_node(urls)
            proxy = random_proxy(self.core.state.proxies)

            match network.network_type:
                case NetworkType.EVM:
                    res = await evm.get_balance(rpc_url, account, coin.token, proxy)
                case NetworkType.SOLANA:
                    res = await solana.get_balance(rpc_url, account, coin.token, proxy)
                case NetworkType.APTOS:
                    res = await aptos.get_balance(rpc_url, account, coin.token, proxy)
                case NetworkType.STARKNET:
                    if coin.token is None:
                        raise ValueError("can't get balance for coin on StarkNet without token address")
                    res = await starknet.get_balance(rpc_url, account, coin.token, proxy)
                case _:
                    return Result.err("check_balance: unknown network")

            rpc_monitoring = RpcMonitoring(
                id=ObjectId(),
                network=network,
                coin=coin.id,
                account=account,
                rpc_url=rpc_url,
                proxy=proxy,
                success=res.is_ok(),
                response_time=round(time.perf_counter() - start_at, ndigits=2),
                error=res.unwrap_err() if res.is_err() else None,
                data=res.to_dict(safe_exception=True)["extra"],
            )
            await self.core.db.rpc_monitoring.insert_one(rpc_monitoring)

            if res.is_ok():
                return res

        return res

    async def check_account_balance(self, id: ObjectId) -> Result[int]:
        account_balance = await self.core.db.account_balance.get(id)
        coin = self.core.services.coin.get_coin(account_balance.coin)

        # self.logger.debug("check_account_balance: %s / %s / %s", network.id, coin.symbol, account_balance.account)

        res = await self._request_balance(coin.network, coin, account_balance.account)
        if res.is_err():
            # logger.debug("check_account_balance: %s", res.err)
            return res

        balance_raw = res.unwrap()
        balance = (
            Decimal(0)
            if balance_raw == 0
            else round(Decimal(balance_raw) / 10**coin.decimals, ndigits=self.core.settings.round_ndigits)
        )
        await self.core.db.group_balance.update_one(
            {"group": account_balance.group, "coin": account_balance.coin},
            {"$set": {f"balances.{account_balance.account}": balance, f"checked_at.{account_balance.account}": utc_now()}},
        )
        await self.core.db.account_balance.set(id, {"balance_raw": str(balance_raw), "balance": balance, "checked_at": utc_now()})

        return res
