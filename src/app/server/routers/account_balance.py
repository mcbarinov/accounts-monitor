from bson import ObjectId
from fastapi import APIRouter
from mm_base6 import cbv
from mm_result import Result

from app.core.db import AccountBalance
from app.core.types import AppView

router = APIRouter(prefix="/api/account-balances", tags=["account-balance"])


@cbv(router)
class CBV(AppView):
    @router.get("/{id}")
    async def get_account_balance(self, id: ObjectId) -> AccountBalance:
        return await self.core.db.account_balance.get(id)

    @router.post("/{id}/check")
    async def check_account_balance(self, id: ObjectId) -> Result[int]:
        return await self.core.services.balance.check_account_balance(id)
