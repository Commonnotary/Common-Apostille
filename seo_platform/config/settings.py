"""
Configuration settings for SEO & AI Monitoring Platform
Common Notary Apostille
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = BASE_DIR / "reports"
LOGS_DIR = BASE_DIR / "logs"

# Create directories if they don't exist
for d in [DATA_DIR, REPORTS_DIR, LOGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Database
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{BASE_DIR / 'data' / 'seo_platform.db'}"
)

# Redis / Celery
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)

# API Keys
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID", "")  # Custom Search Engine ID
GOOGLE_SEARCH_CONSOLE_CREDENTIALS = os.getenv("GOOGLE_SEARCH_CONSOLE_CREDENTIALS", "")
GOOGLE_BUSINESS_PROFILE_CREDENTIALS = os.getenv("GOOGLE_BUSINESS_PROFILE_CREDENTIALS", "")
PAGESPEED_API_KEY = os.getenv("PAGESPEED_API_KEY", "")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

AHREFS_API_KEY = os.getenv("AHREFS_API_KEY", "")
SEMRUSH_API_KEY = os.getenv("SEMRUSH_API_KEY", "")

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")

# Company Information
COMPANY = {
    "name": "Common Notary Apostille",
    "website": "https://commonnotaryapostille.com",
    "phone": os.getenv("COMPANY_PHONE", ""),
    "email": os.getenv("COMPANY_EMAIL", ""),
    "primary_address": {
        "street": os.getenv("COMPANY_STREET", ""),
        "city": "Alexandria",
        "state": "VA",
        "zip": os.getenv("COMPANY_ZIP", ""),
        "country": "US"
    }
}

# Target Service Areas
SERVICE_AREAS = {
    "primary": [
        {"city": "Alexandria", "state": "VA", "region": "Northern Virginia"},
        {"city": "Washington", "state": "DC", "region": "DMV"},
        {"city": "Arlington", "state": "VA", "region": "Northern Virginia"},
        {"city": "Fairfax", "state": "VA", "region": "Northern Virginia"},
        {"city": "Loudoun County", "state": "VA", "region": "Northern Virginia"},
        {"city": "Montgomery County", "state": "MD", "region": "Maryland"},
        {"city": "Prince George's County", "state": "MD", "region": "Maryland"},
    ],
    "secondary": [
        {"city": "Roanoke", "state": "VA", "region": "Southwest Virginia"},
        {"city": "Salem", "state": "VA", "region": "Southwest Virginia"},
        {"city": "Blacksburg", "state": "VA", "region": "Southwest Virginia"},
        {"city": "Christiansburg", "state": "VA", "region": "Southwest Virginia"},
        {"city": "Lynchburg", "state": "VA", "region": "Southwest Virginia"},
    ]
}

# Target Keywords
SERVICE_KEYWORDS = [
    "notary public",
    "mobile notary",
    "apostille services",
    "document authentication",
    "embassy legalization",
    "power of attorney notarization",
    "loan signing agent",
    "real estate closing notary",
    "foreign document notarization",
    "certified translation notarization",
    "notary near me",
    "apostille near me",
    "mobile notary near me",
    "document authentication services",
    "embassy legalization services",
    "Spanish document notarization",
    "international document authentication",
    "hospital notary",
    "nursing home notary",
    "remote online notarization",
]

# Geographic keyword modifiers
GEO_MODIFIERS = [
    "DMV", "DMV area", "DC", "Washington DC",
    "Virginia", "Northern Virginia", "NoVA",
    "Maryland", "Alexandria VA", "Arlington VA",
    "Fairfax VA", "Loudoun VA",
    "Montgomery County MD", "Prince George's County MD",
    "Roanoke VA", "Salem VA", "Blacksburg VA",
    "Christiansburg VA", "Lynchburg VA",
    "Southwest Virginia", "SWVA",
]

# Competitors to track (populate as identified)
COMPETITORS = {
    "dmv": [
        # Add competitor domains/business names for DMV area
    ],
    "swva": [
        # Add competitor domains/business names for SW Virginia
    ]
}

# Scheduling Configuration
SCHEDULE = {
    "keyword_tracking": "weekly",          # Every Monday
    "ai_monitoring": "weekly",             # Every Wednesday
    "technical_audit": "monthly",          # 1st of month
    "backlink_check": "weekly",            # Every Friday
    "competitor_analysis": "bi-weekly",    # Every other Monday
    "content_suggestions": "weekly",       # Every Tuesday
    "report_generation": "weekly",         # Every Sunday
    "local_seo_check": "weekly",           # Every Thursday
}

# Alert Thresholds
ALERTS = {
    "ranking_drop_threshold": 5,       # Alert if rank drops by 5+
    "negative_review_threshold": 3,    # Alert on reviews <= 3 stars
    "page_speed_threshold": 50,        # Alert if score drops below 50
    "uptime_check_interval": 300,      # Check every 5 minutes (seconds)
}

# AI Search Engines to monitor
AI_SEARCH_ENGINES = [
    {
        "name": "ChatGPT",
        "type": "api",
        "api_key_env": "OPENAI_API_KEY"
    },
    {
        "name": "Google AI Overview",
        "type": "serp_scrape",
        "enabled": True
    },
    {
        "name": "Perplexity",
        "type": "web_scrape",
        "url": "https://www.perplexity.ai"
    },
    {
        "name": "Bing Copilot",
        "type": "web_scrape",
        "url": "https://copilot.microsoft.com"
    },
    {
        "name": "Claude",
        "type": "api",
        "api_key_env": "ANTHROPIC_API_KEY"
    }
]

# Report Configuration
REPORT_CONFIG = {
    "email_recipients": os.getenv("REPORT_RECIPIENTS", "").split(","),
    "pdf_output_dir": str(REPORTS_DIR),
    "weekly_report_day": "sunday",
    "monthly_report_day": 1,
}

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = LOGS_DIR / "seo_platform.log"
