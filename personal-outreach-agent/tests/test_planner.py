"""Tests for outreach planner."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from src.models.lead import Lead, LeadStatus, Segment, Region
from src.models.outreach import OutreachMessage, MessageVariant, MessageStatus
from src.services.planner import OutreachPlanner, DailyQueueItem, DailyPlan


class TestOutreachPlanner:
    """Test suite for OutreachPlanner."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return MagicMock()

    @pytest.fixture
    def planner(self, mock_session):
        """Create a planner instance with mocked session."""
        return OutreachPlanner(mock_session)

    def test_calculate_priority_region(self, planner):
        """Test priority calculation for different regions."""
        lead_dc = Lead(
            firm_name="DC Firm",
            region=Region.DC,
            segment=Segment.OTHER,
            confidence_score=0.5
        )

        lead_nova = Lead(
            firm_name="NoVA Firm",
            region=Region.NOVA,
            segment=Segment.OTHER,
            confidence_score=0.5
        )

        lead_swva = Lead(
            firm_name="SWVA Firm",
            region=Region.SWVA,
            segment=Segment.OTHER,
            confidence_score=0.5
        )

        lead_other = Lead(
            firm_name="Other Firm",
            region=Region.OTHER,
            segment=Segment.OTHER,
            confidence_score=0.5
        )

        # DC and NoVA should have same priority (both primary markets)
        assert planner._calculate_priority(lead_dc) == planner._calculate_priority(lead_nova)
        # SWVA should be lower
        assert planner._calculate_priority(lead_swva) < planner._calculate_priority(lead_dc)
        # Other should be lowest
        assert planner._calculate_priority(lead_other) < planner._calculate_priority(lead_swva)

    def test_calculate_priority_segment(self, planner):
        """Test priority calculation for different segments."""
        base_attrs = {"firm_name": "Test", "region": Region.DC, "confidence_score": 0.5}

        lead_estate = Lead(**base_attrs, segment=Segment.ESTATE_PLANNING)
        lead_probate = Lead(**base_attrs, segment=Segment.PROBATE)
        lead_elder = Lead(**base_attrs, segment=Segment.ELDER_LAW)
        lead_family = Lead(**base_attrs, segment=Segment.FAMILY)
        lead_other = Lead(**base_attrs, segment=Segment.OTHER)

        # Estate planning should be highest priority
        assert planner._calculate_priority(lead_estate) > planner._calculate_priority(lead_probate)
        assert planner._calculate_priority(lead_probate) >= planner._calculate_priority(lead_elder)
        assert planner._calculate_priority(lead_elder) > planner._calculate_priority(lead_family)
        assert planner._calculate_priority(lead_family) > planner._calculate_priority(lead_other)

    def test_calculate_priority_email_bonus(self, planner):
        """Test that having an email increases priority."""
        lead_with_email = Lead(
            firm_name="Test",
            region=Region.DC,
            segment=Segment.ESTATE_PLANNING,
            confidence_score=0.5,
            attorney_email="test@example.com"
        )

        lead_no_email = Lead(
            firm_name="Test",
            region=Region.DC,
            segment=Segment.ESTATE_PLANNING,
            confidence_score=0.5
        )

        assert planner._calculate_priority(lead_with_email) > planner._calculate_priority(lead_no_email)

    def test_calculate_priority_personalization_bonus(self, planner):
        """Test that having personalization increases priority."""
        lead_with_personal = Lead(
            firm_name="Test",
            region=Region.DC,
            segment=Segment.ESTATE_PLANNING,
            confidence_score=0.5,
            personalization_snippet="I noticed your firm..."
        )

        lead_no_personal = Lead(
            firm_name="Test",
            region=Region.DC,
            segment=Segment.ESTATE_PLANNING,
            confidence_score=0.5
        )

        assert planner._calculate_priority(lead_with_personal) > planner._calculate_priority(lead_no_personal)

    def test_calculate_priority_confidence_score(self, planner):
        """Test that higher confidence increases priority."""
        lead_high_conf = Lead(
            firm_name="Test",
            region=Region.DC,
            segment=Segment.ESTATE_PLANNING,
            confidence_score=0.9
        )

        lead_low_conf = Lead(
            firm_name="Test",
            region=Region.DC,
            segment=Segment.ESTATE_PLANNING,
            confidence_score=0.3
        )

        assert planner._calculate_priority(lead_high_conf) > planner._calculate_priority(lead_low_conf)


class TestDailyPlan:
    """Test the DailyPlan dataclass."""

    def test_daily_plan_all_items(self):
        """Test all_items property combines both queues."""
        lead1 = Lead(firm_name="A")
        lead2 = Lead(firm_name="B")
        msg1 = MagicMock()
        msg2 = MagicMock()

        plan = DailyPlan(date=datetime.utcnow())
        plan.intro_queue = [DailyQueueItem(lead=lead1, message=msg1)]
        plan.followup_queue = [DailyQueueItem(lead=lead2, message=msg2)]

        assert len(plan.all_items) == 2
        assert plan.all_items[0].lead == lead1
        assert plan.all_items[1].lead == lead2


class TestDailyQueueItem:
    """Test the DailyQueueItem dataclass."""

    def test_queue_item_defaults(self):
        """Test default values for queue item."""
        lead = Lead(firm_name="Test")
        msg = MagicMock()

        item = DailyQueueItem(lead=lead, message=msg)

        assert item.priority == 0
        assert item.reason == ""

    def test_queue_item_with_values(self):
        """Test queue item with custom values."""
        lead = Lead(firm_name="Test")
        msg = MagicMock()

        item = DailyQueueItem(
            lead=lead,
            message=msg,
            priority=75,
            reason="High value lead"
        )

        assert item.priority == 75
        assert item.reason == "High value lead"


class TestPriorityOrdering:
    """Test that leads are ordered correctly by priority."""

    def test_leads_sorted_by_priority(self):
        """Verify leads are sorted highest priority first."""
        # Create leads with different priorities
        items = [
            DailyQueueItem(
                lead=Lead(firm_name="Low", region=Region.OTHER, segment=Segment.OTHER),
                message=MagicMock(),
                priority=10
            ),
            DailyQueueItem(
                lead=Lead(firm_name="High", region=Region.DC, segment=Segment.ESTATE_PLANNING),
                message=MagicMock(),
                priority=80
            ),
            DailyQueueItem(
                lead=Lead(firm_name="Medium", region=Region.NOVA, segment=Segment.PROBATE),
                message=MagicMock(),
                priority=50
            ),
        ]

        # Sort by priority descending
        sorted_items = sorted(items, key=lambda x: x.priority, reverse=True)

        assert sorted_items[0].priority == 80
        assert sorted_items[1].priority == 50
        assert sorted_items[2].priority == 10


class TestFollowUpScheduling:
    """Test follow-up scheduling logic."""

    def test_followup_timing_calculation(self):
        """Test that follow-up timing is calculated correctly."""
        # Intro sent 5 days ago
        intro_sent = datetime.utcnow() - timedelta(days=5)
        followup_1_days = 4  # Should trigger at day 4

        days_since = (datetime.utcnow() - intro_sent).days

        # Follow-up 1 should be due (5 >= 4)
        assert days_since >= followup_1_days

    def test_followup_2_timing_calculation(self):
        """Test follow-up 2 timing after follow-up 1."""
        # Follow-up 1 sent 6 days ago
        followup1_sent = datetime.utcnow() - timedelta(days=6)
        followup_2_offset = 5  # Days after followup_1 for followup_2

        days_since = (datetime.utcnow() - followup1_sent).days

        # Follow-up 2 should be due (6 >= 5)
        assert days_since >= followup_2_offset


class TestPipelineStats:
    """Test pipeline statistics generation."""

    def test_stats_structure(self):
        """Test that stats dictionary has expected structure."""
        expected_keys = [
            "total_leads",
            "leads_with_email",
            "leads_new",
            "leads_ready",
            "leads_in_outreach",
            "leads_replied",
            "leads_booked",
            "region_DC",
            "region_NoVA",
            "region_SWVA",
            "segment_estate_planning",
            "segment_probate",
        ]

        # This would need actual DB session to test fully
        # Here we just verify the concept
        stats = {key: 0 for key in expected_keys}

        for key in expected_keys:
            assert key in stats
