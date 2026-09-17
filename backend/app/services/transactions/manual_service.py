import calendar
from datetime import date
from uuid import UUID, uuid4

from dateutil.relativedelta import relativedelta

from app.models.enums import PaymentMethod, TransactionNature, TransactionType
from app.schemas.finance import TransactionCreate


def add_months(value: date, months: int) -> date:
    target = value + relativedelta(months=months)
    last_day = calendar.monthrange(target.year, target.month)[1]
    return target.replace(day=min(value.day, last_day))


def billing_period(transaction_date: date, closing_day: int | None) -> date:
    day = closing_day or 31
    last_day = calendar.monthrange(transaction_date.year, transaction_date.month)[1]
    close = transaction_date.replace(day=min(day, last_day))
    target = transaction_date if transaction_date <= close else add_months(transaction_date, 1)
    return target.replace(day=1)


class ManualTransactionFactory:
    @staticmethod
    def _enum_value(value: object) -> str:
        return str(getattr(value, "value", value))

    def build(
        self,
        user_id: UUID,
        request: TransactionCreate,
        card_closing_day: int | None = None,
    ) -> list[dict]:
        if request.installments > 1:
            return self._installments(user_id, request, card_closing_day)
        return self._repetitions(user_id, request, card_closing_day)

    def _base(
        self,
        user_id: UUID,
        request: TransactionCreate,
        amount: int,
        transaction_date: date,
        description: str,
        provision: bool,
        card_closing_day: int | None,
    ) -> dict:
        nature = (
            TransactionNature.CREDIT_CARD_PURCHASE
            if request.payment_method == PaymentMethod.CARD
            else TransactionNature.INCOME
            if request.transaction_type == TransactionType.INCOME
            else TransactionNature.EXPENSE
        )
        return {
            "user_id": str(user_id),
            "source": "manual",
            "transaction_type": self._enum_value(request.transaction_type),
            "transaction_nature": nature.value,
            "amount_cents": amount,
            "raw_amount_cents": amount
            if request.transaction_type == TransactionType.INCOME
            else -amount,
            "category_id": str(request.category_id) if request.category_id else None,
            "description": description,
            "original_description": description,
            "transaction_date": transaction_date.isoformat(),
            "is_provision": provision,
            "payment_method": self._enum_value(request.payment_method),
            "credit_card_id": str(request.credit_card_id) if request.credit_card_id else None,
            "billing_period": billing_period(transaction_date, card_closing_day).isoformat()
            if request.payment_method == PaymentMethod.CARD
            else None,
        }

    def _installments(
        self, user_id: UUID, request: TransactionCreate, closing_day: int | None
    ) -> list[dict]:
        group_id = str(uuid4())
        base, remainder = divmod(request.amount_cents, request.installments)
        records = []
        for index in range(request.installments):
            amount = base + (remainder if index == 0 else 0)
            record = self._base(
                user_id,
                request,
                amount,
                add_months(request.transaction_date, index),
                f"{request.description} ({index + 1}/{request.installments})".strip(),
                request.is_provision if index == 0 else True,
                closing_day,
            )
            record.update(
                installment_group_id=group_id,
                installment_number=index + 1,
                installment_count=request.installments,
            )
            records.append(record)
        return records

    def _repetitions(
        self, user_id: UUID, request: TransactionCreate, closing_day: int | None
    ) -> list[dict]:
        group_id = str(uuid4()) if request.repeat_months > 1 else None
        records = []
        for index in range(request.repeat_months):
            suffix = (
                f" (Fixo {index + 1}/{request.repeat_months})" if request.repeat_months > 1 else ""
            )
            record = self._base(
                user_id,
                request,
                request.amount_cents,
                add_months(request.transaction_date, index),
                f"{request.description}{suffix}".strip(),
                request.is_provision if index == 0 else True,
                closing_day,
            )
            record["recurrence_group_id"] = group_id
            records.append(record)
        return records
