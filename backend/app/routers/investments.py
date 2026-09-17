from fastapi import APIRouter
from app.dependencies import RepositoryDep, UserIdDep

router = APIRouter(prefix="/investments", tags=["investments"])


@router.get("")
async def investments(repository: RepositoryDep, user_id: UserIdDep) -> list[dict]:
    rows = await repository.list_table("investments", user_id)
    return [{k: v for k, v in row.items() if k != "raw_payload"} for row in rows]
