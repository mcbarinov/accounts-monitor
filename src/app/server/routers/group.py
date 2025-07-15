import shutil
import tempfile
from pathlib import Path
from typing import Annotated

from bson import ObjectId
from fastapi import APIRouter, Body, File, UploadFile
from mm_base6 import cbv
from starlette.responses import PlainTextResponse

from app.core.constants import Naming
from app.core.db import Group
from app.core.services.group import ProcessAccountBalancesResult, ProcessAccountNamingsResult
from app.core.types import AppView

router = APIRouter(prefix="/api/groups", tags=["group"])


@cbv(router)
class CBV(AppView):
    @router.get("/")
    async def get_all_groups(self) -> list[Group]:
        return await self.core.db.group.find({}, "_id")

    @router.delete("/")
    async def delete_all_groups(self) -> None:
        for group in await self.core.db.group.find({}, "_id"):
            await self.core.services.group.delete_group(group.id)

    @router.post("/import-archive")
    async def import_archive(self, file: Annotated[UploadFile, File()]) -> None:
        """
        Import a group from a zip file.
        """
        if file.filename is None or not file.filename.endswith(".zip"):
            raise ValueError("File must be a zip file")
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            zip_path = tmp_path / file.filename
            with zip_path.open("wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            await self.core.services.group.import_from_zip(zip_path)

    @router.get("/export", response_class=PlainTextResponse)
    async def export_groups(self) -> str:
        return await self.core.services.group.export_as_toml()

    @router.get("/{id}")
    async def get_group(self, id: ObjectId) -> Group:
        return await self.core.db.group.get(id)

    @router.delete("/{id}")
    async def delete_group(self, id: ObjectId) -> None:
        await self.core.services.group.delete_group(ObjectId(id))

    @router.post("/{id}/coins")
    async def add_coin_to_group(self, id: ObjectId, coin_id: Annotated[str, Body(..., embed=True)]) -> None:
        return await self.core.services.group.add_coin(id, coin_id)

    @router.post("/{id}/namings")
    async def add_namings_to_group(self, id: ObjectId, naming: Annotated[Naming, Body(..., embed=True)]) -> None:
        return await self.core.services.group.add_naming(id, naming)

    @router.delete("/{id}/coins/{coin_id}")
    async def remove_coin_from_group(self, id: ObjectId, coin_id: str) -> None:
        return await self.core.services.group.remove_coin(id, coin_id)

    @router.delete("/{id}/namings/{naming}")
    async def remove_naming_from_group(self, id: ObjectId, naming: Naming) -> None:
        return await self.core.services.group.remove_naming(id, naming)

    @router.post("/{id}/process-account-balances")
    async def process_account_balances(self, id: ObjectId) -> ProcessAccountBalancesResult:
        return await self.core.services.group.process_account_balances(ObjectId(id))

    @router.post("/{id}/process-account-names")
    async def process_account_names(self, id: ObjectId) -> ProcessAccountNamingsResult:
        return await self.core.services.group.process_account_names(ObjectId(id))

    @router.post("/{id}/reset-group-balances")
    async def reset_group_balances(self, id: ObjectId) -> None:
        await self.core.services.group.reset_group_balances(ObjectId(id))
