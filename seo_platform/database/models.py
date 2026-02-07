"""
Database models for the SEO & AI Monitoring Platform.
Uses SQLAlchemy ORM with support for SQLite (dev) and PostgreSQL (production).
"""

import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Boolean, Text,
    DateTime, Date, JSON, ForeignKey, Index, Enum as SQLEnum
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.sql import func

from config.settings import DATABASE_URL

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency for getting database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================
# Module 1: Keyword Research & Tracking
# ============================================================

class Keyword(Base):
    __tablename__ = "keywords"

    id = Column(Integer, primary_key=True, autoincrement=True)
    keyword = Column(String(500), nullable=False)
    service_type = Column(String(200))  # e.g., "apostille", "notary", "mobile notary"
    geo_modifier = Column(String(200))  # e.g., "Alexandria VA", "DMV"
    search_volume = Column(Integer)
    competition_level = Column(String(50))  # low, medium, high
    cpc = Column(Float)  # cost per click estimate
    priority = Column(String(50), default="medium")  # high, medium, low
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    rankings = relationship("KeywordRanking", back_populates="keyword_ref", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_keyword_text", "keyword"),
        Index("idx_keyword_geo", "geo_modifier"),
    )


class KeywordRanking(Base):
    __tablename__ = "keyword_rankings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    keyword_id = Column(Integer, ForeignKey("keywords.id"), nullable=False)
    search_engine = Column(String(50), nullable=False)  # google, bing, chatgpt, perplexity, etc.
    position = Column(Integer)  # ranking position (null if not found)
    url_found = Column(String(1000))  # the URL that ranked
    snippet = Column(Text)  # the snippet text shown
    page = Column(Integer)  # which page of results
    tracked_date = Column(Date, nullable=False)
    created_at = Column(DateTime, default=func.now())

    keyword_ref = relationship("Keyword", back_populates="rankings")

    __table_args__ = (
        Index("idx_ranking_date", "tracked_date"),
        Index("idx_ranking_engine", "search_engine"),
        Index("idx_ranking_keyword_date", "keyword_id", "tracked_date"),
    )


# ============================================================
# Module 2: AI Search Optimization
# ============================================================

class AISearchResult(Base):
    __tablename__ = "ai_search_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ai_engine = Column(String(100), nullable=False)  # chatgpt, perplexity, google_ai, bing_copilot, claude
    query = Column(Text, nullable=False)
    response_text = Column(Text)
    mentions_company = Column(Boolean, default=False)
    mention_context = Column(Text)  # surrounding text where mentioned
    competitor_mentions = Column(JSON)  # list of competitor names mentioned
    sentiment = Column(String(50))  # positive, neutral, negative
    position_in_response = Column(Integer)  # order of mention (1st, 2nd, etc.)
    tracked_date = Column(Date, nullable=False)
    created_at = Column(DateTime, default=func.now())

    __table_args__ = (
        Index("idx_ai_engine_date", "ai_engine", "tracked_date"),
    )


class SchemaMarkup(Base):
    __tablename__ = "schema_markups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    page_url = Column(String(1000), nullable=False)
    schema_type = Column(String(200))  # LocalBusiness, NotaryService, etc.
    schema_json = Column(JSON)
    is_deployed = Column(Boolean, default=False)
    validation_status = Column(String(50))  # valid, errors, warnings
    validation_errors = Column(JSON)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


# ============================================================
# Module 3: Local SEO Management
# ============================================================

class BusinessListing(Base):
    __tablename__ = "business_listings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(200), nullable=False)  # google, yelp, bbb, etc.
    listing_url = Column(String(1000))
    service_area = Column(String(200))  # which geographic area this covers
    name_listed = Column(String(500))
    address_listed = Column(Text)
    phone_listed = Column(String(50))
    website_listed = Column(String(1000))
    nap_consistent = Column(Boolean)  # NAP consistency check
    nap_issues = Column(JSON)  # specific inconsistencies found
    listing_score = Column(Float)  # completeness score 0-100
    last_checked = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_listing_platform", "platform"),
        Index("idx_listing_area", "service_area"),
    )


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(200), nullable=False)
    reviewer_name = Column(String(500))
    rating = Column(Float)
    review_text = Column(Text)
    review_date = Column(Date)
    response_text = Column(Text)  # our response
    response_date = Column(Date)
    suggested_response = Column(Text)  # AI-suggested response
    sentiment = Column(String(50))
    service_area = Column(String(200))
    needs_response = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())

    __table_args__ = (
        Index("idx_review_platform", "platform"),
        Index("idx_review_rating", "rating"),
    )


class Citation(Base):
    __tablename__ = "citations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    directory_name = Column(String(500), nullable=False)
    directory_url = Column(String(1000))
    category = Column(String(200))  # legal, business, local, notary-specific
    is_listed = Column(Boolean, default=False)
    listing_url = Column(String(1000))
    domain_authority = Column(Integer)
    priority = Column(String(50))  # high, medium, low
    notes = Column(Text)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class LocalCompetitor(Base):
    __tablename__ = "local_competitors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    business_name = Column(String(500), nullable=False)
    website = Column(String(1000))
    service_area = Column(String(200))
    google_rating = Column(Float)
    review_count = Column(Integer)
    gbp_url = Column(String(1000))
    top_keywords = Column(JSON)
    strengths = Column(JSON)
    weaknesses = Column(JSON)
    last_analyzed = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


# ============================================================
# Module 4: Content Strategy
# ============================================================

class ContentIdea(Base):
    __tablename__ = "content_ideas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    content_type = Column(String(100))  # blog, landing_page, faq, guide
    target_keyword = Column(String(500))
    target_area = Column(String(200))
    draft_content = Column(Text)
    meta_title = Column(String(200))
    meta_description = Column(String(500))
    headers = Column(JSON)  # H1, H2, H3 structure
    word_count = Column(Integer)
    readability_score = Column(Float)
    seo_score = Column(Float)
    status = Column(String(50), default="idea")  # idea, drafted, reviewed, published
    scheduled_date = Column(Date)
    published_url = Column(String(1000))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_content_status", "status"),
        Index("idx_content_type", "content_type"),
    )


class ContentCalendar(Base):
    __tablename__ = "content_calendar"

    id = Column(Integer, primary_key=True, autoincrement=True)
    content_idea_id = Column(Integer, ForeignKey("content_ideas.id"))
    scheduled_date = Column(Date, nullable=False)
    content_type = Column(String(100))
    title = Column(String(500))
    target_platform = Column(String(200))  # website, blog, social
    status = Column(String(50), default="scheduled")  # scheduled, in_progress, published
    assigned_to = Column(String(200))
    notes = Column(Text)
    created_at = Column(DateTime, default=func.now())

    content_idea = relationship("ContentIdea")


# ============================================================
# Module 5: Technical SEO
# ============================================================

class TechnicalAudit(Base):
    __tablename__ = "technical_audits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    audit_date = Column(DateTime, default=func.now())
    overall_score = Column(Float)
    pages_crawled = Column(Integer)
    issues_found = Column(Integer)
    critical_issues = Column(Integer)
    warnings = Column(Integer)
    audit_data = Column(JSON)  # full audit results
    recommendations = Column(JSON)  # prioritized recommendations
    created_at = Column(DateTime, default=func.now())


class PageAudit(Base):
    __tablename__ = "page_audits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    audit_id = Column(Integer, ForeignKey("technical_audits.id"))
    url = Column(String(1000), nullable=False)
    status_code = Column(Integer)
    page_title = Column(String(500))
    meta_description = Column(String(1000))
    h1_tags = Column(JSON)
    h2_tags = Column(JSON)
    word_count = Column(Integer)
    load_time_ms = Column(Integer)
    page_size_kb = Column(Float)
    has_canonical = Column(Boolean)
    canonical_url = Column(String(1000))
    has_robots_meta = Column(Boolean)
    robots_meta = Column(String(200))
    images_without_alt = Column(Integer)
    internal_links = Column(Integer)
    external_links = Column(Integer)
    broken_links = Column(JSON)
    mobile_friendly = Column(Boolean)
    core_web_vitals = Column(JSON)  # LCP, FID, CLS scores
    ssl_valid = Column(Boolean)
    issues = Column(JSON)
    created_at = Column(DateTime, default=func.now())

    audit = relationship("TechnicalAudit")

    __table_args__ = (
        Index("idx_page_url", "url"),
    )


# ============================================================
# Module 6: Backlinks
# ============================================================

class Backlink(Base):
    __tablename__ = "backlinks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_url = Column(String(1000), nullable=False)
    source_domain = Column(String(500))
    target_url = Column(String(1000))
    anchor_text = Column(String(500))
    link_type = Column(String(50))  # dofollow, nofollow
    domain_authority = Column(Integer)
    page_authority = Column(Integer)
    is_active = Column(Boolean, default=True)
    is_toxic = Column(Boolean, default=False)
    toxicity_score = Column(Float)
    first_seen = Column(Date)
    last_checked = Column(Date)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_backlink_domain", "source_domain"),
        Index("idx_backlink_toxic", "is_toxic"),
    )


class BacklinkOpportunity(Base):
    __tablename__ = "backlink_opportunities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    target_site = Column(String(500), nullable=False)
    target_url = Column(String(1000))
    category = Column(String(200))  # legal_directory, notary_association, chamber, state_directory
    domain_authority = Column(Integer)
    contact_info = Column(JSON)
    outreach_status = Column(String(50), default="identified")  # identified, contacted, secured, rejected
    outreach_template = Column(Text)
    notes = Column(Text)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


# ============================================================
# Module 7: Competitor Intelligence
# ============================================================

class Competitor(Base):
    __tablename__ = "competitors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(500), nullable=False)
    domain = Column(String(500))
    service_areas = Column(JSON)  # list of areas they serve
    market = Column(String(200))  # dmv, swva, both
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())

    analyses = relationship("CompetitorAnalysis", back_populates="competitor", cascade="all, delete-orphan")


class CompetitorAnalysis(Base):
    __tablename__ = "competitor_analyses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    competitor_id = Column(Integer, ForeignKey("competitors.id"), nullable=False)
    analysis_date = Column(Date, nullable=False)
    domain_authority = Column(Integer)
    total_backlinks = Column(Integer)
    referring_domains = Column(Integer)
    organic_keywords = Column(Integer)
    estimated_traffic = Column(Integer)
    google_rating = Column(Float)
    total_reviews = Column(Integer)
    top_keywords = Column(JSON)
    recent_content = Column(JSON)  # recently published content
    keyword_gaps = Column(JSON)  # keywords they rank for but we don't
    content_gaps = Column(JSON)  # topics they cover but we don't
    strengths = Column(JSON)
    weaknesses = Column(JSON)
    created_at = Column(DateTime, default=func.now())

    competitor = relationship("Competitor", back_populates="analyses")

    __table_args__ = (
        Index("idx_competitor_date", "competitor_id", "analysis_date"),
    )


# ============================================================
# Module 8: Reporting & Alerts
# ============================================================

class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_type = Column(String(100), nullable=False)  # weekly_seo, monthly_ai, technical_audit
    report_date = Column(Date, nullable=False)
    title = Column(String(500))
    summary = Column(Text)
    data = Column(JSON)  # full report data
    file_path = Column(String(1000))  # path to PDF file
    email_sent = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())

    __table_args__ = (
        Index("idx_report_type_date", "report_type", "report_date"),
    )


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_type = Column(String(100), nullable=False)
    severity = Column(String(50), nullable=False)  # critical, warning, info
    title = Column(String(500))
    message = Column(Text)
    data = Column(JSON)
    is_read = Column(Boolean, default=False)
    is_resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now())

    __table_args__ = (
        Index("idx_alert_type", "alert_type"),
        Index("idx_alert_severity", "severity"),
        Index("idx_alert_unread", "is_read"),
    )


class SEOMetric(Base):
    """Daily aggregate SEO metrics for ROI tracking."""
    __tablename__ = "seo_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    metric_date = Column(Date, nullable=False)
    organic_traffic = Column(Integer)
    organic_impressions = Column(Integer)
    organic_clicks = Column(Integer)
    average_position = Column(Float)
    total_keywords_tracked = Column(Integer)
    keywords_in_top_3 = Column(Integer)
    keywords_in_top_10 = Column(Integer)
    keywords_in_top_20 = Column(Integer)
    total_backlinks = Column(Integer)
    domain_authority = Column(Integer)
    leads_generated = Column(Integer)
    conversions = Column(Integer)
    revenue_attributed = Column(Float)
    created_at = Column(DateTime, default=func.now())

    __table_args__ = (
        Index("idx_metric_date", "metric_date"),
    )


def init_db():
    """Initialize the database, creating all tables."""
    Base.metadata.create_all(bind=engine)
    return engine


if __name__ == "__main__":
    print("Initializing database...")
    init_db()
    print("Database initialized successfully.")
