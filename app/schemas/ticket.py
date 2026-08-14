from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Optional
from app.models.ticket import TicketStatus, TicketPriority

class TicketCreate(BaseModel):
    subject: str = Field(min_length=3, max_length=255)
    description: str = Field(min_length=10)

class TicketUpdate(BaseModel):
    status: Optional[TicketStatus] = None
    priority: Optional[TicketPriority] = None
    assigned_agent_id: Optional[UUID] = None

class TicketOut(BaseModel):
    id: UUID
    organization_id: UUID
    customer_id: UUID
    assigned_agent_id: Optional[UUID]
    subject: str
    description: str
    status: TicketStatus
    priority: TicketPriority
    ai_category: Optional[str]
    ai_priority: Optional[TicketPriority]
    ai_summary: Optional[str]
    ai_suggested_reply: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class TicketListOut(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[TicketOut]