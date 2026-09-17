import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from uuid import UUID

from app.models.enums import AccountType
from app.services.pluggy.normalizer import money_to_cents
from app.services.transactions import PluggyTransactionService


class PluggyInvestmentService:
    def __init__(self, client, repository):
        self.client = client
        self.repository = repository
        self.transactions = PluggyTransactionService(repository)

    async def sync(
        self, user_id: UUID, connection: dict, investment: dict, institution: str
    ) -> dict:
        external_id = str(investment["id"])
        # Local namespace identifies the API resource; never sent as an /accounts id.
        resource_key = f"investment:{external_id}"
        now = datetime.now(UTC).isoformat()
        account, _ = await self.repository.upsert_financial_account(
            {
                "user_id": str(user_id),
                "pluggy_connection_id": connection["id"],
                "pluggy_item_id": connection["item_id"],
                "pluggy_account_id": resource_key,
                "institution_name": institution,
                "name": investment.get("name") or "Investimento",
                "type": "INVESTMENT",
                "subtype": investment.get("type"),
                "currency": investment.get("currencyCode") or "BRL",
                "balance_cents": money_to_cents(investment.get("balance")),
                "raw_payload": investment,
                "last_synced_at": now,
            }
        )
        counts = {"inserted": 0, "updated": 0, "unchanged": 0}
        occurrences: Counter[str] = Counter()
        async for page in self.client.investment_transaction_pages(external_id):
            records = []
            for raw in page:
                identity = raw.get("id")
                if not identity:
                    fingerprint = hashlib.sha256(
                        json.dumps(raw, sort_keys=True, separators=(",", ":")).encode()
                    ).hexdigest()
                    occurrences[fingerprint] += 1
                    identity = f"content:{fingerprint}:{occurrences[fingerprint]}"
                normalized = {**raw, "id": str(identity)}
                movement = raw.get("movementType")
                if raw.get("type") in {"BUY", "SELL"}:
                    normalized["operationType"] = "TRANSFER"
                    normalized["type"] = (
                        "CREDIT"
                        if movement == "CREDIT"
                        else "DEBIT"
                        if movement == "DEBIT"
                        else "TRANSFER"
                    )
                normalized["_original_payload"] = raw
                records.append(normalized)
            result = await self.transactions.persist_page(
                user_id=user_id,
                connection=connection,
                account={"id": resource_key},
                financial_account=account,
                account_type=AccountType.INVESTMENT,
                credit_card_id=None,
                transactions=records,
            )
            for key in counts:
                counts[key] += result[key]
        return counts
