from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status

from app.database import get_repository
from app.repositories.supabase_repository import SupabaseRepository
from app.config import get_settings


async def current_user_id(
    repository: Annotated[SupabaseRepository, Depends(get_repository)],
    x_user_id: Annotated[str | None, Header(alias="X-User-ID")] = None,
) -> UUID:
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="X-User-ID é obrigatório"
        )
    try:
        user_id = UUID(x_user_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail="X-User-ID deve ser um UUID válido") from error
    if user_id != get_settings().app_user_id:
        raise HTTPException(status_code=403, detail="Usuário não autorizado neste servidor pessoal")
    await repository.ensure_user(user_id)
    return user_id


RepositoryDep = Annotated[SupabaseRepository, Depends(get_repository)]
UserIdDep = Annotated[UUID, Depends(current_user_id)]
