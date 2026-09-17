import secrets
import asyncio
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from app.config import get_settings
from app.dependencies import RepositoryDep
from app.services.pluggy.sync_service import PluggySyncService
from app.services.pluggy.client import PluggyClient
from app.services.pluggy.webhook_service import PluggyWebhookService

router = APIRouter(tags=["webhooks"])


async def _process_event(repository: Any, event_id: str, user_id: UUID, item_id: str) -> None:
    service = PluggyWebhookService(repository)
    sync_id = uuid4()
    try:
        for _ in range(30):
            if await repository.start_sync_run(user_id, sync_id):
                async with PluggyClient(get_settings()) as client:
                    await PluggySyncService(client, repository).run(user_id, sync_id, [item_id])
                result = await repository.get_sync_run(user_id, sync_id)
                await service.mark_processed(
                    event_id,
                    None
                    if result and result["status"] == "success"
                    else "Sincronização incompleta; tente novamente",
                )
                return
            await asyncio.sleep(2)
        await repository.update_webhook_event(
            event_id, {"processing_status": "pending", "error": "Aguardando sincronização ativa"}
        )
    except Exception as error:
        await service.mark_processed(event_id, str(error)[:500])


@router.post("/webhooks/pluggy")
async def pluggy_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    repository: RepositoryDep,
    x_webhook_secret: Annotated[str | None, Header(alias="X-Webhook-Secret")] = None,
) -> dict[str, str]:
    configured = get_settings().pluggy_webhook_secret.get_secret_value()
    if not configured:
        raise HTTPException(503, "Webhook não configurado")
    supplied = x_webhook_secret or request.query_params.get("secret")
    if not supplied or not secrets.compare_digest(configured, supplied):
        raise HTTPException(401, "Assinatura de webhook inválida")
    payload = await request.json()
    service = PluggyWebhookService(repository)
    event_id, inserted = await service.register(payload)
    if not inserted:
        return {"status": "duplicate", "event_id": event_id}
    item_id = payload.get("itemId") or (payload.get("data") or {}).get("itemId")
    if item_id:
        connection = await repository.call("connection_owner", {"p_item_id": str(item_id)})
        row = connection[0] if isinstance(connection, list) and connection else connection
        if row:
            background_tasks.add_task(
                _process_event, repository, event_id, UUID(row["user_id"]), str(item_id)
            )
            return {"status": "accepted", "event_id": event_id}
    await service.mark_processed(event_id)
    return {"status": "stored", "event_id": event_id}
