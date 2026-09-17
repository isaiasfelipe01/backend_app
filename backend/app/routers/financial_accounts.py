from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.dependencies import RepositoryDep, UserIdDep
from app.schemas.finance import FinancialAccount, Transaction

router = APIRouter(prefix="/financial-accounts", tags=["financial-accounts"])


@router.get("", response_model=list[FinancialAccount])
async def list_financial_accounts(repository: RepositoryDep, user_id: UserIdDep) -> list[dict]:
    return await repository.list_table("financial_accounts", user_id)


@router.get("/{account_id}", response_model=FinancialAccount)
async def get_financial_account(
    account_id: UUID, repository: RepositoryDep, user_id: UserIdDep
) -> dict:
    rows = await repository.list_table("financial_accounts", user_id, id=account_id)
    if not rows:
        raise HTTPException(404, "Conta não encontrada")
    return rows[0]


@router.get("/{account_id}/transactions", response_model=list[Transaction])
async def account_transactions(
    account_id: UUID, repository: RepositoryDep, user_id: UserIdDep
) -> list[dict]:
    accounts = await repository.list_table("financial_accounts", user_id, id=account_id)
    if not accounts:
        raise HTTPException(404, "Conta não encontrada")
    return await repository.list_table("transactions", user_id, financial_account_id=account_id)
