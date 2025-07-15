from bson import ObjectId
from fastapi import APIRouter
from mm_base6 import cbv
from mm_mongo import MongoDeleteResult

from app.core.types import AppView

router = APIRouter(prefix="/api/history", tags=["history"])


@cbv(router)
class CBV(AppView):
    @router.post("/")
    async def create_history(self, group: ObjectId) -> None:
        await self.core.services.history.create(group)

    @router.delete("/{id}")
    async def delete_history(self, id: ObjectId) -> MongoDeleteResult:
        return await self.core.db.history.delete(id)
