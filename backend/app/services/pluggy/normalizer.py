import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from app.models.enums import AccountType, PaymentMethod, TransactionNature, TransactionType


TRANSFER_TYPES = {"TRANSFER", "PIX", "TED", "DOC", "WIRE_TRANSFER"}
INCOME_TYPES = {"CREDIT", "INCOME", "DEPOSIT"}
EXPENSE_TYPES = {"DEBIT", "EXPENSE", "WITHDRAWAL", "PURCHASE"}
REFUND_TYPES = {"REFUND", "REVERSAL", "CHARGEBACK"}
CARD_PAYMENT_TYPES = {"CREDIT_CARD_PAYMENT", "CARD_PAYMENT", "BILL_PAYMENT"}
INVESTMENT_INCOME_TYPES = {"DIVIDEND", "DIVIDENDS", "INTEREST", "YIELD", "INCOME"}
TRANSFER_TEXT = re.compile(r"\b(pix|ted|doc|transfer[eê]ncia|transf)\b", re.IGNORECASE)
CARD_PAYMENT_TEXT = re.compile(
    r"\b(pagamento|pgto).*(cart[aã]o|fatura)|\bfatura.*(pagamento|pgto)\b", re.IGNORECASE
)
REFUND_TEXT = re.compile(r"\b(estorno|reembolso|refund|chargeback)\b", re.IGNORECASE)
INVESTMENT_INCOME_TEXT = re.compile(
    r"\b(dividendo|juros sobre capital|rendimento|yield)\b", re.IGNORECASE
)


def normalize_account_type(raw_type: Any, subtype: Any = None) -> AccountType:
    value = str(raw_type or "").upper()
    sub = str(subtype or "").upper()
    if value in {"BANK", "CHECKING", "SAVINGS", "PAYMENT"}:
        return AccountType.BANK
    if value in {"CREDIT", "CREDIT_CARD"} or "CREDIT" in sub:
        return AccountType.CREDIT
    if value in {"INVESTMENT", "BROKERAGE"} or any(
        marker in sub for marker in ("INVEST", "BROKER", "SECURIT")
    ):
        return AccountType.INVESTMENT
    return AccountType.OTHER


def money_to_cents(value: Any) -> int:
    try:
        decimal = Decimal(str(value or 0))
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"Valor monetário inválido: {value!r}") from error
    return int((decimal * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def parse_pluggy_date(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if not value:
        raise ValueError("Transação Pluggy sem data")
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()


def _structured_type(payload: dict[str, Any]) -> str:
    candidates = (
        payload.get("type"),
        payload.get("transactionType"),
        payload.get("subtype"),
        payload.get("operationType"),
        (payload.get("paymentData") or {}).get("type"),
        (payload.get("paymentData") or {}).get("paymentMethod"),
    )
    return " ".join(str(value).upper() for value in candidates if value)


def _description(payload: dict[str, Any]) -> str:
    merchant = payload.get("merchant") or {}
    return str(
        merchant.get("name")
        or payload.get("description")
        or payload.get("descriptionRaw")
        or "Transação"
    )


@dataclass(frozen=True)
class NormalizedTransaction:
    pluggy_transaction_id: str
    original_description: str
    description: str
    raw_amount_cents: int
    amount_cents: int
    transaction_type: TransactionType
    transaction_nature: TransactionNature
    payment_method: PaymentMethod
    transaction_date: date
    excluded_from_income_expense: bool
    excluded_from_category_analytics: bool
    is_card_bill_payment: bool
    raw_payload: dict[str, Any]

    def as_record(self) -> dict[str, Any]:
        result = self.__dict__.copy()
        result["transaction_type"] = self.transaction_type.value
        result["transaction_nature"] = self.transaction_nature.value
        result["payment_method"] = self.payment_method.value
        result["transaction_date"] = self.transaction_date.isoformat()
        return result


class PluggyTransactionNormalizer:
    def normalize(
        self, payload: dict[str, Any], account_type: AccountType
    ) -> NormalizedTransaction:
        external_id = payload.get("id")
        if not external_id:
            raise ValueError("Transação Pluggy sem id")
        raw_cents = money_to_cents(payload.get("amount"))
        description = _description(payload)
        structured = _structured_type(payload)
        nature, transaction_type, excluded = self._classify(
            account_type, structured, description, raw_cents
        )
        payment_method = (
            PaymentMethod.CARD
            if account_type == AccountType.CREDIT
            else PaymentMethod.TRANSFER
            if nature in {TransactionNature.TRANSFER, TransactionNature.INVESTMENT_TRANSFER}
            else PaymentMethod.CASH
        )
        return NormalizedTransaction(
            pluggy_transaction_id=str(external_id),
            original_description=description,
            description=description,
            raw_amount_cents=raw_cents,
            amount_cents=abs(raw_cents),
            transaction_type=transaction_type,
            transaction_nature=nature,
            payment_method=payment_method,
            transaction_date=parse_pluggy_date(payload.get("date")),
            excluded_from_income_expense=excluded,
            excluded_from_category_analytics=excluded,
            is_card_bill_payment=nature == TransactionNature.CARD_BILL_PAYMENT,
            raw_payload=payload.get("_original_payload", payload),
        )

    def _classify(
        self, account_type: AccountType, structured: str, description: str, raw_cents: int
    ) -> tuple[TransactionNature, TransactionType, bool]:
        tokens = set(re.findall(r"[A-Z_]+", structured))
        is_refund = bool(tokens & REFUND_TYPES) or bool(REFUND_TEXT.search(description))
        is_card_payment = bool(tokens & CARD_PAYMENT_TYPES) or bool(
            CARD_PAYMENT_TEXT.search(description)
        )
        is_transfer = bool(tokens & (TRANSFER_TYPES | {"TRANSFERENCIA_MESMA_INSTITUICAO"})) or bool(
            TRANSFER_TEXT.search(description)
        )
        direction = (
            TransactionType.INCOME
            if "CREDIT" in tokens
            else TransactionType.EXPENSE
            if "DEBIT" in tokens
            else TransactionType.INCOME
            if raw_cents >= 0
            else TransactionType.EXPENSE
        )

        if account_type == AccountType.CREDIT:
            if is_card_payment:
                return TransactionNature.CARD_BILL_PAYMENT, TransactionType.INCOME, True
            if is_refund:
                return TransactionNature.CREDIT_CARD_REFUND, TransactionType.INCOME, False
            if "CREDIT" in tokens or (not tokens and raw_cents < 0):
                return TransactionNature.UNKNOWN, TransactionType.INCOME, True
            # Pluggy issuers commonly expose purchases as positive amounts. Account
            # type and structured semantics therefore take precedence over sign.
            return TransactionNature.CREDIT_CARD_PURCHASE, TransactionType.EXPENSE, False

        if account_type == AccountType.INVESTMENT:
            if bool(tokens & (INVESTMENT_INCOME_TYPES - {"INCOME"})):
                return TransactionNature.INVESTMENT_INCOME, TransactionType.INCOME, False
            if is_transfer:
                return TransactionNature.INVESTMENT_TRANSFER, direction, True
            kind = TransactionType.INCOME if raw_cents >= 0 else TransactionType.EXPENSE
            return TransactionNature.ADJUSTMENT, kind, True

        if is_card_payment:
            return TransactionNature.CARD_BILL_PAYMENT, TransactionType.EXPENSE, True
        if "RENDIMENTO_APLIC_FINANCEIRA" in tokens:
            return TransactionNature.INVESTMENT_INCOME, TransactionType.INCOME, False
        if "RESGATE_APLIC_FINANCEIRA" in tokens:
            return TransactionNature.INVESTMENT_TRANSFER, direction, True
        if is_transfer:
            return TransactionNature.TRANSFER, direction, False
        if tokens & INCOME_TYPES:
            return TransactionNature.INCOME, TransactionType.INCOME, False
        if tokens & EXPENSE_TYPES:
            return TransactionNature.EXPENSE, TransactionType.EXPENSE, False
        if raw_cents > 0:
            return TransactionNature.INCOME, TransactionType.INCOME, False
        if raw_cents < 0:
            return TransactionNature.EXPENSE, TransactionType.EXPENSE, False
        return TransactionNature.UNKNOWN, TransactionType.EXPENSE, True
