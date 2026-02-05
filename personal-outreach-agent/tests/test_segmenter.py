"""Tests for lead segmentation."""

import pytest
from src.models.lead import Lead, Segment, Region
from src.services.segmenter import LeadSegmenter


class TestLeadSegmenter:
    """Test suite for LeadSegmenter."""

    @pytest.fixture
    def segmenter(self):
        """Create a segmenter instance."""
        return LeadSegmenter()

    def test_classify_estate_planning(self, segmenter):
        """Test classification of estate planning leads."""
        lead = Lead(
            firm_name="Estate Planning Attorneys",
            practice_areas="Estate Planning, Trusts, Wills, Power of Attorney"
        )

        segment, confidence, keywords = segmenter.classify_segment(lead)

        assert segment == Segment.ESTATE_PLANNING
        assert confidence > 0.5
        assert len(keywords) > 0

    def test_classify_probate(self, segmenter):
        """Test classification of probate leads."""
        lead = Lead(
            firm_name="Probate Law Office",
            practice_areas="Probate, Estate Administration, Estate Settlement"
        )

        segment, confidence, keywords = segmenter.classify_segment(lead)

        assert segment == Segment.PROBATE
        assert confidence > 0.5

    def test_classify_elder_law(self, segmenter):
        """Test classification of elder law leads."""
        lead = Lead(
            firm_name="Senior Care Legal",
            practice_areas="Elder Law, Medicaid Planning, Long-term Care, Guardianship"
        )

        segment, confidence, keywords = segmenter.classify_segment(lead)

        assert segment == Segment.ELDER_LAW
        assert confidence > 0.5

    def test_classify_family(self, segmenter):
        """Test classification of family law leads."""
        lead = Lead(
            firm_name="Family Legal Services",
            practice_areas="Family Law, Divorce, Child Custody, Adoption"
        )

        segment, confidence, keywords = segmenter.classify_segment(lead)

        assert segment == Segment.FAMILY
        assert confidence > 0.5

    def test_classify_other(self, segmenter):
        """Test classification of non-matching leads."""
        lead = Lead(
            firm_name="Corporate Law Group",
            practice_areas="Corporate Law, Mergers, Acquisitions, Business"
        )

        segment, confidence, keywords = segmenter.classify_segment(lead)

        assert segment == Segment.OTHER
        assert len(keywords) == 0

    def test_classify_mixed_practice(self, segmenter):
        """Test classification with multiple practice areas."""
        lead = Lead(
            firm_name="Full Service Law Firm",
            practice_areas="Estate Planning, Family Law, Elder Law"
        )

        # Should prioritize estate planning (first in priority order)
        segment, confidence, keywords = segmenter.classify_segment(lead)

        assert segment == Segment.ESTATE_PLANNING

    def test_classify_region_dc(self, segmenter):
        """Test DC region classification."""
        lead = Lead(
            firm_name="DC Law Firm",
            city="Washington",
            state="DC"
        )

        region, confidence = segmenter.classify_region(lead)

        assert region == Region.DC
        assert confidence > 0.5

    def test_classify_region_nova(self, segmenter):
        """Test Northern Virginia region classification."""
        test_cities = ["Alexandria", "Arlington", "Fairfax", "McLean", "Vienna"]

        for city in test_cities:
            lead = Lead(firm_name="Test Firm", city=city, state="VA")
            region, confidence = segmenter.classify_region(lead)
            assert region == Region.NOVA, f"Failed for city: {city}"

    def test_classify_region_swva(self, segmenter):
        """Test Southwest Virginia region classification."""
        test_cities = ["Roanoke", "Christiansburg", "Blacksburg", "Salem"]

        for city in test_cities:
            lead = Lead(firm_name="Test Firm", city=city, state="VA")
            region, confidence = segmenter.classify_region(lead)
            assert region == Region.SWVA, f"Failed for city: {city}"

    def test_classify_region_other(self, segmenter):
        """Test other region classification."""
        lead = Lead(
            firm_name="Remote Firm",
            city="Los Angeles",
            state="CA"
        )

        region, confidence = segmenter.classify_region(lead)

        assert region == Region.OTHER

    def test_segment_lead_updates_lead(self, segmenter):
        """Test that segment_lead modifies the lead object."""
        lead = Lead(
            firm_name="Estate Planning Firm",
            practice_areas="Estate Planning, Trusts",
            city="Arlington",
            state="VA"
        )

        assert lead.segment is None
        assert lead.region is None

        segmenter.segment_lead(lead)

        assert lead.segment == Segment.ESTATE_PLANNING
        assert lead.region == Region.NOVA
        assert lead.confidence_score is not None

    def test_segment_multiple_leads(self, segmenter):
        """Test segmenting multiple leads."""
        leads = [
            Lead(firm_name="Firm A", practice_areas="Estate Planning", city="DC", state="DC"),
            Lead(firm_name="Firm B", practice_areas="Probate", city="Roanoke", state="VA"),
            Lead(firm_name="Firm C", practice_areas="Elder Law", city="Alexandria", state="VA"),
        ]

        segmenter.segment_leads(leads)

        assert leads[0].segment == Segment.ESTATE_PLANNING
        assert leads[0].region == Region.DC

        assert leads[1].segment == Segment.PROBATE
        assert leads[1].region == Region.SWVA

        assert leads[2].segment == Segment.ELDER_LAW
        assert leads[2].region == Region.NOVA

    def test_filter_by_segment(self, segmenter):
        """Test filtering leads by segment."""
        leads = [
            Lead(firm_name="A", segment=Segment.ESTATE_PLANNING),
            Lead(firm_name="B", segment=Segment.PROBATE),
            Lead(firm_name="C", segment=Segment.ESTATE_PLANNING),
            Lead(firm_name="D", segment=Segment.FAMILY),
        ]

        filtered = segmenter.filter_by_segment(leads, [Segment.ESTATE_PLANNING])
        assert len(filtered) == 2

        filtered = segmenter.filter_by_segment(leads, [Segment.ESTATE_PLANNING, Segment.PROBATE])
        assert len(filtered) == 3

    def test_filter_by_region(self, segmenter):
        """Test filtering leads by region."""
        leads = [
            Lead(firm_name="A", region=Region.DC),
            Lead(firm_name="B", region=Region.NOVA),
            Lead(firm_name="C", region=Region.DC),
            Lead(firm_name="D", region=Region.SWVA),
        ]

        filtered = segmenter.filter_by_region(leads, [Region.DC])
        assert len(filtered) == 2

        filtered = segmenter.filter_by_region(leads, [Region.DC, Region.NOVA])
        assert len(filtered) == 3

    def test_get_segment_stats(self, segmenter):
        """Test segment statistics."""
        leads = [
            Lead(firm_name="A", segment=Segment.ESTATE_PLANNING),
            Lead(firm_name="B", segment=Segment.ESTATE_PLANNING),
            Lead(firm_name="C", segment=Segment.PROBATE),
            Lead(firm_name="D", segment=Segment.OTHER),
        ]

        stats = segmenter.get_segment_stats(leads)

        assert stats["estate_planning"] == 2
        assert stats["probate"] == 1
        assert stats["other"] == 1
        assert stats["elder_law"] == 0

    def test_get_region_stats(self, segmenter):
        """Test region statistics."""
        leads = [
            Lead(firm_name="A", region=Region.DC),
            Lead(firm_name="B", region=Region.NOVA),
            Lead(firm_name="C", region=Region.NOVA),
            Lead(firm_name="D", region=Region.OTHER),
        ]

        stats = segmenter.get_region_stats(leads)

        assert stats["DC"] == 1
        assert stats["NoVA"] == 2
        assert stats["SWVA"] == 0
        assert stats["other"] == 1


class TestSegmenterEdgeCases:
    """Test edge cases for segmentation."""

    @pytest.fixture
    def segmenter(self):
        return LeadSegmenter()

    def test_empty_lead(self, segmenter):
        """Test segmentation of lead with no data."""
        lead = Lead(firm_name="Unknown Firm")

        segment, confidence, keywords = segmenter.classify_segment(lead)

        assert segment == Segment.OTHER
        assert confidence == 0.0

    def test_confidence_increases_with_keywords(self, segmenter):
        """Test that confidence increases with more matching keywords."""
        lead_one_keyword = Lead(
            firm_name="Test",
            practice_areas="Estate Planning"
        )

        lead_many_keywords = Lead(
            firm_name="Test",
            practice_areas="Estate Planning, Trusts, Wills, Power of Attorney, Living Trust"
        )

        _, conf1, _ = segmenter.classify_segment(lead_one_keyword)
        _, conf2, _ = segmenter.classify_segment(lead_many_keywords)

        assert conf2 > conf1

    def test_firm_name_used_for_classification(self, segmenter):
        """Test that firm name is used for classification when practice areas missing."""
        lead = Lead(firm_name="Elder Law Specialists")

        segment, confidence, keywords = segmenter.classify_segment(lead)

        assert segment == Segment.ELDER_LAW
        assert "elder law" in [k.lower() for k in keywords]
