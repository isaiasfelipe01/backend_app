from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.schemas.common import ApiModel


class ConnectTokenRequest(ApiModel):
    item_id: str | None = None


class ConnectTokenResponse(ApiModel):
    access_token: str


class PluggyItemCreate(ApiModel):
    item_id: str = Field(min_length=1, max_length=120)
    institution_name: str | None = Field(default=None, max_length=160)
    connector_id: int | None = None
    connector_image_url: str | None = None


class PluggyConnection(ApiModel):
    id: UUID
    item_id: str
    institution_name: str | None = None
    connector_image_url: str | None = None
    status: str
    sync_status: str
    accounts_count: int = 0
    cards_count: int = 0
    investments_count: int = 0
    last_sync_at: datetime | None = None
    last_successful_sync_at: datetime | None = None
    last_sync_error: str | None = None


class SyncRequestResponse(ApiModel):
    sync_id: UUID
    status: str


class SyncSummary(ApiModel):
    sync_id: UUID
    status: str
    institutions_total: int = 0
    institutions_succeeded: int = 0
    institutions_failed: int = 0
    accounts_updated: int = 0
    cards_updated: int = 0
    investments_updated: int = 0
    transactions_inserted: int = 0
    transactions_updated: int = 0
    transactions_unchanged: int = 0
    transfers_matched: int = 0
    card_payments_matched: int = 0
    errors: list[str] = []
