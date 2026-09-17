from copy import deepcopy
from datetime import date
from typing import Any, AsyncIterator
from uuid import UUID, uuid4


class FakeRepository:
    async def upsert_investment(self, values: dict[str, Any]) -> None:
        self.investments = getattr(self, "investments", {})
        self.investments[values["pluggy_investment_id"]] = values

    def __init__(self) -> None:
        self.connections: list[dict[str, Any]] = []
        self.accounts: dict[tuple[str, str], dict[str, Any]] = {}
        self.cards: dict[tuple[str, str], dict[str, Any]] = {}
        self.transactions: dict[tuple[str, str, str], dict[str, Any]] = {}
        self.sync_runs: dict[str, dict[str, Any]] = {}
        self.webhooks: dict[str, dict[str, Any]] = {}

    async def ensure_user(self, user_id: UUID) -> None:
        pass

    async def list_connections(self, user_id: UUID) -> list[dict[str, Any]]:
        return [deepcopy(c) for c in self.connections if c["user_id"] == str(user_id)]

    async def upsert_connection(
        self, user_id: UUID, item_id: str, values: dict[str, Any]
    ) -> dict[str, Any]:
        for c in self.connections:
            if c["user_id"] == str(user_id) and c["item_id"] == item_id:
                c.update(deepcopy(values))
                return deepcopy(c)
        row = {"id": str(uuid4()), "user_id": str(user_id), "item_id": item_id, **deepcopy(values)}
        self.connections.append(row)
        return deepcopy(row)

    async def update_connection(self, connection_id: str, values: dict[str, Any]) -> None:
        next(c for c in self.connections if c["id"] == connection_id).update(deepcopy(values))

    async def start_sync_run(self, user_id: UUID, sync_id: UUID) -> bool:
        if any(
            r["user_id"] == str(user_id) and r["status"] == "running"
            for r in self.sync_runs.values()
        ):
            return False
        self.sync_runs[str(sync_id)] = {
            "id": str(sync_id),
            "user_id": str(user_id),
            "status": "running",
        }
        return True

    async def finish_sync_run(self, sync_id: UUID, values: dict[str, Any]) -> None:
        self.sync_runs.setdefault(str(sync_id), {"id": str(sync_id)}).update(deepcopy(values))

    async def get_sync_run(self, user_id: UUID, sync_id: UUID) -> dict[str, Any] | None:
        return deepcopy(self.sync_runs.get(str(sync_id)))

    async def upsert_financial_account(self, values: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        key = (str(values["user_id"]), values["pluggy_account_id"])
        created = key not in self.accounts
        old_id = self.accounts.get(key, {}).get("id", str(uuid4()))
        self.accounts[key] = {"id": old_id, **deepcopy(values)}
        return deepcopy(self.accounts[key]), created

    async def upsert_credit_card(self, values: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        key = (str(values["user_id"]), values["pluggy_account_id"])
        created = key not in self.cards
        old_id = self.cards.get(key, {}).get("id", str(uuid4()))
        self.cards[key] = {"id": old_id, **deepcopy(values)}
        return deepcopy(self.cards[key]), created

    async def category_id(self, user_id: UUID, category_type: str, name: str) -> str:
        return f"{category_type}:{name}"

    async def upsert_transaction_batch(self, records: list[dict[str, Any]]) -> dict[str, int]:
        result = {"inserted": 0, "updated": 0, "unchanged": 0}
        for incoming in records:
            key = (
                incoming["user_id"],
                incoming["pluggy_account_id"],
                incoming["pluggy_transaction_id"],
            )
            existing = self.transactions.get(key)
            if not existing:
                self.transactions[key] = {"id": str(uuid4()), **deepcopy(incoming)}
                result["inserted"] += 1
            elif existing.get("raw_payload") == incoming.get("raw_payload"):
                result["unchanged"] += 1
            else:
                description = (
                    existing["description"]
                    if existing.get("user_edited_description")
                    else incoming["description"]
                )
                category = (
                    existing.get("category_id")
                    if existing.get("user_edited_category")
                    else incoming.get("category_id")
                )
                flags = {
                    k: existing.get(k) for k in ("user_edited_description", "user_edited_category")
                }
                existing.update(deepcopy(incoming))
                existing.update(description=description, category_id=category, **flags)
                result["updated"] += 1
        return result

    async def reconciliation_candidates(self, user_id: UUID, start: date) -> list[dict[str, Any]]:
        return [deepcopy(t) for t in self.transactions.values() if t["user_id"] == str(user_id)]

    async def update_reconciled_transactions(self, records: list[dict[str, Any]]) -> None:
        for record in records:
            key = (record["user_id"], record["pluggy_account_id"], record["pluggy_transaction_id"])
            self.transactions[key].update(deepcopy(record))

    async def account_types(self, user_id: UUID) -> dict[str, str]:
        return {
            str(a["id"]): a["type"] for a in self.accounts.values() if a["user_id"] == str(user_id)
        }

    async def delete_connection(self, user_id: UUID, item_id: str) -> bool:
        return True

    async def register_webhook_event(self, values: dict[str, Any]) -> bool:
        if values["event_id"] in self.webhooks:
            return False
        self.webhooks[values["event_id"]] = deepcopy(values)
        return True

    async def update_webhook_event(self, event_id: str, values: dict[str, Any]) -> None:
        self.webhooks[event_id].update(values)


class FakePluggyClient:
    async def list_investments(self, item_id: str) -> list[dict]:
        return []

    def __init__(
        self,
        items: dict[str, list[dict]],
        transactions: dict[str, list[dict]],
        fail_items: set[str] | None = None,
    ) -> None:
        self.items = items
        self.transactions = transactions
        self.fail_items = fail_items or set()

    async def get_item(self, item_id: str) -> dict:
        if item_id in self.fail_items:
            raise RuntimeError("instituição indisponível")
        return {"id": item_id, "status": "UPDATED", "connector": {"name": f"Bank {item_id}"}}

    async def list_accounts(self, item_id: str) -> list[dict]:
        return deepcopy(self.items[item_id])

    async def transaction_pages(self, account_id: str) -> AsyncIterator[list[dict]]:
        values = self.transactions.get(account_id, [])
        for start in range(0, len(values), 50):
            yield deepcopy(values[start : start + 50])


def account(account_id: str, kind: str = "BANK", balance: float = 100) -> dict:
    return {
        "id": account_id,
        "name": account_id,
        "type": kind,
        "balance": balance,
        "currencyCode": "BRL",
    }


def transaction(
    tx_id: str,
    amount: float,
    description: str = "Compra",
    kind: str = "DEBIT",
    day: str = "2026-09-10",
) -> dict:
    return {"id": tx_id, "amount": amount, "description": description, "type": kind, "date": day}
