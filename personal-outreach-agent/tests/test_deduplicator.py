"""Tests for lead deduplication."""

import pytest
from src.models.lead import Lead
from src.utils.deduplicator import LeadDeduplicator


class TestLeadDeduplicator:
    """Test suite for LeadDeduplicator."""

    def test_normalize_email(self):
        """Test email normalization."""
        assert LeadDeduplicator._normalize_email("Test@Example.COM") == "test@example.com"
        assert LeadDeduplicator._normalize_email("  test@example.com  ") == "test@example.com"
        assert LeadDeduplicator._normalize_email(None) is None
        assert LeadDeduplicator._normalize_email("") is None

    def test_normalize_phone(self):
        """Test phone number normalization."""
        assert LeadDeduplicator._normalize_phone("(202) 555-0100") == "2025550100"
        assert LeadDeduplicator._normalize_phone("202-555-0100") == "2025550100"
        assert LeadDeduplicator._normalize_phone("202.555.0100") == "2025550100"
        assert LeadDeduplicator._normalize_phone("1-202-555-0100") == "2025550100"
        assert LeadDeduplicator._normalize_phone("+1 202 555 0100") == "2025550100"
        assert LeadDeduplicator._normalize_phone(None) is None

    def test_normalize_firm_name(self):
        """Test firm name normalization."""
        # Test suffix removal
        assert LeadDeduplicator._normalize_firm_name("Smith Law Firm LLC") == "smith"
        assert LeadDeduplicator._normalize_firm_name("Johnson & Associates, P.C.") == "johnson"
        assert LeadDeduplicator._normalize_firm_name("Williams Elder Law PLLC") == "williams elder"
        assert LeadDeduplicator._normalize_firm_name("The Legal Group") == "legal group"

        # Test noise word removal
        assert LeadDeduplicator._normalize_firm_name("The Law Office of John Smith") == "law office john smith"

    def test_normalize_person_name(self):
        """Test person name normalization."""
        assert LeadDeduplicator._normalize_person_name("John Smith, Esq.") == "john smith"
        assert LeadDeduplicator._normalize_person_name("Dr. Jane Doe") == "jane doe"
        assert LeadDeduplicator._normalize_person_name("Robert Johnson Jr.") == "robert johnson"
        assert LeadDeduplicator._normalize_person_name("Mr. James Wilson III") == "james wilson"

    def test_email_match_duplicate(self):
        """Test duplicate detection by email match."""
        existing_lead = Lead(
            firm_name="Test Firm",
            attorney_name="John Smith",
            attorney_email="john@testfirm.com"
        )
        deduper = LeadDeduplicator([existing_lead])

        new_lead = Lead(
            firm_name="Different Firm Name",
            attorney_name="Different Name",
            attorney_email="john@testfirm.com"  # Same email
        )

        is_dup, matched, reason = deduper.is_duplicate(new_lead)
        assert is_dup is True
        assert matched == existing_lead
        assert reason == "email_match"

    def test_phone_match_duplicate(self):
        """Test duplicate detection by phone match."""
        existing_lead = Lead(
            firm_name="Test Firm",
            attorney_name="John Smith",
            attorney_phone="(202) 555-0100"
        )
        deduper = LeadDeduplicator([existing_lead])

        new_lead = Lead(
            firm_name="Different Firm",
            attorney_name="Different Name",
            attorney_phone="202-555-0100"  # Same phone, different format
        )

        is_dup, matched, reason = deduper.is_duplicate(new_lead)
        assert is_dup is True
        assert matched == existing_lead
        assert reason == "phone_match"

    def test_firm_and_attorney_match_duplicate(self):
        """Test duplicate detection by firm and attorney name match."""
        existing_lead = Lead(
            firm_name="Smith Law Firm LLC",
            attorney_name="John Smith, Esq."
        )
        deduper = LeadDeduplicator([existing_lead])

        new_lead = Lead(
            firm_name="Smith Law Firm",  # Same firm, no LLC
            attorney_name="John Smith"  # Same person, no Esq.
        )

        is_dup, matched, reason = deduper.is_duplicate(new_lead)
        assert is_dup is True
        assert matched == existing_lead
        assert "firm" in reason and "attorney" in reason

    def test_unique_lead(self):
        """Test that unique leads are not marked as duplicates."""
        existing_lead = Lead(
            firm_name="Smith Law Firm",
            attorney_name="John Smith",
            attorney_email="john@smithlaw.com"
        )
        deduper = LeadDeduplicator([existing_lead])

        new_lead = Lead(
            firm_name="Johnson Legal Group",
            attorney_name="Jane Johnson",
            attorney_email="jane@johnsonlegal.com"
        )

        is_dup, matched, reason = deduper.is_duplicate(new_lead)
        assert is_dup is False
        assert matched is None
        assert reason == ""

    def test_deduplicate_list(self):
        """Test deduplication of a list of leads."""
        existing_leads = [
            Lead(firm_name="Firm A", attorney_email="a@firma.com"),
            Lead(firm_name="Firm B", attorney_email="b@firmb.com"),
        ]
        deduper = LeadDeduplicator(existing_leads)

        new_leads = [
            Lead(firm_name="Firm C", attorney_email="c@firmc.com"),  # Unique
            Lead(firm_name="Firm A Copy", attorney_email="a@firma.com"),  # Duplicate
            Lead(firm_name="Firm D", attorney_email="d@firmd.com"),  # Unique
            Lead(firm_name="Firm E", attorney_email="c@firmc.com"),  # Duplicate of Firm C
        ]

        unique, duplicates = deduper.deduplicate_list(new_leads)

        assert len(unique) == 2  # Firm C and Firm D
        assert len(duplicates) == 2  # Firm A Copy and Firm E

    def test_similarity(self):
        """Test string similarity calculation."""
        # Exact match
        assert LeadDeduplicator._similarity("john smith", "john smith") == 1.0

        # Very similar
        sim = LeadDeduplicator._similarity("john smith", "john smithe")
        assert sim > 0.9

        # Different
        sim = LeadDeduplicator._similarity("john smith", "jane doe")
        assert sim < 0.5

    def test_website_match_duplicate(self):
        """Test duplicate detection by website match."""
        existing_lead = Lead(
            firm_name="Test Firm",
            attorney_name="John Smith",
            firm_website="https://testfirm.com"
        )
        deduper = LeadDeduplicator([existing_lead])

        new_lead = Lead(
            firm_name="Test Firm Inc",  # Slightly different name
            attorney_name="John Smith",  # Same attorney
            firm_website="https://testfirm.com/"  # Same website with trailing slash
        )

        is_dup, matched, reason = deduper.is_duplicate(new_lead)
        assert is_dup is True
        assert "website" in reason


class TestDeduplicatorEdgeCases:
    """Test edge cases for deduplication."""

    def test_empty_existing_leads(self):
        """Test with no existing leads."""
        deduper = LeadDeduplicator([])

        new_lead = Lead(firm_name="New Firm", attorney_email="test@new.com")
        is_dup, matched, reason = deduper.is_duplicate(new_lead)

        assert is_dup is False
        assert matched is None

    def test_lead_with_no_identifying_info(self):
        """Test lead with minimal identifying information."""
        existing_lead = Lead(firm_name="Existing Firm")
        deduper = LeadDeduplicator([existing_lead])

        new_lead = Lead(firm_name="Different Firm")
        is_dup, matched, reason = deduper.is_duplicate(new_lead)

        assert is_dup is False

    def test_add_lead_updates_index(self):
        """Test that adding a lead updates the internal indexes."""
        deduper = LeadDeduplicator([])

        lead1 = Lead(firm_name="Firm A", attorney_email="a@firma.com")
        deduper.add_lead(lead1)

        lead2 = Lead(firm_name="Firm B", attorney_email="a@firma.com")
        is_dup, matched, reason = deduper.is_duplicate(lead2)

        assert is_dup is True
        assert matched == lead1
