from bson import ObjectId
from fastapi import APIRouter
from mm_base6 import cbv
from mm_result import Result

from app.core.db import AccountName
from app.core.types import AppView

router = APIRouter(prefix="/api/account-namings", tags=["account-naming"])


@cbv(router)
class CBV(AppView):
    @router.get("/{id}")
    async def get_account_name(self, id: ObjectId) -> AccountName:
        return await self.core.db.account_name.get(id)

    @router.post("/{id}/check")
    async def check_account_name(self, id: ObjectId) -> Result[str | None]:
        return await self.core.services.name.check_account_name(id)
