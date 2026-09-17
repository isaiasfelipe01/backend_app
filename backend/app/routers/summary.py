from fastapi import APIRouter, Query

from app.dependencies import RepositoryDep, UserIdDep
from app.schemas.finance import Summary
import asyncio
from app.services.dashboard.planning import next_month_plan

router = APIRouter(prefix="/summary", tags=["summary"])


@router.get('/planning')
async def planning(repository: RepositoryDep, user_id: UserIdDep, month: str = Query(pattern=r'^\d{4}-(0[1-9]|1[0-2])$')) -> dict:
    transactions, cards = await asyncio.gather(repository.list_table('transactions',user_id),repository.list_table('credit_cards',user_id))
    return next_month_plan(month,transactions,cards)


@router.get("", response_model=Summary)
async def summary(
    repository: RepositoryDep,
    user_id: UserIdDep,
    month: str = Query(pattern=r"^\d{4}-\d{2}$"),
) -> dict:
    result = await repository.call("financial_summary", {"p_user_id": user_id, "p_month": month})
    return result[0] if isinstance(result, list) else result


@router.get("/top-categories")
async def top_categories(
    repository: RepositoryDep, user_id: UserIdDep, month: str = Query(pattern=r"^\d{4}-\d{2}$")
) -> list[dict]:
    return await repository.call("top_categories", {"p_user_id": user_id, "p_month": month}) or []


@router.get("/trend")
async def trend(
    repository: RepositoryDep, user_id: UserIdDep, month: str = Query(pattern=r"^\d{4}-\d{2}$")
) -> list[dict]:
    return await repository.call("financial_trend", {"p_user_id": user_id, "p_month": month}) or []
