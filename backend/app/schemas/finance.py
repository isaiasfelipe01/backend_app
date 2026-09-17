from datetime import date, datetime
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.models.enums import (
    CardOrigin,
    CategoryType,
    PaymentMethod,
    Source,
    TransactionNature,
    TransactionType,
)
from app.schemas.common import ApiModel, Identified


class CategoryCreate(ApiModel):
    name: str = Field(min_length=1, max_length=60)
    icon: str = Field(default="💰", max_length=16)
    type: CategoryType


class CategoryUpdate(ApiModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    icon: str | None = Field(default=None, max_length=16)


class Category(CategoryCreate, Identified):
    user_id: UUID
    is_default: bool = False


class TransactionCreate(ApiModel):
    transaction_type: TransactionType
    amount_cents: int = Field(gt=0)
    category_id: UUID | None = None
    description: str = Field(default="", max_length=240)
    transaction_date: date
    is_provision: bool = False
    payment_method: PaymentMethod = PaymentMethod.CASH
    credit_card_id: UUID | None = None
    installments: int = Field(default=1, ge=1, le=120)
    repeat_months: int = Field(default=1, ge=1, le=120)

    @model_validator(mode="after")
    def validate_card(self) -> "TransactionCreate":
        if self.installments > 1 and self.payment_method != PaymentMethod.CARD:
            raise ValueError("Parcelamento é permitido apenas para cartão")
        if self.payment_method == PaymentMethod.CARD and not self.credit_card_id:
            raise ValueError("Cartão é obrigatório para pagamento com cartão")
        return self


class TransactionUpdate(ApiModel):
    amount_cents: int | None = Field(default=None, gt=0)
    transaction_type: TransactionType | None = None
    category_id: UUID | None = None
    description: str | None = Field(default=None, max_length=240)
    transaction_date: date | None = None
    is_provision: bool | None = None
    payment_method: PaymentMethod | None = None
    credit_card_id: UUID | None = None


class Transaction(Identified):
    user_id: UUID
    source: Source
    transaction_type: TransactionType
    transaction_nature: TransactionNature
    amount_cents: int
    raw_amount_cents: int
    description: str
    original_description: str
    transaction_date: date
    category_id: UUID | None = None
    financial_account_id: UUID | None = None
    credit_card_id: UUID | None = None
    payment_method: PaymentMethod | None = None
    billing_period: date | None = None
    is_provision: bool = False
    is_internal_transfer: bool = False
    is_card_bill_payment: bool = False
    excluded_from_income_expense: bool = False
    excluded_from_category_analytics: bool = False
    internal_transfer_group_id: UUID | None = None
    user_edited_description: bool = False
    user_edited_category: bool = False


class CreditCardCreate(ApiModel):
    name: str = Field(min_length=1, max_length=100)
    institution_name: str | None = Field(default=None, max_length=120)
    limit_total_cents: int = Field(gt=0)
    closing_day: int = Field(ge=1, le=31)
    due_day: int = Field(ge=1, le=31)


class CreditCardUpdate(ApiModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    limit_total_cents: int | None = Field(default=None, gt=0)
    closing_day: int | None = Field(default=None, ge=1, le=31)
    due_day: int | None = Field(default=None, ge=1, le=31)


class CreditCard(Identified):
    name: str
    institution_name: str | None = None
    limit_total_cents: int | None = None
    closing_day: int | None = None
    due_day: int | None = None
    user_id: UUID
    origin: CardOrigin
    limit_available_cents: int | None = None
    current_bill_cents: int | None = None
    pluggy_account_id: str | None = None


class BudgetCreate(ApiModel):
    name: str = Field(min_length=1, max_length=80)
    month: date
    limit_cents: int = Field(gt=0)
    category_ids: list[UUID] = Field(min_length=1)

    @field_validator("month")
    @classmethod
    def first_day(cls, value: date) -> date:
        if value.day != 1:
            raise ValueError("month deve ser o primeiro dia do mês")
        return value


class Budget(Identified):
    user_id: UUID
    name: str
    month: date
    limit_cents: int
    category_ids: list[UUID]
    spent_cents: int = 0


class FinancialAccount(Identified):
    user_id: UUID
    pluggy_connection_id: UUID
    pluggy_item_id: str
    pluggy_account_id: str
    institution_name: str
    name: str
    type: str
    subtype: str | None = None
    currency: str = "BRL"
    balance_cents: int = 0
    available_balance_cents: int | None = None
    number_masked: str | None = None
    status: str | None = None
    last_synced_at: datetime | None = None


class Summary(ApiModel):
    month: str
    available_balance_cents: int
    income_cents: int
    expense_cents: int
    cash_expense_cents: int
    card_expense_cents: int
    receivable_provisions_cents: int
    payable_provisions_cents: int
    forecast_balance_cents: int
    bank_balance_cents: int
    investments_cents: int
    current_card_bills_cents: int
    estimated_net_worth_cents: int
