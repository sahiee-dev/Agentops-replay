# backend/app/schemas/event.py
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

# Define EventBase FIRST
class EventBase(BaseModel):
    event_type: str
    tool_name: Optional[str] = None
    flags: Optional[List[str]] = []
    sequence_number: Optional[int] = None

# Then define EventCreate (which inherits from EventBase)
class EventCreate(EventBase):
    session_id: int  # Integer to match your database

# Then define EventRead (which inherits from EventBase)
class EventRead(EventBase):
    id: int
    session_id: int
    timestamp: datetime

    class Config:
        from_attributes = True  # Updated Pydantic v2 syntax
