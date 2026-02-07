"""
Tests for SEO Platform Modules.
Tests core functionality with mocked API calls.
"""

import os
import sys
import pytest
import datetime
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.models import init_db, Base, engine, SessionLocal
from database.models import (
    Keyword, KeywordRanking, AISearchResult, SchemaMarkup,
    BusinessListing, Review, Citation, ContentIdea,
    TechnicalAudit, PageAudit, Backlink, BacklinkOpportunity,
    Competitor, CompetitorAnalysis, Report, Alert, SEOMetric
)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Create test database tables."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    """Provide a transactional database session for tests."""
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


class TestDatabaseModels:
    """Test database model creation and relationships."""

    def test_create_keyword(self, db_session):
        kw = Keyword(
            keyword="apostille services Alexandria VA",
            service_type="apostille",
            geo_modifier="Alexandria VA",
            search_volume=500,
            competition_level="medium",
            priority="high"
        )
        db_session.add(kw)
        db_session.flush()
        assert kw.id is not None
        assert kw.keyword == "apostille services Alexandria VA"

    def test_create_keyword_ranking(self, db_session):
        kw = Keyword(keyword="notary near me", service_type="notary")
        db_session.add(kw)
        db_session.flush()

        ranking = KeywordRanking(
            keyword_id=kw.id,
            search_engine="google",
            position=5,
            url_found="https://commonnotaryapostille.com",
            tracked_date=datetime.date.today()
        )
        db_session.add(ranking)
        db_session.flush()
        assert ranking.keyword_id == kw.id
        assert ranking.position == 5

    def test_create_ai_search_result(self, db_session):
        result = AISearchResult(
            ai_engine="chatgpt",
            query="best notary in Alexandria VA",
            response_text="Common Notary Apostille is a top provider...",
            mentions_company=True,
            sentiment="positive",
            tracked_date=datetime.date.today()
        )
        db_session.add(result)
        db_session.flush()
        assert result.mentions_company is True

    def test_create_business_listing(self, db_session):
        listing = BusinessListing(
            platform="google",
            service_area="Alexandria VA",
            name_listed="Common Notary Apostille",
            nap_consistent=True,
            listing_score=85.0
        )
        db_session.add(listing)
        db_session.flush()
        assert listing.listing_score == 85.0

    def test_create_review(self, db_session):
        review = Review(
            platform="google",
            reviewer_name="John D.",
            rating=5.0,
            review_text="Excellent notary service!",
            review_date=datetime.date.today(),
            sentiment="positive",
            service_area="Alexandria VA"
        )
        db_session.add(review)
        db_session.flush()
        assert review.rating == 5.0

    def test_create_content_idea(self, db_session):
        idea = ContentIdea(
            title="How to Get an Apostille in Virginia",
            content_type="blog",
            target_keyword="apostille Virginia",
            target_area="Virginia",
            status="idea"
        )
        db_session.add(idea)
        db_session.flush()
        assert idea.status == "idea"

    def test_create_technical_audit(self, db_session):
        audit = TechnicalAudit(
            overall_score=78.5,
            pages_crawled=25,
            issues_found=12,
            critical_issues=2,
            warnings=10
        )
        db_session.add(audit)
        db_session.flush()
        assert audit.overall_score == 78.5

    def test_create_backlink(self, db_session):
        link = Backlink(
            source_url="https://example.com/notary-resources",
            source_domain="example.com",
            target_url="https://commonnotaryapostille.com",
            anchor_text="Common Notary Apostille",
            link_type="dofollow",
            domain_authority=45,
            is_toxic=False,
            first_seen=datetime.date.today()
        )
        db_session.add(link)
        db_session.flush()
        assert link.is_toxic is False

    def test_create_competitor(self, db_session):
        comp = Competitor(
            name="Competitor Notary LLC",
            domain="competitornotary.com",
            market="dmv"
        )
        db_session.add(comp)
        db_session.flush()

        analysis = CompetitorAnalysis(
            competitor_id=comp.id,
            analysis_date=datetime.date.today(),
            domain_authority=35,
            google_rating=4.2,
            total_reviews=50
        )
        db_session.add(analysis)
        db_session.flush()
        assert analysis.competitor_id == comp.id

    def test_create_alert(self, db_session):
        alert = Alert(
            alert_type="ranking_drop",
            severity="warning",
            title="Ranking drop for 'notary near me'",
            message="Position dropped from 5 to 12"
        )
        db_session.add(alert)
        db_session.flush()
        assert alert.is_read is False
        assert alert.is_resolved is False

    def test_create_seo_metric(self, db_session):
        metric = SEOMetric(
            metric_date=datetime.date.today(),
            organic_traffic=1500,
            keywords_in_top_10=25,
            domain_authority=30
        )
        db_session.add(metric)
        db_session.flush()
        assert metric.organic_traffic == 1500


class TestHelpers:
    """Test utility helper functions."""

    def test_get_all_keyword_combinations(self):
        from utils.helpers import get_all_keyword_combinations
        combos = get_all_keyword_combinations()
        assert len(combos) > 100  # Should generate many combinations
        assert any(c["priority"] == "high" for c in combos)

    def test_get_all_service_areas(self):
        from utils.helpers import get_all_service_areas
        areas = get_all_service_areas()
        assert len(areas) == 12  # 7 primary + 5 secondary
        assert any(a["city"] == "Alexandria" for a in areas)
        assert any(a["city"] == "Roanoke" for a in areas)

    def test_normalize_url(self):
        from utils.helpers import normalize_url
        assert normalize_url("https://Example.com/Page/") == "https://example.com/page"
        assert normalize_url("https://www.test.com") == "https://www.test.com"

    def test_extract_domain(self):
        from utils.helpers import extract_domain
        assert extract_domain("https://www.example.com/page") == "example.com"
        assert extract_domain("https://sub.domain.com") == "sub.domain.com"

    def test_nap_consistency(self):
        from utils.helpers import calculate_nap_consistency
        result = calculate_nap_consistency(
            "Common Notary Apostille", "123 Main St", "555-123-4567",
            "Common Notary Apostille", "123 Main St", "5551234567"
        )
        assert result["consistent"] is True
        assert result["score"] == 100.0

    def test_nap_inconsistency(self):
        from utils.helpers import calculate_nap_consistency
        result = calculate_nap_consistency(
            "Common Notary Apostille", "123 Main St", "555-123-4567",
            "Common Notary", "456 Oak Ave", "555-999-0000"
        )
        assert result["consistent"] is False
        assert len(result["issues"]) > 0

    def test_compute_seo_score(self):
        from utils.helpers import compute_seo_score
        score = compute_seo_score({
            "page_title": "Apostille Services - Common Notary",
            "meta_description": "Professional apostille services in Alexandria VA. Fast, reliable document authentication for all your needs. Contact us today!",
            "h1_tags": ["Apostille Services"],
            "h2_tags": ["Our Process", "Service Areas"],
            "word_count": 800,
            "images_without_alt": 0,
            "internal_links": 5,
            "mobile_friendly": True,
            "ssl_valid": True
        })
        assert score > 80  # Well-optimized page should score high

    def test_generate_schema_markup(self):
        from utils.helpers import generate_schema_markup
        schema = generate_schema_markup("LocalBusiness")
        assert schema["@type"] == "LocalBusiness"
        assert schema["@context"] == "https://schema.org"
        assert "name" in schema

    def test_format_ranking_change(self):
        from utils.helpers import format_ranking_change
        assert format_ranking_change(3, 7) == "▲4"  # Improved
        assert format_ranking_change(10, 5) == "▼5"  # Dropped
        assert format_ranking_change(5, 5) == "—"    # No change

    def test_get_date_range(self):
        from utils.helpers import get_date_range
        start, end = get_date_range("week")
        assert (end - start).days == 7
        start, end = get_date_range("month")
        assert (end - start).days == 30


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
