from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.models.enums import AccountType
from app.repositories.protocols import FinanceRepository
from app.services.pluggy.normalizer import money_to_cents, normalize_account_type


class PluggyAccountService:
    def __init__(self, repository: FinanceRepository) -> None:
        self.repository = repository

    async def persist(
        self,
        *,
        user_id: UUID,
        connection: dict[str, Any],
        account: dict[str, Any],
        institution_name: str,
    ) -> tuple[dict[str, Any], AccountType, bool]:
        account_type = normalize_account_type(account.get("type"), account.get("subtype"))
        values = {
            "user_id": str(user_id),
            "pluggy_connection_id": connection["id"],
            "pluggy_item_id": connection["item_id"],
            "pluggy_account_id": str(account["id"]),
            "institution_name": institution_name,
            "name": str(account.get("name") or "Conta"),
            "type": account_type.value,
            "subtype": account.get("subtype"),
            "currency": account.get("currencyCode") or "BRL",
            "balance_cents": money_to_cents(account.get("balance")),
            "available_balance_cents": money_to_cents(account["availableBalance"])
            if account.get("availableBalance") is not None
            else None,
            "number_masked": "****" + str(account["number"])[-4:]
            if account.get("number")
            else None,
            "status": account.get("status"),
            "last_synced_at": datetime.now(UTC).isoformat(),
            "raw_payload": account,
        }
        persisted, created = await self.repository.upsert_financial_account(values)
        return persisted, account_type, created
