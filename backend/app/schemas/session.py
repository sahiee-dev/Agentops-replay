# backend/app/schemas/session.py
from datetime import datetime

from pydantic import BaseModel


# Define SessionBase FIRST
class SessionBase(BaseModel):
    agent_name: str | None = None
    status: str | None = None


# Then define SessionCreate (which inherits from SessionBase)
class SessionCreate(SessionBase):
    user_id: int  # Integer to match your database


# Then define SessionRead (which inherits from SessionBase)
class SessionRead(SessionBase):
    id: int
    user_id: int
    started_at: datetime

    class Config:
        from_attributes = True  # Updated Pydantic v2 syntax
