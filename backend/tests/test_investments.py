from uuid import uuid4

import httpx
from pydantic import SecretStr

from app.config import Settings
from app.services.pluggy.client import PluggyClient
from app.services.pluggy.investment_service import PluggyInvestmentService
from tests.fakes import FakeRepository


async def test_investment_history_paginates_and_preserves_raw():
    def handler(request):
        if request.url.path == "/auth":
            return httpx.Response(200, json={"apiKey": "temporary"})
        page = int(request.url.params["page"])
        return httpx.Response(
            200,
            json={
                "totalPages": 2,
                "results": [
                    {
                        "id": f"tx-{page}",
                        "date": "2026-09-01",
                        "type": "BUY" if page == 1 else "DIVIDEND",
                        "movementType": "CREDIT",
                        "amount": "10.01",
                        "description": "investment",
                    }
                ],
            },
        )

    repo = FakeRepository()
    connection = {"id": str(uuid4()), "item_id": "item"}
    settings = Settings(pluggy_client_id="test", pluggy_client_secret=SecretStr("test"))
    async with PluggyClient(settings, httpx.MockTransport(handler)) as client:
        service = PluggyInvestmentService(client, repo)
        args = (
            uuid4(),
            connection,
            {"id": "investment", "name": "Asset", "balance": "100.01"},
            "Bank",
        )
        first = await service.sync(*args)
        second = await service.sync(*args)
    assert first["inserted"] == 2 and second["inserted"] == 0
    rows = list(repo.transactions.values())
    assert rows[0]["transaction_nature"] == "investment_transfer"
    assert rows[0]["excluded_from_income_expense"]
    assert rows[0]["raw_payload"]["type"] == "BUY"
    assert rows[1]["transaction_nature"] == "investment_income"
    assert rows[1]["amount_cents"] == 1001


async def test_duplicate_content_without_external_id_retains_multiplicity():
    class Client:
        async def investment_transaction_pages(self, investment_id):
            yield [
                {"date": "2026-09-01", "type": "BUY", "movementType": "CREDIT", "amount": "1"}
            ] * 2

    repo = FakeRepository()
    service = PluggyInvestmentService(Client(), repo)
    args = (uuid4(), {"id": str(uuid4()), "item_id": "item"}, {"id": "i", "balance": "2"}, "Bank")
    first = await service.sync(*args)
    second = await service.sync(*args)
    assert first["inserted"] == 2 and second["unchanged"] == 2
