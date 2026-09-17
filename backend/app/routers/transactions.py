from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.dependencies import RepositoryDep, UserIdDep
from app.schemas.finance import Transaction, TransactionCreate, TransactionUpdate

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("", response_model=list[Transaction])
async def list_transactions(
    repository: RepositoryDep,
    user_id: UserIdDep,
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    search: str | None = None,
    category_id: UUID | None = None,
    credit_card_id: UUID | None = None,
    financial_account_id: UUID | None = None,
) -> list[dict]:
    return (
        await repository.call(
            "list_transactions",
            {
                "p_user_id": user_id,
                "p_month": month,
                "p_search": search,
                "p_category_id": category_id,
                "p_credit_card_id": credit_card_id,
                "p_financial_account_id": financial_account_id,
            },
        )
        or []
    )


@router.post("", response_model=list[Transaction], status_code=status.HTTP_201_CREATED)
async def create_transaction(
    request: TransactionCreate, repository: RepositoryDep, user_id: UserIdDep
) -> list[dict]:
    raise HTTPException(409, "Lançamentos são importados exclusivamente da Pluggy")


@router.put("/{transaction_id}", response_model=Transaction)
async def update_transaction(
    transaction_id: UUID, request: TransactionUpdate, repository: RepositoryDep, user_id: UserIdDep
) -> dict:
    existing = await repository.list_table("transactions", user_id, id=transaction_id)
    if not existing:
        raise HTTPException(404, "Transação não encontrada")
    values = request.model_dump(exclude_unset=True, mode="json")
    if set(values) - {"description", "category_id"}:
        raise HTTPException(409, "Somente descrição e categoria podem ser editadas")
    if values.get("category_id"):
        categories = await repository.list_table("categories", user_id, id=values["category_id"])
        if not categories or categories[0]["type"] != existing[0]["transaction_type"]:
            raise HTTPException(400, "Categoria incompatível com a transação")
    if "description" in values and existing[0]["source"] == "pluggy":
        values["user_edited_description"] = True
    if "category_id" in values and existing[0]["source"] == "pluggy":
        values["user_edited_category"] = True
    result = await repository.update_owned("transactions", transaction_id, user_id, values)
    return result or {}


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(
    transaction_id: UUID, repository: RepositoryDep, user_id: UserIdDep
) -> None:
    existing = await repository.list_table("transactions", user_id, id=transaction_id)
    if not existing:
        raise HTTPException(404, "Transação não encontrada")
    if existing[0]["source"] == "pluggy":
        raise HTTPException(409, "Transações Open Finance não podem ser excluídas")
    await repository.delete_owned("transactions", transaction_id, user_id)
