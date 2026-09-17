from typing import Any
from uuid import UUID

from app.repositories.protocols import FinanceRepository
from app.services.pluggy.normalizer import money_to_cents


class PluggyCreditCardService:
    def __init__(self, repository: FinanceRepository) -> None:
        self.repository = repository

    async def persist(
        self,
        *,
        user_id: UUID,
        connection: dict[str, Any],
        financial_account: dict[str, Any],
        account: dict[str, Any],
        institution_name: str,
    ) -> tuple[dict[str, Any], bool]:
        credit = account.get("creditData") or {}
        close_date = credit.get("balanceCloseDate")
        due_date = credit.get("balanceDueDate")

        def day_of_month(value: Any) -> int | None:
            if not value:
                return None
            try:
                return int(str(value)[:10].split("-")[2])
            except (ValueError, IndexError):
                return None

        values = {
            "user_id": str(user_id),
            "pluggy_connection_id": connection["id"],
            "financial_account_id": financial_account["id"],
            "pluggy_account_id": str(account["id"]),
            "name": str(account.get("name") or "Cartão"),
            "institution_name": institution_name,
            "origin": "PLUGGY",
            "limit_total_cents": money_to_cents(credit.get("creditLimit"))
            if credit.get("creditLimit") is not None
            else 0,
            "limit_available_cents": money_to_cents(credit.get("availableCreditLimit"))
            if credit.get("availableCreditLimit") is not None
            else None,
            "current_bill_cents": money_to_cents(account["balance"])
            if account.get("balance") is not None
            else None,
            "closing_day": day_of_month(close_date),
            "due_day": day_of_month(due_date),
            "raw_payload": account,
        }
        return await self.repository.upsert_credit_card(values)
