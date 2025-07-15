from mm_apt import ans, balance
from mm_result import Result
from mm_web3 import Proxies, retry


async def get_balance(rpc_url: str, account: str, token: str | None = None, proxy: str | None = None) -> Result[int]:
    if token is None:
        token = "0x1::aptos_coin::AptosCoin"  # nosec  # noqa: S105
    return await balance.get_balance(rpc_url, account, coin_type=token, proxy=proxy, timeout=7.0)


async def get_ans_name(account: str, proxies: Proxies = None) -> Result[str | None]:
    return await retry.retry_with_proxy(5, proxies, lambda proxy: ans.address_to_primary_name(account, proxy=proxy, timeout=5.0))
