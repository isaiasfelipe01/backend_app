from functools import lru_cache
from uuid import UUID

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    pluggy_client_id: str = ""
    pluggy_client_secret: SecretStr = SecretStr("")
    pluggy_webhook_secret: SecretStr = SecretStr("")
    supabase_url: str = ""
    supabase_service_role_key: SecretStr = SecretStr("")
    app_user_id: UUID = UUID("00000000-0000-0000-0000-000000000001")
    api_env: str = "development"
    pluggy_sandbox: bool = False
    pluggy_base_url: str = "https://api.pluggy.ai"
    request_timeout_seconds: float = Field(default=30, gt=0)

    @property
    def pluggy_configured(self) -> bool:
        return bool(self.pluggy_client_id and self.pluggy_client_secret.get_secret_value())

    @property
    def supabase_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_role_key.get_secret_value())


@lru_cache
def get_settings() -> Settings:
    return Settings()
