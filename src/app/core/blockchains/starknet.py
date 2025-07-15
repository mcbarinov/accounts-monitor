from mm_result import Result
from mm_strk import balance, domain
from mm_web3 import Proxies, retry_with_proxy


async def get_balance(rpc_url: str, account: str, token: str, proxy: str | None = None) -> Result[int]:
    return await balance.get_balance(rpc_url, address=account, token=token, proxy=proxy, timeout=7.0)


async def get_starknet_id(account: str, proxies: Proxies = None) -> Result[str | None]:
    return await retry_with_proxy(5, proxies, lambda proxy: domain.address_to_domain(account, proxy=proxy, timeout=5.0))
