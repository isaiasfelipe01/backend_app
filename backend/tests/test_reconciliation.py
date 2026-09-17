from app.models.enums import AccountType
from app.services.transfers import CardPaymentMatcher, InternalTransferMatcher


def transfer(tx_id, account, amount, kind, day="2026-09-10"):
    return {
        "id": tx_id,
        "financial_account_id": account,
        "amount_cents": amount,
        "transaction_type": kind,
        "transaction_nature": "transfer",
        "transaction_date": day,
    }


def test_internal_transfer_pair_is_kept_and_excluded():
    rows = [transfer("out", "a", 10000, "expense"), transfer("in", "b", 10000, "income")]
    assert InternalTransferMatcher().match(rows) == 1
    assert all(r["is_internal_transfer"] and r["excluded_from_income_expense"] for r in rows)
    assert rows[0]["internal_transfer_group_id"] == rows[1]["internal_transfer_group_id"]


def test_same_account_never_matches():
    rows = [transfer("out", "a", 10000, "expense"), transfer("in", "a", 10000, "income")]
    assert InternalTransferMatcher().match(rows) == 0


def test_unrelated_amount_never_matches():
    rows = [transfer("out", "a", 10000, "expense"), transfer("in", "b", 9990, "income")]
    assert InternalTransferMatcher().match(rows) == 0


def test_distant_date_never_matches():
    rows = [
        transfer("out", "a", 10000, "expense", "2026-09-01"),
        transfer("in", "b", 10000, "income", "2026-09-10"),
    ]
    assert InternalTransferMatcher().match(rows) == 0


def test_bank_to_investment_is_neutral():
    rows = [transfer("out", "bank", 100000, "expense"), transfer("in", "broker", 100000, "income")]
    rows[1]["transaction_nature"] = "investment_transfer"
    assert InternalTransferMatcher().match(rows) == 1


def test_investment_to_bank_is_neutral():
    rows = [transfer("out", "broker", 100000, "expense"), transfer("in", "bank", 100000, "income")]
    rows[0]["transaction_nature"] = "investment_transfer"
    assert InternalTransferMatcher().match(rows) == 1


def test_card_bill_two_sides_excluded_without_changing_purchase():
    bank = {**transfer("bank", "bank", 20000, "expense"), "transaction_nature": "card_bill_payment"}
    card = {**transfer("card", "card", 20000, "income"), "transaction_nature": "card_bill_payment"}
    purchase = {
        **transfer("purchase", "card", 20000, "expense"),
        "transaction_nature": "credit_card_purchase",
    }
    rows = [bank, card, purchase]
    matched = CardPaymentMatcher().match(
        rows, {"bank": AccountType.BANK, "card": AccountType.CREDIT}
    )
    assert matched == 1
    assert bank["excluded_from_category_analytics"] and card["excluded_from_category_analytics"]
    assert "excluded_from_category_analytics" not in purchase
