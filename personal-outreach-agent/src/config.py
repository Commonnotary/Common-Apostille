"""Configuration management using environment variables."""

import os
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = Field(
        default="sqlite:///data/outreach.db",
        alias="DATABASE_URL"
    )

    # Scraping Settings
    scrape_delay_seconds: float = Field(
        default=2.0,
        alias="SCRAPE_DELAY_SECONDS"
    )
    max_requests_per_minute: int = Field(
        default=20,
        alias="MAX_REQUESTS_PER_MINUTE"
    )
    user_agent: str = Field(
        default="CommonNotaryApostille-OutreachBot/1.0",
        alias="USER_AGENT"
    )

    # Outreach Settings
    daily_outreach_limit: int = Field(
        default=15,
        alias="DAILY_OUTREACH_LIMIT"
    )
    followup_1_days: int = Field(
        default=4,
        alias="FOLLOWUP_1_DAYS"
    )
    followup_2_days: int = Field(
        default=9,
        alias="FOLLOWUP_2_DAYS"
    )

    # Business Info
    business_name: str = Field(
        default="Common Notary Apostille",
        alias="BUSINESS_NAME"
    )
    business_phone: str = Field(
        default="(202) 555-0100",
        alias="BUSINESS_PHONE"
    )
    business_email: str = Field(
        default="hello@commonnotaryapostille.com",
        alias="BUSINESS_EMAIL"
    )
    business_website: str = Field(
        default="https://commonnotaryapostille.com",
        alias="BUSINESS_WEBSITE"
    )
    contact_name: str = Field(
        default="Common Notary Team",
        alias="CONTACT_NAME"
    )

    # Optional OpenAI key
    openai_api_key: Optional[str] = Field(
        default=None,
        alias="OPENAI_API_KEY"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)


def get_settings() -> Settings:
    """Get application settings."""
    return Settings()


# Target regions for outreach
REGIONS = {
    "DC": {
        "name": "Washington, DC",
        "cities": ["Washington", "DC"],
        "priority": 1
    },
    "NoVA": {
        "name": "Northern Virginia",
        "cities": ["Alexandria", "Arlington", "Fairfax", "Falls Church", "McLean", "Vienna", "Tysons"],
        "priority": 1
    },
    "SWVA": {
        "name": "Southwest Virginia",
        "cities": ["Roanoke", "Christiansburg", "Blacksburg", "Salem", "Radford"],
        "priority": 2
    }
}


# Practice area keywords for segmentation
PRACTICE_AREA_KEYWORDS = {
    "estate_planning": [
        "estate planning", "estate plan", "wills", "trusts", "living trust",
        "revocable trust", "irrevocable trust", "power of attorney", "poa",
        "healthcare directive", "advance directive", "estate attorney"
    ],
    "probate": [
        "probate", "estate administration", "estate settlement", "probate court",
        "executor", "personal representative", "intestate", "testate"
    ],
    "elder_law": [
        "elder law", "elder care", "medicaid planning", "long-term care",
        "nursing home", "guardianship", "conservatorship", "senior"
    ],
    "family": [
        "family law", "divorce", "custody", "adoption", "prenuptial",
        "postnuptial", "domestic relations", "child support"
    ]
}


# Core services (from requirements)
CORE_SERVICES = {
    "notarization": {
        "name": "Mobile Notarization for Estate Documents",
        "description": "POA, trusts, estate planning execution support (homes, hospitals, care facilities, workplaces)",
        "short": "mobile notarization for estate documents"
    },
    "apostille": {
        "name": "Apostille Facilitation",
        "description": "Northern VA + Southwest VA + Federal documents",
        "short": "apostille facilitation for VA and federal documents"
    },
    "loan_signing": {
        "name": "Loan Signing",
        "description": "Loan signing agent services (available on request)",
        "short": "loan signing",
        "mention_only_if_asked": True
    }
}
