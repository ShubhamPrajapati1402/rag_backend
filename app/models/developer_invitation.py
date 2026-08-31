from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy import Column, Integer, String, DateTime
from app.models.document import Base

class DeveloperInvitation(Base):
    """
    SQLAlchemy model representing the 'developer_invitations' table.
    Tracks tokenized invitations sent to prospective Admins & Members.
    """
    __tablename__ = "developer_invitations"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), index=True, nullable=False)
    token = Column(String(255), unique=True, index=True, nullable=False)
    role = Column(String(50), default="MEMBER", nullable=False)  # "ADMIN", "MEMBER"
    invited_by_email = Column(String(255), nullable=False)
    status = Column(String(50), default="PENDING", nullable=False)  # "PENDING", "ACCEPTED", "REVOKED", "EXPIRED"

    expires_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(ZoneInfo("Asia/Kolkata")) + timedelta(days=7),
        nullable=False
    )
    accepted_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(ZoneInfo("Asia/Kolkata")),
        nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(ZoneInfo("Asia/Kolkata")),
        onupdate=lambda: datetime.now(ZoneInfo("Asia/Kolkata")),
        nullable=False
    )

    def is_expired(self) -> bool:
        return datetime.now(ZoneInfo("Asia/Kolkata")) > self.expires_at

    def __repr__(self):
        return f"<DeveloperInvitation(id={self.id}, email='{self.email}', role='{self.role}', status='{self.status}')>"
