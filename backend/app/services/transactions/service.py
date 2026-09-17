from typing import Any
from uuid import UUID

from app.models.enums import AccountType
from app.repositories.protocols import FinanceRepository
from app.services.pluggy.normalizer import PluggyTransactionNormalizer
from app.services.transactions.category_mapper import map_pluggy_category
from app.services.transactions.manual_service import billing_period
from app.services.pluggy.normalizer import parse_pluggy_date


class PluggyTransactionService:
    def __init__(
        self, repository: FinanceRepository, normalizer: PluggyTransactionNormalizer | None = None
    ) -> None:
        self.repository = repository
        self.normalizer = normalizer or PluggyTransactionNormalizer()
        self._categories: dict[tuple[str, str, str], str] = {}

    async def persist_page(
        self,
        *,
        user_id: UUID,
        connection: dict[str, Any],
        account: dict[str, Any],
        financial_account: dict[str, Any],
        account_type: AccountType,
        credit_card_id: str | None,
        transactions: list[dict[str, Any]],
    ) -> dict[str, int]:
        records = []
        for payload in transactions:
            normalized = self.normalizer.normalize(payload, account_type).as_record()
            category_type = (
                "expense"
                if normalized["transaction_nature"] == "credit_card_refund"
                else normalized["transaction_type"]
            )
            category_name = map_pluggy_category(payload, category_type)
            key = (str(user_id), category_type, category_name)
            if key not in self._categories:
                self._categories[key] = await self.repository.category_id(
                    user_id, key[1], category_name
                )
            category_id = self._categories[key]
            closing = (account.get("creditData") or {}).get("balanceCloseDate")
            bill_period = (
                billing_period(
                    parse_pluggy_date(payload["date"]),
                    parse_pluggy_date(closing).day if closing else None,
                )
                if account_type == AccountType.CREDIT
                else None
            )
            records.append(
                {
                    **normalized,
                    "user_id": str(user_id),
                    "source": "pluggy",
                    "pluggy_connection_id": connection["id"],
                    "pluggy_item_id": connection["item_id"],
                    "pluggy_account_id": str(account["id"]),
                    "financial_account_id": financial_account["id"],
                    "credit_card_id": credit_card_id,
                    "category_id": category_id,
                    "billing_period": bill_period.isoformat() if bill_period else None,
                    "is_provision": payload.get("status") == "PENDING"
                    and account_type != AccountType.CREDIT,
                    "pluggy_created_at": payload.get("createdAt"),
                    "pluggy_updated_at": payload.get("updatedAt"),
                }
            )
        return await self.repository.upsert_transaction_batch(records)
