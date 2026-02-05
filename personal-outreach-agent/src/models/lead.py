"""Lead model for storing attorney/firm information."""

from datetime import datetime
from typing import Optional, List
from enum import Enum

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship

from ..database import Base


class Segment(str, Enum):
    """Lead segment/practice area classification."""
    ESTATE_PLANNING = "estate_planning"
    PROBATE = "probate"
    ELDER_LAW = "elder_law"
    FAMILY = "family"
    OTHER = "other"


class Region(str, Enum):
    """Geographic region classification."""
    DC = "DC"
    NOVA = "NoVA"
    SWVA = "SWVA"
    OTHER = "other"


class LeadStatus(str, Enum):
    """Lead status in the outreach pipeline."""
    NEW = "new"
    RESEARCHED = "researched"
    READY = "ready"
    IN_OUTREACH = "in_outreach"
    REPLIED = "replied"
    BOOKED = "booked"
    NOT_NOW = "not_now"
    UNSUBSCRIBED = "unsubscribed"


class Lead(Base):
    """Attorney/Firm lead model."""

    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Firm info
    firm_name = Column(String(255), nullable=False, index=True)
    firm_website = Column(String(500))

    # Attorney info
    attorney_name = Column(String(255), index=True)
    attorney_title = Column(String(255))
    attorney_email = Column(String(255), index=True)
    attorney_phone = Column(String(50))

    # Practice areas (comma-separated)
    practice_areas = Column(Text)

    # Location
    address = Column(Text)
    city = Column(String(100), index=True)
    state = Column(String(50))
    zip_code = Column(String(20))

    # Classification
    segment = Column(SQLEnum(Segment), default=Segment.OTHER, index=True)
    region = Column(SQLEnum(Region), default=Region.OTHER, index=True)

    # Personalization
    personalization_snippet = Column(Text)
    snippet_source_url = Column(String(500))
    snippet_source_text = Column(Text)  # Original text used for personalization

    # Source tracking
    source_url = Column(String(500))
    source_name = Column(String(100))  # e.g., "DC Bar", "Google Maps", etc.

    # Quality indicators
    confidence_score = Column(Float, default=0.5)  # 0.0 to 1.0
    notes = Column(Text)

    # Status
    status = Column(SQLEnum(LeadStatus), default=LeadStatus.NEW, index=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_contacted_at = Column(DateTime)

    # Relationships
    outreach_messages = relationship("OutreachMessage", back_populates="lead", cascade="all, delete-orphan")
    activity_logs = relationship("ActivityLog", back_populates="lead", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Lead(id={self.id}, firm='{self.firm_name}', attorney='{self.attorney_name}')>"

    @property
    def display_name(self) -> str:
        """Get a display name for the lead."""
        if self.attorney_name:
            return f"{self.attorney_name} at {self.firm_name}"
        return self.firm_name

    @property
    def practice_areas_list(self) -> List[str]:
        """Get practice areas as a list."""
        if not self.practice_areas:
            return []
        return [area.strip() for area in self.practice_areas.split(",")]

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "firm_name": self.firm_name,
            "firm_website": self.firm_website,
            "attorney_name": self.attorney_name,
            "attorney_title": self.attorney_title,
            "attorney_email": self.attorney_email,
            "attorney_phone": self.attorney_phone,
            "practice_areas": self.practice_areas_list,
            "city": self.city,
            "state": self.state,
            "segment": self.segment.value if self.segment else None,
            "region": self.region.value if self.region else None,
            "personalization_snippet": self.personalization_snippet,
            "snippet_source_url": self.snippet_source_url,
            "confidence_score": self.confidence_score,
            "status": self.status.value if self.status else None,
            "source_url": self.source_url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
