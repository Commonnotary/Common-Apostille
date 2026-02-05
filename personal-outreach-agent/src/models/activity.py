"""Activity log model for tracking all actions on leads."""

from datetime import datetime
from enum import Enum

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship

from ..database import Base


class ActivityType(str, Enum):
    """Type of activity/action."""
    CREATED = "created"
    RESEARCHED = "researched"
    SEGMENTED = "segmented"
    PERSONALIZED = "personalized"
    MESSAGE_DRAFTED = "message_drafted"
    MESSAGE_APPROVED = "message_approved"
    MESSAGE_SENT = "message_sent"
    MESSAGE_BOUNCED = "message_bounced"
    REPLY_RECEIVED = "reply_received"
    CALL_SCHEDULED = "call_scheduled"
    MEETING_BOOKED = "meeting_booked"
    STATUS_CHANGED = "status_changed"
    NOTE_ADDED = "note_added"


class ActivityLog(Base):
    """Activity log for tracking all lead interactions."""

    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to lead (optional - some activities might be system-wide)
    lead_id = Column(Integer, ForeignKey("leads.id"), index=True)

    # Activity info
    activity_type = Column(SQLEnum(ActivityType), nullable=False, index=True)
    description = Column(Text)
    details = Column(Text)  # JSON-encoded additional data

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    lead = relationship("Lead", back_populates="activity_logs")

    def __repr__(self):
        return f"<ActivityLog(id={self.id}, type={self.activity_type}, lead_id={self.lead_id})>"

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "lead_id": self.lead_id,
            "activity_type": self.activity_type.value if self.activity_type else None,
            "description": self.description,
            "details": self.details,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


def log_activity(
    session,
    activity_type: ActivityType,
    description: str,
    lead_id: int = None,
    details: str = None
) -> ActivityLog:
    """Helper function to log an activity."""
    log = ActivityLog(
        lead_id=lead_id,
        activity_type=activity_type,
        description=description,
        details=details
    )
    session.add(log)
    return log
