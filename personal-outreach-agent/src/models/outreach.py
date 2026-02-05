"""Outreach message model for storing email drafts and sent messages."""

from datetime import datetime
from enum import Enum

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship

from ..database import Base


class MessageVariant(str, Enum):
    """Type of outreach message."""
    INTRO = "intro"
    FOLLOWUP_1 = "followup_1"
    FOLLOWUP_2 = "followup_2"


class MessageStatus(str, Enum):
    """Status of the outreach message."""
    DRAFT = "draft"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    SENT = "sent"
    BOUNCED = "bounced"
    REPLIED = "replied"


class OutreachMessage(Base):
    """Outreach message model."""

    __tablename__ = "outreach_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to lead
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False, index=True)

    # Message content
    variant = Column(SQLEnum(MessageVariant), nullable=False)
    subject = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)

    # Status tracking
    status = Column(SQLEnum(MessageStatus), default=MessageStatus.DRAFT, index=True)

    # Scheduling
    scheduled_at = Column(DateTime)
    sent_at = Column(DateTime)

    # Response tracking
    opened_at = Column(DateTime)
    replied_at = Column(DateTime)
    reply_summary = Column(Text)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    lead = relationship("Lead", back_populates="outreach_messages")

    def __repr__(self):
        return f"<OutreachMessage(id={self.id}, lead_id={self.lead_id}, variant={self.variant}, status={self.status})>"

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "lead_id": self.lead_id,
            "variant": self.variant.value if self.variant else None,
            "subject": self.subject,
            "body": self.body,
            "status": self.status.value if self.status else None,
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @property
    def variant_display(self) -> str:
        """Human-readable variant name."""
        mapping = {
            MessageVariant.INTRO: "Initial Contact",
            MessageVariant.FOLLOWUP_1: "Follow-up #1",
            MessageVariant.FOLLOWUP_2: "Follow-up #2"
        }
        return mapping.get(self.variant, self.variant.value)
