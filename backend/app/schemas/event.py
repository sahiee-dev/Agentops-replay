# backend/app/schemas/event.py
from datetime import datetime

from pydantic import BaseModel


# Define EventBase FIRST
class EventBase(BaseModel):
    event_type: str
    tool_name: str | None = None
    flags: list[str] | None = None
    sequence_number: int | None = None

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
