import pytest

from app.services.pluggy.webhook_service import PluggyWebhookService
from tests.fakes import FakeRepository


@pytest.mark.asyncio
async def test_same_webhook_is_idempotent():
    repo = FakeRepository()
    service = PluggyWebhookService(repo)
    payload = {"id": "event-1", "event": "transactions/updated"}
    _, first = await service.register(payload)
    _, second = await service.register(payload)
    assert first is True and second is False and len(repo.webhooks) == 1


@pytest.mark.asyncio
async def test_event_without_id_has_stable_hash():
    repo = FakeRepository()
    service = PluggyWebhookService(repo)
    one, _ = await service.register({"b": 2, "a": 1})
    two, inserted = await service.register({"a": 1, "b": 2})
    assert one == two and not inserted
