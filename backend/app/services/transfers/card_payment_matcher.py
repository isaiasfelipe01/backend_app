from datetime import date

from app.models.enums import AccountType, TransactionNature, TransactionType


class CardPaymentMatcher:
    def __init__(self, date_window_days: int = 3, tolerance_cents: int = 1) -> None:
        self.date_window_days = date_window_days
        self.tolerance_cents = tolerance_cents

    @staticmethod
    def _date(record: dict) -> date:
        value = record["transaction_date"]
        return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])

    def match(self, records: list[dict], account_types: dict[str, AccountType]) -> int:
        bank_sides = [
            r
            for r in records
            if account_types.get(str(r.get("financial_account_id"))) == AccountType.BANK
            and r.get("transaction_nature") == TransactionNature.CARD_BILL_PAYMENT.value
            and r.get("transaction_type") == TransactionType.EXPENSE.value
        ]
        card_sides = [
            r
            for r in records
            if account_types.get(str(r.get("financial_account_id"))) == AccountType.CREDIT
            and r.get("transaction_nature")
            in {TransactionNature.CARD_BILL_PAYMENT.value, TransactionNature.UNKNOWN.value}
            and r.get("transaction_type") == TransactionType.INCOME.value
        ]
        used: set[str] = set()
        matches = 0
        for bank in bank_sides:
            candidates = []
            for card in card_sides:
                identity = str(card.get("id") or card.get("pluggy_transaction_id"))
                if identity in used:
                    continue
                if card.get("user_id") != bank.get("user_id"):
                    continue
                day_delta = abs((self._date(card) - self._date(bank)).days)
                amount_delta = abs(int(card["amount_cents"]) - int(bank["amount_cents"]))
                if day_delta <= self.date_window_days and amount_delta <= self.tolerance_cents:
                    candidates.append((day_delta, amount_delta, card))
            if len(candidates) != 1:
                continue
            candidates.sort(key=lambda candidate: candidate[:2])
            card = candidates[0][2]
            used.add(str(card.get("id") or card.get("pluggy_transaction_id")))
            for record in (bank, card):
                record.update(
                    transaction_nature=TransactionNature.CARD_BILL_PAYMENT.value,
                    is_card_bill_payment=True,
                    excluded_from_income_expense=True,
                    excluded_from_category_analytics=True,
                )
            matches += 1
        return matches
