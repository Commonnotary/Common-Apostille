"""Lead finder service for discovering attorney leads from public sources."""

import asyncio
import re
import json
from typing import List, Dict, Optional, Any
from urllib.parse import urljoin, urlparse, quote_plus
import logging
from dataclasses import dataclass, field

import httpx
from bs4 import BeautifulSoup

from ..config import get_settings, REGIONS, PRACTICE_AREA_KEYWORDS
from ..models.lead import Lead, Segment, Region, LeadStatus
from ..utils.rate_limiter import get_rate_limiter
from ..utils.robots_checker import get_robots_checker
from ..utils.deduplicator import LeadDeduplicator

logger = logging.getLogger(__name__)


@dataclass
class ScrapedLead:
    """Intermediate representation of a scraped lead before database insertion."""
    firm_name: str
    attorney_name: Optional[str] = None
    attorney_title: Optional[str] = None
    attorney_email: Optional[str] = None
    attorney_phone: Optional[str] = None
    practice_areas: List[str] = field(default_factory=list)
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    website: Optional[str] = None
    source_url: str = ""
    source_name: str = ""
    confidence_score: float = 0.5
    raw_data: Dict[str, Any] = field(default_factory=dict)


class LeadFinder:
    """
    Service for finding attorney leads from public sources.

    Supports:
    - Manual entry (for data from directories that require human lookup)
    - Website scraping (for firms' own websites)
    - CSV/JSON import

    Note: This MVP does NOT automatically scrape State Bar directories or
    Google Maps APIs, as those typically require authentication or have
    strict terms of service. Instead, it provides tools to organize and
    process manually-gathered data.
    """

    def __init__(self, session=None):
        self.settings = get_settings()
        self.rate_limiter = get_rate_limiter()
        self.robots_checker = get_robots_checker()
        self.session = session

    async def _fetch_url(self, url: str) -> Optional[str]:
        """Fetch URL content with rate limiting and robots.txt compliance."""
        # Check robots.txt first
        if not self.robots_checker.can_fetch_sync(url):
            logger.warning(f"robots.txt disallows fetching: {url}")
            return None

        # Apply rate limiting
        self.rate_limiter.sync_acquire(url)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    timeout=30.0,
                    follow_redirects=True,
                    headers={
                        "User-Agent": self.settings.user_agent,
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Accept-Language": "en-US,en;q=0.5",
                    }
                )
                response.raise_for_status()
                return response.text
        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP error fetching {url}: {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    def _fetch_url_sync(self, url: str) -> Optional[str]:
        """Synchronous version of _fetch_url."""
        if not self.robots_checker.can_fetch_sync(url):
            logger.warning(f"robots.txt disallows fetching: {url}")
            return None

        self.rate_limiter.sync_acquire(url)

        try:
            with httpx.Client() as client:
                response = client.get(
                    url,
                    timeout=30.0,
                    follow_redirects=True,
                    headers={
                        "User-Agent": self.settings.user_agent,
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Accept-Language": "en-US,en;q=0.5",
                    }
                )
                response.raise_for_status()
                return response.text
        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP error fetching {url}: {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    def _extract_emails(self, text: str) -> List[str]:
        """Extract email addresses from text."""
        # Email regex pattern
        pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        emails = re.findall(pattern, text)
        # Filter out common false positives
        filtered = [
            e for e in emails
            if not any(x in e.lower() for x in ['example.com', 'domain.com', '@2x', '.png', '.jpg'])
        ]
        return list(set(filtered))

    def _extract_phones(self, text: str) -> List[str]:
        """Extract phone numbers from text."""
        # US phone patterns
        patterns = [
            r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
            r'\d{3}[-.\s]\d{3}[-.\s]\d{4}',
        ]
        phones = []
        for pattern in patterns:
            phones.extend(re.findall(pattern, text))
        return list(set(phones))

    def _detect_region(self, city: str, state: str = None, address: str = None) -> Region:
        """Detect region based on location info."""
        search_text = f"{city or ''} {state or ''} {address or ''}".lower()

        for region_code, region_info in REGIONS.items():
            for region_city in region_info["cities"]:
                if region_city.lower() in search_text:
                    return Region(region_code)

        # Check state
        if state:
            state_lower = state.lower()
            if state_lower in ['dc', 'district of columbia', 'washington dc']:
                return Region.DC
            elif state_lower in ['va', 'virginia']:
                # Need to determine NoVA vs SWVA based on city
                for city_name in REGIONS["NoVA"]["cities"]:
                    if city_name.lower() in search_text:
                        return Region.NOVA
                for city_name in REGIONS["SWVA"]["cities"]:
                    if city_name.lower() in search_text:
                        return Region.SWVA

        return Region.OTHER

    def scrape_firm_website(self, url: str) -> Optional[ScrapedLead]:
        """
        Scrape basic information from a law firm's website.

        This is a best-effort extraction and may not work for all sites.
        Returns partial data that should be reviewed/completed manually.
        """
        html = self._fetch_url_sync(url)
        if not html:
            return None

        soup = BeautifulSoup(html, 'lxml')

        # Try to extract firm name from title or header
        firm_name = None
        if soup.title:
            firm_name = soup.title.string
        if not firm_name:
            h1 = soup.find('h1')
            if h1:
                firm_name = h1.get_text(strip=True)

        if not firm_name:
            # Use domain as fallback
            parsed = urlparse(url)
            firm_name = parsed.netloc.replace('www.', '').split('.')[0].title()

        # Get page text for extraction
        page_text = soup.get_text(separator=' ', strip=True)

        # Extract contact info
        emails = self._extract_emails(page_text)
        phones = self._extract_phones(page_text)

        # Try to find address
        address = None
        address_patterns = [
            r'\d+\s+[\w\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Way|Court|Ct)[,.\s]+[\w\s]+,?\s*(?:VA|DC|Virginia|District of Columbia)\s*\d{5}',
        ]
        for pattern in address_patterns:
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                address = match.group(0)
                break

        # Detect practice areas from page content
        practice_areas = []
        page_lower = page_text.lower()
        for area, keywords in PRACTICE_AREA_KEYWORDS.items():
            for keyword in keywords:
                if keyword in page_lower:
                    # Map to display name
                    area_display = area.replace('_', ' ').title()
                    if area_display not in practice_areas:
                        practice_areas.append(area_display)
                    break

        return ScrapedLead(
            firm_name=firm_name[:255] if firm_name else "Unknown Firm",
            attorney_email=emails[0] if emails else None,
            attorney_phone=phones[0] if phones else None,
            practice_areas=practice_areas,
            address=address,
            website=url,
            source_url=url,
            source_name="website_scrape",
            confidence_score=0.4,  # Low confidence for automated scraping
            raw_data={"all_emails": emails, "all_phones": phones}
        )

    def create_lead_from_scraped(self, scraped: ScrapedLead) -> Lead:
        """Convert a ScrapedLead to a Lead database object."""
        # Detect region
        region = self._detect_region(scraped.city, scraped.state, scraped.address)

        lead = Lead(
            firm_name=scraped.firm_name,
            firm_website=scraped.website,
            attorney_name=scraped.attorney_name,
            attorney_title=scraped.attorney_title,
            attorney_email=scraped.attorney_email,
            attorney_phone=scraped.attorney_phone,
            practice_areas=', '.join(scraped.practice_areas) if scraped.practice_areas else None,
            address=scraped.address,
            city=scraped.city,
            state=scraped.state,
            zip_code=scraped.zip_code,
            region=region,
            source_url=scraped.source_url,
            source_name=scraped.source_name,
            confidence_score=scraped.confidence_score,
            status=LeadStatus.NEW
        )
        return lead

    def create_lead_manual(
        self,
        firm_name: str,
        attorney_name: Optional[str] = None,
        attorney_email: Optional[str] = None,
        attorney_phone: Optional[str] = None,
        practice_areas: Optional[List[str]] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
        website: Optional[str] = None,
        source_url: Optional[str] = None,
        source_name: str = "manual_entry",
        notes: Optional[str] = None
    ) -> Lead:
        """Create a lead from manually entered data."""
        region = self._detect_region(city, state)

        lead = Lead(
            firm_name=firm_name,
            firm_website=website,
            attorney_name=attorney_name,
            attorney_email=attorney_email,
            attorney_phone=attorney_phone,
            practice_areas=', '.join(practice_areas) if practice_areas else None,
            city=city,
            state=state,
            region=region,
            source_url=source_url,
            source_name=source_name,
            confidence_score=0.9,  # High confidence for manual entry
            notes=notes,
            status=LeadStatus.NEW
        )
        return lead

    def import_from_json(self, json_data: List[Dict]) -> List[Lead]:
        """Import leads from JSON data."""
        leads = []
        for item in json_data:
            lead = self.create_lead_manual(
                firm_name=item.get('firm_name', 'Unknown'),
                attorney_name=item.get('attorney_name'),
                attorney_email=item.get('email') or item.get('attorney_email'),
                attorney_phone=item.get('phone') or item.get('attorney_phone'),
                practice_areas=item.get('practice_areas', []),
                city=item.get('city'),
                state=item.get('state'),
                website=item.get('website') or item.get('firm_website'),
                source_url=item.get('source_url'),
                source_name=item.get('source_name', 'json_import'),
                notes=item.get('notes')
            )
            leads.append(lead)
        return leads

    def import_from_csv_rows(self, rows: List[Dict]) -> List[Lead]:
        """Import leads from CSV row dictionaries."""
        # Same as JSON, just different expected source
        leads = []
        for row in rows:
            lead = self.create_lead_manual(
                firm_name=row.get('firm_name') or row.get('Firm Name') or 'Unknown',
                attorney_name=row.get('attorney_name') or row.get('Attorney Name'),
                attorney_email=row.get('email') or row.get('Email') or row.get('attorney_email'),
                attorney_phone=row.get('phone') or row.get('Phone') or row.get('attorney_phone'),
                practice_areas=(row.get('practice_areas') or row.get('Practice Areas') or '').split(','),
                city=row.get('city') or row.get('City'),
                state=row.get('state') or row.get('State'),
                website=row.get('website') or row.get('Website'),
                source_url=row.get('source_url') or row.get('Source URL'),
                source_name='csv_import',
                notes=row.get('notes') or row.get('Notes')
            )
            leads.append(lead)
        return leads


# Sample data generator for demo purposes
def generate_sample_leads() -> List[Dict]:
    """
    Generate sample lead data for demonstration.

    In production, this data would come from:
    - DC Bar directory (manual lookup)
    - Virginia State Bar directory (manual lookup)
    - Google Maps business listings (manual lookup)
    - LinkedIn (manual lookup)
    - Law firm websites (can be scraped)
    - Referrals

    These are fictional examples for demonstration only.
    """
    return [
        {
            "firm_name": "Potomac Estate Planning Group",
            "attorney_name": "Jennifer Martinez",
            "email": "jmartinez@potomacestate.example.com",
            "phone": "(202) 555-0101",
            "practice_areas": ["Estate Planning", "Trusts", "Wills"],
            "city": "Washington",
            "state": "DC",
            "website": "https://potomacestate.example.com",
            "source_name": "DC Bar Directory",
            "source_url": "https://dcbar.org/directory/example",
            "notes": "Specializes in high-net-worth estate planning"
        },
        {
            "firm_name": "Arlington Elder Law Associates",
            "attorney_name": "Robert Chen",
            "email": "rchen@arlingtonelderlaw.example.com",
            "phone": "(703) 555-0102",
            "practice_areas": ["Elder Law", "Medicaid Planning", "Estate Planning"],
            "city": "Arlington",
            "state": "VA",
            "website": "https://arlingtonelderlaw.example.com",
            "source_name": "Virginia State Bar",
            "source_url": "https://vsb.org/directory/example",
            "notes": "Focus on senior care and Medicaid"
        },
        {
            "firm_name": "Old Town Legal Services",
            "attorney_name": "Sarah Williams",
            "email": "swilliams@oldtownlegal.example.com",
            "phone": "(703) 555-0103",
            "practice_areas": ["Probate", "Estate Administration", "Wills"],
            "city": "Alexandria",
            "state": "VA",
            "website": "https://oldtownlegal.example.com",
            "source_name": "Google Maps",
            "notes": "Downtown Alexandria office, handles probate"
        },
        {
            "firm_name": "Fairfax Family Law Center",
            "attorney_name": "Michael Thompson",
            "email": "mthompson@fairfaxfamilylaw.example.com",
            "phone": "(703) 555-0104",
            "practice_areas": ["Family Law", "Divorce", "Child Custody", "Estate Planning"],
            "city": "Fairfax",
            "state": "VA",
            "website": "https://fairfaxfamilylaw.example.com",
            "source_name": "Referral",
            "notes": "Also does estate planning for families"
        },
        {
            "firm_name": "Capitol Hill Estate Attorneys",
            "attorney_name": "Amanda Foster",
            "email": "afoster@capitolhillestate.example.com",
            "phone": "(202) 555-0105",
            "practice_areas": ["Estate Planning", "Trusts", "Tax Planning"],
            "city": "Washington",
            "state": "DC",
            "website": "https://capitolhillestate.example.com",
            "source_name": "DC Bar Directory",
            "notes": "Near Capitol Hill, works with congressional staff"
        },
        {
            "firm_name": "Roanoke Valley Legal Group",
            "attorney_name": "David Morrison",
            "email": "dmorrison@roanokevalleylegal.example.com",
            "phone": "(540) 555-0106",
            "practice_areas": ["Elder Law", "Probate", "Estate Planning"],
            "city": "Roanoke",
            "state": "VA",
            "website": "https://roanokevalleylegal.example.com",
            "source_name": "Virginia State Bar",
            "notes": "Serves Roanoke Valley area"
        },
        {
            "firm_name": "New River Estate Planning",
            "attorney_name": "Lisa Nguyen",
            "email": "lnguyen@newriverestate.example.com",
            "phone": "(540) 555-0107",
            "practice_areas": ["Estate Planning", "Wills", "Power of Attorney"],
            "city": "Blacksburg",
            "state": "VA",
            "website": "https://newriverestate.example.com",
            "source_name": "Google Maps",
            "notes": "Near Virginia Tech campus"
        },
        {
            "firm_name": "McLean Wealth & Estate Law",
            "attorney_name": "Christopher Park",
            "email": "cpark@mcleanwealthlaw.example.com",
            "phone": "(703) 555-0108",
            "practice_areas": ["Estate Planning", "Asset Protection", "Business Succession"],
            "city": "McLean",
            "state": "VA",
            "website": "https://mcleanwealthlaw.example.com",
            "source_name": "Referral",
            "notes": "High-end clientele, complex estate work"
        },
        {
            "firm_name": "Dupont Circle Legal Partners",
            "attorney_name": "Rachel Green",
            "email": "rgreen@dupontlegal.example.com",
            "phone": "(202) 555-0109",
            "practice_areas": ["Family Law", "Wills", "Trusts"],
            "city": "Washington",
            "state": "DC",
            "website": "https://dupontlegal.example.com",
            "source_name": "DC Bar Directory",
            "notes": "Progressive firm, diverse clientele"
        },
        {
            "firm_name": "Christiansburg Law Office",
            "attorney_name": "James Wilson",
            "email": "jwilson@christiansburglawoffice.example.com",
            "phone": "(540) 555-0110",
            "practice_areas": ["Probate", "Real Estate", "Estate Planning"],
            "city": "Christiansburg",
            "state": "VA",
            "website": "https://christiansburglawoffice.example.com",
            "source_name": "Virginia State Bar",
            "notes": "General practice with estate focus"
        }
    ]
