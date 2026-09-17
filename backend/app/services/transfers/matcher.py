from datetime import date
from uuid import uuid4
import re

from app.models.enums import TransactionNature, TransactionType


class InternalTransferMatcher:
    """Reconciles both sides conservatively; descriptions are supporting evidence only."""

    def __init__(self, date_window_days: int = 2, tolerance_cents: int = 0) -> None:
        self.date_window_days = date_window_days
        self.tolerance_cents = tolerance_cents

    @staticmethod
    def _date(record: dict) -> date:
        value = record["transaction_date"]
        return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])

    @staticmethod
    def _eligible(record: dict) -> bool:
        return record.get("transaction_nature") in {
            TransactionNature.TRANSFER.value,
            TransactionNature.INVESTMENT_TRANSFER.value,
        }

    def match(self, records: list[dict]) -> int:
        exits = [
            r
            for r in records
            if self._eligible(r) and r.get("transaction_type") == TransactionType.EXPENSE.value
        ]
        entries = [
            r
            for r in records
            if self._eligible(r) and r.get("transaction_type") == TransactionType.INCOME.value
        ]
        used: set[str] = set()
        matched = 0
        for outgoing in sorted(exits, key=self._date):
            candidates = []
            for incoming in entries:
                identity = str(incoming.get("id") or incoming.get("pluggy_transaction_id"))
                if identity in used:
                    continue
                if incoming.get("user_id") != outgoing.get("user_id"):
                    continue
                if not incoming.get("financial_account_id") or not outgoing.get(
                    "financial_account_id"
                ):
                    continue
                if incoming.get("financial_account_id") == outgoing.get("financial_account_id"):
                    continue
                if not self._compatible_evidence(outgoing, incoming):
                    continue
                delta = abs((self._date(incoming) - self._date(outgoing)).days)
                amount_delta = abs(int(incoming["amount_cents"]) - int(outgoing["amount_cents"]))
                if delta <= self.date_window_days and amount_delta <= self.tolerance_cents:
                    # Exact amount + independently structured transfer semantics +
                    # two owned accounts is sufficient. Text never decides alone.
                    candidates.append((delta, amount_delta, self._date(incoming), incoming))
            if len(candidates) != 1:
                continue
            candidates.sort(key=lambda item: item[:3])
            incoming = candidates[0][3]
            competing = [
                r
                for r in exits
                if self._eligible(r)
                and r.get("user_id") == incoming.get("user_id")
                and r.get("financial_account_id") != incoming.get("financial_account_id")
                and r["amount_cents"] == incoming["amount_cents"]
                and abs((self._date(r) - self._date(incoming)).days) <= self.date_window_days
            ]
            if len(competing) != 1:
                continue
            group_id = str(uuid4())
            for record in (outgoing, incoming):
                record.update(
                    transaction_nature=TransactionNature.INTERNAL_TRANSFER.value,
                    is_internal_transfer=True,
                    internal_transfer_group_id=group_id,
                    excluded_from_income_expense=True,
                    excluded_from_category_analytics=True,
                )
            used.add(str(incoming.get("id") or incoming.get("pluggy_transaction_id")))
            matched += 1
        return matched

    @staticmethod
    def _compatible_evidence(outgoing: dict, incoming: dict) -> bool:
        left, right = outgoing.get("raw_payload") or {}, incoming.get("raw_payload") or {}
        if left.get("currencyCode", "BRL") != right.get("currencyCode", "BRL"):
            return False
        lpay, rpay = left.get("paymentData") or {}, right.get("paymentData") or {}
        for side in ("payer", "receiver"):
            ldoc = (lpay.get(side) or {}).get("documentNumber") or {}
            rdoc = (rpay.get(side) or {}).get("documentNumber") or {}
            lv = re.sub(r"\D", "", str(ldoc.get("value", "")))
            rv = re.sub(r"\D", "", str(rdoc.get("value", "")))
            if lv and rv and lv != rv:
                return False
        lref, rref = lpay.get("referenceNumber"), rpay.get("referenceNumber")
        if lref and rref:
            return lref == rref
        if not left and not right:
            return True
        structured = {"PIX", "TED", "DOC", "TRANSFER", "TRANSFERENCIA_MESMA_INSTITUICAO"}
        return all(
            any(str(p.get(k, "")).upper() in structured for k in ("type", "operationType"))
            or str((p.get("paymentData") or {}).get("paymentMethod", "")).upper() in structured
            or (
                r.get("transaction_nature") == "investment_transfer"
                and p.get("type") in {"BUY", "SELL"}
            )
            for p, r in ((left, outgoing), (right, incoming))
        )
