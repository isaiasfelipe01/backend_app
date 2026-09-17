from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from app.config import get_settings
from app.dependencies import RepositoryDep, UserIdDep
from app.schemas.common import Message
from app.schemas.pluggy import (
    ConnectTokenRequest,
    ConnectTokenResponse,
    PluggyConnection,
    PluggyItemCreate,
    SyncRequestResponse,
    SyncSummary,
)
from app.services.pluggy.client import PluggyClient, PluggyError
from app.services.pluggy.connection_service import PluggyConnectionService
from app.services.pluggy.sync_service import PluggySyncService

router = APIRouter(prefix="/pluggy", tags=["pluggy"])


async def _run_sync(
    repository: Any, user_id: UUID, sync_id: UUID, item_ids: list[str] | None = None
) -> None:
    client = PluggyClient(get_settings())
    try:
        await PluggySyncService(client, repository).run(user_id, sync_id, item_ids)
    finally:
        await client.close()


@router.post("/connect-token", response_model=ConnectTokenResponse)
async def connect_token(request: ConnectTokenRequest, user_id: UserIdDep) -> ConnectTokenResponse:
    del user_id
    async with PluggyClient(get_settings()) as client:
        try:
            token = await client.create_connect_token(request.item_id)
        except PluggyError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error
    return ConnectTokenResponse(access_token=token)


@router.post("/items", response_model=SyncRequestResponse, status_code=status.HTTP_202_ACCEPTED)
async def register_item(
    request: PluggyItemCreate,
    background_tasks: BackgroundTasks,
    repository: RepositoryDep,
    user_id: UserIdDep,
) -> SyncRequestResponse:
    async with PluggyClient(get_settings()) as client:
        try:
            await PluggyConnectionService(client, repository).register(
                user_id, request.item_id, request.model_dump()
            )
        except PluggyError as error:
            raise HTTPException(502, str(error)) from error
    sync_id = uuid4()
    if not await repository.start_sync_run(user_id, sync_id):
        raise HTTPException(409, "Já existe uma sincronização em andamento")
    background_tasks.add_task(_run_sync, repository, user_id, sync_id, [request.item_id])
    return SyncRequestResponse(sync_id=sync_id, status="running")


@router.get("/connections", response_model=list[PluggyConnection])
async def connections(repository: RepositoryDep, user_id: UserIdDep) -> list[dict]:
    return await repository.list_connections(user_id)


@router.post("/sync", response_model=SyncRequestResponse, status_code=status.HTTP_202_ACCEPTED)
async def sync_all(
    background_tasks: BackgroundTasks, repository: RepositoryDep, user_id: UserIdDep
) -> SyncRequestResponse:
    sync_id = uuid4()
    if not await repository.start_sync_run(user_id, sync_id):
        raise HTTPException(409, "Já existe uma sincronização em andamento")
    background_tasks.add_task(_run_sync, repository, user_id, sync_id)
    return SyncRequestResponse(sync_id=sync_id, status="running")


@router.get("/sync/{sync_id}", response_model=SyncSummary)
async def sync_status(sync_id: UUID, repository: RepositoryDep, user_id: UserIdDep) -> dict:
    result = await repository.get_sync_run(user_id, sync_id)
    if not result:
        raise HTTPException(404, "Sincronização não encontrada")
    return {"sync_id": result.pop("id"), **result}


@router.delete("/connections/{item_id}", response_model=Message)
async def disconnect(item_id: str, repository: RepositoryDep, user_id: UserIdDep) -> Message:
    if not await repository.delete_connection(user_id, item_id):
        raise HTTPException(404, "Conexão não encontrada")
    return Message(message="Instituição desconectada; dados manuais foram preservados")
