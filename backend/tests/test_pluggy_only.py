from uuid import uuid4

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import get_repository
from app.dependencies import current_user_id
from app.services.transfers import InternalTransferMatcher
from app.services.pluggy.normalizer import PluggyTransactionNormalizer
from app.models.enums import AccountType


@pytest.fixture
async def client():
    async def repo():
        return object()

    async def user():
        return uuid4()

    app.dependency_overrides[get_repository] = repo
    app.dependency_overrides[current_user_id] = user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def test_manual_transaction_is_blocked(client):
    r = await client.post(
        "/transactions",
        json={"transaction_type": "expense", "amount_cents": 100, "transaction_date": "2026-09-01"},
    )
    assert r.status_code == 409


async def test_manual_card_is_blocked(client):
    r = await client.post(
        "/credit-cards",
        json={"name": "Manual", "limit_total_cents": 100, "closing_day": 10, "due_day": 20},
    )
    assert r.status_code == 409


async def test_health(client):
    assert (await client.get("/health")).status_code == 200


def test_structured_debit_overrides_positive_bank_transfer():
    r = PluggyTransactionNormalizer().normalize(
        {"id": "x", "type": "DEBIT", "operationType": "PIX", "amount": "100", "date": "2026-09-01"},
        AccountType.BANK,
    )
    assert r.transaction_type == "expense" and r.transaction_nature == "transfer"


def test_ambiguous_transfers_not_matched():
    rows = [
        dict(
            id=str(i),
            financial_account_id=str(i),
            user_id="u",
            amount_cents=100,
            transaction_date="2026-09-01",
            transaction_type="expense" if i == 0 else "income",
            transaction_nature="transfer",
        )
        for i in range(3)
    ]
    assert InternalTransferMatcher().match(rows) == 0


def test_different_users_not_matched():
    rows = [
        dict(
            id=str(i),
            financial_account_id=str(i),
            user_id=str(i),
            amount_cents=100,
            transaction_date="2026-09-01",
            transaction_type="expense" if i == 0 else "income",
            transaction_nature="transfer",
        )
        for i in range(2)
    ]
    assert InternalTransferMatcher().match(rows) == 0


def test_unknown_card_credit_is_not_income():
    r = PluggyTransactionNormalizer().normalize(
        {"id": "x", "type": "CREDIT", "amount": "100", "date": "2026-09-01"}, AccountType.CREDIT
    )
    assert r.excluded_from_income_expense and r.transaction_nature == "unknown"
