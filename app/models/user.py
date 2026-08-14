from sqlalchemy import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey, Enum as sqlEnum
from datetime import datetime
from app.core.database import Base
import uuid
import enum
from sqlalchemy.dialects.postgresql import UUID

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    AGENT = "agent"
    CUSTOMER = "customer"

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(sqlEnum(UserRole), default=UserRole.CUSTOMER)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    __table_args__ = (
        {"sqlite_autoincrement": True},
    )