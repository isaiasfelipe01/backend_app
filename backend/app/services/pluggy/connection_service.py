from typing import Any
from uuid import UUID

from app.repositories.protocols import FinanceRepository
from app.services.pluggy.client import PluggyClient


class PluggyConnectionService:
    def __init__(self, client: PluggyClient, repository: FinanceRepository) -> None:
        self.client = client
        self.repository = repository

    async def register(
        self,
        user_id: UUID,
        item_id: str,
        supplied: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        supplied = supplied or {}
        item = await self.client.get_item(item_id)
        connector = item.get("connector") or {}
        return await self.repository.upsert_connection(
            user_id,
            item_id,
            {
                "institution_name": supplied.get("institution_name")
                or connector.get("name")
                or "Instituição",
                "connector_id": supplied.get("connector_id") or connector.get("id"),
                "connector_image_url": supplied.get("connector_image_url")
                or connector.get("imageUrl"),
                "status": item.get("status") or "CONNECTED",
                "sync_status": "pending",
                "raw_payload": item,
            },
        )
