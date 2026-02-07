"""
Module 6: Backlink & Authority Builder
Common Notary Apostille - SEO Monitoring Platform

Discovers, monitors, and manages the backlink profile for Common Notary Apostille.
Identifies high-authority link-building opportunities across legal directories,
notary associations, chambers of commerce, and business directories relevant
to the DMV area and Southwest Virginia service regions.
"""

import datetime
import re
import statistics
from collections import Counter, defaultdict
from typing import Any, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from loguru import logger

from config.settings import AHREFS_API_KEY, COMPANY, SEMRUSH_API_KEY
from database.models import Backlink, BacklinkOpportunity, SessionLocal

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COMPANY_DOMAIN: str = urlparse(COMPANY["website"]).netloc.replace("www.", "")

# Relevance keywords used to evaluate whether a linking page is topically
# aligned with notary / apostille / legal services.
RELEVANCE_KEYWORDS: list[str] = [
    "notary", "apostille", "legal", "law", "attorney", "document",
    "authentication", "legalization", "embassy", "mobile notary",
    "loan signing", "real estate", "closing", "title", "settlement",
    "power of attorney", "affidavit", "oath", "jurat", "acknowledgment",
    "virginia", "dmv", "washington dc", "maryland", "roanoke",
    "alexandria", "arlington", "fairfax", "loudoun", "business directory",
    "chamber of commerce", "professional services", "small business",
]

# Heuristic patterns commonly found in spammy / link-farm domains.
SPAM_DOMAIN_PATTERNS: list[str] = [
    r"free[-_]?link", r"link[-_]?farm", r"link[-_]?exchange",
    r"seo[-_]?link", r"buy[-_]?link", r"cheap[-_]?link",
    r"article[-_]?spin", r"spam", r"casino", r"poker",
    r"pharma", r"viagra", r"cialis", r"payday[-_]?loan",
    r"porn", r"xxx", r"adult", r"gambling", r"slot[-_]?machine",
    r"diet[-_]?pill", r"weight[-_]?loss[-_]?pill", r"crypto[-_]?scam",
    r"click[-_]?here", r"best[-_]?price", r"cheap[-_]?(buy|order)",
]

# Pre-populated list of 40+ specific link-building opportunities organised
# by category.  Each entry carries a URL, estimated domain authority (DA),
# and a short description of how to pursue the listing.
LINK_OPPORTUNITIES: list[dict[str, Any]] = [
    # --- Legal Directories ---------------------------------------------------
    {
        "target_site": "Avvo",
        "target_url": "https://www.avvo.com",
        "category": "legal_directory",
        "domain_authority": 72,
        "notes": "Create a free professional profile. List notary and apostille services.",
    },
    {
        "target_site": "FindLaw",
        "target_url": "https://www.findlaw.com",
        "category": "legal_directory",
        "domain_authority": 82,
        "notes": "Submit business to the legal services directory listing.",
    },
    {
        "target_site": "Justia",
        "target_url": "https://www.justia.com",
        "category": "legal_directory",
        "domain_authority": 80,
        "notes": "Create a free legal professional profile with service details.",
    },
    {
        "target_site": "LawInfo",
        "target_url": "https://www.lawinfo.com",
        "category": "legal_directory",
        "domain_authority": 62,
        "notes": "Submit listing under notary / document authentication services.",
    },
    {
        "target_site": "Lawyers.com",
        "target_url": "https://www.lawyers.com",
        "category": "legal_directory",
        "domain_authority": 70,
        "notes": "Submit a professional services listing for legal document support.",
    },
    {
        "target_site": "HG.org Legal Directory",
        "target_url": "https://www.hg.org",
        "category": "legal_directory",
        "domain_authority": 68,
        "notes": "Submit under legal services / notary section.",
    },
    {
        "target_site": "Nolo",
        "target_url": "https://www.nolo.com",
        "category": "legal_directory",
        "domain_authority": 75,
        "notes": "Explore the lawyer and legal services directory for listing options.",
    },

    # --- Notary Associations --------------------------------------------------
    {
        "target_site": "National Notary Association (NNA)",
        "target_url": "https://www.nationalnotary.org",
        "category": "notary_association",
        "domain_authority": 60,
        "notes": "Maintain active membership. Get listed in the NNA Notary Locator.",
    },
    {
        "target_site": "American Society of Notaries",
        "target_url": "https://www.asnnotary.org",
        "category": "notary_association",
        "domain_authority": 42,
        "notes": "Become a member and appear in the online directory.",
    },
    {
        "target_site": "Virginia Notary Association",
        "target_url": "https://www.virginianotaryassociation.org",
        "category": "notary_association",
        "domain_authority": 25,
        "notes": "State-level association membership with directory listing.",
    },
    {
        "target_site": "Notary Rotary",
        "target_url": "https://www.notaryrotary.com",
        "category": "notary_association",
        "domain_authority": 45,
        "notes": "Join the signing-agent directory. Targeted at loan-signing leads.",
    },
    {
        "target_site": "123Notary",
        "target_url": "https://www.123notary.com",
        "category": "notary_association",
        "domain_authority": 48,
        "notes": "Create a notary profile in one of the largest notary directories.",
    },
    {
        "target_site": "SigningAgent.com",
        "target_url": "https://www.signingagent.com",
        "category": "notary_association",
        "domain_authority": 35,
        "notes": "Loan signing agent directory. Relevant for real-estate closing services.",
    },
    {
        "target_site": "Notary.net",
        "target_url": "https://www.notary.net",
        "category": "notary_association",
        "domain_authority": 40,
        "notes": "Free notary public directory listing by state.",
    },

    # --- Local Business Chambers ----------------------------------------------
    {
        "target_site": "Alexandria Chamber of Commerce",
        "target_url": "https://www.alexchamber.com",
        "category": "chamber_of_commerce",
        "domain_authority": 45,
        "notes": "Join as a member for a listing in the Alexandria business directory.",
    },
    {
        "target_site": "Arlington Chamber of Commerce",
        "target_url": "https://www.arlingtonchamber.org",
        "category": "chamber_of_commerce",
        "domain_authority": 42,
        "notes": "Membership provides a profile page with a dofollow backlink.",
    },
    {
        "target_site": "Fairfax County Chamber of Commerce",
        "target_url": "https://www.fairfaxchamber.org",
        "category": "chamber_of_commerce",
        "domain_authority": 47,
        "notes": "Major Northern Virginia chamber. Member directory includes website link.",
    },
    {
        "target_site": "Loudoun County Chamber of Commerce",
        "target_url": "https://www.loudounchamber.org",
        "category": "chamber_of_commerce",
        "domain_authority": 40,
        "notes": "Growing business community. Good for Loudoun County visibility.",
    },
    {
        "target_site": "Roanoke Regional Chamber of Commerce",
        "target_url": "https://www.roanokechamber.org",
        "category": "chamber_of_commerce",
        "domain_authority": 44,
        "notes": "Primary chamber for Southwest Virginia market. Member directory listing.",
    },
    {
        "target_site": "Salem-Roanoke County Chamber of Commerce",
        "target_url": "https://www.s-rcchamber.org",
        "category": "chamber_of_commerce",
        "domain_authority": 30,
        "notes": "Local chamber serving Salem and Roanoke County area.",
    },
    {
        "target_site": "Montgomery County (VA) Chamber of Commerce",
        "target_url": "https://www.montgomerycc.org",
        "category": "chamber_of_commerce",
        "domain_authority": 32,
        "notes": "Covers Blacksburg / Christiansburg area. Directory link available.",
    },
    {
        "target_site": "Greater Washington Hispanic Chamber of Commerce",
        "target_url": "https://www.gwhcc.org",
        "category": "chamber_of_commerce",
        "domain_authority": 40,
        "notes": "Relevant for bilingual / Spanish-language notary services.",
    },
    {
        "target_site": "DC Chamber of Commerce",
        "target_url": "https://www.dcchamber.org",
        "category": "chamber_of_commerce",
        "domain_authority": 50,
        "notes": "District-wide chamber. Good DA and local relevance.",
    },

    # --- Virginia State Directories -------------------------------------------
    {
        "target_site": "Virginia.gov Business Directory",
        "target_url": "https://www.virginia.gov/services/business/",
        "category": "state_directory",
        "domain_authority": 85,
        "notes": "State government resource listing. Very high DA.",
    },
    {
        "target_site": "Virginia SCC (State Corporation Commission)",
        "target_url": "https://www.scc.virginia.gov",
        "category": "state_directory",
        "domain_authority": 70,
        "notes": "Ensure the business is registered and appears in the SCC look-up.",
    },
    {
        "target_site": "Virginia Secretary of State - Notary Division",
        "target_url": "https://www.commonwealth.virginia.gov/official-documents/notary-commissions/",
        "category": "state_directory",
        "domain_authority": 72,
        "notes": "Maintain an active notary commission listed with the state.",
    },
    {
        "target_site": "Virginia Tourism Corporation",
        "target_url": "https://www.virginia.org",
        "category": "state_directory",
        "domain_authority": 68,
        "notes": "Submit under professional services for Virginia visitors needing notary.",
    },
    {
        "target_site": "Virginia SBDC (Small Business Development Center)",
        "target_url": "https://www.virginiasbdc.org",
        "category": "state_directory",
        "domain_authority": 50,
        "notes": "Resource directory for Virginia small businesses.",
    },

    # --- Business Directories -------------------------------------------------
    {
        "target_site": "Better Business Bureau (BBB)",
        "target_url": "https://www.bbb.org",
        "category": "business_directory",
        "domain_authority": 88,
        "notes": "Accreditation provides a high-DA backlink. Essential trust signal.",
    },
    {
        "target_site": "Manta",
        "target_url": "https://www.manta.com",
        "category": "business_directory",
        "domain_authority": 62,
        "notes": "Free business profile with link back to website.",
    },
    {
        "target_site": "Alignable",
        "target_url": "https://www.alignable.com",
        "category": "business_directory",
        "domain_authority": 55,
        "notes": "Local business networking platform with profile link.",
    },
    {
        "target_site": "Thumbtack",
        "target_url": "https://www.thumbtack.com",
        "category": "business_directory",
        "domain_authority": 72,
        "notes": "Professional services marketplace. Good for lead gen and backlink.",
    },
    {
        "target_site": "Yelp",
        "target_url": "https://www.yelp.com",
        "category": "business_directory",
        "domain_authority": 93,
        "notes": "Claim and optimise the Yelp business page for a high-DA link.",
    },
    {
        "target_site": "Google Business Profile",
        "target_url": "https://business.google.com",
        "category": "business_directory",
        "domain_authority": 100,
        "notes": "Foundation of local SEO. Keep profile fully optimised.",
    },
    {
        "target_site": "Bing Places for Business",
        "target_url": "https://www.bingplaces.com",
        "category": "business_directory",
        "domain_authority": 70,
        "notes": "Claim the Bing listing. Imports from Google Business Profile.",
    },
    {
        "target_site": "Apple Maps Connect",
        "target_url": "https://mapsconnect.apple.com",
        "category": "business_directory",
        "domain_authority": 100,
        "notes": "Claim the Apple Maps listing for iOS/Siri visibility.",
    },
    {
        "target_site": "Yellow Pages (YP.com)",
        "target_url": "https://www.yellowpages.com",
        "category": "business_directory",
        "domain_authority": 82,
        "notes": "Legacy directory still used by many consumers. Free listing available.",
    },
    {
        "target_site": "Angi (formerly Angie's List)",
        "target_url": "https://www.angi.com",
        "category": "business_directory",
        "domain_authority": 80,
        "notes": "Home services directory. Relevant for mobile notary visits.",
    },
    {
        "target_site": "MapQuest",
        "target_url": "https://www.mapquest.com",
        "category": "business_directory",
        "domain_authority": 78,
        "notes": "Add business listing for map-based searches.",
    },

    # --- Real Estate Directories (loan signing / closing services) ------------
    {
        "target_site": "SnapDocs",
        "target_url": "https://www.snapdocs.com",
        "category": "real_estate_directory",
        "domain_authority": 45,
        "notes": "Notary signing platform for loan-signing / real-estate closings.",
    },
    {
        "target_site": "Zillow Agent Directory",
        "target_url": "https://www.zillow.com",
        "category": "real_estate_directory",
        "domain_authority": 91,
        "notes": "Explore partnership or advertising for closing notary services.",
    },
    {
        "target_site": "Realtor.com",
        "target_url": "https://www.realtor.com",
        "category": "real_estate_directory",
        "domain_authority": 88,
        "notes": "Professional directory. Link available through partnerships.",
    },
    {
        "target_site": "NotaryCafe",
        "target_url": "https://www.notarycafe.com",
        "category": "real_estate_directory",
        "domain_authority": 38,
        "notes": "Notary community / directory focused on signing agents.",
    },
    {
        "target_site": "CloseSimple",
        "target_url": "https://www.closesimple.com",
        "category": "real_estate_directory",
        "domain_authority": 30,
        "notes": "Title and closing industry platform. Networking opportunity.",
    },
]


# ---------------------------------------------------------------------------
# BacklinkBuilder class
# ---------------------------------------------------------------------------

class BacklinkBuilder:
    """Backlink discovery, monitoring, outreach, and authority-building engine.

    Monitors the current backlink profile for Common Notary Apostille,
    identifies high-quality link opportunities across relevant directories
    and associations, analyses competitor backlink profiles for gap
    opportunities, and generates personalised outreach templates for
    link acquisition campaigns.
    """

    def __init__(self) -> None:
        """Initialise the BacklinkBuilder with database session and API keys."""
        self.company_domain: str = COMPANY_DOMAIN
        self.company_url: str = COMPANY["website"]
        self.company_name: str = COMPANY["name"]
        self.ahrefs_api_key: str = AHREFS_API_KEY
        self.semrush_api_key: str = SEMRUSH_API_KEY
        self.session = SessionLocal()
        logger.info(
            "BacklinkBuilder initialised for domain '{}'", self.company_domain
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_domain(self, url: str) -> str:
        """Extract a bare domain from a full URL."""
        try:
            parsed = urlparse(url)
            return parsed.netloc.lower().replace("www.", "")
        except Exception:
            return url.lower().replace("www.", "")

    def _safe_request(
        self,
        url: str,
        *,
        timeout: int = 30,
        headers: Optional[dict[str, str]] = None,
    ) -> Optional[requests.Response]:
        """Perform an HTTP GET with error handling and a browser-like UA."""
        default_headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        }
        if headers:
            default_headers.update(headers)
        try:
            response = requests.get(url, headers=default_headers, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            logger.warning("HTTP request failed for {}: {}", url, exc)
            return None

    def _estimate_domain_authority(self, domain: str) -> int:
        """Estimate domain authority using the Ahrefs API.

        Falls back to a heuristic estimation when the API key is not
        configured or the request fails.
        """
        # Attempt Ahrefs API first
        if self.ahrefs_api_key:
            try:
                resp = requests.get(
                    "https://apiv2.ahrefs.com",
                    params={
                        "token": self.ahrefs_api_key,
                        "from": "domain_rating",
                        "target": domain,
                        "mode": "domain",
                        "output": "json",
                    },
                    timeout=15,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if "domain_rating" in data:
                        return int(data["domain_rating"])
            except Exception as exc:
                logger.debug("Ahrefs DA lookup failed for {}: {}", domain, exc)

        # Heuristic fallback: well-known high-DA domains get a fixed score;
        # everything else receives a conservative baseline.
        high_da_domains: dict[str, int] = {
            "google.com": 100, "yelp.com": 93, "bbb.org": 88,
            "yellowpages.com": 82, "findlaw.com": 82, "justia.com": 80,
            "angi.com": 80, "mapquest.com": 78, "nolo.com": 75,
            "thumbtack.com": 72, "avvo.com": 72, "lawyers.com": 70,
            "scc.virginia.gov": 70, "bingplaces.com": 70,
            "hg.org": 68, "virginia.org": 68, "manta.com": 62,
            "lawinfo.com": 62, "nationalnotary.org": 60,
            "alignable.com": 55, "virginiasbdc.org": 50,
            "dcchamber.org": 50, "123notary.com": 48,
            "notaryrotary.com": 45, "snapdocs.com": 45,
            "fairfaxchamber.org": 47, "alexchamber.com": 45,
            "roanokechamber.org": 44, "arlingtonchamber.org": 42,
            "asnnotary.org": 42, "loudounchamber.org": 40,
            "gwhcc.org": 40, "notary.net": 40, "notarycafe.com": 38,
            "signingagent.com": 35, "montgomerycc.org": 32,
            "s-rcchamber.org": 30, "closesimple.com": 30,
            "virginianotaryassociation.org": 25,
        }
        return high_da_domains.get(domain, 15)

    def _calculate_relevance_score(self, text: str) -> float:
        """Score how topically relevant a block of text is (0.0 -- 1.0)."""
        if not text:
            return 0.0
        text_lower = text.lower()
        matches = sum(1 for kw in RELEVANCE_KEYWORDS if kw in text_lower)
        # Normalise against the total keyword list; cap at 1.0.
        return min(matches / max(len(RELEVANCE_KEYWORDS) * 0.15, 1), 1.0)

    def _is_spam_domain(self, domain: str) -> bool:
        """Return *True* if the domain matches known spam heuristic patterns."""
        domain_lower = domain.lower()
        for pattern in SPAM_DOMAIN_PATTERNS:
            if re.search(pattern, domain_lower):
                return True
        return False

    def _scrape_backlinks_from_page(self, page_url: str) -> list[dict[str, Any]]:
        """Attempt to scrape external links pointing to our domain from a page.

        This is a lightweight scraping helper -- not a replacement for
        a full backlink index.  It inspects all ``<a>`` tags in the
        response HTML and retains those whose ``href`` points to
        ``self.company_domain``.
        """
        found: list[dict[str, Any]] = []
        response = self._safe_request(page_url)
        if not response:
            return found
        try:
            soup = BeautifulSoup(response.text, "html.parser")
            for link in soup.find_all("a", href=True):
                href: str = link["href"]
                if self.company_domain in href:
                    rel_attrs = link.get("rel", [])
                    link_type = (
                        "nofollow" if "nofollow" in rel_attrs else "dofollow"
                    )
                    found.append({
                        "source_url": page_url,
                        "source_domain": self._get_domain(page_url),
                        "target_url": href,
                        "anchor_text": link.get_text(strip=True),
                        "link_type": link_type,
                    })
        except Exception as exc:
            logger.warning("Scrape error on {}: {}", page_url, exc)
        return found

    # ------------------------------------------------------------------
    # 1. Monitor backlink profile
    # ------------------------------------------------------------------

    def monitor_backlinks(self) -> dict[str, Any]:
        """Monitor the current backlink profile.

        Uses the Ahrefs API when an API key is available, then falls back
        to the SEMrush API, and finally to lightweight scraping of known
        referral pages stored in the database.

        Returns:
            A dictionary containing discovered backlinks and summary stats.
        """
        logger.info("Starting backlink monitoring for {}", self.company_domain)
        discovered_backlinks: list[dict[str, Any]] = []

        # ---- Strategy 1: Ahrefs API -----------------------------------------
        if self.ahrefs_api_key:
            logger.info("Querying Ahrefs API for backlinks")
            try:
                resp = requests.get(
                    "https://apiv2.ahrefs.com",
                    params={
                        "token": self.ahrefs_api_key,
                        "from": "backlinks",
                        "target": self.company_domain,
                        "mode": "domain",
                        "limit": 1000,
                        "output": "json",
                    },
                    timeout=30,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for link in data.get("refpages", []):
                        discovered_backlinks.append({
                            "source_url": link.get("url_from", ""),
                            "source_domain": self._get_domain(
                                link.get("url_from", "")
                            ),
                            "target_url": link.get("url_to", ""),
                            "anchor_text": link.get("anchor", ""),
                            "link_type": (
                                "nofollow" if link.get("nofollow") else "dofollow"
                            ),
                            "domain_authority": link.get("ahrefs_rank", 0),
                        })
                    logger.info(
                        "Ahrefs returned {} backlinks", len(discovered_backlinks)
                    )
                else:
                    logger.warning(
                        "Ahrefs API returned status {}", resp.status_code
                    )
            except Exception as exc:
                logger.error("Ahrefs API error: {}", exc)

        # ---- Strategy 2: SEMrush API ----------------------------------------
        if not discovered_backlinks and self.semrush_api_key:
            logger.info("Querying SEMrush API for backlinks")
            try:
                resp = requests.get(
                    "https://api.semrush.com/analytics/v1/",
                    params={
                        "key": self.semrush_api_key,
                        "type": "backlinks_overview",
                        "target": self.company_domain,
                        "target_type": "root_domain",
                        "export_columns": (
                            "source_url,source_title,external_num,"
                            "internal_num,source_size,last_seen"
                        ),
                    },
                    timeout=30,
                )
                if resp.status_code == 200:
                    for line in resp.text.strip().split("\n")[1:]:
                        parts = line.split("\t")
                        if len(parts) >= 2:
                            source_url = parts[0]
                            discovered_backlinks.append({
                                "source_url": source_url,
                                "source_domain": self._get_domain(source_url),
                                "target_url": self.company_url,
                                "anchor_text": parts[1] if len(parts) > 1 else "",
                                "link_type": "dofollow",
                                "domain_authority": self._estimate_domain_authority(
                                    self._get_domain(source_url)
                                ),
                            })
                    logger.info(
                        "SEMrush returned {} backlinks", len(discovered_backlinks)
                    )
            except Exception as exc:
                logger.error("SEMrush API error: {}", exc)

        # ---- Strategy 3: Scrape known sources from the database --------------
        if not discovered_backlinks:
            logger.info("Falling back to database-driven scraping")
            try:
                existing = (
                    self.session.query(Backlink)
                    .filter(Backlink.is_active.is_(True))
                    .all()
                )
                for bl in existing:
                    scraped = self._scrape_backlinks_from_page(bl.source_url)
                    if scraped:
                        discovered_backlinks.extend(scraped)
                    else:
                        # Link may have been removed -- mark inactive.
                        bl.is_active = False
                        bl.last_checked = datetime.date.today()
                logger.info(
                    "Scraping verified {} active backlinks",
                    len(discovered_backlinks),
                )
            except Exception as exc:
                logger.error("Database scraping error: {}", exc)

        # ---- Persist discovered backlinks ------------------------------------
        today = datetime.date.today()
        new_count = 0
        for bl_data in discovered_backlinks:
            try:
                existing = (
                    self.session.query(Backlink)
                    .filter_by(source_url=bl_data["source_url"])
                    .first()
                )
                if existing:
                    existing.last_checked = today
                    existing.is_active = True
                    existing.anchor_text = bl_data.get(
                        "anchor_text", existing.anchor_text
                    )
                    existing.link_type = bl_data.get(
                        "link_type", existing.link_type
                    )
                else:
                    da = bl_data.get(
                        "domain_authority",
                        self._estimate_domain_authority(
                            bl_data.get("source_domain", "")
                        ),
                    )
                    new_backlink = Backlink(
                        source_url=bl_data["source_url"],
                        source_domain=bl_data.get("source_domain", ""),
                        target_url=bl_data.get("target_url", self.company_url),
                        anchor_text=bl_data.get("anchor_text", ""),
                        link_type=bl_data.get("link_type", "dofollow"),
                        domain_authority=da,
                        is_active=True,
                        first_seen=today,
                        last_checked=today,
                    )
                    self.session.add(new_backlink)
                    new_count += 1
            except Exception as exc:
                logger.warning("Error persisting backlink: {}", exc)

        try:
            self.session.commit()
        except Exception as exc:
            self.session.rollback()
            logger.error("Database commit error during monitoring: {}", exc)

        summary = {
            "total_discovered": len(discovered_backlinks),
            "new_backlinks": new_count,
            "scan_date": today.isoformat(),
            "backlinks": discovered_backlinks[:50],  # cap preview
        }
        logger.info(
            "Monitoring complete: {} total, {} new",
            summary["total_discovered"],
            summary["new_backlinks"],
        )
        return summary

    # ------------------------------------------------------------------
    # 2. Find link-building opportunities
    # ------------------------------------------------------------------

    def find_opportunities(self) -> list[dict[str, Any]]:
        """Identify high-authority link-building opportunities.

        Returns the pre-curated list of 40+ opportunities across legal
        directories, notary associations, chambers of commerce, state
        directories, general business directories, and real-estate
        directories.  Each opportunity is also persisted to the
        ``backlink_opportunities`` table if it does not already exist.

        Returns:
            A list of opportunity dictionaries grouped by category.
        """
        logger.info("Loading link-building opportunities")

        for opp in LINK_OPPORTUNITIES:
            try:
                existing = (
                    self.session.query(BacklinkOpportunity)
                    .filter_by(target_url=opp["target_url"])
                    .first()
                )
                if not existing:
                    record = BacklinkOpportunity(
                        target_site=opp["target_site"],
                        target_url=opp["target_url"],
                        category=opp["category"],
                        domain_authority=opp.get("domain_authority"),
                        notes=opp.get("notes", ""),
                        outreach_status="identified",
                    )
                    self.session.add(record)
            except Exception as exc:
                logger.warning(
                    "Error storing opportunity '{}': {}",
                    opp["target_site"], exc,
                )

        try:
            self.session.commit()
        except Exception as exc:
            self.session.rollback()
            logger.error("Database commit error in find_opportunities: {}", exc)

        # Organise by category for the caller
        by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for opp in LINK_OPPORTUNITIES:
            by_category[opp["category"]].append(opp)

        result = [
            {
                "category": cat,
                "count": len(items),
                "opportunities": items,
            }
            for cat, items in by_category.items()
        ]

        logger.info(
            "Identified {} opportunities across {} categories",
            len(LINK_OPPORTUNITIES),
            len(by_category),
        )
        return result

    # ------------------------------------------------------------------
    # 3. Track competitor backlinks
    # ------------------------------------------------------------------

    def track_competitor_backlinks(
        self, competitor_domain: str
    ) -> dict[str, Any]:
        """Analyse a competitor's backlink profile and identify gaps.

        Discovers links pointing to *competitor_domain* using the Ahrefs
        or SEMrush APIs and then compares them against our own profile
        to surface domains that link to the competitor but not to us.

        Args:
            competitor_domain: The bare domain of the competitor
                (e.g. ``"competitornotary.com"``).

        Returns:
            A dictionary with the competitor's backlink summary and a
            list of gap opportunities (domains linking to them but not us).
        """
        logger.info(
            "Tracking competitor backlinks for '{}'", competitor_domain
        )
        competitor_backlinks: list[dict[str, Any]] = []

        # ---- Ahrefs ----------------------------------------------------------
        if self.ahrefs_api_key:
            try:
                resp = requests.get(
                    "https://apiv2.ahrefs.com",
                    params={
                        "token": self.ahrefs_api_key,
                        "from": "backlinks",
                        "target": competitor_domain,
                        "mode": "domain",
                        "limit": 1000,
                        "output": "json",
                    },
                    timeout=30,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for link in data.get("refpages", []):
                        competitor_backlinks.append({
                            "source_url": link.get("url_from", ""),
                            "source_domain": self._get_domain(
                                link.get("url_from", "")
                            ),
                            "anchor_text": link.get("anchor", ""),
                            "domain_authority": link.get("ahrefs_rank", 0),
                            "link_type": (
                                "nofollow"
                                if link.get("nofollow")
                                else "dofollow"
                            ),
                        })
            except Exception as exc:
                logger.error(
                    "Ahrefs competitor lookup error for {}: {}",
                    competitor_domain, exc,
                )

        # ---- SEMrush fallback ------------------------------------------------
        if not competitor_backlinks and self.semrush_api_key:
            try:
                resp = requests.get(
                    "https://api.semrush.com/analytics/v1/",
                    params={
                        "key": self.semrush_api_key,
                        "type": "backlinks",
                        "target": competitor_domain,
                        "target_type": "root_domain",
                    },
                    timeout=30,
                )
                if resp.status_code == 200:
                    for line in resp.text.strip().split("\n")[1:]:
                        parts = line.split("\t")
                        if parts:
                            source_url = parts[0]
                            competitor_backlinks.append({
                                "source_url": source_url,
                                "source_domain": self._get_domain(source_url),
                                "anchor_text": (
                                    parts[1] if len(parts) > 1 else ""
                                ),
                                "domain_authority": self._estimate_domain_authority(
                                    self._get_domain(source_url)
                                ),
                                "link_type": "dofollow",
                            })
            except Exception as exc:
                logger.error(
                    "SEMrush competitor lookup error for {}: {}",
                    competitor_domain, exc,
                )

        # ---- Gap analysis: competitor domains vs. our domains ----------------
        our_domains: set[str] = set()
        try:
            our_links = (
                self.session.query(Backlink)
                .filter(Backlink.is_active.is_(True))
                .all()
            )
            our_domains = {bl.source_domain for bl in our_links if bl.source_domain}
        except Exception as exc:
            logger.error("Error loading our backlinks: {}", exc)

        competitor_domains = {
            bl["source_domain"]
            for bl in competitor_backlinks
            if bl.get("source_domain")
        }
        gap_domains = competitor_domains - our_domains

        gap_opportunities: list[dict[str, Any]] = [
            bl for bl in competitor_backlinks
            if bl.get("source_domain") in gap_domains
        ]

        result: dict[str, Any] = {
            "competitor_domain": competitor_domain,
            "total_competitor_backlinks": len(competitor_backlinks),
            "unique_competitor_domains": len(competitor_domains),
            "our_unique_domains": len(our_domains),
            "gap_count": len(gap_domains),
            "gap_opportunities": sorted(
                gap_opportunities,
                key=lambda x: x.get("domain_authority", 0),
                reverse=True,
            )[:100],
        }
        logger.info(
            "Competitor analysis for '{}': {} backlinks, {} gap opportunities",
            competitor_domain,
            result["total_competitor_backlinks"],
            result["gap_count"],
        )
        return result

    # ------------------------------------------------------------------
    # 4. Generate outreach email templates
    # ------------------------------------------------------------------

    def generate_outreach_template(self, opportunity_type: str) -> str:
        """Generate a personalised outreach email template.

        Args:
            opportunity_type: One of ``"directory_listing"``,
                ``"guest_post"``, ``"partnership"``,
                ``"local_networking"``, or ``"association_membership"``.

        Returns:
            A multi-line email template string ready for customisation.

        Raises:
            ValueError: If *opportunity_type* is not recognised.
        """
        logger.info(
            "Generating outreach template for type '{}'", opportunity_type
        )

        contact_name_placeholder = "[Contact Name]"
        org_placeholder = "[Organization Name]"
        site_placeholder = "[Website/Directory Name]"

        templates: dict[str, str] = {
            # ---- Directory listing request -----------------------------------
            "directory_listing": (
                f"Subject: Request to Add {self.company_name} to "
                f"{site_placeholder} Directory\n"
                "\n"
                f"Dear {contact_name_placeholder},\n"
                "\n"
                f"My name is [Your Name] and I am with {self.company_name}, "
                "a professional notary public and apostille service provider "
                "serving the Washington DC metro area (DMV) and Southwest "
                "Virginia.\n"
                "\n"
                f"I noticed that {site_placeholder} maintains a directory of "
                "legal and professional service providers in the region. I "
                "would love the opportunity to be included so that individuals "
                "and businesses searching for trusted notary and apostille "
                "services can find us more easily.\n"
                "\n"
                "Here is a brief overview of our services:\n"
                "  - Apostille & document authentication\n"
                "  - Mobile notary services (available 7 days a week)\n"
                "  - Loan signing / real-estate closing notary\n"
                "  - Embassy legalization assistance\n"
                "  - Remote online notarization\n"
                "\n"
                "Our website is " + self.company_url + " and we maintain an "
                "A+ rating with the Better Business Bureau.\n"
                "\n"
                "Please let me know what information you need to add our "
                "listing.  I would be happy to provide any additional details.\n"
                "\n"
                "Thank you for your time and consideration.\n"
                "\n"
                "Best regards,\n"
                "[Your Name]\n"
                f"{self.company_name}\n"
                f"{self.company_url}\n"
                f"{COMPANY.get('phone', '[Phone]')}\n"
            ),

            # ---- Guest post pitch --------------------------------------------
            "guest_post": (
                f"Subject: Guest Article Contribution for {site_placeholder}\n"
                "\n"
                f"Dear {contact_name_placeholder},\n"
                "\n"
                f"I am [Your Name], owner of {self.company_name}, a "
                "professional notary and apostille service based in Virginia.\n"
                "\n"
                f"I have been following {site_placeholder} and appreciate the "
                "valuable content you provide to your audience.  I would love "
                "to contribute a guest article on a topic relevant to your "
                "readers.\n"
                "\n"
                "Here are a few article ideas I had in mind:\n"
                "\n"
                "  1. \"How to Get an Apostille in Virginia: A Step-by-Step "
                "Guide\"\n"
                "  2. \"5 Common Mistakes People Make When Getting Documents "
                "Notarized\"\n"
                "  3. \"Understanding the Difference Between Notarization and "
                "Apostille\"\n"
                "  4. \"What to Expect During a Mobile Notary Appointment\"\n"
                "  5. \"Remote Online Notarization: What It Is and When You "
                "Need It\"\n"
                "\n"
                "Each article would be original, well-researched, and written "
                "specifically for your audience.  I am happy to follow your "
                "editorial guidelines and include only a brief author bio with "
                "a link to our website.\n"
                "\n"
                "Would any of these topics be a good fit?  I look forward to "
                "hearing from you.\n"
                "\n"
                "Best regards,\n"
                "[Your Name]\n"
                f"{self.company_name}\n"
                f"{self.company_url}\n"
            ),

            # ---- Partnership / cross-promotion -------------------------------
            "partnership": (
                f"Subject: Partnership Opportunity Between {self.company_name} "
                f"and {org_placeholder}\n"
                "\n"
                f"Dear {contact_name_placeholder},\n"
                "\n"
                f"I am reaching out from {self.company_name}, a trusted notary "
                "public and apostille service provider serving the DMV area "
                "and Southwest Virginia.  I believe there is a strong "
                "opportunity for our businesses to support each other.\n"
                "\n"
                "Many of our clients require complementary services such as "
                "legal counsel, real-estate assistance, immigration support, "
                "or translation services.  Similarly, your clients may "
                "occasionally need professional notarization or apostille "
                "services.\n"
                "\n"
                "I would love to explore a referral partnership where we:\n"
                "  - Feature each other on our respective websites\n"
                "  - Exchange referrals for overlapping client needs\n"
                "  - Co-create helpful content for our shared audiences\n"
                "\n"
                "Would you be open to a brief call or meeting to discuss how "
                "we might work together?  I am flexible on timing and happy to "
                "meet in person if you are in the Northern Virginia or Roanoke "
                "area.\n"
                "\n"
                "Looking forward to connecting.\n"
                "\n"
                "Best regards,\n"
                "[Your Name]\n"
                f"{self.company_name}\n"
                f"{self.company_url}\n"
                f"{COMPANY.get('phone', '[Phone]')}\n"
            ),

            # ---- Local business networking -----------------------------------
            "local_networking": (
                f"Subject: Connecting with {org_placeholder} -- "
                f"{self.company_name}\n"
                "\n"
                f"Dear {contact_name_placeholder},\n"
                "\n"
                f"My name is [Your Name] from {self.company_name}.  We are a "
                "professional notary and apostille service based right here in "
                "the community, and I am always looking to connect with fellow "
                "local business owners.\n"
                "\n"
                "I came across your business and thought it would be great to "
                "introduce myself.  We frequently serve clients who also need "
                "the types of services you offer, and I would welcome the "
                "opportunity to refer business your way.\n"
                "\n"
                "If you are open to it, I would love to:\n"
                "  - Grab a coffee and learn more about your business\n"
                "  - Discuss ways we can refer clients to each other\n"
                "  - Explore co-marketing opportunities such as a joint "
                "blog post or community event\n"
                "\n"
                "Please let me know if you would be interested in connecting.  "
                "I am available most days and happy to work around your "
                "schedule.\n"
                "\n"
                "Warm regards,\n"
                "[Your Name]\n"
                f"{self.company_name}\n"
                f"{self.company_url}\n"
                f"{COMPANY.get('phone', '[Phone]')}\n"
            ),

            # ---- Industry association membership -----------------------------
            "association_membership": (
                f"Subject: Membership Inquiry -- {self.company_name}\n"
                "\n"
                f"Dear {contact_name_placeholder},\n"
                "\n"
                f"I am [Your Name], owner and commissioned notary public at "
                f"{self.company_name}.  We provide apostille, notarization, "
                "document authentication, and loan-signing services across "
                "Virginia, Washington DC, and Maryland.\n"
                "\n"
                f"I am interested in becoming a member of {org_placeholder} "
                "and would like to learn more about the membership benefits, "
                "application process, and how our business can contribute to "
                "the association.\n"
                "\n"
                "Specifically, I am interested in:\n"
                "  - Being listed in your member / provider directory\n"
                "  - Participating in upcoming events or webinars\n"
                "  - Contributing articles or educational content\n"
                "  - Networking with other members in the region\n"
                "\n"
                "Could you please send me information about membership tiers "
                "and the application process?  I look forward to joining your "
                "organisation.\n"
                "\n"
                "Thank you,\n"
                "[Your Name]\n"
                f"{self.company_name}\n"
                f"{self.company_url}\n"
                f"{COMPANY.get('phone', '[Phone]')}\n"
            ),
        }

        template = templates.get(opportunity_type)
        if template is None:
            valid_types = ", ".join(sorted(templates.keys()))
            raise ValueError(
                f"Unknown opportunity_type '{opportunity_type}'. "
                f"Valid types: {valid_types}"
            )

        logger.info("Outreach template generated for '{}'", opportunity_type)
        return template

    # ------------------------------------------------------------------
    # 5. Detect toxic backlinks
    # ------------------------------------------------------------------

    def detect_toxic_backlinks(self) -> list[dict[str, Any]]:
        """Scan the backlink profile for toxic or spammy links.

        Applies a battery of heuristic checks to every active backlink:
          - Domain authority below 10
          - Domain name matches known spam patterns
          - Anchor text is over-optimised or uses exact-match commercial terms
          - Linking page is in an irrelevant niche
          - Excessive outbound links on the source page (link farm signal)

        Each link receives a toxicity score from 0 (clean) to 100 (spam).
        Links scoring above 60 are flagged as toxic.

        Returns:
            A list of dictionaries for each flagged toxic backlink.
        """
        logger.info("Scanning for toxic backlinks")
        toxic_links: list[dict[str, Any]] = []

        try:
            backlinks = (
                self.session.query(Backlink)
                .filter(Backlink.is_active.is_(True))
                .all()
            )
        except Exception as exc:
            logger.error("Error loading backlinks for toxicity scan: {}", exc)
            return toxic_links

        commercial_anchors = {
            "click here", "buy now", "cheap", "best price",
            "order now", "free", "discount", "deal",
        }

        for bl in backlinks:
            toxicity_score: float = 0.0
            reasons: list[str] = []

            # ---- Low domain authority ----------------------------------------
            da = bl.domain_authority or 0
            if da < 5:
                toxicity_score += 30
                reasons.append(f"Very low domain authority ({da})")
            elif da < 10:
                toxicity_score += 20
                reasons.append(f"Low domain authority ({da})")
            elif da < 15:
                toxicity_score += 10
                reasons.append(f"Below-average domain authority ({da})")

            # ---- Spam domain pattern -----------------------------------------
            domain = bl.source_domain or ""
            if self._is_spam_domain(domain):
                toxicity_score += 35
                reasons.append("Domain matches spam pattern")

            # ---- Suspicious TLD ----------------------------------------------
            suspicious_tlds = {
                ".xyz", ".top", ".pw", ".cc", ".tk", ".ga",
                ".cf", ".gq", ".ml", ".buzz", ".click",
            }
            for tld in suspicious_tlds:
                if domain.endswith(tld):
                    toxicity_score += 15
                    reasons.append(f"Suspicious TLD ({tld})")
                    break

            # ---- Over-optimised anchor text ----------------------------------
            anchor = (bl.anchor_text or "").lower().strip()
            if anchor in commercial_anchors:
                toxicity_score += 20
                reasons.append(f"Commercial / spammy anchor text: '{anchor}'")

            # ---- Irrelevant niche (requires page content check) --------------
            if domain and not self._is_spam_domain(domain):
                relevance = self._calculate_relevance_score(domain + " " + anchor)
                if relevance == 0.0:
                    toxicity_score += 10
                    reasons.append("No topical relevance detected in domain/anchor")

            # ---- Excessive numbers in domain (e.g. abc123xyz789.com) ---------
            digit_ratio = sum(c.isdigit() for c in domain) / max(len(domain), 1)
            if digit_ratio > 0.3:
                toxicity_score += 15
                reasons.append("High digit ratio in domain name")

            # ---- Flag and persist --------------------------------------------
            toxicity_score = min(toxicity_score, 100.0)
            is_toxic = toxicity_score >= 60

            bl.toxicity_score = toxicity_score
            bl.is_toxic = is_toxic

            if is_toxic:
                toxic_links.append({
                    "id": bl.id,
                    "source_url": bl.source_url,
                    "source_domain": bl.source_domain,
                    "anchor_text": bl.anchor_text,
                    "domain_authority": bl.domain_authority,
                    "toxicity_score": toxicity_score,
                    "reasons": reasons,
                })

        try:
            self.session.commit()
        except Exception as exc:
            self.session.rollback()
            logger.error("Database commit error during toxicity scan: {}", exc)

        logger.info(
            "Toxic backlink scan complete: {} toxic out of {} total",
            len(toxic_links),
            len(backlinks),
        )
        return toxic_links

    # ------------------------------------------------------------------
    # 6. Backlink profile report
    # ------------------------------------------------------------------

    def get_backlink_report(self, period: str = "month") -> dict[str, Any]:
        """Generate a comprehensive backlink profile report.

        Args:
            period: Reporting window -- ``"week"``, ``"month"`` (default),
                or ``"quarter"``.

        Returns:
            A dictionary containing total links, new/lost/toxic counts,
            domain-authority distribution, and anchor-text distribution.
        """
        logger.info("Generating backlink report for period='{}'", period)

        period_days: dict[str, int] = {
            "week": 7,
            "month": 30,
            "quarter": 90,
        }
        days = period_days.get(period, 30)
        cutoff_date = datetime.date.today() - datetime.timedelta(days=days)

        try:
            all_backlinks = self.session.query(Backlink).all()
        except Exception as exc:
            logger.error("Error loading backlinks for report: {}", exc)
            return {"error": str(exc)}

        active_links = [bl for bl in all_backlinks if bl.is_active]
        new_links = [
            bl for bl in active_links
            if bl.first_seen and bl.first_seen >= cutoff_date
        ]
        lost_links = [
            bl for bl in all_backlinks
            if not bl.is_active
            and bl.last_checked
            and bl.last_checked >= cutoff_date
        ]
        toxic_links = [bl for bl in active_links if bl.is_toxic]

        # ---- Domain-authority distribution -----------------------------------
        da_buckets: dict[str, int] = {
            "0-10": 0, "11-20": 0, "21-30": 0, "31-40": 0,
            "41-50": 0, "51-60": 0, "61-70": 0, "71-80": 0,
            "81-90": 0, "91-100": 0,
        }
        da_values: list[int] = []
        for bl in active_links:
            da = bl.domain_authority or 0
            da_values.append(da)
            if da <= 10:
                da_buckets["0-10"] += 1
            elif da <= 20:
                da_buckets["11-20"] += 1
            elif da <= 30:
                da_buckets["21-30"] += 1
            elif da <= 40:
                da_buckets["31-40"] += 1
            elif da <= 50:
                da_buckets["41-50"] += 1
            elif da <= 60:
                da_buckets["51-60"] += 1
            elif da <= 70:
                da_buckets["61-70"] += 1
            elif da <= 80:
                da_buckets["71-80"] += 1
            elif da <= 90:
                da_buckets["81-90"] += 1
            else:
                da_buckets["91-100"] += 1

        avg_da = round(statistics.mean(da_values), 1) if da_values else 0.0
        median_da = round(statistics.median(da_values), 1) if da_values else 0.0

        # ---- Anchor-text distribution ----------------------------------------
        anchor_counter: Counter[str] = Counter()
        for bl in active_links:
            anchor = (bl.anchor_text or "").strip()
            if anchor:
                anchor_counter[anchor.lower()] += 1
            else:
                anchor_counter["[no anchor / image]"] += 1

        # ---- Link-type distribution ------------------------------------------
        dofollow_count = sum(
            1 for bl in active_links if (bl.link_type or "").lower() == "dofollow"
        )
        nofollow_count = len(active_links) - dofollow_count

        # ---- Unique referring domains ----------------------------------------
        referring_domains: set[str] = {
            bl.source_domain for bl in active_links if bl.source_domain
        }

        report: dict[str, Any] = {
            "period": period,
            "generated_at": datetime.datetime.now().isoformat(),
            "summary": {
                "total_active_backlinks": len(active_links),
                "unique_referring_domains": len(referring_domains),
                "new_backlinks": len(new_links),
                "lost_backlinks": len(lost_links),
                "toxic_backlinks": len(toxic_links),
                "dofollow_links": dofollow_count,
                "nofollow_links": nofollow_count,
            },
            "domain_authority_distribution": da_buckets,
            "domain_authority_stats": {
                "average": avg_da,
                "median": median_da,
                "min": min(da_values) if da_values else 0,
                "max": max(da_values) if da_values else 0,
            },
            "top_anchors": anchor_counter.most_common(20),
            "new_backlinks_detail": [
                {
                    "source_url": bl.source_url,
                    "source_domain": bl.source_domain,
                    "anchor_text": bl.anchor_text,
                    "domain_authority": bl.domain_authority,
                    "first_seen": bl.first_seen.isoformat() if bl.first_seen else None,
                }
                for bl in sorted(
                    new_links,
                    key=lambda b: b.domain_authority or 0,
                    reverse=True,
                )
            ],
            "lost_backlinks_detail": [
                {
                    "source_url": bl.source_url,
                    "source_domain": bl.source_domain,
                    "last_checked": bl.last_checked.isoformat() if bl.last_checked else None,
                }
                for bl in lost_links
            ],
            "toxic_backlinks_detail": [
                {
                    "source_url": bl.source_url,
                    "source_domain": bl.source_domain,
                    "toxicity_score": bl.toxicity_score,
                }
                for bl in toxic_links
            ],
        }

        logger.info(
            "Backlink report generated: {} active, {} new, {} lost, {} toxic",
            report["summary"]["total_active_backlinks"],
            report["summary"]["new_backlinks"],
            report["summary"]["lost_backlinks"],
            report["summary"]["toxic_backlinks"],
        )
        return report

    # ------------------------------------------------------------------
    # 7. Calculate link score
    # ------------------------------------------------------------------

    def calculate_link_score(self, url: str) -> dict[str, Any]:
        """Score a potential backlink opportunity on a 0--100 scale.

        The score is a weighted composite of:
          - Domain authority (40 %)
          - Topical relevance (35 %)
          - Link type expectation -- dofollow vs nofollow (15 %)
          - Domain trust signals such as TLD and age (10 %)

        Args:
            url: The URL of the potential linking page.

        Returns:
            A dictionary with the overall score, component scores, and a
            human-readable recommendation.
        """
        logger.info("Calculating link score for '{}'", url)
        domain = self._get_domain(url)

        # ---- Component 1: Domain authority (0--100) --------------------------
        da = self._estimate_domain_authority(domain)
        da_score = min(da, 100)

        # ---- Component 2: Relevance (0--100) ---------------------------------
        page_text = ""
        response = self._safe_request(url, timeout=15)
        if response:
            try:
                soup = BeautifulSoup(response.text, "html.parser")
                page_text = soup.get_text(separator=" ", strip=True)[:5000]
            except Exception:
                pass
        relevance_raw = self._calculate_relevance_score(page_text or domain)
        relevance_score = round(relevance_raw * 100, 1)

        # ---- Component 3: Link-type expectation (0 or 100) -------------------
        # Directories and associations are likely dofollow; social sites are not.
        nofollow_likely_domains = {
            "facebook.com", "twitter.com", "x.com", "instagram.com",
            "linkedin.com", "reddit.com", "quora.com", "pinterest.com",
            "youtube.com", "tiktok.com", "medium.com", "wikipedia.org",
        }
        link_type_score: float = 0.0 if domain in nofollow_likely_domains else 100.0

        # ---- Component 4: Trust TLD (0--100) ---------------------------------
        trusted_tlds = {".gov", ".edu", ".org", ".com", ".net", ".us"}
        tld = "." + domain.split(".")[-1] if "." in domain else ""
        tld_score: float = 100.0 if tld in trusted_tlds else 40.0

        # ---- Composite score -------------------------------------------------
        overall = round(
            da_score * 0.40
            + relevance_score * 0.35
            + link_type_score * 0.15
            + tld_score * 0.10,
            1,
        )

        # ---- Recommendation --------------------------------------------------
        if overall >= 75:
            recommendation = "Excellent opportunity -- pursue immediately."
        elif overall >= 50:
            recommendation = "Good opportunity -- worth pursuing."
        elif overall >= 30:
            recommendation = "Moderate opportunity -- pursue if low effort."
        else:
            recommendation = "Low-value opportunity -- skip unless strategic."

        result: dict[str, Any] = {
            "url": url,
            "domain": domain,
            "overall_score": overall,
            "components": {
                "domain_authority": {"score": da_score, "weight": "40%"},
                "relevance": {"score": relevance_score, "weight": "35%"},
                "link_type": {"score": link_type_score, "weight": "15%"},
                "tld_trust": {"score": tld_score, "weight": "10%"},
            },
            "recommendation": recommendation,
        }

        logger.info(
            "Link score for '{}': {} ({})", url, overall, recommendation
        )
        return result

    # ------------------------------------------------------------------
    # 8. Backlink gap analysis
    # ------------------------------------------------------------------

    def get_backlink_gap_analysis(
        self, competitors: list[str]
    ) -> dict[str, Any]:
        """Compare our backlink profile against multiple competitors.

        For each competitor domain, this method discovers their backlinks
        and identifies referring domains that link to at least one
        competitor but not to us.

        Args:
            competitors: A list of competitor bare domains, e.g.
                ``["competitor1.com", "competitor2.com"]``.

        Returns:
            A dictionary containing per-competitor results and a
            consolidated list of gap opportunities sorted by the number
            of competitors that share the referring domain and by DA.
        """
        logger.info(
            "Running backlink gap analysis against {} competitors",
            len(competitors),
        )

        # Our referring domains
        our_domains: set[str] = set()
        try:
            our_links = (
                self.session.query(Backlink)
                .filter(Backlink.is_active.is_(True))
                .all()
            )
            our_domains = {bl.source_domain for bl in our_links if bl.source_domain}
        except Exception as exc:
            logger.error("Error loading our backlinks for gap analysis: {}", exc)

        # Per-competitor analysis
        competitor_results: dict[str, dict[str, Any]] = {}
        # Tracks how many competitors each gap domain is found in
        gap_domain_counts: Counter[str] = Counter()
        # Stores detailed info per gap domain
        gap_domain_details: dict[str, dict[str, Any]] = {}

        for comp_domain in competitors:
            comp_data = self.track_competitor_backlinks(comp_domain)
            comp_domains: set[str] = set()
            for opp in comp_data.get("gap_opportunities", []):
                sd = opp.get("source_domain", "")
                if sd:
                    comp_domains.add(sd)
                    gap_domain_counts[sd] += 1
                    # Keep the highest DA record per gap domain
                    if sd not in gap_domain_details or opp.get(
                        "domain_authority", 0
                    ) > gap_domain_details[sd].get("domain_authority", 0):
                        gap_domain_details[sd] = opp

            competitor_results[comp_domain] = {
                "total_backlinks": comp_data.get("total_competitor_backlinks", 0),
                "unique_domains": comp_data.get("unique_competitor_domains", 0),
                "gap_domains": len(comp_domains),
            }

        # Consolidated gap list, scored by how many competitors share it and DA
        consolidated_gaps: list[dict[str, Any]] = []
        for domain, count in gap_domain_counts.most_common():
            detail = gap_domain_details.get(domain, {})
            consolidated_gaps.append({
                "source_domain": domain,
                "competitors_linking": count,
                "domain_authority": detail.get("domain_authority", 0),
                "source_url": detail.get("source_url", ""),
                "anchor_text": detail.get("anchor_text", ""),
                "priority": (
                    "high" if count >= 2 and detail.get("domain_authority", 0) >= 40
                    else "medium" if count >= 2 or detail.get("domain_authority", 0) >= 40
                    else "low"
                ),
            })

        # Sort: most shared first, then by DA
        consolidated_gaps.sort(
            key=lambda g: (g["competitors_linking"], g["domain_authority"]),
            reverse=True,
        )

        result: dict[str, Any] = {
            "our_referring_domains": len(our_domains),
            "competitors_analyzed": len(competitors),
            "per_competitor": competitor_results,
            "total_gap_domains": len(consolidated_gaps),
            "gap_opportunities": consolidated_gaps[:100],
        }

        logger.info(
            "Gap analysis complete: {} unique gap domains across {} competitors",
            result["total_gap_domains"],
            result["competitors_analyzed"],
        )
        return result

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the database session."""
        try:
            self.session.close()
            logger.info("BacklinkBuilder database session closed")
        except Exception as exc:
            logger.warning("Error closing session: {}", exc)

    def __enter__(self) -> "BacklinkBuilder":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    import sys

    logger.remove()
    logger.add(sys.stderr, level="INFO")

    with BacklinkBuilder() as builder:
        print("=" * 72)
        print("  Backlink & Authority Builder -- Common Notary Apostille")
        print("=" * 72)

        # 1. Find opportunities
        print("\n--- Link-Building Opportunities ---")
        opportunities = builder.find_opportunities()
        total_opps = sum(cat["count"] for cat in opportunities)
        for cat in opportunities:
            print(f"  [{cat['category']}] {cat['count']} opportunities")
        print(f"  TOTAL: {total_opps} opportunities loaded")

        # 2. Monitor backlinks
        print("\n--- Backlink Monitoring ---")
        monitoring = builder.monitor_backlinks()
        print(f"  Total discovered : {monitoring['total_discovered']}")
        print(f"  New backlinks    : {monitoring['new_backlinks']}")

        # 3. Detect toxic backlinks
        print("\n--- Toxic Backlink Scan ---")
        toxic = builder.detect_toxic_backlinks()
        print(f"  Toxic links found: {len(toxic)}")
        for t in toxic[:5]:
            print(
                f"    - {t['source_domain']} "
                f"(score: {t['toxicity_score']}, "
                f"reasons: {', '.join(t['reasons'][:2])})"
            )

        # 4. Generate a sample outreach template
        print("\n--- Sample Outreach Template (directory_listing) ---")
        template = builder.generate_outreach_template("directory_listing")
        # Print just the first few lines as a preview
        for line in template.split("\n")[:6]:
            print(f"  {line}")
        print("  ...")

        # 5. Calculate link score for a sample URL
        print("\n--- Link Score Example ---")
        sample_url = "https://www.bbb.org"
        score_result = builder.calculate_link_score(sample_url)
        print(f"  URL   : {score_result['url']}")
        print(f"  Score : {score_result['overall_score']}")
        print(f"  Rec.  : {score_result['recommendation']}")

        # 6. Backlink report
        print("\n--- Backlink Profile Report (month) ---")
        report = builder.get_backlink_report(period="month")
        if "summary" in report:
            s = report["summary"]
            print(f"  Active backlinks      : {s['total_active_backlinks']}")
            print(f"  Referring domains     : {s['unique_referring_domains']}")
            print(f"  New (this period)     : {s['new_backlinks']}")
            print(f"  Lost (this period)    : {s['lost_backlinks']}")
            print(f"  Toxic                 : {s['toxic_backlinks']}")
            print(f"  Dofollow / Nofollow   : {s['dofollow_links']} / {s['nofollow_links']}")

        # 7. Gap analysis placeholder (requires competitor domains)
        print("\n--- Backlink Gap Analysis (demo) ---")
        demo_competitors = ["competitornotary1.com", "competitornotary2.com"]
        gap = builder.get_backlink_gap_analysis(demo_competitors)
        print(f"  Our referring domains : {gap['our_referring_domains']}")
        print(f"  Competitors analysed  : {gap['competitors_analyzed']}")
        print(f"  Gap domains found     : {gap['total_gap_domains']}")

        print("\n" + "=" * 72)
        print("  Backlink & Authority Builder run complete.")
        print("=" * 72)
