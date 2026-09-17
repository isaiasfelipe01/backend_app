from datetime import date
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.enums import PaymentMethod, TransactionType
from app.schemas.finance import TransactionCreate
from app.services.transactions.manual_service import (
    ManualTransactionFactory,
    add_months,
    billing_period,
)


def request(**overrides):
    values = dict(
        transaction_type=TransactionType.EXPENSE,
        amount_cents=1000,
        description="Compra",
        transaction_date=date(2026, 1, 31),
        payment_method=PaymentMethod.CASH,
    )
    values.update(overrides)
    return TransactionCreate(**values)


def test_month_increment_clamps_invalid_day():
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)


def test_installment_remainder_goes_to_first():
    card = uuid4()
    rows = ManualTransactionFactory().build(
        uuid4(),
        request(
            amount_cents=1001,
            installments=3,
            payment_method=PaymentMethod.CARD,
            credit_card_id=card,
        ),
        10,
    )
    assert [r["amount_cents"] for r in rows] == [335, 333, 333]
    assert [r["installment_number"] for r in rows] == [1, 2, 3]


def test_future_fixed_expenses_are_provisions():
    rows = ManualTransactionFactory().build(uuid4(), request(repeat_months=3), None)
    assert [r["is_provision"] for r in rows] == [False, True, True]


def test_cash_installments_are_rejected():
    with pytest.raises(ValidationError):
        request(installments=2)


def test_billing_period_respects_closing():
    assert billing_period(date(2026, 9, 11), 10) == date(2026, 10, 1)
    assert billing_period(date(2026, 9, 10), 10) == date(2026, 9, 1)
