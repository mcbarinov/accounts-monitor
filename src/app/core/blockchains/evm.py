from mm_eth import retry, rpc
from mm_result import Result
from mm_web3 import Proxies


async def get_balance(
    node: str, account: str, token: str | None = None, proxy: str | None = None, timeout: float = 7
) -> Result[int]:
    if token:
        return await rpc.erc20_balance(node, token=token, wallet=account, proxy=proxy, timeout=timeout)
    return await rpc.eth_get_balance(node, account, timeout=timeout, proxy=proxy)


async def get_ens_name(rpc_urls: list[str], account: str, proxies: Proxies = None) -> Result[str | None]:
    return await retry.ens_name(5, rpc_urls, proxies, address=account, timeout=5.0)
