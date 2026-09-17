from functools import lru_cache

from fastapi import HTTPException, status
from supabase import Client, create_client

from app.config import get_settings
from app.repositories.supabase_repository import SupabaseRepository


@lru_cache
def get_supabase_client() -> Client:
    settings = get_settings()
    if not settings.supabase_configured:
        raise RuntimeError("SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY não configurados")
    return create_client(
        settings.supabase_url, settings.supabase_service_role_key.get_secret_value()
    )


def get_repository() -> SupabaseRepository:
    try:
        return SupabaseRepository(get_supabase_client())
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
        ) from error
