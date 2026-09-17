from uuid import UUID, uuid4

import pytest

from app.services.pluggy.sync_service import PluggySyncService
from tests.fakes import FakePluggyClient, FakeRepository, account, transaction


USER = UUID("00000000-0000-0000-0000-000000000001")


async def setup_repo(*item_ids):
    repo = FakeRepository()
    for item_id in item_ids:
        await repo.upsert_connection(
            USER, item_id, {"institution_name": item_id, "status": "ok", "sync_status": "pending"}
        )
    return repo


@pytest.mark.asyncio
async def test_imports_multiple_account_types_and_all_transactions():
    repo = await setup_repo("one")
    items = {
        "one": [account("bank", "BANK"), account("card", "CREDIT"), account("invest", "INVESTMENT")]
    }
    txs = {
        "bank": [transaction("b", -1)],
        "card": [transaction("c", 2)],
        "invest": [transaction("i", 3, kind="DIVIDEND")],
    }
    run = uuid4()
    await PluggySyncService(FakePluggyClient(items, txs), repo).run(USER, run)
    assert len(repo.accounts) == 3 and len(repo.cards) == 1 and len(repo.transactions) == 3
    assert repo.sync_runs[str(run)]["investments_updated"] == 1


@pytest.mark.asyncio
async def test_first_100_second_zero_third_three():
    repo = await setup_repo("one")
    items = {"one": [account("bank")]}
    values = [transaction(str(i), -i) for i in range(1, 101)]
    client = FakePluggyClient(items, {"bank": values})
    first = uuid4()
    await PluggySyncService(client, repo).run(USER, first)
    assert repo.sync_runs[str(first)]["transactions_inserted"] == 100
    second = uuid4()
    await PluggySyncService(client, repo).run(USER, second)
    assert repo.sync_runs[str(second)]["transactions_inserted"] == 0
    values.extend(transaction(f"new{i}", -10) for i in range(3))
    third = uuid4()
    await PluggySyncService(client, repo).run(USER, third)
    assert repo.sync_runs[str(third)]["transactions_inserted"] == 3


@pytest.mark.asyncio
async def test_balance_is_updated_in_place():
    repo = await setup_repo("one")
    item = account("bank", balance=100)
    client = FakePluggyClient({"one": [item]}, {"bank": []})
    await PluggySyncService(client, repo).run(USER, uuid4())
    account_id = next(iter(repo.accounts.values()))["id"]
    item["balance"] = 250
    await PluggySyncService(client, repo).run(USER, uuid4())
    stored = next(iter(repo.accounts.values()))
    assert stored["id"] == account_id and stored["balance_cents"] == 25000


@pytest.mark.asyncio
async def test_external_transaction_update_is_reconciled():
    repo = await setup_repo("one")
    row = transaction("tx", -10, "Old")
    client = FakePluggyClient({"one": [account("bank")]}, {"bank": [row]})
    await PluggySyncService(client, repo).run(USER, uuid4())
    row["description"] = "New"
    run = uuid4()
    await PluggySyncService(client, repo).run(USER, run)
    assert repo.sync_runs[str(run)]["transactions_updated"] == 1
    assert next(iter(repo.transactions.values()))["description"] == "New"


@pytest.mark.asyncio
async def test_local_category_survives_sync():
    repo = await setup_repo("one")
    row = transaction("tx", -10)
    client = FakePluggyClient({"one": [account("bank")]}, {"bank": [row]})
    await PluggySyncService(client, repo).run(USER, uuid4())
    stored = next(iter(repo.transactions.values()))
    stored.update(category_id="custom", user_edited_category=True)
    row["amount"] = -11
    await PluggySyncService(client, repo).run(USER, uuid4())
    assert next(iter(repo.transactions.values()))["category_id"] == "custom"


@pytest.mark.asyncio
async def test_one_institution_failure_does_not_stop_other():
    repo = await setup_repo("bad", "good")
    client = FakePluggyClient({"bad": [], "good": [account("bank")]}, {"bank": []}, {"bad"})
    run = uuid4()
    await PluggySyncService(client, repo).run(USER, run)
    result = repo.sync_runs[str(run)]
    assert result["institutions_failed"] == 1 and result["institutions_succeeded"] == 1
    assert result["status"] == "partial"


@pytest.mark.asyncio
async def test_concurrent_sync_lock():
    repo = FakeRepository()
    assert await repo.start_sync_run(USER, uuid4())
    assert not await repo.start_sync_run(USER, uuid4())
