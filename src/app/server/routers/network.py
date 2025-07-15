from typing import Annotated

from fastapi import APIRouter, Query
from mm_base6 import cbv
from mm_web3 import Network

from app.core.types import AppView

router = APIRouter(prefix="/api/networks", tags=["network"])


@cbv(router)
class CBV(AppView):
    @router.post("/update-mm-node-checker")
    async def update_node_checker(self) -> dict[str, list[str]] | None:
        return await self.core.services.network.update_mm_node_checker()

    @router.delete("/{id}/delete-rpc-url")
    async def delete_rpc_url(self, id: Network, url: Annotated[str, Query()]) -> None:
        await self.core.services.network.delete_rpc_url(id, url)

    @router.post("/{id}/check-next-network-balances")
    async def check_next_network_balances(self, id: Network) -> int | None:
        return await self.core.services.balance.check_next_network(id)
