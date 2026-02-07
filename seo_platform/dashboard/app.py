"""
SEO & AI Monitoring Platform Dashboard
Common Notary Apostille

Main Streamlit web dashboard providing comprehensive SEO monitoring,
AI search visibility tracking, local SEO management, content strategy,
technical auditing, backlink analysis, competitor intelligence, and reporting.

Run with: streamlit run seo_platform/dashboard/app.py
"""

import sys
import os
import datetime
import random
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ---------------------------------------------------------------------------
# Path setup -- allow imports from the seo_platform package
# ---------------------------------------------------------------------------
_PLATFORM_ROOT = Path(__file__).resolve().parent.parent
if str(_PLATFORM_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLATFORM_ROOT))
if str(_PLATFORM_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(_PLATFORM_ROOT.parent))

# ---------------------------------------------------------------------------
# Graceful module imports -- the dashboard must work even when individual
# modules are not yet fully implemented.
# ---------------------------------------------------------------------------

try:
    from modules.keyword_tracker import KeywordTracker
except Exception:
    KeywordTracker = None

try:
    from modules.ai_search_optimizer import AISearchOptimizer
except Exception:
    AISearchOptimizer = None

try:
    from modules.local_seo_manager import LocalSEOManager
except Exception:
    LocalSEOManager = None

try:
    from modules.content_strategy import ContentStrategyEngine
except Exception:
    ContentStrategyEngine = None

try:
    from modules.technical_auditor import TechnicalSEOAuditor
except Exception:
    TechnicalSEOAuditor = None

try:
    from modules.backlink_builder import BacklinkBuilder
except Exception:
    BacklinkBuilder = None

try:
    from modules.competitor_intel import CompetitorIntelligence
except Exception:
    CompetitorIntelligence = None

try:
    from modules.reporting import ReportingEngine, AlertManager
except Exception:
    ReportingEngine = None
    AlertManager = None

try:
    from database.models import (
        SessionLocal, Keyword, KeywordRanking, AISearchResult,
        SchemaMarkup, BusinessListing, Review, Citation, LocalCompetitor,
        ContentIdea, ContentCalendar, TechnicalAudit, PageAudit,
        Backlink, BacklinkOpportunity, Competitor, CompetitorAnalysis,
        Report, Alert, SEOMetric,
    )
    _DB_AVAILABLE = True
except Exception:
    _DB_AVAILABLE = False

try:
    from config.settings import (
        COMPANY, SERVICE_AREAS, SERVICE_KEYWORDS, GEO_MODIFIERS,
        AI_SEARCH_ENGINES, COMPETITORS as CONFIG_COMPETITORS,
        SCHEDULE, ALERTS as ALERT_THRESHOLDS, REPORT_CONFIG,
    )
except Exception:
    COMPANY = {"name": "Common Notary Apostille", "website": "https://commonnotaryapostille.com"}
    SERVICE_AREAS = {"primary": [], "secondary": []}
    SERVICE_KEYWORDS = []
    GEO_MODIFIERS = []
    AI_SEARCH_ENGINES = []
    CONFIG_COMPETITORS = {}
    SCHEDULE = {}
    ALERT_THRESHOLDS = {}
    REPORT_CONFIG = {}


# ===================================================================
# PAGE CONFIGURATION & CUSTOM CSS
# ===================================================================

st.set_page_config(
    page_title="SEO Dashboard | Common Notary Apostille",
    page_icon="https://commonnotaryapostille.com/favicon.ico",
    layout="wide",
    initial_sidebar_state="expanded",
)

_CUSTOM_CSS = """
<style>
/* ---------- Import Google Fonts ---------- */
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700&family=Inter:wght@300;400;500;600;700&display=swap');

/* ---------- Root Variables ---------- */
:root {
    --gold-primary: #c9a84c;
    --gold-light: #F4E4BC;
    --gold-dark: #B8962E;
    --black-primary: #1a1a1a;
    --black-soft: #222222;
    --black-card: #161616;
    --white: #FFFFFF;
    --gray-300: #CCCCCC;
    --gray-400: #999999;
    --gray-500: #666666;
    --success: #4CAF50;
    --error: #E53935;
    --warning: #FFA726;
}

/* ---------- Global Overrides ---------- */
.stApp {
    background-color: var(--black-primary) !important;
    color: var(--white) !important;
    font-family: 'Inter', sans-serif !important;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background-color: #111111 !important;
    border-right: 1px solid rgba(201,168,76,0.25) !important;
}
section[data-testid="stSidebar"] .stRadio > label,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] li {
    color: var(--gray-300) !important;
}
section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label[data-baseweb="radio"] {
    color: var(--gray-300) !important;
}

/* Header bar */
header[data-testid="stHeader"] {
    background-color: rgba(17,17,17,0.95) !important;
    backdrop-filter: blur(10px);
    border-bottom: 1px solid rgba(201,168,76,0.2) !important;
}

/* Metrics */
div[data-testid="stMetric"] {
    background: var(--black-soft) !important;
    border: 1px solid rgba(201,168,76,0.2) !important;
    border-radius: 10px !important;
    padding: 16px 20px !important;
}
div[data-testid="stMetric"] label {
    color: var(--gray-400) !important;
    font-size: 0.85rem !important;
}
div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
    color: var(--gold-primary) !important;
    font-family: 'Playfair Display', serif !important;
    font-weight: 700 !important;
}
div[data-testid="stMetricDelta"] svg {
    display: inline !important;
}

/* Tabs */
button[data-baseweb="tab"] {
    color: var(--gray-400) !important;
    font-weight: 500 !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
    color: var(--gold-primary) !important;
    border-bottom-color: var(--gold-primary) !important;
}
div[data-baseweb="tab-highlight"] {
    background-color: var(--gold-primary) !important;
}

/* Expanders */
details[data-testid="stExpander"] {
    background: var(--black-soft) !important;
    border: 1px solid rgba(201,168,76,0.15) !important;
    border-radius: 8px !important;
}
details[data-testid="stExpander"] summary span {
    color: var(--gold-primary) !important;
    font-weight: 600 !important;
}

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, #c9a84c 0%, #F4E4BC 50%, #c9a84c 100%) !important;
    color: var(--black-primary) !important;
    border: none !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
    transition: all 0.3s ease !important;
}
.stButton > button:hover {
    box-shadow: 0 4px 20px rgba(201,168,76,0.4) !important;
    transform: translateY(-1px);
}
/* Secondary / outline style for download buttons */
.stDownloadButton > button {
    background: transparent !important;
    color: var(--gold-primary) !important;
    border: 2px solid var(--gold-primary) !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
}
.stDownloadButton > button:hover {
    background: rgba(201,168,76,0.1) !important;
}

/* DataFrames / tables */
div[data-testid="stDataFrame"] {
    border: 1px solid rgba(201,168,76,0.15) !important;
    border-radius: 8px !important;
}

/* Selectbox, multiselect, text_input */
div[data-baseweb="select"] > div,
div[data-baseweb="input"] > div {
    background-color: var(--black-soft) !important;
    border-color: rgba(201,168,76,0.3) !important;
    color: var(--white) !important;
}

/* Plotly charts -- transparent background */
.js-plotly-plot .plotly .main-svg {
    background: transparent !important;
}

/* Gold heading helper */
.gold-heading {
    font-family: 'Playfair Display', serif;
    color: #c9a84c;
    font-weight: 700;
    margin-bottom: 4px;
}
.section-divider {
    border: none;
    border-top: 1px solid rgba(201,168,76,0.2);
    margin: 1.5rem 0;
}

/* Alert cards */
.alert-critical { border-left: 4px solid #E53935 !important; }
.alert-warning  { border-left: 4px solid #FFA726 !important; }
.alert-info     { border-left: 4px solid #42A5F5 !important; }

/* Score badges */
.score-good    { color: #4CAF50; font-weight: 700; }
.score-ok      { color: #FFA726; font-weight: 700; }
.score-bad     { color: #E53935; font-weight: 700; }

/* Hide default Streamlit branding */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
</style>
"""

st.markdown(_CUSTOM_CSS, unsafe_allow_html=True)


# ===================================================================
# SESSION STATE INITIALIZATION
# ===================================================================

_DEFAULTS = {
    "current_page": "Home",
    "selected_keywords": [],
    "selected_competitor": None,
    "audit_running": False,
    "content_gen_running": False,
    "report_generating": False,
    "alert_filters": {"severity": "all", "read": "all"},
    "settings_saved": False,
    "api_keys": {
        "google_api_key": "",
        "google_cse_id": "",
        "openai_api_key": "",
        "anthropic_api_key": "",
        "ahrefs_api_key": "",
        "semrush_api_key": "",
        "sendgrid_api_key": "",
    },
    "email_notifications": True,
    "schedule_config": dict(SCHEDULE) if SCHEDULE else {},
    "alert_thresholds": dict(ALERT_THRESHOLDS) if ALERT_THRESHOLDS else {},
}

for key, default_val in _DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = default_val


# ===================================================================
# HELPER UTILITIES
# ===================================================================

def _get_db():
    """Return a database session if available, else None."""
    if not _DB_AVAILABLE:
        return None
    try:
        return SessionLocal()
    except Exception:
        return None


def _close_db(db):
    if db is not None:
        try:
            db.close()
        except Exception:
            pass


def _today():
    return datetime.date.today()


def _days_ago(n):
    return _today() - datetime.timedelta(days=n)


def _random_trend(n=30, base=15, amplitude=8):
    """Generate a plausible placeholder trend line."""
    vals = []
    v = base
    for _ in range(n):
        v += random.uniform(-amplitude * 0.3, amplitude * 0.3)
        v = max(1, min(base + amplitude, v))
        vals.append(round(v, 1))
    return vals


def _score_color(score):
    if score >= 75:
        return "score-good"
    if score >= 50:
        return "score-ok"
    return "score-bad"


def _severity_icon(sev):
    return {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(sev, "⚪")


def _placeholder_notice():
    st.info(
        "Live data is not yet available. The values shown below are "
        "illustrative placeholders. Connect your API keys and run the "
        "first data collection to populate real metrics."
    )


def _plotly_layout(fig, title="", height=380):
    """Apply consistent dark-theme layout to a Plotly figure."""
    fig.update_layout(
        title=dict(text=title, font=dict(color="#c9a84c", size=16, family="Playfair Display")),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(26,26,26,0.6)",
        font=dict(color="#cccccc", family="Inter"),
        height=height,
        margin=dict(l=40, r=20, t=50, b=40),
        legend=dict(font=dict(color="#999999")),
        xaxis=dict(gridcolor="rgba(201,168,76,0.1)", zerolinecolor="rgba(201,168,76,0.15)"),
        yaxis=dict(gridcolor="rgba(201,168,76,0.1)", zerolinecolor="rgba(201,168,76,0.15)"),
    )
    return fig


# ===================================================================
# PLACEHOLDER / DEMO DATA GENERATORS
# ===================================================================

def _demo_keywords_df():
    keywords = [
        ("apostille services Alexandria VA", 3, 5, "google", 720),
        ("mobile notary DMV", 7, 8, "google", 480),
        ("notary near me", 12, 15, "google", 3600),
        ("apostille near me", 5, 4, "google", 2400),
        ("document authentication DC", 9, 12, "google", 320),
        ("embassy legalization Virginia", 6, 6, "google", 210),
        ("loan signing agent Northern Virginia", 4, 7, "google", 390),
        ("mobile notary Alexandria VA", 2, 3, "google", 590),
        ("power of attorney notarization DMV", 8, 11, "google", 260),
        ("apostille services Roanoke VA", 1, 1, "google", 170),
        ("notary public Arlington VA", 11, 14, "google", 450),
        ("hospital notary near me", 6, 9, "google", 140),
        ("real estate closing notary NoVA", 10, 13, "google", 280),
        ("Spanish notary near me", 3, 5, "google", 190),
        ("remote online notarization Virginia", 15, 18, "google", 520),
        ("apostille services DMV", 4, 3, "bing", 310),
        ("mobile notary near me", 8, 10, "bing", 1200),
        ("certified translation notarization DC", 5, 7, "bing", 90),
    ]
    rows = []
    for kw, pos, prev, engine, vol in keywords:
        change = prev - pos
        rows.append({
            "Keyword": kw,
            "Position": pos,
            "Previous": prev,
            "Change": change,
            "Engine": engine.title(),
            "Volume": vol,
        })
    return pd.DataFrame(rows)


def _demo_ai_results():
    engines = ["ChatGPT", "Perplexity", "Google AI", "Bing Copilot", "Claude"]
    data = []
    for eng in engines:
        score = random.randint(40, 95)
        data.append({
            "Engine": eng,
            "Visibility Score": score,
            "Mentions": random.randint(2, 15),
            "Sentiment": random.choice(["Positive", "Neutral", "Positive", "Neutral", "Negative"]),
            "Last Checked": (_today() - datetime.timedelta(days=random.randint(0, 6))).isoformat(),
        })
    return pd.DataFrame(data)


def _demo_service_areas():
    areas = []
    for tier, tier_areas in SERVICE_AREAS.items():
        for a in tier_areas:
            areas.append({
                "City": a.get("city", ""),
                "State": a.get("state", ""),
                "Region": a.get("region", ""),
                "Tier": tier.title(),
                "SEO Score": random.randint(45, 95),
                "NAP OK": random.choice([True, True, True, False]),
                "GBP Score": random.randint(50, 100),
                "Reviews": random.randint(3, 85),
                "Avg Rating": round(random.uniform(3.8, 5.0), 1),
            })
    if not areas:
        areas.append({
            "City": "Alexandria", "State": "VA", "Region": "Northern Virginia",
            "Tier": "Primary", "SEO Score": 78, "NAP OK": True,
            "GBP Score": 85, "Reviews": 42, "Avg Rating": 4.7,
        })
    return pd.DataFrame(areas)


def _demo_content_ideas():
    ideas = [
        ("How to Get an Apostille in Virginia: Complete 2026 Guide", "blog", "published", 92),
        ("Mobile Notary vs Office Visit: Which Is Right for You?", "blog", "drafted", 78),
        ("Understanding Embassy Legalization for the DMV Area", "blog", "idea", 0),
        ("Apostille Services for Roanoke & Southwest Virginia", "landing_page", "published", 88),
        ("FAQ: Power of Attorney Notarization in DC, MD & VA", "faq", "reviewed", 85),
        ("Remote Online Notarization: What You Need to Know", "blog", "idea", 0),
        ("Hospital & Nursing Home Notary Services Guide", "guide", "drafted", 65),
        ("Bilingual Notary Services in the DMV Area", "landing_page", "idea", 0),
    ]
    rows = []
    for title, ctype, status, score in ideas:
        rows.append({
            "Title": title,
            "Type": ctype.replace("_", " ").title(),
            "Status": status.title(),
            "SEO Score": score,
            "Scheduled": (_today() + datetime.timedelta(days=random.randint(1, 30))).isoformat() if status != "published" else "",
        })
    return pd.DataFrame(rows)


def _demo_audit_results():
    return {
        "overall_score": 74,
        "pages_crawled": 28,
        "issues_found": 17,
        "critical_issues": 3,
        "warnings": 8,
        "info": 6,
        "core_web_vitals": {"LCP": 2.4, "FID": 85, "CLS": 0.12},
        "issues": [
            {"severity": "critical", "page": "/services", "issue": "Missing H1 tag"},
            {"severity": "critical", "page": "/apostille-dc", "issue": "Duplicate meta description"},
            {"severity": "critical", "page": "/contact", "issue": "Broken internal link to /team"},
            {"severity": "warning", "page": "/", "issue": "Image missing alt text (hero banner)"},
            {"severity": "warning", "page": "/blog/apostille-guide", "issue": "Title tag exceeds 60 characters"},
            {"severity": "warning", "page": "/services/mobile-notary", "issue": "Low word count (189 words)"},
            {"severity": "warning", "page": "/about", "issue": "No internal links to service pages"},
            {"severity": "warning", "page": "/faq", "issue": "Missing FAQ schema markup"},
            {"severity": "warning", "page": "/services/loan-signing", "issue": "No meta description"},
            {"severity": "warning", "page": "/blog", "issue": "Multiple H1 tags detected"},
            {"severity": "warning", "page": "/apostille-roanoke", "issue": "Slow load time (4.2s)"},
            {"severity": "info", "page": "/sitemap.xml", "issue": "Sitemap does not include blog posts"},
            {"severity": "info", "page": "/robots.txt", "issue": "Consider adding crawl-delay directive"},
            {"severity": "info", "page": "/services", "issue": "Consider adding breadcrumb schema"},
            {"severity": "info", "page": "/blog/apostille-guide", "issue": "Add internal links to related posts"},
            {"severity": "info", "page": "/", "issue": "Consider lazy-loading below-fold images"},
            {"severity": "info", "page": "/contact", "issue": "Add LocalBusiness schema markup"},
        ],
    }


def _demo_backlinks_df():
    sources = [
        ("va-notary-association.org", 62, "Common Notary Apostille", "dofollow", False),
        ("bbb.org/virginia", 91, "notary services", "dofollow", False),
        ("yelp.com/biz/common-notary", 94, "Common Notary", "nofollow", False),
        ("alexandriagazette.com/business", 45, "apostille Alexandria", "dofollow", False),
        ("dmvnotaries.com/directory", 38, "Click Here", "dofollow", False),
        ("spamlinks-directory.xyz", 5, "cheap notary", "dofollow", True),
        ("chamber-alexandria.org/members", 55, "Common Notary Apostille", "dofollow", False),
        ("lawyers.com/notary-resources", 71, "document authentication", "dofollow", False),
        ("nova-business-guide.com", 33, "mobile notary VA", "dofollow", False),
        ("roanoke-times.com/services", 58, "notary services Roanoke", "dofollow", False),
    ]
    rows = []
    for domain, da, anchor, ltype, toxic in sources:
        rows.append({
            "Source Domain": domain,
            "DA": da,
            "Anchor Text": anchor,
            "Type": ltype,
            "Toxic": toxic,
            "First Seen": (_today() - datetime.timedelta(days=random.randint(10, 365))).isoformat(),
            "Status": "Active",
        })
    return pd.DataFrame(rows)


def _demo_competitors_df():
    comps = [
        ("DMV Notary Express", "dmvnotaryexpress.com", "DMV", 45, 38, 4.5, 127),
        ("Capital Apostille", "capitalapostille.com", "DMV", 52, 54, 4.3, 89),
        ("Virginia Mobile Notary", "vamobilenotary.com", "Both", 39, 29, 4.7, 65),
        ("Roanoke Notary Services", "roanokenotary.com", "SWVA", 28, 15, 4.1, 31),
        ("DC Document Auth", "dcdocauth.com", "DMV", 41, 42, 4.4, 72),
    ]
    rows = []
    for name, domain, market, da, blinks, rating, reviews in comps:
        rows.append({
            "Name": name,
            "Domain": domain,
            "Market": market,
            "DA": da,
            "Backlinks": blinks,
            "Rating": rating,
            "Reviews": reviews,
        })
    return pd.DataFrame(rows)


def _demo_alerts():
    alerts = [
        ("critical", "Ranking Drop", "apostille services Alexandria VA dropped from #3 to #9", False, 1),
        ("warning", "New Negative Review", "2-star review on Google: 'Slow service...'", False, 2),
        ("info", "New Backlink Acquired", "Link from va-notary-association.org (DA 62)", True, 3),
        ("warning", "Page Speed Decline", "Homepage LCP increased to 3.8s (threshold: 2.5s)", False, 1),
        ("info", "Content Published", "Blog post 'Apostille Guide 2026' is now live", True, 5),
        ("critical", "SSL Certificate Expiring", "SSL cert expires in 14 days - renew immediately", False, 0),
        ("warning", "Competitor Gained Keyword", "Capital Apostille now ranks #2 for 'apostille DC'", False, 2),
    ]
    rows = []
    for sev, title, msg, is_read, days in alerts:
        rows.append({
            "severity": sev,
            "title": title,
            "message": msg,
            "is_read": is_read,
            "created_at": (_today() - datetime.timedelta(days=days)).isoformat(),
        })
    return rows


# ===================================================================
# SIDEBAR NAVIGATION
# ===================================================================

def _render_sidebar():
    with st.sidebar:
        st.markdown(
            "<div style='text-align:center; padding: 10px 0 20px 0;'>"
            "<span style='font-family: Playfair Display, serif; font-size:1.35rem; "
            "font-weight:700; color:#c9a84c;'>Common Notary</span><br>"
            "<span style='font-size:0.75rem; color:#999; letter-spacing:1.5px; "
            "text-transform:uppercase;'>Apostille Services</span>"
            "</div>",
            unsafe_allow_html=True,
        )
        st.markdown("<hr style='border-color:rgba(201,168,76,0.2); margin:0 0 12px 0;'>", unsafe_allow_html=True)

        pages = [
            "Home",
            "Keyword Rankings",
            "AI Search Visibility",
            "Local SEO",
            "Content Strategy",
            "Technical SEO",
            "Backlinks",
            "Competitors",
            "Reports & Alerts",
            "Settings",
        ]
        page = st.radio("Navigation", pages, index=pages.index(st.session_state.current_page), label_visibility="collapsed")
        st.session_state.current_page = page

        st.markdown("<hr style='border-color:rgba(201,168,76,0.2); margin:16px 0;'>", unsafe_allow_html=True)
        st.markdown(
            "<p style='font-size:0.75rem; color:#666;'>"
            "SEO & AI Monitoring Platform v1.0<br>"
            f"&copy; {datetime.date.today().year} Common Notary Apostille"
            "</p>",
            unsafe_allow_html=True,
        )

    return page


# ===================================================================
# PAGE: HOME / OVERVIEW DASHBOARD
# ===================================================================

def _page_home():
    st.markdown(
        "<h1 class='gold-heading' style='font-size:2rem;'>SEO & AI Monitoring Dashboard</h1>"
        "<p style='color:#999; margin-bottom:24px;'>Common Notary Apostille &mdash; Real-time performance overview</p>",
        unsafe_allow_html=True,
    )
    _placeholder_notice()

    # --- KPI cards ---
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Total Keywords", 156, delta="12 new")
    c2.metric("Top 10 Keywords", 38, delta="+5")
    c3.metric("AI Visibility", "72%", delta="+4%")
    c4.metric("Domain Authority", 34, delta="+2")
    c5.metric("Total Backlinks", 87, delta="+9")
    c6.metric("SEO Score", 74, delta="+3")

    st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)

    # --- Charts row ---
    left, right = st.columns([2, 1])

    with left:
        dates = [_days_ago(30 - i) for i in range(30)]
        avg_pos = _random_trend(30, base=12, amplitude=6)
        top10 = [int(random.uniform(28, 42)) for _ in range(30)]
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(
            go.Scatter(x=dates, y=avg_pos, name="Avg Position", line=dict(color="#c9a84c", width=2.5), fill="tozeroy", fillcolor="rgba(201,168,76,0.08)"),
            secondary_y=False,
        )
        fig.add_trace(
            go.Bar(x=dates, y=top10, name="Keywords in Top 10", marker_color="rgba(201,168,76,0.35)"),
            secondary_y=True,
        )
        fig.update_yaxes(title_text="Avg Position", secondary_y=False, autorange="reversed")
        fig.update_yaxes(title_text="Top 10 Count", secondary_y=True)
        _plotly_layout(fig, "Ranking Trend (Last 30 Days)", height=380)
        st.plotly_chart(fig, use_container_width=True)

    with right:
        st.markdown("<p class='gold-heading' style='font-size:1.1rem; margin-bottom:8px;'>Recent Alerts</p>", unsafe_allow_html=True)
        for alert in _demo_alerts()[:5]:
            icon = _severity_icon(alert["severity"])
            st.markdown(
                f"<div style='background:#222; border-radius:6px; padding:8px 12px; margin-bottom:6px; "
                f"border-left:3px solid {"#E53935" if alert["severity"]=="critical" else "#FFA726" if alert["severity"]=="warning" else "#42A5F5"};'>"
                f"<span style='font-size:0.82rem; color:#ccc;'>{icon} <b>{alert['title']}</b></span><br>"
                f"<span style='font-size:0.75rem; color:#888;'>{alert['message'][:80]}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
        if st.button("View All Alerts", key="home_alerts_btn"):
            st.session_state.current_page = "Reports & Alerts"
            st.rerun()

    st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)

    # --- Quick stats row ---
    q1, q2, q3 = st.columns(3)
    with q1:
        st.markdown("<p class='gold-heading' style='font-size:1rem;'>Top Performing Keywords</p>", unsafe_allow_html=True)
        df = _demo_keywords_df().sort_values("Position").head(5)[["Keyword", "Position", "Change"]]
        st.dataframe(df, hide_index=True, use_container_width=True)
    with q2:
        st.markdown("<p class='gold-heading' style='font-size:1rem;'>AI Visibility by Engine</p>", unsafe_allow_html=True)
        ai_df = _demo_ai_results()[["Engine", "Visibility Score"]]
        fig2 = px.bar(ai_df, x="Engine", y="Visibility Score", color_discrete_sequence=["#c9a84c"])
        _plotly_layout(fig2, "", height=260)
        st.plotly_chart(fig2, use_container_width=True)
    with q3:
        st.markdown("<p class='gold-heading' style='font-size:1rem;'>Content Pipeline</p>", unsafe_allow_html=True)
        cdf = _demo_content_ideas()
        status_counts = cdf["Status"].value_counts().reset_index()
        status_counts.columns = ["Status", "Count"]
        fig3 = px.pie(status_counts, names="Status", values="Count", color_discrete_sequence=["#c9a84c", "#F4E4BC", "#B8962E", "#666"])
        _plotly_layout(fig3, "", height=260)
        fig3.update_traces(textinfo="label+value", textfont_color="#fff")
        st.plotly_chart(fig3, use_container_width=True)


# ===================================================================
# PAGE: KEYWORD RANKINGS
# ===================================================================

def _page_keywords():
    st.markdown("<h1 class='gold-heading' style='font-size:1.8rem;'>Keyword Rankings</h1>", unsafe_allow_html=True)
    _placeholder_notice()

    df = _demo_keywords_df()

    # --- Filters ---
    with st.expander("Filters", expanded=True):
        fc1, fc2, fc3, fc4 = st.columns(4)
        engine_filter = fc1.selectbox("Search Engine", ["All"] + sorted(df["Engine"].unique().tolist()), key="kw_eng")
        geo_options = ["All"] + sorted(GEO_MODIFIERS) if GEO_MODIFIERS else ["All"]
        geo_filter = fc2.selectbox("Geo Area", geo_options, key="kw_geo")
        svc_options = ["All", "apostille", "notary", "mobile notary", "loan signing", "other"]
        svc_filter = fc3.selectbox("Service Type", svc_options, key="kw_svc")
        pos_filter = fc4.selectbox("Position Range", ["All", "Top 3", "Top 10", "Top 20", "11-50", "50+"], key="kw_pos")

    filtered = df.copy()
    if engine_filter != "All":
        filtered = filtered[filtered["Engine"] == engine_filter]
    if pos_filter == "Top 3":
        filtered = filtered[filtered["Position"] <= 3]
    elif pos_filter == "Top 10":
        filtered = filtered[filtered["Position"] <= 10]
    elif pos_filter == "Top 20":
        filtered = filtered[filtered["Position"] <= 20]
    elif pos_filter == "11-50":
        filtered = filtered[(filtered["Position"] >= 11) & (filtered["Position"] <= 50)]
    elif pos_filter == "50+":
        filtered = filtered[filtered["Position"] > 50]

    # --- Tabs ---
    tab_table, tab_trends, tab_movers, tab_add = st.tabs(["Rankings Table", "Trend Charts", "Top Movers", "Add Keyword"])

    with tab_table:
        def _highlight_change(val):
            if isinstance(val, (int, float)):
                if val > 0:
                    return "color: #4CAF50; font-weight: 700;"
                if val < 0:
                    return "color: #E53935; font-weight: 700;"
            return ""

        st.dataframe(
            filtered.style.applymap(_highlight_change, subset=["Change"]),
            hide_index=True,
            use_container_width=True,
            height=480,
        )
        st.caption(f"Showing {len(filtered)} of {len(df)} tracked keywords")

    with tab_trends:
        sel_kws = st.multiselect(
            "Select keywords to compare",
            df["Keyword"].unique().tolist(),
            default=df["Keyword"].unique().tolist()[:3],
            key="kw_trend_sel",
        )
        if sel_kws:
            dates = [_days_ago(30 - i) for i in range(30)]
            fig = go.Figure()
            for kw in sel_kws:
                row = df[df["Keyword"] == kw].iloc[0]
                base = row["Position"]
                trend = _random_trend(30, base=base, amplitude=4)
                fig.add_trace(go.Scatter(x=dates, y=trend, name=kw[:40], mode="lines+markers", marker=dict(size=4)))
            fig.update_yaxes(autorange="reversed", title_text="Position")
            _plotly_layout(fig, "Keyword Position Trend (30 Days)", height=420)
            st.plotly_chart(fig, use_container_width=True)

    with tab_movers:
        mc1, mc2 = st.columns(2)
        with mc1:
            st.markdown("<p class='gold-heading'>Biggest Gainers</p>", unsafe_allow_html=True)
            gainers = df[df["Change"] > 0].sort_values("Change", ascending=False).head(5)
            st.dataframe(gainers[["Keyword", "Position", "Change"]], hide_index=True, use_container_width=True)
        with mc2:
            st.markdown("<p class='gold-heading'>Biggest Losers</p>", unsafe_allow_html=True)
            losers = df[df["Change"] < 0].sort_values("Change").head(5)
            st.dataframe(losers[["Keyword", "Position", "Change"]], hide_index=True, use_container_width=True)

    with tab_add:
        with st.form("add_keyword_form"):
            st.markdown("<p class='gold-heading'>Add New Keyword</p>", unsafe_allow_html=True)
            ak1, ak2 = st.columns(2)
            new_kw = ak1.text_input("Keyword phrase")
            new_geo = ak2.selectbox("Geo modifier", ["None"] + GEO_MODIFIERS if GEO_MODIFIERS else ["None"])
            ak3, ak4 = st.columns(2)
            new_engine = ak3.selectbox("Search engine", ["Google", "Bing", "Both"])
            new_priority = ak4.selectbox("Priority", ["High", "Medium", "Low"])
            submitted = st.form_submit_button("Add Keyword")
            if submitted and new_kw:
                st.success(f"Keyword '{new_kw}' added to tracking queue.")
            elif submitted:
                st.warning("Please enter a keyword phrase.")


# ===================================================================
# PAGE: AI SEARCH VISIBILITY
# ===================================================================

def _page_ai_visibility():
    st.markdown("<h1 class='gold-heading' style='font-size:1.8rem;'>AI Search Visibility</h1>", unsafe_allow_html=True)
    _placeholder_notice()

    ai_df = _demo_ai_results()

    # --- Score cards ---
    cols = st.columns(len(ai_df))
    for i, row in ai_df.iterrows():
        with cols[i]:
            delta_val = random.choice(["+3%", "+1%", "-2%", "+5%", "0%"])
            st.metric(row["Engine"], f"{row['Visibility Score']}%", delta=delta_val)

    st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)

    tab_results, tab_mentions, tab_comp, tab_schema = st.tabs([
        "Monitoring Results", "Mention Tracking", "Competitor Mentions", "Schema Status"
    ])

    with tab_results:
        st.markdown("<p class='gold-heading'>Recent AI Monitoring Results</p>", unsafe_allow_html=True)
        queries = [
            "best apostille service in Virginia",
            "notary near me Alexandria VA",
            "how to get an apostille in DC",
            "mobile notary DMV area",
            "document authentication services Washington DC",
        ]
        result_rows = []
        for q in queries:
            for eng in ["ChatGPT", "Perplexity", "Google AI"]:
                mentioned = random.choice([True, True, False])
                result_rows.append({
                    "Query": q,
                    "Engine": eng,
                    "Mentioned": "Yes" if mentioned else "No",
                    "Position": random.randint(1, 5) if mentioned else "-",
                    "Sentiment": random.choice(["Positive", "Neutral"]) if mentioned else "-",
                    "Date": (_today() - datetime.timedelta(days=random.randint(0, 7))).isoformat(),
                })
        st.dataframe(pd.DataFrame(result_rows), hide_index=True, use_container_width=True, height=400)

    with tab_mentions:
        st.markdown("<p class='gold-heading'>Company Mentions Over Time</p>", unsafe_allow_html=True)
        dates = [_days_ago(30 - i) for i in range(30)]
        fig = go.Figure()
        for eng in ["ChatGPT", "Perplexity", "Google AI", "Bing Copilot", "Claude"]:
            mentions = [random.randint(0, 5) for _ in range(30)]
            fig.add_trace(go.Scatter(x=dates, y=mentions, name=eng, mode="lines", stackgroup="one"))
        _plotly_layout(fig, "Daily Company Mentions by AI Engine", height=380)
        st.plotly_chart(fig, use_container_width=True)

    with tab_comp:
        st.markdown("<p class='gold-heading'>Competitor Mentions Comparison</p>", unsafe_allow_html=True)
        comp_names = ["Common Notary Apostille", "DMV Notary Express", "Capital Apostille", "VA Mobile Notary"]
        comp_mentions = [random.randint(20, 60) for _ in comp_names]
        fig = px.bar(x=comp_names, y=comp_mentions, color_discrete_sequence=["#c9a84c", "#888", "#888", "#888"])
        fig.update_layout(xaxis_title="", yaxis_title="Total AI Mentions (30 days)")
        _plotly_layout(fig, "AI Mentions: Us vs Competitors", height=350)
        st.plotly_chart(fig, use_container_width=True)

    with tab_schema:
        st.markdown("<p class='gold-heading'>Schema Markup Status</p>", unsafe_allow_html=True)
        schema_rows = [
            {"Page": "/", "Schema Type": "LocalBusiness", "Deployed": True, "Valid": True},
            {"Page": "/services", "Schema Type": "ProfessionalService", "Deployed": True, "Valid": True},
            {"Page": "/faq", "Schema Type": "FAQPage", "Deployed": False, "Valid": False},
            {"Page": "/services/apostille", "Schema Type": "Service", "Deployed": True, "Valid": True},
            {"Page": "/contact", "Schema Type": "LocalBusiness", "Deployed": True, "Valid": False},
            {"Page": "/blog/apostille-guide", "Schema Type": "Article", "Deployed": False, "Valid": False},
        ]
        schema_df = pd.DataFrame(schema_rows)
        st.dataframe(schema_df, hide_index=True, use_container_width=True)
        deployed = sum(1 for r in schema_rows if r["Deployed"])
        st.caption(f"{deployed}/{len(schema_rows)} pages have schema markup deployed")


# ===================================================================
# PAGE: LOCAL SEO
# ===================================================================

def _page_local_seo():
    st.markdown("<h1 class='gold-heading' style='font-size:1.8rem;'>Local SEO Management</h1>", unsafe_allow_html=True)
    _placeholder_notice()

    areas_df = _demo_service_areas()

    tab_areas, tab_nap, tab_reviews, tab_citations, tab_gbp = st.tabs([
        "Service Areas", "NAP Consistency", "Reviews", "Citations", "GBP Recommendations"
    ])

    with tab_areas:
        st.markdown("<p class='gold-heading'>Service Area Performance</p>", unsafe_allow_html=True)
        for _, row in areas_df.iterrows():
            with st.expander(f"{row['City']}, {row['State']} ({row['Tier']}) -- SEO Score: {row['SEO Score']}"):
                ac1, ac2, ac3, ac4 = st.columns(4)
                ac1.metric("SEO Score", row["SEO Score"])
                ac2.metric("GBP Score", row["GBP Score"])
                ac3.metric("Reviews", row["Reviews"])
                ac4.metric("Avg Rating", row["Avg Rating"])

    with tab_nap:
        st.markdown("<p class='gold-heading'>NAP Consistency Across Listings</p>", unsafe_allow_html=True)
        platforms = ["Google Business Profile", "Yelp", "BBB", "Yellow Pages", "Apple Maps", "Bing Places", "Facebook"]
        nap_rows = []
        for p in platforms:
            consistent = random.choice([True, True, True, False])
            nap_rows.append({
                "Platform": p,
                "Name Match": True,
                "Address Match": consistent,
                "Phone Match": random.choice([True, True, False]) if not consistent else True,
                "Overall": "Consistent" if consistent else "Issues Found",
            })
        nap_df = pd.DataFrame(nap_rows)
        st.dataframe(nap_df, hide_index=True, use_container_width=True)
        consistent_count = sum(1 for r in nap_rows if r["Overall"] == "Consistent")
        st.caption(f"NAP Consistency Rate: {consistent_count}/{len(nap_rows)} platforms ({round(consistent_count/len(nap_rows)*100)}%)")

    with tab_reviews:
        st.markdown("<p class='gold-heading'>Recent Reviews</p>", unsafe_allow_html=True)
        reviews_data = [
            {"Platform": "Google", "Rating": 5, "Excerpt": "Excellent service! Fast apostille processing...", "Date": _days_ago(2).isoformat(), "Responded": True},
            {"Platform": "Google", "Rating": 4, "Excerpt": "Very professional mobile notary service...", "Date": _days_ago(5).isoformat(), "Responded": True},
            {"Platform": "Yelp", "Rating": 5, "Excerpt": "Best notary in the Alexandria area...", "Date": _days_ago(8).isoformat(), "Responded": False},
            {"Platform": "Google", "Rating": 2, "Excerpt": "Took longer than expected for apostille...", "Date": _days_ago(3).isoformat(), "Responded": False},
            {"Platform": "BBB", "Rating": 5, "Excerpt": "A+ service for embassy legalization...", "Date": _days_ago(12).isoformat(), "Responded": True},
        ]
        for rev in reviews_data:
            star_str = "★" * rev["Rating"] + "☆" * (5 - rev["Rating"])
            badge = "Responded" if rev["Responded"] else "Needs Response"
            badge_color = "#4CAF50" if rev["Responded"] else "#FFA726"
            st.markdown(
                f"<div style='background:#222; border-radius:8px; padding:12px 16px; margin-bottom:8px; "
                f"border-left:3px solid {"#4CAF50" if rev["Rating"]>=4 else "#FFA726" if rev["Rating"]==3 else "#E53935"};'>"
                f"<span style='color:#c9a84c; font-weight:600;'>{rev['Platform']}</span> "
                f"<span style='color:#c9a84c;'>{star_str}</span> "
                f"<span style='float:right; font-size:0.75rem; color:{badge_color}; background:rgba(0,0,0,0.3); "
                f"padding:2px 8px; border-radius:4px;'>{badge}</span><br>"
                f"<span style='color:#ccc; font-size:0.9rem;'>{rev['Excerpt']}</span><br>"
                f"<span style='color:#666; font-size:0.75rem;'>{rev['Date']}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

    with tab_citations:
        st.markdown("<p class='gold-heading'>Citation Status & Opportunities</p>", unsafe_allow_html=True)
        citation_rows = [
            {"Directory": "Google Business Profile", "Category": "Core", "Listed": True, "DA": 100, "Priority": "High"},
            {"Directory": "Yelp", "Category": "Core", "Listed": True, "DA": 94, "Priority": "High"},
            {"Directory": "BBB", "Category": "Business", "Listed": True, "DA": 91, "Priority": "High"},
            {"Directory": "Avvo", "Category": "Legal", "Listed": False, "DA": 72, "Priority": "High"},
            {"Directory": "Yellow Pages", "Category": "Core", "Listed": True, "DA": 85, "Priority": "Medium"},
            {"Directory": "Apple Maps", "Category": "Core", "Listed": False, "DA": 100, "Priority": "High"},
            {"Directory": "Notary Rotary", "Category": "Notary-Specific", "Listed": True, "DA": 45, "Priority": "Medium"},
            {"Directory": "123Notary", "Category": "Notary-Specific", "Listed": False, "DA": 42, "Priority": "Medium"},
            {"Directory": "NNA Directory", "Category": "Notary-Specific", "Listed": True, "DA": 55, "Priority": "Medium"},
            {"Directory": "Chamber of Commerce", "Category": "Local", "Listed": True, "DA": 55, "Priority": "Medium"},
        ]
        cit_df = pd.DataFrame(citation_rows)
        st.dataframe(cit_df, hide_index=True, use_container_width=True)
        listed = sum(1 for r in citation_rows if r["Listed"])
        st.caption(f"Listed: {listed}/{len(citation_rows)} directories")

    with tab_gbp:
        st.markdown("<p class='gold-heading'>Google Business Profile Optimization</p>", unsafe_allow_html=True)
        recs = [
            ("Add more photos", "Upload at least 10 business photos including office, team, and service examples", "High"),
            ("Post weekly updates", "Regular Google Posts improve visibility and engagement", "High"),
            ("Respond to all reviews", "2 reviews are awaiting response", "High"),
            ("Add Q&A content", "Pre-populate FAQ section with common notary/apostille questions", "Medium"),
            ("Update business hours", "Verify holiday hours are current", "Low"),
            ("Add service menu", "List all service types with descriptions and pricing", "Medium"),
            ("Enable messaging", "Turn on Google messaging for direct customer inquiries", "Medium"),
        ]
        for title, desc, priority in recs:
            pcolor = "#E53935" if priority == "High" else "#FFA726" if priority == "Medium" else "#42A5F5"
            st.markdown(
                f"<div style='background:#222; border-radius:6px; padding:10px 14px; margin-bottom:6px;'>"
                f"<span style='color:#fff; font-weight:600;'>{title}</span> "
                f"<span style='background:{pcolor}20; color:{pcolor}; font-size:0.7rem; padding:2px 6px; "
                f"border-radius:3px; font-weight:600;'>{priority}</span><br>"
                f"<span style='color:#999; font-size:0.85rem;'>{desc}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )


# ===================================================================
# PAGE: CONTENT STRATEGY
# ===================================================================

def _page_content():
    st.markdown("<h1 class='gold-heading' style='font-size:1.8rem;'>Content Strategy</h1>", unsafe_allow_html=True)
    _placeholder_notice()

    cdf = _demo_content_ideas()

    tab_cal, tab_ideas, tab_editor, tab_perf = st.tabs([
        "Content Calendar", "Idea Generator", "Draft Viewer", "Performance"
    ])

    with tab_cal:
        st.markdown("<p class='gold-heading'>Content Calendar</p>", unsafe_allow_html=True)
        cal_data = []
        for i in range(14):
            d = _today() + datetime.timedelta(days=i)
            if d.weekday() < 5:
                has = random.choice([True, False, False])
                if has:
                    cal_data.append({
                        "Date": d.isoformat(),
                        "Day": d.strftime("%A"),
                        "Title": random.choice(cdf["Title"].tolist()),
                        "Type": random.choice(["Blog", "Landing Page", "Social"]),
                        "Status": random.choice(["Scheduled", "In Progress", "Draft"]),
                    })
        if cal_data:
            st.dataframe(pd.DataFrame(cal_data), hide_index=True, use_container_width=True)
        else:
            st.info("No content scheduled for the next 2 weeks.")

    with tab_ideas:
        st.markdown("<p class='gold-heading'>Blog Idea Generator</p>", unsafe_allow_html=True)
        if st.button("Generate New Ideas", key="gen_ideas"):
            st.session_state.content_gen_running = True
        if st.session_state.get("content_gen_running"):
            with st.spinner("Generating content ideas based on keyword trends and gaps..."):
                pass  # In production this would call ContentStrategyEngine
            st.session_state.content_gen_running = False

        ideas = [
            "Step-by-Step: Getting a Federal Apostille for FBI Background Checks",
            "Virginia Notary Laws 2026: What Changed and What It Means for You",
            "Apostille vs Embassy Legalization: Which Do You Need?",
            "5 Common Mistakes When Getting Documents Apostilled in DC",
            "Why Mobile Notary Services Are Booming in Northern Virginia",
            "How to Prepare Documents for International Use (DMV Guide)",
            "Hospital Notarization: A Complete Guide for Families",
            "Real Estate Closings in Virginia: The Notary's Role Explained",
        ]
        for idx, idea in enumerate(ideas):
            ic1, ic2 = st.columns([5, 1])
            ic1.markdown(f"**{idx+1}.** {idea}")
            ic2.button("Draft", key=f"draft_{idx}")

    with tab_editor:
        st.markdown("<p class='gold-heading'>Draft Content</p>", unsafe_allow_html=True)
        drafts = cdf[cdf["Status"].isin(["Drafted", "Reviewed"])]
        if not drafts.empty:
            selected_draft = st.selectbox("Select draft", drafts["Title"].tolist(), key="draft_sel")
            st.text_area(
                "Content Editor",
                value=f"# {selected_draft}\n\nDraft content placeholder. In production, this loads "
                      f"the actual draft from the database for editing.\n\n"
                      f"## Introduction\n\nLorem ipsum dolor sit amet, consectetur adipiscing elit. "
                      f"Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.\n\n"
                      f"## Key Points\n\n- Point one about the topic\n- Point two with details\n"
                      f"- Point three for completeness\n\n## Conclusion\n\nSummary and call to action.",
                height=400,
                key="content_editor",
            )
            ec1, ec2, ec3 = st.columns(3)
            ec1.button("Save Draft", key="save_draft")
            ec2.button("Check SEO Score", key="check_seo")
            ec3.button("Publish", key="publish_draft")
        else:
            st.info("No drafts available. Generate ideas and create drafts first.")

    with tab_perf:
        st.markdown("<p class='gold-heading'>Content Performance</p>", unsafe_allow_html=True)
        perf_data = []
        published = cdf[cdf["Status"] == "Published"]
        for _, row in published.iterrows():
            perf_data.append({
                "Title": row["Title"],
                "SEO Score": row["SEO Score"],
                "Pageviews (30d)": random.randint(50, 1200),
                "Avg Time on Page": f"{random.randint(1,5)}:{random.randint(10,59):02d}",
                "Bounce Rate": f"{random.randint(25,65)}%",
                "Conversions": random.randint(0, 15),
            })
        if perf_data:
            st.dataframe(pd.DataFrame(perf_data), hide_index=True, use_container_width=True)
        else:
            st.info("No published content to report on yet.")


# ===================================================================
# PAGE: TECHNICAL SEO
# ===================================================================

def _page_technical():
    st.markdown("<h1 class='gold-heading' style='font-size:1.8rem;'>Technical SEO Audit</h1>", unsafe_allow_html=True)
    _placeholder_notice()

    audit = _demo_audit_results()

    # --- Score overview ---
    sc1, sc2, sc3, sc4, sc5 = st.columns(5)
    sc1.metric("Overall Score", audit["overall_score"])
    sc2.metric("Pages Crawled", audit["pages_crawled"])
    sc3.metric("Critical Issues", audit["critical_issues"], delta="-1", delta_color="inverse")
    sc4.metric("Warnings", audit["warnings"])
    sc5.metric("Info", audit["info"])

    st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)

    tab_issues, tab_cwv, tab_pages, tab_compare = st.tabs([
        "Issues List", "Core Web Vitals", "Page Audits", "Audit Comparison"
    ])

    with tab_issues:
        st.markdown("<p class='gold-heading'>Issues by Severity</p>", unsafe_allow_html=True)
        sev_filter = st.selectbox("Filter by severity", ["All", "Critical", "Warning", "Info"], key="tech_sev")
        issues = audit["issues"]
        if sev_filter != "All":
            issues = [i for i in issues if i["severity"] == sev_filter.lower()]

        for issue in sorted(issues, key=lambda x: {"critical": 0, "warning": 1, "info": 2}[x["severity"]]):
            sev = issue["severity"]
            color = "#E53935" if sev == "critical" else "#FFA726" if sev == "warning" else "#42A5F5"
            st.markdown(
                f"<div style='background:#222; border-radius:6px; padding:10px 14px; margin-bottom:6px; "
                f"border-left:3px solid {color};'>"
                f"<span style='background:{color}20; color:{color}; font-size:0.7rem; padding:2px 6px; "
                f"border-radius:3px; font-weight:600; text-transform:uppercase;'>{sev}</span> "
                f"<span style='color:#ccc; font-size:0.75rem;'>{issue['page']}</span><br>"
                f"<span style='color:#fff; font-size:0.9rem;'>{issue['issue']}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

    with tab_cwv:
        st.markdown("<p class='gold-heading'>Core Web Vitals</p>", unsafe_allow_html=True)
        cwv = audit["core_web_vitals"]
        vc1, vc2, vc3 = st.columns(3)

        lcp = cwv["LCP"]
        lcp_status = "Good" if lcp <= 2.5 else "Needs Improvement" if lcp <= 4.0 else "Poor"
        lcp_color = "#4CAF50" if lcp <= 2.5 else "#FFA726" if lcp <= 4.0 else "#E53935"
        with vc1:
            st.markdown(
                f"<div style='background:#222; border-radius:10px; padding:24px; text-align:center;'>"
                f"<p style='color:#999; font-size:0.85rem; margin-bottom:4px;'>Largest Contentful Paint</p>"
                f"<p style='color:{lcp_color}; font-size:2.5rem; font-weight:700; font-family:Playfair Display;'>{lcp}s</p>"
                f"<p style='color:{lcp_color}; font-size:0.85rem;'>{lcp_status}</p>"
                f"<p style='color:#666; font-size:0.75rem;'>Target: &le; 2.5s</p>"
                f"</div>",
                unsafe_allow_html=True,
            )

        fid = cwv["FID"]
        fid_status = "Good" if fid <= 100 else "Needs Improvement" if fid <= 300 else "Poor"
        fid_color = "#4CAF50" if fid <= 100 else "#FFA726" if fid <= 300 else "#E53935"
        with vc2:
            st.markdown(
                f"<div style='background:#222; border-radius:10px; padding:24px; text-align:center;'>"
                f"<p style='color:#999; font-size:0.85rem; margin-bottom:4px;'>First Input Delay</p>"
                f"<p style='color:{fid_color}; font-size:2.5rem; font-weight:700; font-family:Playfair Display;'>{fid}ms</p>"
                f"<p style='color:{fid_color}; font-size:0.85rem;'>{fid_status}</p>"
                f"<p style='color:#666; font-size:0.75rem;'>Target: &le; 100ms</p>"
                f"</div>",
                unsafe_allow_html=True,
            )

        cls_val = cwv["CLS"]
        cls_status = "Good" if cls_val <= 0.1 else "Needs Improvement" if cls_val <= 0.25 else "Poor"
        cls_color = "#4CAF50" if cls_val <= 0.1 else "#FFA726" if cls_val <= 0.25 else "#E53935"
        with vc3:
            st.markdown(
                f"<div style='background:#222; border-radius:10px; padding:24px; text-align:center;'>"
                f"<p style='color:#999; font-size:0.85rem; margin-bottom:4px;'>Cumulative Layout Shift</p>"
                f"<p style='color:{cls_color}; font-size:2.5rem; font-weight:700; font-family:Playfair Display;'>{cls_val}</p>"
                f"<p style='color:{cls_color}; font-size:0.85rem;'>{cls_status}</p>"
                f"<p style='color:#666; font-size:0.75rem;'>Target: &le; 0.1</p>"
                f"</div>",
                unsafe_allow_html=True,
            )

    with tab_pages:
        st.markdown("<p class='gold-heading'>Page-by-Page Audit Results</p>", unsafe_allow_html=True)
        page_rows = []
        pages_list = ["/", "/services", "/services/apostille", "/services/mobile-notary",
                      "/services/loan-signing", "/about", "/contact", "/faq",
                      "/blog", "/blog/apostille-guide", "/apostille-dc", "/apostille-roanoke"]
        for p in pages_list:
            page_rows.append({
                "URL": p,
                "Status": random.choice([200, 200, 200, 301, 200]),
                "Title": "OK" if random.random() > 0.2 else "Issue",
                "Meta Desc": "OK" if random.random() > 0.3 else "Missing",
                "H1": "OK" if random.random() > 0.2 else "Issue",
                "Load (ms)": random.randint(400, 4200),
                "Words": random.randint(150, 1800),
                "SEO Score": random.randint(45, 98),
            })
        st.dataframe(pd.DataFrame(page_rows), hide_index=True, use_container_width=True, height=400)

    with tab_compare:
        st.markdown("<p class='gold-heading'>Audit Comparison (Previous vs Current)</p>", unsafe_allow_html=True)
        comp_metrics = ["Overall Score", "Critical Issues", "Warnings", "Pages Crawled", "Avg Load Time (ms)"]
        previous = [68, 5, 12, 24, 2800]
        current = [74, 3, 8, 28, 2400]
        fig = go.Figure()
        fig.add_trace(go.Bar(name="Previous Audit", x=comp_metrics, y=previous, marker_color="#666"))
        fig.add_trace(go.Bar(name="Current Audit", x=comp_metrics, y=current, marker_color="#c9a84c"))
        fig.update_layout(barmode="group")
        _plotly_layout(fig, "Audit Comparison", height=380)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)
    if st.button("Run New Technical Audit", key="run_audit"):
        st.session_state.audit_running = True
    if st.session_state.get("audit_running"):
        with st.spinner("Running technical SEO audit... This may take a few minutes."):
            pass  # In production: TechnicalSEOAuditor().run_audit()
        st.session_state.audit_running = False
        st.success("Audit completed. Results displayed above (demo data).")


# ===================================================================
# PAGE: BACKLINKS
# ===================================================================

def _page_backlinks():
    st.markdown("<h1 class='gold-heading' style='font-size:1.8rem;'>Backlink Analysis</h1>", unsafe_allow_html=True)
    _placeholder_notice()

    bl_df = _demo_backlinks_df()

    # --- Overview metrics ---
    total = len(bl_df)
    toxic = bl_df["Toxic"].sum()
    new_30d = len(bl_df[bl_df["First Seen"] >= _days_ago(30).isoformat()])
    bm1, bm2, bm3, bm4 = st.columns(4)
    bm1.metric("Total Backlinks", total)
    bm2.metric("New (30d)", new_30d, delta=f"+{new_30d}")
    bm3.metric("Lost (30d)", random.randint(0, 2))
    bm4.metric("Toxic Links", int(toxic), delta=f"{int(toxic)}", delta_color="inverse")

    st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)

    tab_list, tab_opps, tab_comp, tab_toxic = st.tabs([
        "Backlink List", "Opportunities", "Competitor Comparison", "Toxic Links"
    ])

    with tab_list:
        st.markdown("<p class='gold-heading'>All Backlinks</p>", unsafe_allow_html=True)
        st.dataframe(bl_df, hide_index=True, use_container_width=True, height=400)

    with tab_opps:
        st.markdown("<p class='gold-heading'>Link Building Opportunities</p>", unsafe_allow_html=True)
        opps = [
            {"Target": "Avvo.com Lawyer Directory", "DA": 72, "Category": "Legal", "Status": "Identified", "Outreach": "Not Started"},
            {"Target": "Virginia State Bar Resources", "DA": 68, "Category": "Legal", "Status": "Identified", "Outreach": "Not Started"},
            {"Target": "Alexandria Chamber of Commerce", "DA": 55, "Category": "Local", "Status": "Contacted", "Outreach": "Email Sent"},
            {"Target": "NOVA Business Journal", "DA": 48, "Category": "Media", "Status": "Contacted", "Outreach": "Follow-up"},
            {"Target": "Roanoke Regional Partnership", "DA": 42, "Category": "Local", "Status": "Secured", "Outreach": "Completed"},
            {"Target": "National Notary Association Blog", "DA": 60, "Category": "Industry", "Status": "Identified", "Outreach": "Not Started"},
        ]
        st.dataframe(pd.DataFrame(opps), hide_index=True, use_container_width=True)

    with tab_comp:
        st.markdown("<p class='gold-heading'>Competitor Backlink Comparison</p>", unsafe_allow_html=True)
        comp_bl = {
            "Common Notary Apostille": 87,
            "DMV Notary Express": 38,
            "Capital Apostille": 54,
            "VA Mobile Notary": 29,
            "DC Document Auth": 42,
        }
        fig = px.bar(
            x=list(comp_bl.keys()), y=list(comp_bl.values()),
            color=list(comp_bl.keys()),
            color_discrete_sequence=["#c9a84c", "#666", "#777", "#555", "#888"],
        )
        fig.update_layout(xaxis_title="", yaxis_title="Total Backlinks", showlegend=False)
        _plotly_layout(fig, "Backlink Profile Comparison", height=350)
        st.plotly_chart(fig, use_container_width=True)

    with tab_toxic:
        st.markdown("<p class='gold-heading'>Toxic Backlink Alerts</p>", unsafe_allow_html=True)
        toxic_links = bl_df[bl_df["Toxic"] == True]
        if not toxic_links.empty:
            st.warning(f"{len(toxic_links)} toxic backlink(s) detected. Consider disavowing.")
            st.dataframe(toxic_links, hide_index=True, use_container_width=True)
            st.button("Generate Disavow File", key="disavow_btn")
        else:
            st.success("No toxic backlinks detected.")


# ===================================================================
# PAGE: COMPETITORS
# ===================================================================

def _page_competitors():
    st.markdown("<h1 class='gold-heading' style='font-size:1.8rem;'>Competitor Intelligence</h1>", unsafe_allow_html=True)
    _placeholder_notice()

    comp_df = _demo_competitors_df()

    tab_overview, tab_market, tab_kwgap, tab_contentgap, tab_cards = st.tabs([
        "Comparison Table", "Market Overview", "Keyword Gap", "Content Gap", "Strength / Weakness"
    ])

    with tab_overview:
        st.markdown("<p class='gold-heading'>Competitor Comparison</p>", unsafe_allow_html=True)
        # Add ourselves for comparison
        us = pd.DataFrame([{
            "Name": "Common Notary Apostille",
            "Domain": "commonnotaryapostille.com",
            "Market": "Both",
            "DA": 34,
            "Backlinks": 87,
            "Rating": 4.8,
            "Reviews": 52,
        }])
        full = pd.concat([us, comp_df], ignore_index=True)
        st.dataframe(full, hide_index=True, use_container_width=True)

    with tab_market:
        st.markdown("<p class='gold-heading'>Market Overview by Area</p>", unsafe_allow_html=True)
        mc1, mc2 = st.columns(2)
        with mc1:
            st.markdown("**DMV Area Competitors**")
            dmv = comp_df[comp_df["Market"].isin(["DMV", "Both"])]
            fig = px.scatter(dmv, x="DA", y="Reviews", size="Backlinks", color="Name",
                             hover_data=["Domain", "Rating"], color_discrete_sequence=px.colors.qualitative.Set2)
            _plotly_layout(fig, "DMV Market Map", height=350)
            st.plotly_chart(fig, use_container_width=True)
        with mc2:
            st.markdown("**SWVA Competitors**")
            swva = comp_df[comp_df["Market"].isin(["SWVA", "Both"])]
            fig = px.scatter(swva, x="DA", y="Reviews", size="Backlinks", color="Name",
                             hover_data=["Domain", "Rating"], color_discrete_sequence=px.colors.qualitative.Set2)
            _plotly_layout(fig, "SWVA Market Map", height=350)
            st.plotly_chart(fig, use_container_width=True)

    with tab_kwgap:
        st.markdown("<p class='gold-heading'>Keyword Gap Analysis</p>", unsafe_allow_html=True)
        st.markdown("Keywords competitors rank for that **we do not**:")
        gap_kws = [
            {"Keyword": "apostille service Washington DC", "Volume": 390, "Competitor": "Capital Apostille", "Their Pos": 3, "Our Pos": "-"},
            {"Keyword": "notarization services near me DMV", "Volume": 210, "Competitor": "DMV Notary Express", "Their Pos": 5, "Our Pos": "-"},
            {"Keyword": "Virginia apostille same day", "Volume": 170, "Competitor": "VA Mobile Notary", "Their Pos": 2, "Our Pos": "-"},
            {"Keyword": "emergency notary DC", "Volume": 140, "Competitor": "DMV Notary Express", "Their Pos": 4, "Our Pos": "-"},
            {"Keyword": "power of attorney notary Maryland", "Volume": 260, "Competitor": "Capital Apostille", "Their Pos": 7, "Our Pos": "22"},
        ]
        st.dataframe(pd.DataFrame(gap_kws), hide_index=True, use_container_width=True)

    with tab_contentgap:
        st.markdown("<p class='gold-heading'>Content Gap Analysis</p>", unsafe_allow_html=True)
        st.markdown("Content topics competitors cover that **we have not addressed**:")
        content_gaps = [
            {"Topic": "Same-day apostille processing guide", "Competitor": "Capital Apostille", "Content Type": "Blog", "Est. Traffic": 320},
            {"Topic": "State-by-state apostille requirements", "Competitor": "VA Mobile Notary", "Content Type": "Guide", "Est. Traffic": 580},
            {"Topic": "Notary fee calculator", "Competitor": "DMV Notary Express", "Content Type": "Tool", "Est. Traffic": 450},
            {"Topic": "Embassy legalization country guide", "Competitor": "DC Document Auth", "Content Type": "Resource", "Est. Traffic": 210},
        ]
        st.dataframe(pd.DataFrame(content_gaps), hide_index=True, use_container_width=True)

    with tab_cards:
        st.markdown("<p class='gold-heading'>Competitor Profiles</p>", unsafe_allow_html=True)
        for _, comp in comp_df.iterrows():
            with st.expander(f"{comp['Name']} ({comp['Domain']})"):
                cc1, cc2, cc3, cc4 = st.columns(4)
                cc1.metric("Domain Authority", comp["DA"])
                cc2.metric("Backlinks", comp["Backlinks"])
                cc3.metric("Google Rating", comp["Rating"])
                cc4.metric("Reviews", comp["Reviews"])

                sc1, sc2 = st.columns(2)
                with sc1:
                    st.markdown("**Strengths**")
                    strengths = random.sample([
                        "Strong local citations", "High review count", "Active blog",
                        "Fast website", "Good schema markup", "Strong social presence",
                    ], 3)
                    for s in strengths:
                        st.markdown(f"- {s}")
                with sc2:
                    st.markdown("**Weaknesses**")
                    weaknesses = random.sample([
                        "Low domain authority", "Few backlinks", "No blog content",
                        "Poor mobile experience", "Missing schema", "Thin content",
                        "No AI optimization", "Limited service areas",
                    ], 3)
                    for w in weaknesses:
                        st.markdown(f"- {w}")


# ===================================================================
# PAGE: REPORTS & ALERTS
# ===================================================================

def _page_reports():
    st.markdown("<h1 class='gold-heading' style='font-size:1.8rem;'>Reports & Alerts</h1>", unsafe_allow_html=True)
    _placeholder_notice()

    tab_gen, tab_alerts, tab_roi = st.tabs(["Generate Reports", "Alert Feed", "ROI Metrics"])

    with tab_gen:
        st.markdown("<p class='gold-heading'>Report Generation</p>", unsafe_allow_html=True)
        rg1, rg2, rg3 = st.columns(3)

        with rg1:
            st.markdown(
                "<div style='background:#222; border-radius:10px; padding:20px; text-align:center;'>"
                "<p style='color:#c9a84c; font-size:1.1rem; font-weight:600;'>Weekly SEO Report</p>"
                "<p style='color:#999; font-size:0.85rem;'>Rankings, traffic, backlinks, and key changes</p>"
                "</div>",
                unsafe_allow_html=True,
            )
            if st.button("Generate Weekly Report", key="gen_weekly"):
                with st.spinner("Generating report..."):
                    pass
                st.success("Weekly SEO report generated.")
            st.download_button("Download PDF", data=b"PDF placeholder", file_name="weekly_seo_report.pdf", mime="application/pdf", key="dl_weekly")

        with rg2:
            st.markdown(
                "<div style='background:#222; border-radius:10px; padding:20px; text-align:center;'>"
                "<p style='color:#c9a84c; font-size:1.1rem; font-weight:600;'>Monthly AI Report</p>"
                "<p style='color:#999; font-size:0.85rem;'>AI visibility, mentions, competitor comparison</p>"
                "</div>",
                unsafe_allow_html=True,
            )
            if st.button("Generate AI Report", key="gen_ai"):
                with st.spinner("Generating report..."):
                    pass
                st.success("Monthly AI report generated.")
            st.download_button("Download PDF", data=b"PDF placeholder", file_name="monthly_ai_report.pdf", mime="application/pdf", key="dl_ai")

        with rg3:
            st.markdown(
                "<div style='background:#222; border-radius:10px; padding:20px; text-align:center;'>"
                "<p style='color:#c9a84c; font-size:1.1rem; font-weight:600;'>Technical Audit Report</p>"
                "<p style='color:#999; font-size:0.85rem;'>Full audit results, issues, and recommendations</p>"
                "</div>",
                unsafe_allow_html=True,
            )
            if st.button("Generate Audit Report", key="gen_audit"):
                with st.spinner("Generating report..."):
                    pass
                st.success("Technical audit report generated.")
            st.download_button("Download PDF", data=b"PDF placeholder", file_name="technical_audit_report.pdf", mime="application/pdf", key="dl_audit")

    with tab_alerts:
        st.markdown("<p class='gold-heading'>Alert Feed</p>", unsafe_allow_html=True)

        af1, af2 = st.columns(2)
        sev_f = af1.selectbox("Severity", ["All", "Critical", "Warning", "Info"], key="alert_sev_filter")
        read_f = af2.selectbox("Status", ["All", "Unread", "Read"], key="alert_read_filter")

        alerts = _demo_alerts()
        if sev_f != "All":
            alerts = [a for a in alerts if a["severity"] == sev_f.lower()]
        if read_f == "Unread":
            alerts = [a for a in alerts if not a["is_read"]]
        elif read_f == "Read":
            alerts = [a for a in alerts if a["is_read"]]

        for idx, alert in enumerate(alerts):
            sev = alert["severity"]
            color = "#E53935" if sev == "critical" else "#FFA726" if sev == "warning" else "#42A5F5"
            read_badge = "<span style='color:#4CAF50; font-size:0.7rem;'>READ</span>" if alert["is_read"] else "<span style='color:#FFA726; font-size:0.7rem;'>NEW</span>"
            st.markdown(
                f"<div style='background:#222; border-radius:8px; padding:12px 16px; margin-bottom:8px; "
                f"border-left:4px solid {color};'>"
                f"<span style='background:{color}20; color:{color}; font-size:0.7rem; padding:2px 6px; "
                f"border-radius:3px; font-weight:600; text-transform:uppercase;'>{sev}</span> "
                f"{read_badge} "
                f"<span style='color:#666; font-size:0.75rem; float:right;'>{alert['created_at']}</span><br>"
                f"<span style='color:#fff; font-weight:600; font-size:0.95rem;'>{alert['title']}</span><br>"
                f"<span style='color:#999; font-size:0.85rem;'>{alert['message']}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
            acol1, acol2, acol3 = st.columns([1, 1, 6])
            acol1.button("Mark Read", key=f"read_{idx}")
            acol2.button("Resolve", key=f"resolve_{idx}")

        st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)
        st.markdown("<p class='gold-heading'>Alert Threshold Settings</p>", unsafe_allow_html=True)
        with st.form("alert_settings_form"):
            as1, as2 = st.columns(2)
            as1.number_input("Ranking drop threshold (positions)", value=5, min_value=1, max_value=50, key="alert_rank_drop")
            as2.number_input("Negative review threshold (stars)", value=3, min_value=1, max_value=5, key="alert_neg_review")
            as3, as4 = st.columns(2)
            as3.number_input("Page speed alert threshold", value=50, min_value=0, max_value=100, key="alert_pagespeed")
            as4.number_input("Uptime check interval (seconds)", value=300, min_value=60, max_value=3600, key="alert_uptime")
            if st.form_submit_button("Save Alert Settings"):
                st.success("Alert thresholds updated.")

    with tab_roi:
        st.markdown("<p class='gold-heading'>ROI Metrics</p>", unsafe_allow_html=True)

        rm1, rm2, rm3, rm4 = st.columns(4)
        rm1.metric("Organic Traffic (30d)", "2,847", delta="+12%")
        rm2.metric("Leads Generated", 34, delta="+8")
        rm3.metric("Conversions", 18, delta="+5")
        rm4.metric("Est. Revenue", "$4,230", delta="+$980")

        dates = [_days_ago(30 - i) for i in range(30)]
        traffic = [random.randint(60, 140) for _ in range(30)]
        leads = [random.randint(0, 4) for _ in range(30)]

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Scatter(x=dates, y=traffic, name="Organic Traffic", line=dict(color="#c9a84c", width=2), fill="tozeroy", fillcolor="rgba(201,168,76,0.08)"), secondary_y=False)
        fig.add_trace(go.Bar(x=dates, y=leads, name="Leads", marker_color="rgba(76,175,80,0.5)"), secondary_y=True)
        fig.update_yaxes(title_text="Daily Visitors", secondary_y=False)
        fig.update_yaxes(title_text="Leads", secondary_y=True)
        _plotly_layout(fig, "Traffic & Leads (30 Days)", height=380)
        st.plotly_chart(fig, use_container_width=True)


# ===================================================================
# PAGE: SETTINGS
# ===================================================================

def _page_settings():
    st.markdown("<h1 class='gold-heading' style='font-size:1.8rem;'>Settings</h1>", unsafe_allow_html=True)

    tab_api, tab_areas, tab_comp, tab_alerts, tab_email, tab_sched = st.tabs([
        "API Keys", "Service Areas", "Competitors", "Alert Thresholds", "Email Notifications", "Schedules"
    ])

    with tab_api:
        st.markdown("<p class='gold-heading'>API Key Configuration</p>", unsafe_allow_html=True)
        st.markdown(
            "<p style='color:#999; font-size:0.85rem;'>API keys are stored as environment variables. "
            "Update them in your <code>.env</code> file or enter below for this session.</p>",
            unsafe_allow_html=True,
        )
        with st.form("api_keys_form"):
            ak = st.session_state.api_keys
            ak["google_api_key"] = st.text_input("Google API Key", value=ak.get("google_api_key", ""), type="password")
            ak["google_cse_id"] = st.text_input("Google CSE ID", value=ak.get("google_cse_id", ""), type="password")
            ak["openai_api_key"] = st.text_input("OpenAI API Key", value=ak.get("openai_api_key", ""), type="password")
            ak["anthropic_api_key"] = st.text_input("Anthropic API Key", value=ak.get("anthropic_api_key", ""), type="password")
            ak["ahrefs_api_key"] = st.text_input("Ahrefs API Key", value=ak.get("ahrefs_api_key", ""), type="password")
            ak["semrush_api_key"] = st.text_input("SEMrush API Key", value=ak.get("semrush_api_key", ""), type="password")
            ak["sendgrid_api_key"] = st.text_input("SendGrid API Key", value=ak.get("sendgrid_api_key", ""), type="password")
            if st.form_submit_button("Save API Keys"):
                st.session_state.api_keys = ak
                st.success("API keys saved for this session. For persistence, update your .env file.")

    with tab_areas:
        st.markdown("<p class='gold-heading'>Service Area Management</p>", unsafe_allow_html=True)
        st.markdown("**Primary Service Areas**")
        primary = SERVICE_AREAS.get("primary", [])
        if primary:
            st.dataframe(pd.DataFrame(primary), hide_index=True, use_container_width=True)
        else:
            st.info("No primary service areas configured. Update config/settings.py.")

        st.markdown("**Secondary Service Areas**")
        secondary = SERVICE_AREAS.get("secondary", [])
        if secondary:
            st.dataframe(pd.DataFrame(secondary), hide_index=True, use_container_width=True)
        else:
            st.info("No secondary service areas configured.")

        with st.form("add_area_form"):
            st.markdown("**Add New Service Area**")
            na1, na2, na3, na4 = st.columns(4)
            new_city = na1.text_input("City", key="new_area_city")
            new_state = na2.text_input("State", key="new_area_state")
            new_region = na3.text_input("Region", key="new_area_region")
            new_tier = na4.selectbox("Tier", ["Primary", "Secondary"], key="new_area_tier")
            if st.form_submit_button("Add Service Area"):
                if new_city and new_state:
                    st.success(f"Service area '{new_city}, {new_state}' added. Update config/settings.py to persist.")
                else:
                    st.warning("City and State are required.")

    with tab_comp:
        st.markdown("<p class='gold-heading'>Competitor Management</p>", unsafe_allow_html=True)
        comp_df = _demo_competitors_df()
        edited_df = st.data_editor(
            comp_df,
            num_rows="dynamic",
            use_container_width=True,
            key="comp_editor",
        )
        if st.button("Save Competitor List", key="save_comps"):
            st.success("Competitor list saved.")

    with tab_alerts:
        st.markdown("<p class='gold-heading'>Alert Threshold Configuration</p>", unsafe_allow_html=True)
        with st.form("settings_alert_form"):
            sa1, sa2 = st.columns(2)
            rank_thresh = sa1.number_input(
                "Ranking drop alert (positions)",
                value=st.session_state.alert_thresholds.get("ranking_drop_threshold", 5),
                min_value=1, max_value=50,
            )
            review_thresh = sa2.number_input(
                "Negative review alert (max stars)",
                value=st.session_state.alert_thresholds.get("negative_review_threshold", 3),
                min_value=1, max_value=5,
            )
            sa3, sa4 = st.columns(2)
            speed_thresh = sa3.number_input(
                "Page speed alert (min score)",
                value=st.session_state.alert_thresholds.get("page_speed_threshold", 50),
                min_value=0, max_value=100,
            )
            uptime_int = sa4.number_input(
                "Uptime check interval (seconds)",
                value=st.session_state.alert_thresholds.get("uptime_check_interval", 300),
                min_value=60, max_value=3600,
            )
            if st.form_submit_button("Save Thresholds"):
                st.session_state.alert_thresholds = {
                    "ranking_drop_threshold": rank_thresh,
                    "negative_review_threshold": review_thresh,
                    "page_speed_threshold": speed_thresh,
                    "uptime_check_interval": uptime_int,
                }
                st.success("Alert thresholds updated.")

    with tab_email:
        st.markdown("<p class='gold-heading'>Email Notification Settings</p>", unsafe_allow_html=True)
        with st.form("email_form"):
            email_on = st.toggle("Enable email notifications", value=st.session_state.email_notifications)
            recipients = st.text_area(
                "Notification recipients (one email per line)",
                value="\n".join(REPORT_CONFIG.get("email_recipients", [])),
                height=120,
            )
            en1, en2 = st.columns(2)
            en1.selectbox("Report frequency", ["Weekly", "Bi-weekly", "Monthly"], key="email_freq")
            en2.selectbox("Preferred send day", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"], key="email_day")
            if st.form_submit_button("Save Email Settings"):
                st.session_state.email_notifications = email_on
                st.success("Email notification settings saved.")

    with tab_sched:
        st.markdown("<p class='gold-heading'>Schedule Configuration</p>", unsafe_allow_html=True)
        st.markdown(
            "<p style='color:#999; font-size:0.85rem;'>Configure how often each module runs its data collection tasks.</p>",
            unsafe_allow_html=True,
        )
        with st.form("schedule_form"):
            schedule = st.session_state.schedule_config
            freq_options = ["daily", "weekly", "bi-weekly", "monthly"]
            sc1, sc2 = st.columns(2)
            schedule["keyword_tracking"] = sc1.selectbox(
                "Keyword Tracking", freq_options,
                index=freq_options.index(schedule.get("keyword_tracking", "weekly")),
                key="sched_kw",
            )
            schedule["ai_monitoring"] = sc2.selectbox(
                "AI Monitoring", freq_options,
                index=freq_options.index(schedule.get("ai_monitoring", "weekly")),
                key="sched_ai",
            )
            sc3, sc4 = st.columns(2)
            schedule["technical_audit"] = sc3.selectbox(
                "Technical Audit", freq_options,
                index=freq_options.index(schedule.get("technical_audit", "monthly")),
                key="sched_tech",
            )
            schedule["backlink_check"] = sc4.selectbox(
                "Backlink Check", freq_options,
                index=freq_options.index(schedule.get("backlink_check", "weekly")),
                key="sched_bl",
            )
            sc5, sc6 = st.columns(2)
            schedule["competitor_analysis"] = sc5.selectbox(
                "Competitor Analysis", freq_options,
                index=freq_options.index(schedule.get("competitor_analysis", "bi-weekly")),
                key="sched_comp",
            )
            schedule["content_suggestions"] = sc6.selectbox(
                "Content Suggestions", freq_options,
                index=freq_options.index(schedule.get("content_suggestions", "weekly")),
                key="sched_content",
            )
            sc7, sc8 = st.columns(2)
            schedule["report_generation"] = sc7.selectbox(
                "Report Generation", freq_options,
                index=freq_options.index(schedule.get("report_generation", "weekly")),
                key="sched_report",
            )
            schedule["local_seo_check"] = sc8.selectbox(
                "Local SEO Check", freq_options,
                index=freq_options.index(schedule.get("local_seo_check", "weekly")),
                key="sched_local",
            )
            if st.form_submit_button("Save Schedule"):
                st.session_state.schedule_config = schedule
                st.success("Schedule configuration saved.")


# ===================================================================
# MAIN APPLICATION ROUTER
# ===================================================================

def main():
    page = _render_sidebar()

    _page_map = {
        "Home": _page_home,
        "Keyword Rankings": _page_keywords,
        "AI Search Visibility": _page_ai_visibility,
        "Local SEO": _page_local_seo,
        "Content Strategy": _page_content,
        "Technical SEO": _page_technical,
        "Backlinks": _page_backlinks,
        "Competitors": _page_competitors,
        "Reports & Alerts": _page_reports,
        "Settings": _page_settings,
    }

    render_fn = _page_map.get(page, _page_home)

    try:
        render_fn()
    except Exception as exc:
        st.error(f"An error occurred while rendering the {page} page.")
        with st.expander("Error Details"):
            st.exception(exc)
        st.info("This may be caused by missing module dependencies or unconfigured API keys. Check the Settings page.")


if __name__ == "__main__":
    main()
