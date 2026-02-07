"""
Utility helpers for the SEO & AI Monitoring Platform.
"""

import re
import time
import hashlib
import datetime
from urllib.parse import urlparse, urljoin
from typing import Optional
from functools import wraps

import requests
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import COMPANY, SERVICE_AREAS, SERVICE_KEYWORDS, GEO_MODIFIERS


def get_all_keyword_combinations() -> list[dict]:
    """Generate all keyword + geo modifier combinations to track."""
    combinations = []

    for keyword in SERVICE_KEYWORDS:
        # Base keyword without geo modifier
        combinations.append({
            "keyword": keyword,
            "service_type": keyword,
            "geo_modifier": None,
            "priority": "medium"
        })

        # With geo modifiers
        for geo in GEO_MODIFIERS:
            full_keyword = f"{keyword} {geo}"
            priority = "high" if geo in [
                "Alexandria VA", "DMV", "Washington DC", "Northern Virginia"
            ] else "medium"

            combinations.append({
                "keyword": full_keyword,
                "service_type": keyword,
                "geo_modifier": geo,
                "priority": priority
            })

    # Add special high-intent keywords
    special_keywords = [
        "notary near me",
        "apostille near me",
        "mobile notary near me",
        "24 hour notary near me",
        "emergency notary near me",
        "notary open now near me",
        "best notary in Alexandria VA",
        "best apostille service in Virginia",
        "how to get an apostille in Virginia",
        "how to get an apostille in DC",
        "how to get an apostille in Maryland",
        "apostille for foreign documents Virginia",
        "Spanish notary near me",
        "bilingual notary DMV",
        "hospital notary Alexandria VA",
        "real estate closing notary Northern Virginia",
        "loan signing agent DMV area",
    ]

    for kw in special_keywords:
        combinations.append({
            "keyword": kw,
            "service_type": "special",
            "geo_modifier": None,
            "priority": "high"
        })

    return combinations


def get_all_service_areas() -> list[dict]:
    """Get all service areas as flat list."""
    all_areas = []
    for tier, areas in SERVICE_AREAS.items():
        for area in areas:
            area["tier"] = tier
            all_areas.append(area)
    return all_areas


def normalize_url(url: str) -> str:
    """Normalize a URL for comparison."""
    parsed = urlparse(url.lower().strip())
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def extract_domain(url: str) -> str:
    """Extract the domain from a URL."""
    parsed = urlparse(url)
    return parsed.netloc.lower().replace("www.", "")


def calculate_nap_consistency(
    expected_name: str,
    expected_address: str,
    expected_phone: str,
    found_name: str,
    found_address: str,
    found_phone: str
) -> dict:
    """Check NAP (Name, Address, Phone) consistency."""
    issues = []

    # Normalize for comparison
    def normalize(s):
        return re.sub(r'[^\w\s]', '', s.lower().strip()) if s else ""

    name_match = normalize(expected_name) == normalize(found_name)
    address_match = normalize(expected_address) in normalize(found_address) or normalize(found_address) in normalize(expected_address)
    phone_match = re.sub(r'\D', '', expected_phone) == re.sub(r'\D', '', found_phone) if expected_phone and found_phone else False

    if not name_match:
        issues.append(f"Name mismatch: expected '{expected_name}', found '{found_name}'")
    if not address_match:
        issues.append(f"Address mismatch: expected '{expected_address}', found '{found_address}'")
    if not phone_match:
        issues.append(f"Phone mismatch: expected '{expected_phone}', found '{found_phone}'")

    return {
        "consistent": len(issues) == 0,
        "name_match": name_match,
        "address_match": address_match,
        "phone_match": phone_match,
        "issues": issues,
        "score": sum([name_match, address_match, phone_match]) / 3 * 100
    }


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def fetch_url(url: str, timeout: int = 30, headers: Optional[dict] = None) -> requests.Response:
    """Fetch a URL with retry logic."""
    default_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    if headers:
        default_headers.update(headers)

    response = requests.get(url, headers=default_headers, timeout=timeout)
    response.raise_for_status()
    return response


def compute_seo_score(page_data: dict) -> float:
    """Compute an SEO score for a page based on various factors."""
    score = 0
    max_score = 0

    checks = [
        ("has_title", 10, bool(page_data.get("page_title"))),
        ("title_length", 10, 30 <= len(page_data.get("page_title", "")) <= 60),
        ("has_meta_desc", 10, bool(page_data.get("meta_description"))),
        ("meta_desc_length", 10, 120 <= len(page_data.get("meta_description", "")) <= 160),
        ("has_h1", 10, bool(page_data.get("h1_tags"))),
        ("single_h1", 5, len(page_data.get("h1_tags", [])) == 1),
        ("has_h2", 5, bool(page_data.get("h2_tags"))),
        ("word_count_ok", 10, (page_data.get("word_count", 0) or 0) >= 300),
        ("has_images_alt", 10, page_data.get("images_without_alt", 1) == 0),
        ("has_internal_links", 10, (page_data.get("internal_links", 0) or 0) >= 3),
        ("mobile_friendly", 10, page_data.get("mobile_friendly", False)),
        ("ssl_valid", 10, page_data.get("ssl_valid", False)),
    ]

    for name, points, passed in checks:
        max_score += points
        if passed:
            score += points

    return round(score / max_score * 100, 1) if max_score > 0 else 0


def generate_schema_markup(schema_type: str, area: Optional[dict] = None) -> dict:
    """Generate JSON-LD schema markup for the business."""
    company = COMPANY

    if schema_type == "LocalBusiness":
        schema = {
            "@context": "https://schema.org",
            "@type": "LocalBusiness",
            "name": company["name"],
            "url": company["website"],
            "telephone": company["phone"],
            "email": company["email"],
            "address": {
                "@type": "PostalAddress",
                "streetAddress": company["primary_address"]["street"],
                "addressLocality": area["city"] if area else company["primary_address"]["city"],
                "addressRegion": area["state"] if area else company["primary_address"]["state"],
                "postalCode": company["primary_address"]["zip"],
                "addressCountry": "US"
            },
            "priceRange": "$$",
            "openingHoursSpecification": [
                {
                    "@type": "OpeningHoursSpecification",
                    "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
                    "opens": "09:00",
                    "closes": "18:00"
                },
                {
                    "@type": "OpeningHoursSpecification",
                    "dayOfWeek": "Saturday",
                    "opens": "10:00",
                    "closes": "14:00"
                }
            ],
            "sameAs": []
        }

    elif schema_type == "NotaryService":
        schema = {
            "@context": "https://schema.org",
            "@type": "ProfessionalService",
            "name": company["name"],
            "description": "Professional notary public and apostille services serving the DMV area, Roanoke, and Southwest Virginia. Mobile notary, document authentication, embassy legalization, and more.",
            "url": company["website"],
            "telephone": company["phone"],
            "areaServed": [
                {"@type": "City", "name": a["city"], "containedInPlace": {"@type": "State", "name": a["state"]}}
                for a in get_all_service_areas()
            ],
            "hasOfferCatalog": {
                "@type": "OfferCatalog",
                "name": "Notary & Apostille Services",
                "itemListElement": [
                    {"@type": "Offer", "itemOffered": {"@type": "Service", "name": "Apostille Services"}},
                    {"@type": "Offer", "itemOffered": {"@type": "Service", "name": "Mobile Notary"}},
                    {"@type": "Offer", "itemOffered": {"@type": "Service", "name": "Document Authentication"}},
                    {"@type": "Offer", "itemOffered": {"@type": "Service", "name": "Embassy Legalization"}},
                    {"@type": "Offer", "itemOffered": {"@type": "Service", "name": "Power of Attorney Notarization"}},
                    {"@type": "Offer", "itemOffered": {"@type": "Service", "name": "Loan Signing Agent Services"}},
                    {"@type": "Offer", "itemOffered": {"@type": "Service", "name": "Real Estate Closing Notary"}},
                    {"@type": "Offer", "itemOffered": {"@type": "Service", "name": "Foreign Document Notarization"}},
                    {"@type": "Offer", "itemOffered": {"@type": "Service", "name": "Certified Translation Notarization"}},
                ]
            },
            "address": {
                "@type": "PostalAddress",
                "addressLocality": company["primary_address"]["city"],
                "addressRegion": company["primary_address"]["state"],
                "addressCountry": "US"
            }
        }

    elif schema_type == "FAQPage":
        schema = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": []
        }

    else:
        schema = {
            "@context": "https://schema.org",
            "@type": schema_type,
            "name": company["name"],
            "url": company["website"]
        }

    return schema


def format_ranking_change(current: int, previous: int) -> str:
    """Format a ranking change for display."""
    if previous is None or current is None:
        return "NEW" if current else "N/A"
    diff = previous - current  # positive means improved
    if diff > 0:
        return f"▲{diff}"
    elif diff < 0:
        return f"▼{abs(diff)}"
    return "—"


def get_date_range(period: str = "week") -> tuple:
    """Get start and end dates for a reporting period."""
    today = datetime.date.today()
    if period == "week":
        start = today - datetime.timedelta(days=7)
    elif period == "month":
        start = today - datetime.timedelta(days=30)
    elif period == "quarter":
        start = today - datetime.timedelta(days=90)
    else:
        start = today - datetime.timedelta(days=7)
    return start, today
