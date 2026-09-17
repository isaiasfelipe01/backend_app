from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class Message(ApiModel):
    message: str


class Identified(ApiModel):
    id: UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None
