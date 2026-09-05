import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, HttpUrl
from app.models.models import SourceType


class OfficialSourceCreate(BaseModel):
    organization_id: Optional[uuid.UUID] = None
    source_name: str
    source_type: SourceType = SourceType.RECRUITMENT
    official_domain: str
    notification_url: str
    parser_type: str = "upsc"
    check_frequency_minutes: int = 60
    active: bool = True


class OfficialSourceResponse(BaseModel):
    id: uuid.UUID
    source_name: str
    source_type: SourceType
    official_domain: str
    notification_url: str
    parser_type: str
    active: bool
    last_checked_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None

    class Config:
        from_attributes = True
