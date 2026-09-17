import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from app.repositories.protocols import FinanceRepository


class PluggyWebhookService:
    def __init__(self, repository: FinanceRepository) -> None:
        self.repository = repository

    async def register(self, payload: dict[str, Any]) -> tuple[str, bool]:
        supplied_id = payload.get("id") or payload.get("eventId")
        event_id = (
            str(supplied_id)
            if supplied_id
            else hashlib.sha256(
                json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
        )
        inserted = await self.repository.register_webhook_event(
            {
                "event_id": event_id,
                "event_type": payload.get("event") or payload.get("type") or "unknown",
                "payload": payload,
                "processing_status": "pending",
            }
        )
        return event_id, inserted

    async def mark_processed(self, event_id: str, error: str | None = None) -> None:
        await self.repository.update_webhook_event(
            event_id,
            {
                "processing_status": "error" if error else "processed",
                "error": error,
                "processed_at": datetime.now(UTC).isoformat(),
            },
        )
