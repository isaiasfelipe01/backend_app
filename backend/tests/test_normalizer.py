import pytest

from app.models.enums import AccountType, TransactionNature, TransactionType
from app.services.pluggy.normalizer import (
    PluggyTransactionNormalizer,
    money_to_cents,
    normalize_account_type,
)


normalizer = PluggyTransactionNormalizer()


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("BANK", AccountType.BANK),
        ("CREDIT", AccountType.CREDIT),
        ("INVESTMENT", AccountType.INVESTMENT),
        ("unexpected", AccountType.OTHER),
    ],
)
def test_account_types(raw, expected):
    assert normalize_account_type(raw) == expected


def test_money_uses_decimal_rounding():
    assert money_to_cents("49.52") == 4952


def test_positive_credit_amount_is_purchase_expense():
    result = normalizer.normalize(
        {"id": "1", "amount": 200, "date": "2026-09-01", "description": "SUPERMERCADO"},
        AccountType.CREDIT,
    )
    assert result.transaction_nature == TransactionNature.CREDIT_CARD_PURCHASE
    assert result.transaction_type == TransactionType.EXPENSE


def test_credit_refund_reduces_consumption():
    result = normalizer.normalize(
        {"id": "1", "amount": -20, "date": "2026-09-01", "type": "REFUND"}, AccountType.CREDIT
    )
    assert result.transaction_nature == TransactionNature.CREDIT_CARD_REFUND
    assert result.transaction_type == TransactionType.INCOME


def test_card_payment_side_is_excluded():
    result = normalizer.normalize(
        {"id": "1", "amount": 100, "date": "2026-09-01", "type": "CREDIT_CARD_PAYMENT"},
        AccountType.CREDIT,
    )
    assert result.is_card_bill_payment and result.excluded_from_income_expense


def test_investment_dividend_is_income():
    result = normalizer.normalize(
        {"id": "1", "amount": 50, "date": "2026-09-01", "type": "DIVIDEND"}, AccountType.INVESTMENT
    )
    assert result.transaction_nature == TransactionNature.INVESTMENT_INCOME


def test_investment_transfer_is_neutral_candidate():
    result = normalizer.normalize(
        {"id": "1", "amount": 1000, "date": "2026-09-01", "type": "TRANSFER"},
        AccountType.INVESTMENT,
    )
    assert result.transaction_nature == TransactionNature.INVESTMENT_TRANSFER
    assert result.excluded_from_income_expense


def test_unknown_zero_is_excluded():
    result = normalizer.normalize({"id": "1", "amount": 0, "date": "2026-09-01"}, AccountType.BANK)
    assert result.transaction_nature == TransactionNature.UNKNOWN
    assert result.excluded_from_income_expense
