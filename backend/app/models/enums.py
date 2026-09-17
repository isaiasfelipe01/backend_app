from enum import StrEnum


class AccountType(StrEnum):
    BANK = "BANK"
    CREDIT = "CREDIT"
    INVESTMENT = "INVESTMENT"
    OTHER = "OTHER"


class Source(StrEnum):
    MANUAL = "manual"
    PLUGGY = "pluggy"


class TransactionType(StrEnum):
    INCOME = "income"
    EXPENSE = "expense"


class TransactionNature(StrEnum):
    INCOME = "income"
    EXPENSE = "expense"
    CREDIT_CARD_PURCHASE = "credit_card_purchase"
    CREDIT_CARD_REFUND = "credit_card_refund"
    CARD_BILL_PAYMENT = "card_bill_payment"
    TRANSFER = "transfer"
    INTERNAL_TRANSFER = "internal_transfer"
    INVESTMENT_TRANSFER = "investment_transfer"
    INVESTMENT_INCOME = "investment_income"
    ADJUSTMENT = "adjustment"
    UNKNOWN = "unknown"


class PaymentMethod(StrEnum):
    CASH = "cash"
    CARD = "card"
    TRANSFER = "transfer"
    OTHER = "other"


class CategoryType(StrEnum):
    INCOME = "income"
    EXPENSE = "expense"


class CardOrigin(StrEnum):
    MANUAL = "MANUAL"
    PLUGGY = "PLUGGY"


class SyncStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    ERROR = "error"
