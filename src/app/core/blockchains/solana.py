from mm_result import Result
from mm_sol import rpc, spl_token


async def get_balance(rpc_url: str, account: str, token: str | None = None, proxy: str | None = None) -> Result[int]:
    if token:
        return await spl_token.get_balance(rpc_url, owner=account, token=token, proxy=proxy, timeout=5)
    return await rpc.get_balance(rpc_url, account, proxy=proxy, timeout=5)
