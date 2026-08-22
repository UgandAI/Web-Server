from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class LogbookEntryBase(BaseModel):
    activity_type: str
    date: str
    crop: str
    field: str
    note: Optional[str] = None

class LogbookEntryCreate(LogbookEntryBase):
    pass

class LogbookEntryUpdate(LogbookEntryBase):
    activity_type: Optional[str] = None
    date: Optional[str] = None
    crop: Optional[str] = None
    field: Optional[str] = None
    note: Optional[str] = None

class LogbookEntryResponse(LogbookEntryBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
