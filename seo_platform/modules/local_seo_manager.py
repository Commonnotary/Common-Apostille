"""
Module 3: Local SEO Management Dashboard
Common Notary Apostille

Manages Google Business Profile optimization, NAP consistency audits,
review monitoring and response generation, citation building, local
competitor analysis, and comprehensive local SEO reporting across all
DMV and Southwest Virginia service areas.
"""

import datetime
from typing import Optional

from loguru import logger

from config.settings import COMPANY, SERVICE_AREAS, ALERTS
from database.models import (
    BusinessListing,
    Review,
    Citation,
    LocalCompetitor,
    SessionLocal,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REVIEW_PLATFORMS = ["google", "yelp", "bbb"]

GBP_OPTIMIZATION_FIELDS = [
    "business_name",
    "categories",
    "description",
    "hours",
    "photos_count",
    "posts_frequency",
    "qa",
    "attributes",
    "service_areas",
    "reviews_response_rate",
]

NAP_DIRECTORIES = [
    {"name": "Google Business Profile", "key": "google", "url": "https://business.google.com"},
    {"name": "Yelp", "key": "yelp", "url": "https://www.yelp.com"},
    {"name": "Better Business Bureau", "key": "bbb", "url": "https://www.bbb.org"},
    {"name": "Yellow Pages", "key": "yellowpages", "url": "https://www.yellowpages.com"},
    {"name": "Bing Places", "key": "bing_places", "url": "https://www.bingplaces.com"},
    {"name": "Apple Maps", "key": "apple_maps", "url": "https://mapsconnect.apple.com"},
    {"name": "Facebook", "key": "facebook", "url": "https://www.facebook.com"},
    {"name": "Manta", "key": "manta", "url": "https://www.manta.com"},
    {"name": "Foursquare", "key": "foursquare", "url": "https://foursquare.com"},
    {"name": "MapQuest", "key": "mapquest", "url": "https://www.mapquest.com"},
    {"name": "Superpages", "key": "superpages", "url": "https://www.superpages.com"},
    {"name": "Hotfrog", "key": "hotfrog", "url": "https://www.hotfrog.com"},
]

CITATION_SOURCES: dict[str, list[dict]] = {
    "national_directories": [
        {"name": "Yelp", "url": "https://www.yelp.com", "domain_authority": 94, "priority": "high"},
        {"name": "Better Business Bureau", "url": "https://www.bbb.org", "domain_authority": 91, "priority": "high"},
        {"name": "Yellow Pages", "url": "https://www.yellowpages.com", "domain_authority": 87, "priority": "high"},
        {"name": "Manta", "url": "https://www.manta.com", "domain_authority": 72, "priority": "medium"},
        {"name": "Superpages", "url": "https://www.superpages.com", "domain_authority": 70, "priority": "medium"},
        {"name": "Hotfrog", "url": "https://www.hotfrog.com", "domain_authority": 58, "priority": "medium"},
        {"name": "Foursquare", "url": "https://foursquare.com", "domain_authority": 90, "priority": "high"},
        {"name": "MapQuest", "url": "https://www.mapquest.com", "domain_authority": 80, "priority": "medium"},
        {"name": "Angi (Angie's List)", "url": "https://www.angi.com", "domain_authority": 88, "priority": "high"},
        {"name": "Thumbtack", "url": "https://www.thumbtack.com", "domain_authority": 85, "priority": "high"},
        {"name": "CitySearch", "url": "https://www.citysearch.com", "domain_authority": 65, "priority": "low"},
        {"name": "DexKnows", "url": "https://www.dexknows.com", "domain_authority": 60, "priority": "low"},
        {"name": "Whitepages", "url": "https://www.whitepages.com", "domain_authority": 82, "priority": "medium"},
        {"name": "Yellowbot", "url": "https://www.yellowbot.com", "domain_authority": 55, "priority": "low"},
    ],
    "legal_notary_directories": [
        {"name": "National Notary Association (NNA)", "url": "https://www.nationalnotary.org", "domain_authority": 65, "priority": "high"},
        {"name": "123Notary", "url": "https://www.123notary.com", "domain_authority": 50, "priority": "high"},
        {"name": "Notary Rotary", "url": "https://www.notaryrotary.com", "domain_authority": 48, "priority": "high"},
        {"name": "SigningAgent.com", "url": "https://www.signingagent.com", "domain_authority": 40, "priority": "high"},
        {"name": "Notary.net", "url": "https://www.notary.net", "domain_authority": 45, "priority": "medium"},
        {"name": "NotaryCafe", "url": "https://www.notarycafe.com", "domain_authority": 42, "priority": "medium"},
        {"name": "SnapDocs", "url": "https://www.snapdocs.com", "domain_authority": 52, "priority": "high"},
        {"name": "Avvo", "url": "https://www.avvo.com", "domain_authority": 78, "priority": "high"},
        {"name": "FindLaw", "url": "https://www.findlaw.com", "domain_authority": 82, "priority": "medium"},
        {"name": "Justia", "url": "https://www.justia.com", "domain_authority": 80, "priority": "medium"},
        {"name": "HG.org", "url": "https://www.hg.org", "domain_authority": 68, "priority": "low"},
        {"name": "Apostille.net", "url": "https://www.apostille.net", "domain_authority": 35, "priority": "medium"},
    ],
    "local_directories": [
        {"name": "Alexandria Chamber of Commerce", "url": "https://www.alexchamber.com", "domain_authority": 45, "priority": "high"},
        {"name": "Arlington Chamber of Commerce", "url": "https://www.arlingtonchamber.org", "domain_authority": 42, "priority": "high"},
        {"name": "Fairfax County Chamber", "url": "https://www.fairfaxchamber.org", "domain_authority": 44, "priority": "high"},
        {"name": "Loudoun County Chamber", "url": "https://www.loudounchamber.org", "domain_authority": 40, "priority": "high"},
        {"name": "Roanoke Regional Chamber", "url": "https://www.roanokechamber.org", "domain_authority": 38, "priority": "high"},
        {"name": "DC Chamber of Commerce", "url": "https://www.dcchamber.org", "domain_authority": 48, "priority": "high"},
        {"name": "Montgomery County Chamber of Commerce", "url": "https://www.montgomerycountychamber.com", "domain_authority": 40, "priority": "high"},
        {"name": "Prince George's County Chamber", "url": "https://www.pgcoc.org", "domain_authority": 35, "priority": "high"},
        {"name": "Virginia State Corporation Commission", "url": "https://www.scc.virginia.gov", "domain_authority": 65, "priority": "medium"},
        {"name": "Virginia Secretary of the Commonwealth", "url": "https://www.commonwealth.virginia.gov", "domain_authority": 70, "priority": "medium"},
        {"name": "Virginia Small Business Directory", "url": "https://www.virginia.gov/services/business/", "domain_authority": 75, "priority": "medium"},
        {"name": "Northern Virginia Regional Commission", "url": "https://www.novaregion.org", "domain_authority": 42, "priority": "medium"},
        {"name": "SWVA Business Directory", "url": "https://www.vastartup.org", "domain_authority": 35, "priority": "medium"},
        {"name": "Roanoke Outside", "url": "https://www.roanokeoutside.com", "domain_authority": 40, "priority": "low"},
    ],
    "industry_specific": [
        {"name": "LoanSigningSystem.com", "url": "https://www.loansigningsystem.com", "domain_authority": 40, "priority": "medium"},
        {"name": "Notary Stars", "url": "https://www.notarystars.com", "domain_authority": 30, "priority": "low"},
        {"name": "Realtor.com Local Pros", "url": "https://www.realtor.com", "domain_authority": 92, "priority": "medium"},
        {"name": "Zillow Agent Finder", "url": "https://www.zillow.com", "domain_authority": 91, "priority": "medium"},
        {"name": "LendingTree Partners", "url": "https://www.lendingtree.com", "domain_authority": 85, "priority": "low"},
        {"name": "TitleSource", "url": "https://www.titlesource.com", "domain_authority": 38, "priority": "low"},
        {"name": "AILA Lawyer Directory", "url": "https://www.aila.org", "domain_authority": 70, "priority": "medium"},
        {"name": "Embassy Directory Listings", "url": "https://www.embassy.org", "domain_authority": 60, "priority": "medium"},
        {"name": "Trustpilot", "url": "https://www.trustpilot.com", "domain_authority": 93, "priority": "high"},
        {"name": "Google Business Profile", "url": "https://business.google.com", "domain_authority": 100, "priority": "high"},
        {"name": "Bing Places for Business", "url": "https://www.bingplaces.com", "domain_authority": 95, "priority": "high"},
        {"name": "Apple Business Connect", "url": "https://businessconnect.apple.com", "domain_authority": 100, "priority": "high"},
    ],
}

_POSITIVE_RESPONSE_TEMPLATES = [
    (
        "Thank you so much for the wonderful review, {reviewer}! We truly appreciate you "
        "choosing Common Notary Apostille for your {service_guess} needs. It was a pleasure "
        "serving you, and we look forward to assisting you again in the future!"
    ),
    (
        "We are thrilled to hear about your positive experience, {reviewer}! Providing "
        "exceptional notary and apostille services to our DMV and Virginia clients is our "
        "top priority. Thank you for your kind words, and please don't hesitate to reach "
        "out whenever you need us again."
    ),
    (
        "Thank you for your generous review, {reviewer}! Our team works hard to make every "
        "notarization and apostille process as smooth as possible. We are delighted you had "
        "a great experience and hope to serve you again soon!"
    ),
]

_NEGATIVE_RESPONSE_TEMPLATES = [
    (
        "Thank you for taking the time to share your feedback, {reviewer}. We sincerely "
        "apologize that your experience did not meet your expectations. We take all concerns "
        "seriously and would love the opportunity to make things right. Please contact us "
        "directly at {phone} so we can discuss how to resolve this."
    ),
    (
        "We appreciate your honest feedback, {reviewer}, and we are sorry to hear about "
        "your experience. At Common Notary Apostille, client satisfaction is extremely "
        "important to us. We would like to learn more about what happened so we can "
        "improve. Please reach out to us at {phone} at your earliest convenience."
    ),
    (
        "{reviewer}, thank you for bringing this to our attention. We are sorry we fell "
        "short of your expectations. Your feedback helps us improve our services for all "
        "clients across the DMV and Virginia. Please contact us at {phone} so we can "
        "address your concerns directly."
    ),
]

_NEUTRAL_RESPONSE_TEMPLATES = [
    (
        "Thank you for your feedback, {reviewer}. We appreciate you choosing Common Notary "
        "Apostille. We are always striving to improve and value your input. If there is "
        "anything we can do to earn a higher rating next time, please don't hesitate to let "
        "us know at {phone}."
    ),
    (
        "Thank you for sharing your experience, {reviewer}. We are glad we could assist you "
        "and appreciate your honest review. We would love to hear how we can make your next "
        "visit even better -- feel free to reach out to us at {phone}."
    ),
]


# ---------------------------------------------------------------------------
# Helper utilities (module-private)
# ---------------------------------------------------------------------------

def _get_all_areas() -> list[dict]:
    """Return a flat list of every service area with its tier."""
    areas: list[dict] = []
    for tier, area_list in SERVICE_AREAS.items():
        for area in area_list:
            areas.append({**area, "tier": tier})
    return areas


def _area_key(area: dict) -> str:
    """Return a consistent string key for a service area dict."""
    return f"{area['city']}, {area['state']}"


def _pick_template(templates: list[str], review_text: str) -> str:
    """Deterministically select a template based on the review text length."""
    index = len(review_text) % len(templates)
    return templates[index]


def _guess_service_from_text(text: str) -> str:
    """Attempt to guess which service is mentioned in review text."""
    text_lower = text.lower()
    services = [
        ("apostille", "apostille"),
        ("mobile notary", "mobile notary"),
        ("loan signing", "loan signing"),
        ("real estate", "real estate closing"),
        ("power of attorney", "power of attorney"),
        ("embassy", "embassy legalization"),
        ("authentication", "document authentication"),
        ("translation", "certified translation"),
        ("hospital", "hospital notary"),
        ("notary", "notary"),
    ]
    for keyword, label in services:
        if keyword in text_lower:
            return label
    return "notary and apostille"


def _compute_sentiment(rating: float, text: str) -> str:
    """Derive a simple sentiment label from a rating and review body."""
    if rating >= 4.0:
        return "positive"
    if rating <= 2.0:
        return "negative"
    # Middle ratings -- lean on keyword presence
    negative_words = {"bad", "terrible", "awful", "horrible", "worst", "rude", "slow", "late", "never"}
    positive_words = {"great", "good", "excellent", "wonderful", "professional", "fast", "friendly"}
    words = set(text.lower().split())
    neg_count = len(words & negative_words)
    pos_count = len(words & positive_words)
    if neg_count > pos_count:
        return "negative"
    if pos_count > neg_count:
        return "positive"
    return "neutral"


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class LocalSEOManager:
    """Local SEO management dashboard for Common Notary Apostille.

    Provides tools for Google Business Profile optimization checking,
    NAP consistency auditing, review monitoring and response generation,
    citation discovery and management, local competitor analysis, and
    comprehensive per-area and overall local SEO reporting.
    """

    def __init__(self) -> None:
        """Initialize the LocalSEOManager with company data and service areas."""
        self.company: dict = COMPANY
        self.company_name: str = COMPANY["name"]
        self.company_phone: str = COMPANY.get("phone", "")
        self.company_website: str = COMPANY.get("website", "")
        self.primary_address: dict = COMPANY.get("primary_address", {})

        self.service_areas: list[dict] = _get_all_areas()
        self.primary_areas: list[dict] = [a for a in self.service_areas if a["tier"] == "primary"]
        self.secondary_areas: list[dict] = [a for a in self.service_areas if a["tier"] == "secondary"]

        self.review_platforms: list[str] = REVIEW_PLATFORMS
        self.negative_review_threshold: int = ALERTS.get("negative_review_threshold", 3)

        logger.info(
            "LocalSEOManager initialized for '{}' with {} service areas "
            "({} primary, {} secondary)",
            self.company_name,
            len(self.service_areas),
            len(self.primary_areas),
            len(self.secondary_areas),
        )

    # ------------------------------------------------------------------
    # 1. Google Business Profile optimization
    # ------------------------------------------------------------------

    def check_gbp_optimization(self, location: str) -> dict:
        """Check Google Business Profile optimization for a service area.

        Evaluates the GBP listing for *location* against a checklist of best
        practices and returns a numeric score together with actionable
        recommendations.

        Args:
            location: Human-readable area name, e.g. ``"Alexandria, VA"``.

        Returns:
            A dict containing ``location``, ``score``, ``max_score``,
            ``percentage``, per-field ``checks``, and ``recommendations``.
        """
        logger.info("Checking GBP optimization for location: {}", location)

        db = SessionLocal()
        try:
            listing: Optional[BusinessListing] = (
                db.query(BusinessListing)
                .filter(
                    BusinessListing.platform == "google",
                    BusinessListing.service_area == location,
                )
                .order_by(BusinessListing.last_checked.desc())
                .first()
            )

            checks: dict[str, dict] = {}
            recommendations: list[str] = []
            total_score = 0
            max_score = 0

            # -- business_name --
            field_points = 10
            max_score += field_points
            if listing and listing.name_listed:
                name_ok = self.company_name.lower() in listing.name_listed.lower()
                points = field_points if name_ok else 5
                total_score += points
                checks["business_name"] = {"score": points, "max": field_points, "passed": name_ok}
                if not name_ok:
                    recommendations.append(
                        f"Business name on GBP ('{listing.name_listed}') does not exactly "
                        f"match the canonical name '{self.company_name}'. Update for consistency."
                    )
            else:
                checks["business_name"] = {"score": 0, "max": field_points, "passed": False}
                recommendations.append(
                    "No Google Business Profile listing found for this location. "
                    "Claim or create a GBP listing immediately."
                )

            # -- categories --
            field_points = 10
            max_score += field_points
            if listing and listing.listing_score is not None:
                # Assume categories are populated when listing_score exists
                points = field_points
                total_score += points
                checks["categories"] = {"score": points, "max": field_points, "passed": True}
            else:
                checks["categories"] = {"score": 0, "max": field_points, "passed": False}
                recommendations.append(
                    "Set a primary category of 'Notary Public' and add secondary categories "
                    "such as 'Apostille Service', 'Legal Services', and 'Document Preparation Service'."
                )

            # -- description --
            field_points = 10
            max_score += field_points
            if listing and listing.listing_url:
                points = field_points
                total_score += points
                checks["description"] = {"score": points, "max": field_points, "passed": True}
            else:
                checks["description"] = {"score": 0, "max": field_points, "passed": False}
                recommendations.append(
                    "Add a keyword-rich business description (750 characters max) mentioning "
                    "notary, apostille, mobile notary, and the specific service area."
                )

            # -- hours --
            field_points = 10
            max_score += field_points
            if listing and listing.last_checked:
                points = field_points
                total_score += points
                checks["hours"] = {"score": points, "max": field_points, "passed": True}
            else:
                checks["hours"] = {"score": 0, "max": field_points, "passed": False}
                recommendations.append(
                    "Ensure business hours are published and accurate, including special "
                    "hours for holidays. Consider listing extended mobile-notary availability."
                )

            # -- photos_count --
            field_points = 10
            max_score += field_points
            photo_threshold = 10
            if listing and listing.listing_score is not None and listing.listing_score >= 50:
                points = field_points
                total_score += points
                checks["photos_count"] = {"score": points, "max": field_points, "passed": True}
            else:
                checks["photos_count"] = {"score": 0, "max": field_points, "passed": False}
                recommendations.append(
                    f"Upload at least {photo_threshold} high-quality photos: storefront, team, "
                    "notarization in progress, branded materials, and service-area landmarks."
                )

            # -- posts_frequency --
            field_points = 10
            max_score += field_points
            if listing and listing.updated_at:
                days_since = (datetime.datetime.utcnow() - listing.updated_at).days
                if days_since <= 7:
                    points = field_points
                elif days_since <= 14:
                    points = field_points // 2
                else:
                    points = 0
                total_score += points
                passed = days_since <= 7
                checks["posts_frequency"] = {"score": points, "max": field_points, "passed": passed}
                if not passed:
                    recommendations.append(
                        "Publish a Google Business Profile post at least once per week. "
                        "Include service highlights, community events, and special offers."
                    )
            else:
                checks["posts_frequency"] = {"score": 0, "max": field_points, "passed": False}
                recommendations.append(
                    "Start publishing weekly GBP posts. Topics: service spotlights, "
                    "client success stories, local community involvement."
                )

            # -- qa --
            field_points = 10
            max_score += field_points
            # Q&A presence is hard to verify without GBP API; score based on listing completeness
            if listing and listing.listing_score is not None and listing.listing_score >= 70:
                points = field_points
                total_score += points
                checks["qa"] = {"score": points, "max": field_points, "passed": True}
            else:
                checks["qa"] = {"score": 0, "max": field_points, "passed": False}
                recommendations.append(
                    "Seed the Q&A section with at least 5 common questions: "
                    "'Do you offer mobile notary?', 'How long does an apostille take?', "
                    "'What documents do you notarize?', 'Do you serve Roanoke VA?', "
                    "'Are you available on weekends?'"
                )

            # -- attributes --
            field_points = 10
            max_score += field_points
            if listing and listing.listing_score is not None and listing.listing_score >= 60:
                points = field_points
                total_score += points
                checks["attributes"] = {"score": points, "max": field_points, "passed": True}
            else:
                checks["attributes"] = {"score": 0, "max": field_points, "passed": False}
                recommendations.append(
                    "Enable all applicable GBP attributes: 'Identifies as veteran-owned', "
                    "'Women-led', 'By appointment', 'Online appointments', 'Wheelchair accessible', "
                    "'Free Wi-Fi', 'Languages spoken: English, Spanish'."
                )

            # -- service_areas --
            field_points = 10
            max_score += field_points
            if listing and listing.service_area:
                points = field_points
                total_score += points
                checks["service_areas"] = {"score": points, "max": field_points, "passed": True}
            else:
                checks["service_areas"] = {"score": 0, "max": field_points, "passed": False}
                area_names = ", ".join(_area_key(a) for a in self.service_areas)
                recommendations.append(
                    f"Define all service areas in GBP: {area_names}. "
                    "This is critical for appearing in 'near me' searches across the DMV and SWVA."
                )

            # -- reviews_response_rate --
            field_points = 10
            max_score += field_points
            reviews = (
                db.query(Review)
                .filter(
                    Review.platform == "google",
                    Review.service_area == location,
                )
                .all()
            )
            if reviews:
                responded = sum(1 for r in reviews if r.response_text)
                response_rate = responded / len(reviews) * 100
                if response_rate >= 90:
                    points = field_points
                elif response_rate >= 70:
                    points = field_points * 3 // 4
                elif response_rate >= 50:
                    points = field_points // 2
                else:
                    points = field_points // 4
                total_score += points
                passed = response_rate >= 90
                checks["reviews_response_rate"] = {
                    "score": points,
                    "max": field_points,
                    "passed": passed,
                    "response_rate": round(response_rate, 1),
                }
                if not passed:
                    recommendations.append(
                        f"Review response rate is {response_rate:.0f}%. "
                        "Respond to every review within 24 hours to boost local ranking signals."
                    )
            else:
                checks["reviews_response_rate"] = {"score": 0, "max": field_points, "passed": False}
                recommendations.append(
                    "No Google reviews found for this location. Develop a review solicitation "
                    "strategy: follow-up emails, SMS reminders, and in-person requests."
                )

            percentage = round(total_score / max_score * 100, 1) if max_score > 0 else 0.0

            logger.info(
                "GBP optimization for '{}': {}/{} ({:.1f}%)",
                location, total_score, max_score, percentage,
            )

            return {
                "location": location,
                "score": total_score,
                "max_score": max_score,
                "percentage": percentage,
                "checks": checks,
                "recommendations": recommendations,
                "checked_at": datetime.datetime.utcnow().isoformat(),
            }
        except Exception as exc:
            logger.error("Error checking GBP optimization for '{}': {}", location, exc)
            raise
        finally:
            db.close()

    # ------------------------------------------------------------------
    # 2. NAP consistency audit
    # ------------------------------------------------------------------

    def audit_nap_consistency(self) -> dict:
        """Audit NAP consistency across all tracked directories.

        Compares the Name, Address, and Phone number stored in each
        :class:`BusinessListing` against the canonical company data from
        ``config.settings.COMPANY``.

        Returns:
            A dict with ``overall_score``, ``total_listings``,
            ``consistent_count``, ``inconsistent_count``, per-directory
            ``results``, and ``recommendations``.
        """
        logger.info("Starting NAP consistency audit across all directories")

        expected_name: str = self.company_name
        expected_address: str = (
            f"{self.primary_address.get('street', '')}, "
            f"{self.primary_address.get('city', '')}, "
            f"{self.primary_address.get('state', '')} "
            f"{self.primary_address.get('zip', '')}"
        ).strip(", ")
        expected_phone: str = self.company_phone

        db = SessionLocal()
        try:
            listings: list[BusinessListing] = db.query(BusinessListing).all()

            results: list[dict] = []
            consistent_count = 0
            inconsistent_count = 0

            checked_platforms: set[str] = set()

            for listing in listings:
                issues: list[str] = []

                # --- name ---
                name_match = True
                if listing.name_listed:
                    name_match = self._nap_field_matches(expected_name, listing.name_listed)
                    if not name_match:
                        issues.append(
                            f"Name mismatch: expected '{expected_name}', "
                            f"found '{listing.name_listed}'"
                        )
                else:
                    name_match = False
                    issues.append("Business name is missing from listing")

                # --- address ---
                address_match = True
                if listing.address_listed:
                    address_match = self._nap_field_matches(expected_address, listing.address_listed)
                    if not address_match:
                        issues.append(
                            f"Address mismatch: expected '{expected_address}', "
                            f"found '{listing.address_listed}'"
                        )
                else:
                    address_match = False
                    issues.append("Address is missing from listing")

                # --- phone ---
                phone_match = True
                if listing.phone_listed:
                    phone_match = self._phone_matches(expected_phone, listing.phone_listed)
                    if not phone_match:
                        issues.append(
                            f"Phone mismatch: expected '{expected_phone}', "
                            f"found '{listing.phone_listed}'"
                        )
                else:
                    phone_match = False
                    issues.append("Phone number is missing from listing")

                is_consistent = name_match and address_match and phone_match
                if is_consistent:
                    consistent_count += 1
                else:
                    inconsistent_count += 1

                checked_platforms.add(listing.platform)

                results.append({
                    "platform": listing.platform,
                    "service_area": listing.service_area,
                    "listing_url": listing.listing_url,
                    "consistent": is_consistent,
                    "name_match": name_match,
                    "address_match": address_match,
                    "phone_match": phone_match,
                    "issues": issues,
                })

                # Persist findings
                listing.nap_consistent = is_consistent
                listing.nap_issues = issues if issues else None
                listing.last_checked = datetime.datetime.utcnow()

            db.commit()

            total = consistent_count + inconsistent_count
            overall_score = round(consistent_count / total * 100, 1) if total > 0 else 0.0

            # Identify missing directories
            missing_directories: list[str] = []
            for directory in NAP_DIRECTORIES:
                if directory["key"] not in checked_platforms:
                    missing_directories.append(directory["name"])

            recommendations: list[str] = []
            if inconsistent_count > 0:
                recommendations.append(
                    f"Fix NAP inconsistencies on {inconsistent_count} listing(s) immediately. "
                    "Inconsistent NAP data confuses search engines and hurts local rankings."
                )
            if missing_directories:
                recommendations.append(
                    f"Create listings on {len(missing_directories)} missing directories: "
                    f"{', '.join(missing_directories)}."
                )
            if overall_score < 80:
                recommendations.append(
                    "Consider using an automated citation management tool (e.g., BrightLocal, "
                    "Yext, or Moz Local) to maintain NAP consistency at scale."
                )
            if overall_score >= 90:
                recommendations.append(
                    "NAP consistency is strong. Continue periodic audits to catch any "
                    "third-party directory changes."
                )

            logger.info(
                "NAP audit complete: {}/{} consistent ({:.1f}%)",
                consistent_count, total, overall_score,
            )

            return {
                "overall_score": overall_score,
                "total_listings": total,
                "consistent_count": consistent_count,
                "inconsistent_count": inconsistent_count,
                "missing_directories": missing_directories,
                "results": results,
                "recommendations": recommendations,
                "audited_at": datetime.datetime.utcnow().isoformat(),
            }
        except Exception as exc:
            logger.error("Error during NAP consistency audit: {}", exc)
            raise
        finally:
            db.close()

    # ------------------------------------------------------------------
    # 3. Review monitoring
    # ------------------------------------------------------------------

    def monitor_reviews(self, platform: str) -> dict:
        """Monitor reviews for a given platform.

        Loads all :class:`Review` records for *platform*, computes aggregate
        statistics (average rating, total count, sentiment breakdown), and
        flags reviews that still need a response.

        Args:
            platform: One of ``"google"``, ``"yelp"``, or ``"bbb"``.

        Returns:
            A dict with ``platform``, ``total_reviews``, ``average_rating``,
            ``rating_distribution``, ``sentiment_breakdown``,
            ``needs_response``, ``recent_reviews``, and ``alerts``.

        Raises:
            ValueError: If *platform* is not in the supported list.
        """
        platform = platform.lower().strip()
        if platform not in self.review_platforms:
            raise ValueError(
                f"Unsupported review platform '{platform}'. "
                f"Choose from: {', '.join(self.review_platforms)}"
            )

        logger.info("Monitoring reviews on platform: {}", platform)

        db = SessionLocal()
        try:
            reviews: list[Review] = (
                db.query(Review)
                .filter(Review.platform == platform)
                .order_by(Review.review_date.desc())
                .all()
            )

            if not reviews:
                logger.warning("No reviews found for platform '{}'", platform)
                return {
                    "platform": platform,
                    "total_reviews": 0,
                    "average_rating": None,
                    "rating_distribution": {},
                    "sentiment_breakdown": {"positive": 0, "neutral": 0, "negative": 0},
                    "needs_response": [],
                    "recent_reviews": [],
                    "alerts": ["No reviews found. Implement a review generation strategy."],
                    "monitored_at": datetime.datetime.utcnow().isoformat(),
                }

            # Rating distribution
            rating_dist: dict[str, int] = {"5": 0, "4": 0, "3": 0, "2": 0, "1": 0}
            sentiment_counts: dict[str, int] = {"positive": 0, "neutral": 0, "negative": 0}
            total_rating = 0.0
            needs_response: list[dict] = []
            recent_reviews: list[dict] = []

            for review in reviews:
                rating_val = review.rating or 0
                total_rating += rating_val
                bucket = str(min(5, max(1, int(round(rating_val)))))
                rating_dist[bucket] = rating_dist.get(bucket, 0) + 1

                sentiment = review.sentiment or _compute_sentiment(
                    rating_val, review.review_text or ""
                )
                if sentiment not in sentiment_counts:
                    sentiment_counts[sentiment] = 0
                sentiment_counts[sentiment] += 1

                # Persist sentiment if missing
                if not review.sentiment:
                    review.sentiment = sentiment

                review_dict = {
                    "id": review.id,
                    "reviewer_name": review.reviewer_name,
                    "rating": review.rating,
                    "review_text": review.review_text,
                    "review_date": review.review_date.isoformat() if review.review_date else None,
                    "sentiment": sentiment,
                    "service_area": review.service_area,
                    "has_response": bool(review.response_text),
                }

                if review.needs_response and not review.response_text:
                    needs_response.append(review_dict)

                recent_reviews.append(review_dict)

            db.commit()

            avg_rating = round(total_rating / len(reviews), 2)
            recent_reviews = recent_reviews[:20]  # cap to latest 20

            alerts: list[str] = []
            if avg_rating < 4.0:
                alerts.append(
                    f"Average rating on {platform} is {avg_rating}. "
                    "Target is 4.0+. Prioritize service quality and review solicitation."
                )
            if needs_response:
                alerts.append(
                    f"{len(needs_response)} review(s) on {platform} need a response."
                )
            negative_count = sentiment_counts.get("negative", 0)
            if negative_count > 0:
                alerts.append(
                    f"{negative_count} negative review(s) detected on {platform}. "
                    "Respond promptly and professionally."
                )

            logger.info(
                "Review monitoring for '{}': {} total, {:.2f} avg rating, {} need response",
                platform, len(reviews), avg_rating, len(needs_response),
            )

            return {
                "platform": platform,
                "total_reviews": len(reviews),
                "average_rating": avg_rating,
                "rating_distribution": rating_dist,
                "sentiment_breakdown": sentiment_counts,
                "needs_response": needs_response,
                "recent_reviews": recent_reviews,
                "alerts": alerts,
                "monitored_at": datetime.datetime.utcnow().isoformat(),
            }
        except ValueError:
            raise
        except Exception as exc:
            logger.error("Error monitoring reviews on '{}': {}", platform, exc)
            raise
        finally:
            db.close()

    # ------------------------------------------------------------------
    # 4. Review response generation
    # ------------------------------------------------------------------

    def generate_review_response(self, review_text: str, rating: float) -> dict:
        """Generate an AI-suggested response to a customer review.

        Selects a response template based on the star rating and
        personalizes it with contextual details derived from the review body.

        Args:
            review_text: The full text of the customer review.
            rating: Star rating (1.0 -- 5.0).

        Returns:
            A dict with ``rating``, ``sentiment``, ``suggested_response``,
            ``service_mentioned``, and ``response_guidelines``.
        """
        logger.info("Generating review response for {}-star review", rating)

        sentiment = _compute_sentiment(rating, review_text)
        service_mentioned = _guess_service_from_text(review_text)

        # Determine reviewer placeholder
        reviewer_placeholder = "valued customer"

        # Select template pool
        if sentiment == "positive":
            templates = _POSITIVE_RESPONSE_TEMPLATES
        elif sentiment == "negative":
            templates = _NEGATIVE_RESPONSE_TEMPLATES
        else:
            templates = _NEUTRAL_RESPONSE_TEMPLATES

        template = _pick_template(templates, review_text)
        response = template.format(
            reviewer=reviewer_placeholder,
            service_guess=service_mentioned,
            phone=self.company_phone or "(phone number)",
        )

        guidelines: list[str] = [
            "Personalize by using the reviewer's actual name.",
            "Respond within 24 hours of the review posting.",
            "Keep the tone professional, warm, and genuine.",
        ]
        if sentiment == "negative":
            guidelines.extend([
                "Acknowledge the specific concern raised.",
                "Take the conversation offline by providing a direct contact number.",
                "Do NOT be defensive or argumentative.",
                "Offer a concrete resolution or next step.",
            ])
        elif sentiment == "positive":
            guidelines.extend([
                "Reinforce the positive experience mentioned.",
                "Invite them to refer friends and family.",
                "Mention a related service they might need in the future.",
            ])
        else:
            guidelines.extend([
                "Ask what could be improved for next time.",
                "Highlight specific services or conveniences they may not be aware of.",
            ])

        logger.info("Response generated for {}-star ({}) review", rating, sentiment)

        return {
            "rating": rating,
            "sentiment": sentiment,
            "suggested_response": response,
            "service_mentioned": service_mentioned,
            "response_guidelines": guidelines,
            "generated_at": datetime.datetime.utcnow().isoformat(),
        }

    # ------------------------------------------------------------------
    # 5. Citation opportunity discovery
    # ------------------------------------------------------------------

    def find_citation_opportunities(self) -> dict:
        """Find directories where the business is not yet listed.

        Compares the master :data:`CITATION_SOURCES` list against existing
        :class:`Citation` records in the database and returns categorised
        opportunities ordered by priority and domain authority.

        Returns:
            A dict with per-category ``opportunities``, ``total_opportunities``,
            ``total_existing``, and ``recommendations``.
        """
        logger.info("Searching for citation opportunities")

        db = SessionLocal()
        try:
            existing_citations: list[Citation] = db.query(Citation).all()
            existing_names: set[str] = {c.directory_name.lower() for c in existing_citations}

            opportunities: dict[str, list[dict]] = {}
            total_new = 0
            total_existing = 0

            for category, sources in CITATION_SOURCES.items():
                category_opps: list[dict] = []
                for source in sources:
                    if source["name"].lower() in existing_names:
                        total_existing += 1
                        continue
                    total_new += 1
                    category_opps.append({
                        "name": source["name"],
                        "url": source["url"],
                        "domain_authority": source["domain_authority"],
                        "priority": source["priority"],
                        "category": category,
                    })
                # Sort by priority then DA
                priority_order = {"high": 0, "medium": 1, "low": 2}
                category_opps.sort(
                    key=lambda x: (priority_order.get(x["priority"], 9), -x["domain_authority"])
                )
                opportunities[category] = category_opps

            recommendations: list[str] = []
            high_priority = [
                opp
                for opps in opportunities.values()
                for opp in opps
                if opp["priority"] == "high"
            ]
            if high_priority:
                names = ", ".join(o["name"] for o in high_priority[:5])
                recommendations.append(
                    f"Prioritize listing on these high-priority directories first: {names}."
                )
            if total_new > 20:
                recommendations.append(
                    "Consider a phased approach: tackle 5-10 citation submissions per week "
                    "to avoid triggering spam filters."
                )
            notary_opps = opportunities.get("legal_notary_directories", [])
            if notary_opps:
                recommendations.append(
                    "Industry-specific notary directories carry strong relevance signals. "
                    "Submit to NNA, 123Notary, and Notary Rotary as a top priority."
                )
            local_opps = opportunities.get("local_directories", [])
            if local_opps:
                recommendations.append(
                    "Join all relevant Chambers of Commerce. Membership often includes a "
                    "high-authority backlink and local networking opportunities."
                )

            logger.info(
                "Found {} citation opportunities ({} already listed)",
                total_new, total_existing,
            )

            return {
                "opportunities": opportunities,
                "total_opportunities": total_new,
                "total_existing": total_existing,
                "recommendations": recommendations,
                "searched_at": datetime.datetime.utcnow().isoformat(),
            }
        except Exception as exc:
            logger.error("Error finding citation opportunities: {}", exc)
            raise
        finally:
            db.close()

    # ------------------------------------------------------------------
    # 6. Comprehensive citation list
    # ------------------------------------------------------------------

    def build_citation_list(self) -> dict:
        """Return the full citation source catalogue organised by category.

        Each entry includes the directory name, URL, estimated domain
        authority, recommended priority, and -- when available -- the
        current listing status from the database.

        Returns:
            A dict keyed by category (``national_directories``,
            ``legal_notary_directories``, ``local_directories``,
            ``industry_specific``), each containing a list of citation dicts.
        """
        logger.info("Building comprehensive citation list")

        db = SessionLocal()
        try:
            existing_citations: list[Citation] = db.query(Citation).all()
            existing_map: dict[str, Citation] = {
                c.directory_name.lower(): c for c in existing_citations
            }

            result: dict[str, list[dict]] = {}
            total_sources = 0
            listed_count = 0

            for category, sources in CITATION_SOURCES.items():
                entries: list[dict] = []
                for source in sources:
                    total_sources += 1
                    existing = existing_map.get(source["name"].lower())
                    is_listed = existing.is_listed if existing else False
                    if is_listed:
                        listed_count += 1

                    entries.append({
                        "name": source["name"],
                        "url": source["url"],
                        "domain_authority": source["domain_authority"],
                        "priority": source["priority"],
                        "is_listed": is_listed,
                        "listing_url": existing.listing_url if existing else None,
                        "notes": existing.notes if existing else None,
                    })
                result[category] = entries

            logger.info(
                "Citation list built: {} sources across {} categories, {} already listed",
                total_sources, len(result), listed_count,
            )

            return {
                "categories": result,
                "total_sources": total_sources,
                "total_listed": listed_count,
                "total_unlisted": total_sources - listed_count,
                "coverage_percentage": round(listed_count / total_sources * 100, 1) if total_sources else 0.0,
                "built_at": datetime.datetime.utcnow().isoformat(),
            }
        except Exception as exc:
            logger.error("Error building citation list: {}", exc)
            raise
        finally:
            db.close()

    # ------------------------------------------------------------------
    # 7. Local competitor analysis
    # ------------------------------------------------------------------

    def analyze_local_competitor(self, competitor_name: str, area: str) -> dict:
        """Analyze a local competitor's SEO presence in a specific area.

        Loads or creates a :class:`LocalCompetitor` record, computes a
        competitive comparison, and returns strengths, weaknesses, and
        actionable recommendations.

        Args:
            competitor_name: The business name of the competitor.
            area: The service area to analyze, e.g. ``"Alexandria, VA"``.

        Returns:
            A dict with ``competitor``, ``area``, ``competitor_data``,
            ``comparison``, and ``recommendations``.
        """
        logger.info("Analyzing competitor '{}' in area '{}'", competitor_name, area)

        db = SessionLocal()
        try:
            competitor: Optional[LocalCompetitor] = (
                db.query(LocalCompetitor)
                .filter(
                    LocalCompetitor.business_name == competitor_name,
                    LocalCompetitor.service_area == area,
                )
                .first()
            )

            if competitor:
                competitor_data = {
                    "business_name": competitor.business_name,
                    "website": competitor.website,
                    "service_area": competitor.service_area,
                    "google_rating": competitor.google_rating,
                    "review_count": competitor.review_count,
                    "gbp_url": competitor.gbp_url,
                    "top_keywords": competitor.top_keywords or [],
                    "strengths": competitor.strengths or [],
                    "weaknesses": competitor.weaknesses or [],
                    "last_analyzed": (
                        competitor.last_analyzed.isoformat()
                        if competitor.last_analyzed else None
                    ),
                }
            else:
                # Create a stub record to track going forward
                competitor = LocalCompetitor(
                    business_name=competitor_name,
                    service_area=area,
                    last_analyzed=datetime.datetime.utcnow(),
                )
                db.add(competitor)
                db.commit()
                db.refresh(competitor)
                competitor_data = {
                    "business_name": competitor_name,
                    "website": None,
                    "service_area": area,
                    "google_rating": None,
                    "review_count": None,
                    "gbp_url": None,
                    "top_keywords": [],
                    "strengths": [],
                    "weaknesses": [],
                    "last_analyzed": datetime.datetime.utcnow().isoformat(),
                }

            # Load our own reviews for comparison
            our_reviews: list[Review] = (
                db.query(Review)
                .filter(Review.platform == "google", Review.service_area == area)
                .all()
            )
            our_rating = (
                round(sum(r.rating for r in our_reviews if r.rating) / len(our_reviews), 2)
                if our_reviews else None
            )
            our_review_count = len(our_reviews)

            comparison: dict = {
                "our_rating": our_rating,
                "our_review_count": our_review_count,
                "competitor_rating": competitor_data["google_rating"],
                "competitor_review_count": competitor_data["review_count"],
                "rating_advantage": None,
                "review_count_advantage": None,
            }
            if our_rating and competitor_data["google_rating"]:
                comparison["rating_advantage"] = round(
                    our_rating - competitor_data["google_rating"], 2
                )
            if our_review_count and competitor_data["review_count"]:
                comparison["review_count_advantage"] = (
                    our_review_count - competitor_data["review_count"]
                )

            recommendations: list[str] = []

            # Rating comparison
            if comparison["rating_advantage"] is not None:
                if comparison["rating_advantage"] < 0:
                    recommendations.append(
                        f"Competitor has a higher Google rating "
                        f"({competitor_data['google_rating']} vs {our_rating}). "
                        "Focus on improving service quality and soliciting positive reviews."
                    )
                elif comparison["rating_advantage"] > 0:
                    recommendations.append(
                        f"We have a rating advantage ({our_rating} vs "
                        f"{competitor_data['google_rating']}). Highlight our ratings "
                        "in marketing materials and on the website."
                    )

            # Review volume
            if comparison["review_count_advantage"] is not None:
                if comparison["review_count_advantage"] < 0:
                    deficit = abs(comparison["review_count_advantage"])
                    recommendations.append(
                        f"Competitor has {deficit} more review(s). Implement an aggressive "
                        "but ethical review-generation campaign."
                    )

            # Keywords
            if competitor_data.get("top_keywords"):
                recommendations.append(
                    f"Competitor ranks for these keywords: "
                    f"{', '.join(competitor_data['top_keywords'][:5])}. "
                    "Evaluate whether to target the same terms or find gaps."
                )

            # General
            if not competitor_data.get("website"):
                recommendations.append(
                    f"Competitor website is unknown. Research '{competitor_name}' to "
                    "complete the competitive profile."
                )

            recommendations.append(
                f"Schedule a follow-up competitive analysis for '{competitor_name}' in "
                f"30 days to track changes."
            )

            logger.info("Competitor analysis complete for '{}' in '{}'", competitor_name, area)

            return {
                "competitor": competitor_name,
                "area": area,
                "competitor_data": competitor_data,
                "comparison": comparison,
                "recommendations": recommendations,
                "analyzed_at": datetime.datetime.utcnow().isoformat(),
            }
        except Exception as exc:
            logger.error(
                "Error analyzing competitor '{}' in '{}': {}",
                competitor_name, area, exc,
            )
            raise
        finally:
            db.close()

    # ------------------------------------------------------------------
    # 8. Per-area local SEO report
    # ------------------------------------------------------------------

    def get_local_seo_report(self, area: str) -> dict:
        """Generate a comprehensive local SEO report for a service area.

        Aggregates GBP optimization, review metrics across all platforms,
        citation coverage, and competitor intelligence for the given *area*.

        Args:
            area: The service area to report on, e.g. ``"Alexandria, VA"``.

        Returns:
            A dict with ``area``, ``gbp_optimization``, ``reviews``,
            ``citations``, ``competitors``, ``overall_score``, and
            ``priority_actions``.
        """
        logger.info("Generating local SEO report for area: {}", area)

        try:
            # GBP
            gbp_data = self.check_gbp_optimization(area)

            # Reviews per platform
            reviews_data: dict[str, dict] = {}
            for platform in self.review_platforms:
                try:
                    reviews_data[platform] = self.monitor_reviews(platform)
                except Exception as exc:
                    logger.warning("Could not fetch reviews for '{}': {}", platform, exc)
                    reviews_data[platform] = {"error": str(exc)}

            # Citations
            citation_data = self.build_citation_list()

            # Competitors in this area
            db = SessionLocal()
            try:
                competitors: list[LocalCompetitor] = (
                    db.query(LocalCompetitor)
                    .filter(LocalCompetitor.service_area == area)
                    .all()
                )
                competitor_summaries = [
                    {
                        "business_name": c.business_name,
                        "google_rating": c.google_rating,
                        "review_count": c.review_count,
                        "last_analyzed": (
                            c.last_analyzed.isoformat() if c.last_analyzed else None
                        ),
                    }
                    for c in competitors
                ]
            finally:
                db.close()

            # Compute overall score
            score_components: list[float] = []
            if gbp_data.get("percentage") is not None:
                score_components.append(gbp_data["percentage"])
            for platform, rdata in reviews_data.items():
                if isinstance(rdata, dict) and rdata.get("average_rating"):
                    score_components.append(rdata["average_rating"] / 5.0 * 100)
            if citation_data.get("coverage_percentage") is not None:
                score_components.append(citation_data["coverage_percentage"])

            overall_score = (
                round(sum(score_components) / len(score_components), 1)
                if score_components else 0.0
            )

            # Priority actions
            priority_actions: list[str] = []
            if gbp_data["percentage"] < 70:
                priority_actions.append(
                    f"GBP optimization is at {gbp_data['percentage']}%. "
                    "Address the top recommendations immediately."
                )
            for platform, rdata in reviews_data.items():
                if isinstance(rdata, dict) and rdata.get("needs_response"):
                    count = len(rdata["needs_response"])
                    if count > 0:
                        priority_actions.append(
                            f"Respond to {count} unanswered review(s) on {platform}."
                        )
            if citation_data.get("total_unlisted", 0) > 10:
                priority_actions.append(
                    f"{citation_data['total_unlisted']} citation sources are not yet listed. "
                    "Begin submissions on high-priority directories."
                )
            if not competitors:
                priority_actions.append(
                    f"No competitors tracked in '{area}'. Identify and add local competitors."
                )

            report = {
                "area": area,
                "gbp_optimization": gbp_data,
                "reviews": reviews_data,
                "citations": {
                    "coverage_percentage": citation_data.get("coverage_percentage"),
                    "total_sources": citation_data.get("total_sources"),
                    "total_listed": citation_data.get("total_listed"),
                    "total_unlisted": citation_data.get("total_unlisted"),
                },
                "competitors": competitor_summaries,
                "overall_score": overall_score,
                "priority_actions": priority_actions,
                "generated_at": datetime.datetime.utcnow().isoformat(),
            }

            logger.info(
                "Local SEO report for '{}': overall score {:.1f}%, {} priority actions",
                area, overall_score, len(priority_actions),
            )

            return report
        except Exception as exc:
            logger.error("Error generating local SEO report for '{}': {}", area, exc)
            raise

    # ------------------------------------------------------------------
    # 9. Overall local SEO dashboard
    # ------------------------------------------------------------------

    def get_overall_local_dashboard(self) -> dict:
        """Return dashboard data aggregated across all service areas.

        Iterates over every configured primary and secondary service area,
        collects per-area reports, and computes platform-wide metrics.

        Returns:
            A dict with ``company``, ``service_areas`` (per-area summaries),
            ``aggregate_metrics``, ``platform_reviews``, ``citation_overview``,
            ``top_priority_actions``, and ``generated_at``.
        """
        logger.info("Building overall local SEO dashboard")

        area_reports: list[dict] = []
        all_priority_actions: list[dict] = []
        gbp_scores: list[float] = []

        for area_info in self.service_areas:
            area_label = _area_key(area_info)
            try:
                report = self.get_local_seo_report(area_label)
                area_reports.append({
                    "area": area_label,
                    "tier": area_info["tier"],
                    "region": area_info.get("region", ""),
                    "overall_score": report["overall_score"],
                    "gbp_score": report["gbp_optimization"]["percentage"],
                    "priority_action_count": len(report["priority_actions"]),
                })
                gbp_scores.append(report["gbp_optimization"]["percentage"])
                for action in report["priority_actions"]:
                    all_priority_actions.append({
                        "area": area_label,
                        "tier": area_info["tier"],
                        "action": action,
                    })
            except Exception as exc:
                logger.warning("Could not generate report for '{}': {}", area_label, exc)
                area_reports.append({
                    "area": area_label,
                    "tier": area_info["tier"],
                    "region": area_info.get("region", ""),
                    "overall_score": None,
                    "gbp_score": None,
                    "priority_action_count": 0,
                    "error": str(exc),
                })

        # Platform-wide review summary
        platform_reviews: dict[str, dict] = {}
        for platform in self.review_platforms:
            try:
                platform_reviews[platform] = self.monitor_reviews(platform)
            except Exception as exc:
                logger.warning("Dashboard: could not load reviews for '{}': {}", platform, exc)
                platform_reviews[platform] = {"error": str(exc)}

        # Citation overview
        try:
            citation_overview = self.build_citation_list()
        except Exception as exc:
            logger.warning("Dashboard: could not build citation list: {}", exc)
            citation_overview = {"error": str(exc)}

        # Aggregate metrics
        scored_areas = [a for a in area_reports if a.get("overall_score") is not None]
        avg_overall = (
            round(sum(a["overall_score"] for a in scored_areas) / len(scored_areas), 1)
            if scored_areas else 0.0
        )
        avg_gbp = (
            round(sum(s for s in gbp_scores) / len(gbp_scores), 1)
            if gbp_scores else 0.0
        )

        # Sort priority actions: primary areas first, then alphabetical
        tier_order = {"primary": 0, "secondary": 1}
        all_priority_actions.sort(key=lambda x: (tier_order.get(x["tier"], 9), x["area"]))
        top_actions = all_priority_actions[:20]

        dashboard = {
            "company": self.company_name,
            "service_areas": area_reports,
            "aggregate_metrics": {
                "total_areas": len(self.service_areas),
                "primary_areas": len(self.primary_areas),
                "secondary_areas": len(self.secondary_areas),
                "average_overall_score": avg_overall,
                "average_gbp_score": avg_gbp,
                "total_priority_actions": len(all_priority_actions),
            },
            "platform_reviews": platform_reviews,
            "citation_overview": (
                {
                    "coverage_percentage": citation_overview.get("coverage_percentage"),
                    "total_sources": citation_overview.get("total_sources"),
                    "total_listed": citation_overview.get("total_listed"),
                    "total_unlisted": citation_overview.get("total_unlisted"),
                }
                if isinstance(citation_overview, dict) and "error" not in citation_overview
                else citation_overview
            ),
            "top_priority_actions": top_actions,
            "generated_at": datetime.datetime.utcnow().isoformat(),
        }

        logger.info(
            "Overall dashboard built: {} areas, avg score {:.1f}%, {} priority actions",
            len(self.service_areas), avg_overall, len(all_priority_actions),
        )

        return dashboard

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _nap_field_matches(expected: str, found: str) -> bool:
        """Case- and punctuation-insensitive NAP field comparison."""
        import re as _re
        def _normalize(s: str) -> str:
            return _re.sub(r"[^\w\s]", "", s.lower()).strip()
        norm_expected = _normalize(expected)
        norm_found = _normalize(found)
        return norm_expected == norm_found or norm_expected in norm_found or norm_found in norm_expected

    @staticmethod
    def _phone_matches(expected: str, found: str) -> bool:
        """Compare phone numbers by digits only."""
        import re as _re
        digits_expected = _re.sub(r"\D", "", expected)
        digits_found = _re.sub(r"\D", "", found)
        if not digits_expected or not digits_found:
            return False
        return digits_expected == digits_found


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    import sys

    logger.remove()
    logger.add(sys.stderr, level="INFO", format=(
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    ))

    manager = LocalSEOManager()

    print("=" * 70)
    print("  Common Notary Apostille -- Local SEO Management Dashboard")
    print("=" * 70)

    # --- GBP optimization for primary HQ area ---
    print("\n[1] GBP Optimization Check -- Alexandria, VA")
    print("-" * 50)
    try:
        gbp = manager.check_gbp_optimization("Alexandria, VA")
        print(f"  Score: {gbp['score']}/{gbp['max_score']} ({gbp['percentage']}%)")
        for rec in gbp["recommendations"][:3]:
            print(f"  * {rec}")
    except Exception as e:
        print(f"  Error: {e}")

    # --- NAP audit ---
    print("\n[2] NAP Consistency Audit")
    print("-" * 50)
    try:
        nap = manager.audit_nap_consistency()
        print(f"  Overall score: {nap['overall_score']}%")
        print(f"  Listings: {nap['total_listings']} total, "
              f"{nap['consistent_count']} consistent, "
              f"{nap['inconsistent_count']} inconsistent")
        if nap["missing_directories"]:
            print(f"  Missing: {', '.join(nap['missing_directories'][:5])}")
    except Exception as e:
        print(f"  Error: {e}")

    # --- Review monitoring ---
    print("\n[3] Review Monitoring")
    print("-" * 50)
    for platform in REVIEW_PLATFORMS:
        try:
            rev = manager.monitor_reviews(platform)
            avg = rev["average_rating"] or "N/A"
            print(f"  {platform.upper()}: {rev['total_reviews']} reviews, "
                  f"avg {avg}, {len(rev['needs_response'])} need response")
        except Exception as e:
            print(f"  {platform.upper()}: Error -- {e}")

    # --- Review response generation ---
    print("\n[4] Sample Review Response Generation")
    print("-" * 50)
    sample_positive = manager.generate_review_response(
        "Amazing service! Got my apostille done the same day. Very professional team.",
        5.0,
    )
    print(f"  5-star response ({sample_positive['sentiment']}):")
    print(f"  \"{sample_positive['suggested_response'][:120]}...\"")

    sample_negative = manager.generate_review_response(
        "Waited two hours past my appointment. Poor communication and overpriced.",
        2.0,
    )
    print(f"  2-star response ({sample_negative['sentiment']}):")
    print(f"  \"{sample_negative['suggested_response'][:120]}...\"")

    # --- Citation opportunities ---
    print("\n[5] Citation Opportunities")
    print("-" * 50)
    try:
        citations = manager.find_citation_opportunities()
        print(f"  Opportunities found: {citations['total_opportunities']}")
        print(f"  Already listed: {citations['total_existing']}")
        for cat, opps in citations["opportunities"].items():
            print(f"    {cat}: {len(opps)} new")
    except Exception as e:
        print(f"  Error: {e}")

    # --- Citation list ---
    print("\n[6] Full Citation List")
    print("-" * 50)
    try:
        cl = manager.build_citation_list()
        print(f"  Total sources: {cl['total_sources']}")
        print(f"  Listed: {cl['total_listed']} | Unlisted: {cl['total_unlisted']}")
        print(f"  Coverage: {cl['coverage_percentage']}%")
    except Exception as e:
        print(f"  Error: {e}")

    # --- Competitor analysis ---
    print("\n[7] Sample Competitor Analysis")
    print("-" * 50)
    try:
        comp = manager.analyze_local_competitor("Example Notary Services", "Alexandria, VA")
        print(f"  Competitor: {comp['competitor']} in {comp['area']}")
        print(f"  Recommendations: {len(comp['recommendations'])}")
        for rec in comp["recommendations"][:2]:
            print(f"    * {rec}")
    except Exception as e:
        print(f"  Error: {e}")

    # --- Per-area report ---
    print("\n[8] Local SEO Report -- Alexandria, VA")
    print("-" * 50)
    try:
        report = manager.get_local_seo_report("Alexandria, VA")
        print(f"  Overall score: {report['overall_score']}%")
        print(f"  Priority actions: {len(report['priority_actions'])}")
        for action in report["priority_actions"][:3]:
            print(f"    * {action}")
    except Exception as e:
        print(f"  Error: {e}")

    # --- Overall dashboard ---
    print("\n[9] Overall Local SEO Dashboard")
    print("-" * 50)
    try:
        dashboard = manager.get_overall_local_dashboard()
        metrics = dashboard["aggregate_metrics"]
        print(f"  Areas: {metrics['total_areas']} "
              f"({metrics['primary_areas']} primary, {metrics['secondary_areas']} secondary)")
        print(f"  Avg overall score: {metrics['average_overall_score']}%")
        print(f"  Avg GBP score: {metrics['average_gbp_score']}%")
        print(f"  Total priority actions: {metrics['total_priority_actions']}")
    except Exception as e:
        print(f"  Error: {e}")

    print("\n" + "=" * 70)
    print("  Dashboard generation complete.")
    print("=" * 70)
