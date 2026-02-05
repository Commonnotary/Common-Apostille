"""Outreach planner service for managing daily queues and scheduling."""

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
import logging

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from ..config import get_settings, REGIONS
from ..models.lead import Lead, LeadStatus, Segment, Region
from ..models.outreach import OutreachMessage, MessageVariant, MessageStatus
from ..models.activity import ActivityLog, ActivityType, log_activity

logger = logging.getLogger(__name__)


@dataclass
class DailyQueueItem:
    """An item in the daily outreach queue."""
    lead: Lead
    message: OutreachMessage
    priority: int = 0
    reason: str = ""


@dataclass
class DailyPlan:
    """A day's outreach plan."""
    date: datetime
    intro_queue: List[DailyQueueItem] = field(default_factory=list)
    followup_queue: List[DailyQueueItem] = field(default_factory=list)
    total_count: int = 0

    @property
    def all_items(self) -> List[DailyQueueItem]:
        return self.intro_queue + self.followup_queue


class OutreachPlanner:
    """
    Service for planning and managing outreach activities.

    Handles:
    - Daily queue generation (new intros + scheduled follow-ups)
    - Follow-up scheduling based on configured delays
    - Priority ordering (by region, segment, confidence)
    - Status tracking
    """

    def __init__(self, session: Session):
        self.session = session
        self.settings = get_settings()

    def _calculate_priority(self, lead: Lead) -> int:
        """
        Calculate priority score for a lead (higher = more priority).

        Factors:
        - Region priority (DC/NoVA > SWVA > Other)
        - Segment (Estate Planning > Probate > Elder Law > Family > Other)
        - Confidence score
        - Has personalization
        """
        priority = 0

        # Region priority
        region_scores = {
            Region.DC: 30,
            Region.NOVA: 30,
            Region.SWVA: 20,
            Region.OTHER: 0
        }
        priority += region_scores.get(lead.region, 0)

        # Segment priority
        segment_scores = {
            Segment.ESTATE_PLANNING: 25,
            Segment.PROBATE: 20,
            Segment.ELDER_LAW: 20,
            Segment.FAMILY: 15,
            Segment.OTHER: 5
        }
        priority += segment_scores.get(lead.segment, 0)

        # Confidence score (0-1 scaled to 0-20)
        if lead.confidence_score:
            priority += int(lead.confidence_score * 20)

        # Bonus for having personalization
        if lead.personalization_snippet:
            priority += 10

        # Bonus for having email (required for outreach)
        if lead.attorney_email:
            priority += 15

        return priority

    def get_leads_ready_for_intro(self, limit: Optional[int] = None) -> List[Lead]:
        """
        Get leads that are ready for initial outreach.

        Criteria:
        - Status is NEW or RESEARCHED or READY
        - Has not been contacted yet
        - Has email address
        """
        query = self.session.query(Lead).filter(
            Lead.status.in_([LeadStatus.NEW, LeadStatus.RESEARCHED, LeadStatus.READY]),
            Lead.attorney_email.isnot(None),
            Lead.last_contacted_at.is_(None)
        ).order_by(Lead.confidence_score.desc())

        if limit:
            query = query.limit(limit)

        return query.all()

    def get_leads_needing_followup(self) -> List[Tuple[Lead, MessageVariant]]:
        """
        Get leads that need follow-up messages.

        Checks for:
        - Intro sent, followup_1 not sent, X days passed
        - Followup_1 sent, followup_2 not sent, Y days passed
        """
        results = []
        now = datetime.utcnow()

        # Get all leads in outreach
        leads_in_outreach = self.session.query(Lead).filter(
            Lead.status == LeadStatus.IN_OUTREACH
        ).all()

        for lead in leads_in_outreach:
            # Get sent messages for this lead
            sent_messages = self.session.query(OutreachMessage).filter(
                OutreachMessage.lead_id == lead.id,
                OutreachMessage.status == MessageStatus.SENT
            ).all()

            sent_variants = {msg.variant for msg in sent_messages}

            # Check if followup_1 is due
            if MessageVariant.INTRO in sent_variants and MessageVariant.FOLLOWUP_1 not in sent_variants:
                # Find the intro message
                intro = next((m for m in sent_messages if m.variant == MessageVariant.INTRO), None)
                if intro and intro.sent_at:
                    days_since = (now - intro.sent_at).days
                    if days_since >= self.settings.followup_1_days:
                        results.append((lead, MessageVariant.FOLLOWUP_1))

            # Check if followup_2 is due
            elif MessageVariant.FOLLOWUP_1 in sent_variants and MessageVariant.FOLLOWUP_2 not in sent_variants:
                # Find the followup_1 message
                followup1 = next((m for m in sent_messages if m.variant == MessageVariant.FOLLOWUP_1), None)
                if followup1 and followup1.sent_at:
                    days_since = (now - followup1.sent_at).days
                    if days_since >= (self.settings.followup_2_days - self.settings.followup_1_days):
                        results.append((lead, MessageVariant.FOLLOWUP_2))

        return results

    def generate_daily_plan(self, target_date: datetime = None) -> DailyPlan:
        """
        Generate a daily outreach plan.

        Includes:
        - New intro emails (up to daily limit minus follow-ups)
        - Scheduled follow-up emails
        """
        if target_date is None:
            target_date = datetime.utcnow()

        plan = DailyPlan(date=target_date)
        daily_limit = self.settings.daily_outreach_limit

        # First, get follow-ups (these take priority)
        followups_needed = self.get_leads_needing_followup()
        for lead, variant in followups_needed:
            # Get or create the follow-up message
            message = self.session.query(OutreachMessage).filter(
                OutreachMessage.lead_id == lead.id,
                OutreachMessage.variant == variant
            ).first()

            if message:
                priority = self._calculate_priority(lead)
                item = DailyQueueItem(
                    lead=lead,
                    message=message,
                    priority=priority,
                    reason=f"Follow-up due ({variant.value})"
                )
                plan.followup_queue.append(item)

        # Sort follow-ups by priority
        plan.followup_queue.sort(key=lambda x: x.priority, reverse=True)

        # Calculate remaining slots for intros
        remaining_slots = daily_limit - len(plan.followup_queue)

        if remaining_slots > 0:
            # Get leads ready for intro
            ready_leads = self.get_leads_ready_for_intro(limit=remaining_slots * 2)  # Get extra for filtering

            for lead in ready_leads:
                if len(plan.intro_queue) >= remaining_slots:
                    break

                # Get or create intro message
                message = self.session.query(OutreachMessage).filter(
                    OutreachMessage.lead_id == lead.id,
                    OutreachMessage.variant == MessageVariant.INTRO
                ).first()

                if message and message.status == MessageStatus.DRAFT:
                    priority = self._calculate_priority(lead)
                    item = DailyQueueItem(
                        lead=lead,
                        message=message,
                        priority=priority,
                        reason="New outreach"
                    )
                    plan.intro_queue.append(item)

            # Sort intros by priority
            plan.intro_queue.sort(key=lambda x: x.priority, reverse=True)

        plan.total_count = len(plan.intro_queue) + len(plan.followup_queue)
        return plan

    def mark_message_approved(self, message: OutreachMessage) -> OutreachMessage:
        """Mark a message as approved for sending."""
        message.status = MessageStatus.APPROVED
        message.updated_at = datetime.utcnow()

        log_activity(
            self.session,
            ActivityType.MESSAGE_APPROVED,
            f"Approved {message.variant.value} message",
            lead_id=message.lead_id
        )

        return message

    def mark_message_sent(self, message: OutreachMessage) -> OutreachMessage:
        """Mark a message as sent."""
        message.status = MessageStatus.SENT
        message.sent_at = datetime.utcnow()
        message.updated_at = datetime.utcnow()

        # Update lead status
        lead = message.lead
        if lead:
            lead.status = LeadStatus.IN_OUTREACH
            lead.last_contacted_at = datetime.utcnow()

        log_activity(
            self.session,
            ActivityType.MESSAGE_SENT,
            f"Sent {message.variant.value} message",
            lead_id=message.lead_id
        )

        return message

    def mark_lead_replied(self, lead: Lead, reply_summary: str = None) -> Lead:
        """Mark a lead as having replied."""
        lead.status = LeadStatus.REPLIED

        log_activity(
            self.session,
            ActivityType.REPLY_RECEIVED,
            f"Received reply from {lead.display_name}",
            lead_id=lead.id,
            details=reply_summary
        )

        return lead

    def mark_lead_booked(self, lead: Lead, notes: str = None) -> Lead:
        """Mark a lead as having booked a meeting/call."""
        lead.status = LeadStatus.BOOKED

        log_activity(
            self.session,
            ActivityType.MEETING_BOOKED,
            f"Meeting booked with {lead.display_name}",
            lead_id=lead.id,
            details=notes
        )

        return lead

    def mark_lead_not_now(self, lead: Lead, notes: str = None) -> Lead:
        """Mark a lead as not interested right now."""
        lead.status = LeadStatus.NOT_NOW
        if notes:
            lead.notes = (lead.notes or "") + f"\n[{datetime.utcnow().date()}] {notes}"

        log_activity(
            self.session,
            ActivityType.STATUS_CHANGED,
            f"Marked {lead.display_name} as 'not now'",
            lead_id=lead.id,
            details=notes
        )

        return lead

    def get_pipeline_stats(self) -> Dict[str, int]:
        """Get statistics about the outreach pipeline."""
        stats = {}

        # Count by lead status
        for status in LeadStatus:
            count = self.session.query(Lead).filter(Lead.status == status).count()
            stats[f"leads_{status.value}"] = count

        # Count by message status
        for status in MessageStatus:
            count = self.session.query(OutreachMessage).filter(
                OutreachMessage.status == status
            ).count()
            stats[f"messages_{status.value}"] = count

        # Total leads
        stats["total_leads"] = self.session.query(Lead).count()

        # Leads with email
        stats["leads_with_email"] = self.session.query(Lead).filter(
            Lead.attorney_email.isnot(None)
        ).count()

        # Leads by region
        for region in Region:
            count = self.session.query(Lead).filter(Lead.region == region).count()
            stats[f"region_{region.value}"] = count

        # Leads by segment
        for segment in Segment:
            count = self.session.query(Lead).filter(Lead.segment == segment).count()
            stats[f"segment_{segment.value}"] = count

        return stats

    def get_activity_log(
        self,
        lead_id: int = None,
        limit: int = 50
    ) -> List[ActivityLog]:
        """Get recent activity log entries."""
        query = self.session.query(ActivityLog).order_by(
            ActivityLog.created_at.desc()
        )

        if lead_id:
            query = query.filter(ActivityLog.lead_id == lead_id)

        return query.limit(limit).all()
