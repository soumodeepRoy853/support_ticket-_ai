import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Enum as SqlEnum
from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from pgvector.sqlalchemy import Vector

class TicketStatus(str, enum.Enum):
    OPEN = "open"
    PENDING = "pending"
    RESOLVED = "resolved"
    CLOSED = "closed"

class TicketPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    assigned_agent_id = mapped_column(ForeignKey("users.id"), nullable=True)

    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[TicketStatus] = mapped_column(SqlEnum(TicketStatus), default=TicketStatus.OPEN)
    priority: Mapped[TicketPriority] = mapped_column(SqlEnum(TicketPriority), default=TicketPriority.MEDIUM)

    # AI-populated fields — nullable because they're filled asynchronously after creation
    ai_category = mapped_column(String(100), nullable=True)
    ai_priority = mapped_column(SqlEnum(TicketPriority), nullable=True)
    ai_summary = mapped_column(Text, nullable=True)
    ai_suggested_reply = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    embedding: Mapped[list[float]] = mapped_column(Vector(768), nullable=True)

    __table_args__ = (
        Index("ix_tickets_org_status", "organization_id", "status"),
    )