from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.dependencies import RepositoryDep, UserIdDep
from app.schemas.finance import Category, CategoryCreate, CategoryUpdate

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[Category])
async def list_categories(repository: RepositoryDep, user_id: UserIdDep) -> list[dict]:
    return await repository.list_table("categories", user_id)


@router.post("", response_model=Category, status_code=status.HTTP_201_CREATED)
async def create_category(
    request: CategoryCreate, repository: RepositoryDep, user_id: UserIdDep
) -> dict:
    return await repository.insert_table(
        "categories",
        {"user_id": str(user_id), **request.model_dump(mode="json"), "is_default": False},
    )


@router.put("/{category_id}", response_model=Category)
async def update_category(
    category_id: UUID, request: CategoryUpdate, repository: RepositoryDep, user_id: UserIdDep
) -> dict:
    rows = await repository.list_table("categories", user_id, id=category_id)
    if not rows:
        raise HTTPException(404, "Categoria não encontrada")
    if rows[0]["is_default"]:
        raise HTTPException(409, "Categorias padrão não podem ser editadas")
    result = await repository.update_owned(
        "categories", category_id, user_id, request.model_dump(exclude_none=True)
    )
    return result or {}


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(category_id: UUID, repository: RepositoryDep, user_id: UserIdDep) -> None:
    result = await repository.call(
        "delete_custom_category", {"p_user_id": user_id, "p_category_id": category_id}
    )
    if not result:
        raise HTTPException(404, "Categoria não encontrada ou protegida")
