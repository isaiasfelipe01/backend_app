from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.dependencies import RepositoryDep, UserIdDep
from app.schemas.finance import Budget, BudgetCreate

router = APIRouter(prefix="/budgets", tags=["budgets"])


@router.get("", response_model=list[Budget])
async def list_budgets(
    repository: RepositoryDep,
    user_id: UserIdDep,
    month: str = Query(pattern=r"^\d{4}-\d{2}$"),
) -> list[dict]:
    return await repository.call("list_budgets", {"p_user_id": user_id, "p_month": month}) or []


@router.post("", response_model=Budget)
async def upsert_budget(
    request: BudgetCreate, repository: RepositoryDep, user_id: UserIdDep
) -> dict:
    result = await repository.call(
        "upsert_budget",
        {
            "p_user_id": user_id,
            "p_name": request.name,
            "p_month": request.month,
            "p_limit_cents": request.limit_cents,
            "p_category_ids": request.category_ids,
        },
    )
    if not result:
        raise HTTPException(400, "Categorias inválidas para a meta")
    rows = await repository.call(
        "list_budgets", {"p_user_id": user_id, "p_month": request.month.strftime("%Y-%m")}
    )
    return next(row for row in rows if row["name"] == request.name)


@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_budget(budget_id: UUID, repository: RepositoryDep, user_id: UserIdDep) -> None:
    if not await repository.delete_owned("budgets", budget_id, user_id):
        raise HTTPException(404, "Meta não encontrada")
