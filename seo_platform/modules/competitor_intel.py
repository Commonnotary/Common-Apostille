"""
Module 7: Competitor Intelligence
SEO & AI Monitoring Platform - Common Notary Apostille

Discovers, analyzes, and monitors competitors across the DMV area and
Southwest Virginia.  Produces keyword-gap, content-gap, and backlink-gap
analyses, surfaces competitor weaknesses, and generates comprehensive
intelligence reports with prioritized action items.
"""

from __future__ import annotations

import datetime
import hashlib
import re
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from loguru import logger
from sqlalchemy import desc, func

from config.settings import (
    COMPANY,
    COMPETITORS,
    GOOGLE_API_KEY,
    GOOGLE_CSE_ID,
    SERVICE_AREAS,
    SERVICE_KEYWORDS,
    GEO_MODIFIERS,
)
from database.models import (
    Competitor,
    CompetitorAnalysis,
    Backlink,
    KeywordRanking,
    Keyword,
    Alert,
    SessionLocal,
)
from utils.helpers import extract_domain, fetch_url, normalize_url


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

_SEARCH_QUERIES_BY_TYPE: Dict[str, List[str]] = {
    "notary": [
        "notary public",
        "mobile notary",
        "notary near me",
        "notary services",
        "loan signing agent",
    ],
    "apostille": [
        "apostille services",
        "apostille near me",
        "document authentication",
        "embassy legalization",
    ],
    "all": [
        "notary public",
        "mobile notary",
        "apostille services",
        "document authentication",
        "notary near me",
        "apostille near me",
        "mobile notary near me",
        "loan signing agent",
        "embassy legalization",
    ],
}

_OUR_DOMAIN: str = extract_domain(COMPANY["website"])


# ---------------------------------------------------------------------------
# Helpers (module-private)
# ---------------------------------------------------------------------------


def _area_label(area: Dict[str, str]) -> str:
    """Return a human-readable label for a service-area dict."""
    return f"{area.get('city', 'Unknown')}, {area.get('state', '')}"


def _hash_id(*parts: str) -> str:
    """Produce a short deterministic hex digest for deduplication."""
    raw = "|".join(str(p).lower().strip() for p in parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _safe_get(url: str, timeout: int = 20) -> Optional[requests.Response]:
    """Attempt a GET request; return *None* on failure instead of raising."""
    try:
        return fetch_url(url, timeout=timeout)
    except Exception as exc:
        logger.warning("Failed to fetch {}: {}", url, exc)
        return None


def _google_custom_search(query: str, num: int = 10) -> List[Dict[str, Any]]:
    """Execute a Google Custom Search JSON API call.

    Returns a list of result dicts with keys *title*, *link*, *snippet*, and
    *displayLink*.  Returns an empty list when API keys are missing or on
    error.
    """
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        logger.debug("Google CSE credentials not configured; skipping API search.")
        return []

    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": GOOGLE_API_KEY,
        "cx": GOOGLE_CSE_ID,
        "q": query,
        "num": min(num, 10),
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("items", [])
    except Exception as exc:
        logger.error("Google CSE request failed for '{}': {}", query, exc)
        return []


def _scrape_serp_results(query: str, num: int = 20) -> List[Dict[str, Any]]:
    """Scrape organic Google results for *query* via HTML parsing.

    This is a best-effort fallback when the Custom Search JSON API is not
    available.  Results may be limited by rate-limits and CAPTCHAs.
    """
    results: List[Dict[str, Any]] = []
    search_url = "https://www.google.com/search"
    params = {"q": query, "num": num, "hl": "en"}
    headers = {"User-Agent": _USER_AGENT}

    try:
        resp = requests.get(search_url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        for g in soup.select("div.tF2Cxc, div.g"):
            link_tag = g.select_one("a[href]")
            title_tag = g.select_one("h3")
            snippet_tag = g.select_one("div.VwiC3b, span.aCOpRe")
            if link_tag and title_tag:
                href = link_tag["href"]
                if href.startswith("/url?q="):
                    href = href.split("/url?q=")[1].split("&")[0]
                results.append({
                    "title": title_tag.get_text(strip=True),
                    "link": href,
                    "snippet": snippet_tag.get_text(strip=True) if snippet_tag else "",
                    "displayLink": extract_domain(href),
                })
    except Exception as exc:
        logger.warning("SERP scrape failed for '{}': {}", query, exc)

    return results


def _estimate_domain_authority(domain: str) -> int:
    """Return a rough 0-100 domain-authority estimate.

    Uses simple heuristics (homepage status, page count, HTTPS) when
    third-party APIs are unavailable.  This is intentionally conservative.
    """
    score = 0
    url = f"https://{domain}"
    resp = _safe_get(url, timeout=10)
    if resp is None:
        return 0

    # HTTPS available
    if resp.url.startswith("https://"):
        score += 15

    # Homepage loads correctly
    if resp.status_code == 200:
        score += 10
        soup = BeautifulSoup(resp.text, "html.parser")
        # Has title
        if soup.title:
            score += 5
        # Has meta description
        if soup.find("meta", attrs={"name": "description"}):
            score += 5
        # Count internal links as a rough proxy of site size
        internal_links = [
            a["href"]
            for a in soup.find_all("a", href=True)
            if domain in a["href"] or a["href"].startswith("/")
        ]
        if len(internal_links) > 30:
            score += 15
        elif len(internal_links) > 15:
            score += 10
        elif len(internal_links) > 5:
            score += 5

        # Schema markup present
        if soup.find("script", attrs={"type": "application/ld+json"}):
            score += 10

        # Content length
        text_len = len(soup.get_text(strip=True))
        if text_len > 5000:
            score += 10
        elif text_len > 2000:
            score += 5

    return min(score, 100)


def _extract_page_topics(url: str) -> List[str]:
    """Fetch a page and return a list of topic strings from its headings."""
    topics: List[str] = []
    resp = _safe_get(url, timeout=15)
    if resp is None:
        return topics

    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup.find_all(["h1", "h2", "h3"]):
        text = tag.get_text(strip=True)
        if text and len(text) > 3:
            topics.append(text)
    return topics


# ===================================================================
# Main class
# ===================================================================


class CompetitorIntelligence:
    """Discover, analyze, and monitor competitors in the notary / apostille
    market across the DMV area and Southwest Virginia.

    All database interactions use short-lived sessions created from
    ``SessionLocal`` to stay compatible with the platform's session
    management strategy.
    """

    def __init__(self) -> None:
        self.our_domain: str = _OUR_DOMAIN
        self.our_website: str = COMPANY["website"]
        self.company_name: str = COMPANY["name"]
        logger.info(
            "CompetitorIntelligence initialized for {} ({})",
            self.company_name,
            self.our_domain,
        )

    # ------------------------------------------------------------------
    # 1. discover_competitors
    # ------------------------------------------------------------------

    def discover_competitors(
        self,
        area: Dict[str, str],
        service_type: str = "notary",
    ) -> List[Dict[str, Any]]:
        """Find top competitors in *area* for *service_type*.

        Searches Google for relevant keyword + geo combinations, collects
        unique domains from the results, filters out our own site, and
        persists newly-discovered competitors to the database.

        Args:
            area: A dict with at least ``city`` and ``state`` keys
                  (matching the shape used in ``config.settings.SERVICE_AREAS``).
            service_type: One of ``"notary"``, ``"apostille"``, or ``"all"``.

        Returns:
            A list of dicts describing each discovered competitor, with keys
            ``name``, ``domain``, ``url``, and ``source_query``.
        """
        label = _area_label(area)
        logger.info("Discovering {} competitors in {}", service_type, label)

        queries = _SEARCH_QUERIES_BY_TYPE.get(service_type, _SEARCH_QUERIES_BY_TYPE["all"])
        geo = f"{area.get('city', '')} {area.get('state', '')}".strip()

        seen_domains: set[str] = set()
        discovered: List[Dict[str, Any]] = []

        for base_query in queries:
            full_query = f"{base_query} {geo}"
            logger.debug("Searching: {}", full_query)

            # Prefer the official API; fall back to scraping
            results = _google_custom_search(full_query)
            if not results:
                results = _scrape_serp_results(full_query)
                # Be polite to Google when scraping
                time.sleep(2)

            for item in results:
                domain = extract_domain(item.get("link", ""))
                if not domain or domain == self.our_domain or domain in seen_domains:
                    continue
                # Skip obvious non-competitors (major platforms, directories)
                skip_domains = {
                    "google.com", "yelp.com", "facebook.com", "bbb.org",
                    "yellowpages.com", "mapquest.com", "thumbtack.com",
                    "angi.com", "homeadvisor.com", "nextdoor.com",
                    "linkedin.com", "twitter.com", "instagram.com",
                    "youtube.com", "wikipedia.org", "reddit.com",
                }
                if domain in skip_domains:
                    continue

                seen_domains.add(domain)
                discovered.append({
                    "name": item.get("title", domain),
                    "domain": domain,
                    "url": item.get("link", ""),
                    "source_query": full_query,
                })

        # Determine market tag
        region = area.get("region", "").lower()
        if "southwest" in region or "swva" in region:
            market = "swva"
        elif any(kw in region for kw in ("dmv", "northern virginia", "maryland")):
            market = "dmv"
        else:
            market = "dmv"

        # Persist to database
        db = SessionLocal()
        new_count = 0
        try:
            for comp in discovered:
                exists = (
                    db.query(Competitor)
                    .filter(Competitor.domain == comp["domain"])
                    .first()
                )
                if not exists:
                    db.add(
                        Competitor(
                            name=comp["name"],
                            domain=comp["domain"],
                            service_areas=[_area_label(area)],
                            market=market,
                            is_active=True,
                        )
                    )
                    new_count += 1
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.error("DB error persisting competitors: {}", exc)
        finally:
            db.close()

        logger.info(
            "Discovered {} competitors in {} ({} new)",
            len(discovered),
            label,
            new_count,
        )
        return discovered

    # ------------------------------------------------------------------
    # 2. analyze_competitor
    # ------------------------------------------------------------------

    def analyze_competitor(self, competitor_id: int) -> Dict[str, Any]:
        """Run a comprehensive analysis on a single competitor.

        Gathers domain authority estimate, backlink profile estimate,
        keyword rankings overlap, content analysis, Google reviews
        (rating and count), service-offerings comparison, and website
        technical quality estimate.

        Args:
            competitor_id: Primary key of the ``Competitor`` record.

        Returns:
            A dict containing every analysis dimension, or an empty dict
            if the competitor is not found.
        """
        db = SessionLocal()
        try:
            competitor = db.query(Competitor).filter(Competitor.id == competitor_id).first()
            if not competitor:
                logger.warning("Competitor id={} not found", competitor_id)
                return {}

            domain = competitor.domain
            comp_url = f"https://{domain}"
            logger.info("Analyzing competitor: {} ({})", competitor.name, domain)

            # --- Domain authority & backlink estimate ---
            da = _estimate_domain_authority(domain)
            backlink_estimate = self._estimate_backlinks(domain)

            # --- Keyword rankings overlap ---
            keyword_overlap = self._analyze_keyword_overlap(domain, db)

            # --- Content analysis ---
            content_analysis = self._analyze_content(comp_url)

            # --- Google reviews ---
            reviews = self._fetch_google_reviews(competitor.name, domain)

            # --- Service offerings ---
            services = self._extract_services(comp_url)
            our_services = self._get_our_services()
            service_comparison = {
                "competitor_services": services,
                "our_services": our_services,
                "they_have_we_dont": [s for s in services if s.lower() not in {o.lower() for o in our_services}],
                "we_have_they_dont": [s for s in our_services if s.lower() not in {o.lower() for o in services}],
            }

            # --- Technical quality estimate ---
            tech_quality = self._assess_technical_quality(comp_url)

            analysis_result: Dict[str, Any] = {
                "competitor_id": competitor_id,
                "competitor_name": competitor.name,
                "domain": domain,
                "analysis_date": datetime.date.today().isoformat(),
                "domain_authority": da,
                "backlink_profile": backlink_estimate,
                "keyword_overlap": keyword_overlap,
                "content_analysis": content_analysis,
                "google_reviews": reviews,
                "service_comparison": service_comparison,
                "technical_quality": tech_quality,
            }

            # Persist analysis snapshot
            self._save_analysis(competitor_id, analysis_result, db)

            logger.info("Analysis complete for {} (DA ~{})", competitor.name, da)
            return analysis_result

        except Exception as exc:
            logger.error("Error analysing competitor {}: {}", competitor_id, exc)
            return {}
        finally:
            db.close()

    # ------------------------------------------------------------------
    # 3. compare_keywords
    # ------------------------------------------------------------------

    def compare_keywords(self, competitor_id: int) -> Dict[str, Any]:
        """Compare keyword rankings between us and *competitor_id*.

        Identifies:
        - Keywords we both rank for (overlap)
        - Keywords they rank for but we do not (gap / opportunity)
        - Keywords we rank for but they do not (advantage)

        Returns:
            A dict with keys ``overlap``, ``their_exclusive``,
            ``our_exclusive``, and ``summary``.
        """
        db = SessionLocal()
        try:
            competitor = db.query(Competitor).filter(Competitor.id == competitor_id).first()
            if not competitor:
                logger.warning("Competitor id={} not found", competitor_id)
                return {}

            logger.info("Comparing keywords with {}", competitor.name)

            # Gather our latest rankings
            our_rankings = self._get_our_keyword_rankings(db)
            # Estimate competitor keyword rankings
            their_rankings = self._estimate_competitor_keywords(competitor.domain)

            our_kws = set(our_rankings.keys())
            their_kws = set(their_rankings.keys())

            overlap = our_kws & their_kws
            their_exclusive = their_kws - our_kws
            our_exclusive = our_kws - their_kws

            overlap_detail = []
            for kw in sorted(overlap):
                our_pos = our_rankings[kw]
                their_pos = their_rankings[kw]
                overlap_detail.append({
                    "keyword": kw,
                    "our_position": our_pos,
                    "their_position": their_pos,
                    "we_win": our_pos < their_pos if our_pos and their_pos else None,
                })

            their_exclusive_detail = [
                {"keyword": kw, "their_position": their_rankings[kw]}
                for kw in sorted(their_exclusive)
            ]

            our_exclusive_detail = [
                {"keyword": kw, "our_position": our_rankings[kw]}
                for kw in sorted(our_exclusive)
            ]

            result = {
                "competitor_id": competitor_id,
                "competitor_name": competitor.name,
                "overlap": overlap_detail,
                "their_exclusive": their_exclusive_detail,
                "our_exclusive": our_exclusive_detail,
                "summary": {
                    "total_overlap": len(overlap),
                    "keyword_gaps": len(their_exclusive),
                    "our_advantages": len(our_exclusive),
                    "top_gaps": their_exclusive_detail[:10],
                },
            }

            logger.info(
                "Keyword comparison with {}: {} overlap, {} gaps, {} advantages",
                competitor.name,
                len(overlap),
                len(their_exclusive),
                len(our_exclusive),
            )
            return result

        except Exception as exc:
            logger.error("Keyword comparison failed for competitor {}: {}", competitor_id, exc)
            return {}
        finally:
            db.close()

    # ------------------------------------------------------------------
    # 4. compare_content
    # ------------------------------------------------------------------

    def compare_content(self, competitor_id: int) -> Dict[str, Any]:
        """Compare content coverage with *competitor_id*.

        Crawls the competitor's sitemap / main pages and compares against our
        own known pages to surface topics or page types they have that we
        are missing.

        Returns:
            A dict with ``their_pages``, ``our_pages``, ``content_gaps``,
            and ``recommendations``.
        """
        db = SessionLocal()
        try:
            competitor = db.query(Competitor).filter(Competitor.id == competitor_id).first()
            if not competitor:
                logger.warning("Competitor id={} not found", competitor_id)
                return {}

            logger.info("Comparing content with {}", competitor.name)

            their_pages = self._crawl_site_pages(f"https://{competitor.domain}")
            our_pages = self._crawl_site_pages(self.our_website)

            their_topics = set()
            for page in their_pages:
                for topic in page.get("topics", []):
                    their_topics.add(topic.lower().strip())

            our_topics = set()
            for page in our_pages:
                for topic in page.get("topics", []):
                    our_topics.add(topic.lower().strip())

            content_gaps = sorted(their_topics - our_topics)
            our_unique = sorted(our_topics - their_topics)

            # Classify page types
            their_page_types = self._classify_pages(their_pages)
            our_page_types = self._classify_pages(our_pages)

            missing_page_types = {
                ptype: count
                for ptype, count in their_page_types.items()
                if count > our_page_types.get(ptype, 0)
            }

            recommendations: List[str] = []
            if missing_page_types.get("blog", 0) > 0:
                recommendations.append(
                    f"Competitor has ~{their_page_types.get('blog', 0)} blog posts vs "
                    f"our ~{our_page_types.get('blog', 0)}. Consider increasing blog output."
                )
            if missing_page_types.get("landing_page", 0) > 0:
                recommendations.append(
                    "Competitor has more location/service landing pages. "
                    "Create dedicated pages for under-served areas."
                )
            if content_gaps:
                top_gaps = content_gaps[:5]
                recommendations.append(
                    f"Top content-topic gaps to fill: {', '.join(top_gaps)}"
                )

            result = {
                "competitor_id": competitor_id,
                "competitor_name": competitor.name,
                "their_pages": their_pages,
                "our_pages": our_pages,
                "their_page_types": their_page_types,
                "our_page_types": our_page_types,
                "content_gaps": content_gaps,
                "our_unique_topics": our_unique,
                "missing_page_types": missing_page_types,
                "recommendations": recommendations,
            }

            logger.info(
                "Content comparison with {}: {} gaps found",
                competitor.name,
                len(content_gaps),
            )
            return result

        except Exception as exc:
            logger.error("Content comparison failed for competitor {}: {}", competitor_id, exc)
            return {}
        finally:
            db.close()

    # ------------------------------------------------------------------
    # 5. compare_backlinks
    # ------------------------------------------------------------------

    def compare_backlinks(self, competitor_id: int) -> Dict[str, Any]:
        """Compare backlink profiles between us and *competitor_id*.

        Identifies link sources the competitor has that we lack.

        Returns:
            A dict with ``our_backlinks``, ``their_backlinks``,
            ``link_gaps``, and ``recommendations``.
        """
        db = SessionLocal()
        try:
            competitor = db.query(Competitor).filter(Competitor.id == competitor_id).first()
            if not competitor:
                logger.warning("Competitor id={} not found", competitor_id)
                return {}

            logger.info("Comparing backlinks with {}", competitor.name)

            # Our backlinks from the database
            our_backlinks_rows = (
                db.query(Backlink)
                .filter(Backlink.is_active.is_(True))
                .all()
            )
            our_domains = {
                b.source_domain for b in our_backlinks_rows if b.source_domain
            }
            our_backlink_list = [
                {
                    "source_domain": b.source_domain,
                    "source_url": b.source_url,
                    "anchor_text": b.anchor_text,
                    "domain_authority": b.domain_authority,
                    "link_type": b.link_type,
                }
                for b in our_backlinks_rows
            ]

            # Competitor backlinks - estimate via common directories/sources
            their_backlinks = self._discover_competitor_backlinks(competitor.domain)
            their_domains = {b["source_domain"] for b in their_backlinks}

            # Gaps: domains linking to them but not to us
            gap_domains = their_domains - our_domains
            link_gaps = [b for b in their_backlinks if b["source_domain"] in gap_domains]

            # Sort gaps by estimated authority descending
            link_gaps.sort(key=lambda x: x.get("domain_authority", 0), reverse=True)

            recommendations: List[str] = []
            high_value_gaps = [g for g in link_gaps if g.get("domain_authority", 0) >= 30]
            if high_value_gaps:
                recommendations.append(
                    f"Found {len(high_value_gaps)} high-authority link gaps (DA >= 30). "
                    "Prioritize outreach to these domains."
                )
            if link_gaps:
                top_sources = [g["source_domain"] for g in link_gaps[:5]]
                recommendations.append(
                    f"Top link-gap sources to target: {', '.join(top_sources)}"
                )

            result = {
                "competitor_id": competitor_id,
                "competitor_name": competitor.name,
                "our_backlinks_count": len(our_backlinks_rows),
                "our_referring_domains": len(our_domains),
                "their_backlinks_count": len(their_backlinks),
                "their_referring_domains": len(their_domains),
                "link_gaps": link_gaps,
                "gap_count": len(link_gaps),
                "recommendations": recommendations,
            }

            logger.info(
                "Backlink comparison with {}: {} gap domains found",
                competitor.name,
                len(gap_domains),
            )
            return result

        except Exception as exc:
            logger.error("Backlink comparison failed for competitor {}: {}", competitor_id, exc)
            return {}
        finally:
            db.close()

    # ------------------------------------------------------------------
    # 6. monitor_competitor_changes
    # ------------------------------------------------------------------

    def monitor_competitor_changes(self) -> List[Dict[str, Any]]:
        """Detect significant SEO moves by all active competitors.

        Compares the latest analysis snapshot for each competitor against
        the previous one and generates alerts for:
        - New pages / content published
        - Ranking changes
        - New backlinks acquired
        - Review count or rating changes

        Returns:
            A list of alert dicts.
        """
        logger.info("Monitoring competitor changes")
        alerts: List[Dict[str, Any]] = []

        db = SessionLocal()
        try:
            competitors = (
                db.query(Competitor)
                .filter(Competitor.is_active.is_(True))
                .all()
            )

            for comp in competitors:
                analyses = (
                    db.query(CompetitorAnalysis)
                    .filter(CompetitorAnalysis.competitor_id == comp.id)
                    .order_by(desc(CompetitorAnalysis.analysis_date))
                    .limit(2)
                    .all()
                )

                if len(analyses) < 2:
                    logger.debug(
                        "Skipping {} - fewer than 2 analyses available", comp.name
                    )
                    continue

                latest = analyses[0]
                previous = analyses[1]

                comp_alerts = self._detect_changes(comp, latest, previous)
                for alert_data in comp_alerts:
                    alert = Alert(
                        alert_type="competitor_change",
                        severity=alert_data["severity"],
                        title=alert_data["title"],
                        message=alert_data["message"],
                        data=alert_data.get("data"),
                    )
                    db.add(alert)
                    alerts.append(alert_data)

            db.commit()
        except Exception as exc:
            db.rollback()
            logger.error("Error monitoring competitor changes: {}", exc)
        finally:
            db.close()

        logger.info("Competitor monitoring complete: {} alerts generated", len(alerts))
        return alerts

    # ------------------------------------------------------------------
    # 7. identify_weaknesses
    # ------------------------------------------------------------------

    def identify_weaknesses(self, competitor_id: int) -> Dict[str, Any]:
        """Identify exploitable weaknesses for *competitor_id*.

        Checks for:
        - Thin content on key pages
        - Geographic areas they do not serve well
        - Negative reviews / common complaints
        - Technical SEO problems
        - Missing schema markup

        Returns:
            A dict grouping weaknesses by category with recommendations.
        """
        db = SessionLocal()
        try:
            competitor = db.query(Competitor).filter(Competitor.id == competitor_id).first()
            if not competitor:
                logger.warning("Competitor id={} not found", competitor_id)
                return {}

            logger.info("Identifying weaknesses for {}", competitor.name)
            comp_url = f"https://{competitor.domain}"

            # --- Thin content ---
            thin_content = self._find_thin_content(comp_url)

            # --- Locations not served well ---
            underserved = self._find_underserved_areas(competitor)

            # --- Negative reviews ---
            negative_reviews = self._find_negative_reviews(competitor.name, competitor.domain)

            # --- Technical issues ---
            tech_issues = self._find_technical_issues(comp_url)

            # --- Missing schema ---
            schema_issues = self._check_schema_markup(comp_url)

            # --- Build recommendations ---
            recommendations: List[str] = []
            if thin_content:
                recommendations.append(
                    f"Competitor has {len(thin_content)} pages with thin content. "
                    "Create in-depth content on the same topics to outrank them."
                )
            if underserved:
                areas_str = ", ".join(underserved[:5])
                recommendations.append(
                    f"Competitor is weak in these areas: {areas_str}. "
                    "Create geo-specific landing pages to capture local traffic."
                )
            if negative_reviews:
                common_complaints = list({r.get("theme", "") for r in negative_reviews if r.get("theme")})
                if common_complaints:
                    recommendations.append(
                        "Common competitor complaints: "
                        + ", ".join(common_complaints[:3])
                        + ". Highlight our strengths in these areas."
                    )
            if tech_issues:
                recommendations.append(
                    f"Competitor has {len(tech_issues)} technical SEO issues. "
                    "Ensure our site is technically superior."
                )
            if schema_issues.get("missing_types"):
                recommendations.append(
                    "Competitor is missing schema types: "
                    + ", ".join(schema_issues["missing_types"])
                    + ". Ensure ours are implemented for a competitive edge."
                )

            result = {
                "competitor_id": competitor_id,
                "competitor_name": competitor.name,
                "weaknesses": {
                    "thin_content": thin_content,
                    "underserved_areas": underserved,
                    "negative_reviews": negative_reviews,
                    "technical_issues": tech_issues,
                    "schema_issues": schema_issues,
                },
                "recommendations": recommendations,
                "weakness_score": self._calculate_weakness_score(
                    thin_content, underserved, negative_reviews, tech_issues, schema_issues
                ),
            }

            logger.info(
                "Weakness analysis for {}: score={}/100",
                competitor.name,
                result["weakness_score"],
            )
            return result

        except Exception as exc:
            logger.error("Weakness analysis failed for competitor {}: {}", competitor_id, exc)
            return {}
        finally:
            db.close()

    # ------------------------------------------------------------------
    # 8. get_market_overview
    # ------------------------------------------------------------------

    def get_market_overview(self, area: Dict[str, str]) -> Dict[str, Any]:
        """Return a competitive-landscape snapshot for *area*.

        Includes competitor count, average domain authority, review
        landscape, keyword-density summary, and a market-difficulty
        rating.
        """
        label = _area_label(area)
        logger.info("Generating market overview for {}", label)

        db = SessionLocal()
        try:
            region = area.get("region", "").lower()
            if "southwest" in region or "swva" in region:
                market_key = "swva"
            else:
                market_key = "dmv"

            competitors = (
                db.query(Competitor)
                .filter(Competitor.is_active.is_(True), Competitor.market == market_key)
                .all()
            )

            comp_summaries: List[Dict[str, Any]] = []
            total_da = 0
            total_reviews = 0
            rating_sum = 0.0
            rated_count = 0

            for comp in competitors:
                latest = (
                    db.query(CompetitorAnalysis)
                    .filter(CompetitorAnalysis.competitor_id == comp.id)
                    .order_by(desc(CompetitorAnalysis.analysis_date))
                    .first()
                )
                da = latest.domain_authority if latest and latest.domain_authority else 0
                reviews = latest.total_reviews if latest and latest.total_reviews else 0
                rating = latest.google_rating if latest and latest.google_rating else None

                total_da += da
                total_reviews += reviews
                if rating is not None:
                    rating_sum += rating
                    rated_count += 1

                comp_summaries.append({
                    "name": comp.name,
                    "domain": comp.domain,
                    "domain_authority": da,
                    "total_reviews": reviews,
                    "google_rating": rating,
                })

            count = len(competitors)
            avg_da = round(total_da / count, 1) if count else 0
            avg_rating = round(rating_sum / rated_count, 2) if rated_count else None
            avg_reviews = round(total_reviews / count) if count else 0

            # Market difficulty: simple heuristic
            if avg_da >= 40 and count >= 10:
                difficulty = "high"
            elif avg_da >= 25 or count >= 6:
                difficulty = "medium"
            else:
                difficulty = "low"

            result = {
                "area": label,
                "market": market_key,
                "competitor_count": count,
                "competitors": comp_summaries,
                "average_domain_authority": avg_da,
                "average_google_rating": avg_rating,
                "average_review_count": avg_reviews,
                "total_reviews_in_market": total_reviews,
                "market_difficulty": difficulty,
                "generated_at": datetime.datetime.utcnow().isoformat(),
            }

            logger.info(
                "Market overview for {}: {} competitors, avg DA {}, difficulty={}",
                label,
                count,
                avg_da,
                difficulty,
            )
            return result

        except Exception as exc:
            logger.error("Market overview failed for {}: {}", label, exc)
            return {}
        finally:
            db.close()

    # ------------------------------------------------------------------
    # 9. get_competitor_report
    # ------------------------------------------------------------------

    def get_competitor_report(self) -> Dict[str, Any]:
        """Generate a comprehensive competitor-intelligence report.

        Aggregates data across all active competitors and produces:
        - Executive summary
        - Per-competitor scorecards
        - Keyword gap highlights
        - Content gap highlights
        - Backlink gap highlights
        - Prioritized action items
        """
        logger.info("Generating comprehensive competitor report")

        db = SessionLocal()
        try:
            competitors = (
                db.query(Competitor)
                .filter(Competitor.is_active.is_(True))
                .all()
            )

            scorecards: List[Dict[str, Any]] = []
            all_keyword_gaps: List[str] = []
            all_content_gaps: List[str] = []
            all_link_gaps: List[Dict[str, Any]] = []
            action_items: List[Dict[str, Any]] = []

            for comp in competitors:
                latest: Optional[CompetitorAnalysis] = (
                    db.query(CompetitorAnalysis)
                    .filter(CompetitorAnalysis.competitor_id == comp.id)
                    .order_by(desc(CompetitorAnalysis.analysis_date))
                    .first()
                )

                da = latest.domain_authority if latest else None
                reviews = latest.total_reviews if latest else None
                rating = latest.google_rating if latest else None
                kw_gaps = latest.keyword_gaps if latest and latest.keyword_gaps else []
                ct_gaps = latest.content_gaps if latest and latest.content_gaps else []
                strengths = latest.strengths if latest and latest.strengths else []
                weaknesses = latest.weaknesses if latest and latest.weaknesses else []

                seo_score = self._compute_seo_strength(latest)

                scorecards.append({
                    "competitor_id": comp.id,
                    "name": comp.name,
                    "domain": comp.domain,
                    "market": comp.market,
                    "domain_authority": da,
                    "total_reviews": reviews,
                    "google_rating": rating,
                    "seo_strength_score": seo_score,
                    "strengths": strengths,
                    "weaknesses": weaknesses,
                })

                all_keyword_gaps.extend(kw_gaps if isinstance(kw_gaps, list) else [])
                all_content_gaps.extend(ct_gaps if isinstance(ct_gaps, list) else [])

            # Deduplicate gaps
            unique_keyword_gaps = sorted(set(all_keyword_gaps))
            unique_content_gaps = sorted(set(all_content_gaps))

            # Build action items from most common gaps
            kw_gap_counts = defaultdict(int)
            for kw in all_keyword_gaps:
                kw_gap_counts[kw] += 1
            top_kw_gaps = sorted(kw_gap_counts.items(), key=lambda x: x[1], reverse=True)[:10]

            for kw, count in top_kw_gaps:
                action_items.append({
                    "type": "keyword_gap",
                    "priority": "high" if count >= 2 else "medium",
                    "action": f"Create or optimize content targeting '{kw}' "
                              f"({count} competitors rank for this).",
                })

            if unique_content_gaps:
                for topic in unique_content_gaps[:5]:
                    action_items.append({
                        "type": "content_gap",
                        "priority": "medium",
                        "action": f"Develop content covering: {topic}",
                    })

            # Sort scorecards by strength
            scorecards.sort(key=lambda s: s["seo_strength_score"], reverse=True)

            # Executive summary
            strongest = scorecards[0] if scorecards else None
            summary_parts = [
                f"Tracking {len(competitors)} active competitors.",
            ]
            if strongest:
                summary_parts.append(
                    f"Strongest competitor: {strongest['name']} "
                    f"(SEO score {strongest['seo_strength_score']}/100)."
                )
            summary_parts.append(
                f"Identified {len(unique_keyword_gaps)} unique keyword gaps "
                f"and {len(unique_content_gaps)} content-topic gaps."
            )

            report = {
                "report_date": datetime.date.today().isoformat(),
                "executive_summary": " ".join(summary_parts),
                "competitor_count": len(competitors),
                "scorecards": scorecards,
                "keyword_gaps": unique_keyword_gaps,
                "content_gaps": unique_content_gaps,
                "link_gaps": all_link_gaps,
                "action_items": action_items,
                "generated_at": datetime.datetime.utcnow().isoformat(),
            }

            logger.info(
                "Competitor report generated: {} competitors, {} action items",
                len(competitors),
                len(action_items),
            )
            return report

        except Exception as exc:
            logger.error("Competitor report generation failed: {}", exc)
            return {}
        finally:
            db.close()

    # ------------------------------------------------------------------
    # 10. rank_competitors
    # ------------------------------------------------------------------

    def rank_competitors(self, area: Dict[str, str]) -> List[Dict[str, Any]]:
        """Rank all competitors in *area* by an SEO-strength composite score.

        The score (0-100) blends domain authority, backlink profile, keyword
        coverage, review strength, and content quality estimates.

        Returns:
            A list of dicts sorted by ``seo_strength_score`` descending.
        """
        label = _area_label(area)
        logger.info("Ranking competitors in {}", label)

        db = SessionLocal()
        try:
            region = area.get("region", "").lower()
            if "southwest" in region or "swva" in region:
                market_key = "swva"
            else:
                market_key = "dmv"

            competitors = (
                db.query(Competitor)
                .filter(Competitor.is_active.is_(True), Competitor.market == market_key)
                .all()
            )

            ranked: List[Dict[str, Any]] = []
            for comp in competitors:
                latest: Optional[CompetitorAnalysis] = (
                    db.query(CompetitorAnalysis)
                    .filter(CompetitorAnalysis.competitor_id == comp.id)
                    .order_by(desc(CompetitorAnalysis.analysis_date))
                    .first()
                )

                seo_score = self._compute_seo_strength(latest)

                ranked.append({
                    "competitor_id": comp.id,
                    "name": comp.name,
                    "domain": comp.domain,
                    "seo_strength_score": seo_score,
                    "domain_authority": latest.domain_authority if latest else None,
                    "total_backlinks": latest.total_backlinks if latest else None,
                    "organic_keywords": latest.organic_keywords if latest else None,
                    "total_reviews": latest.total_reviews if latest else None,
                    "google_rating": latest.google_rating if latest else None,
                })

            ranked.sort(key=lambda r: r["seo_strength_score"], reverse=True)

            # Assign ordinal rank
            for idx, entry in enumerate(ranked, start=1):
                entry["rank"] = idx

            logger.info(
                "Ranked {} competitors in {}; top={} (score {})",
                len(ranked),
                label,
                ranked[0]["name"] if ranked else "N/A",
                ranked[0]["seo_strength_score"] if ranked else 0,
            )
            return ranked

        except Exception as exc:
            logger.error("Competitor ranking failed for {}: {}", label, exc)
            return []
        finally:
            db.close()

    # ==================================================================
    # Internal / private helper methods
    # ==================================================================

    def _estimate_backlinks(self, domain: str) -> Dict[str, Any]:
        """Return a rough backlink-profile estimate for *domain*."""
        # Check for links from well-known directories / sources
        known_sources = [
            "yelp.com", "bbb.org", "yellowpages.com", "superpages.com",
            "manta.com", "chamberofcommerce.com", "notary.net",
            "123notary.com", "notarycafe.com", "signingagent.com",
        ]
        found_sources: List[str] = []
        for source in known_sources:
            search_query = f"site:{source} {domain}"
            results = _google_custom_search(search_query, num=3)
            if not results:
                results = _scrape_serp_results(search_query, num=5)
                time.sleep(1)
            if results:
                found_sources.append(source)

        return {
            "estimated_referring_domains": len(found_sources) * 3,  # rough multiplier
            "known_directory_links": found_sources,
            "estimated_total_backlinks": len(found_sources) * 8,
        }

    def _analyze_keyword_overlap(
        self,
        competitor_domain: str,
        db: Any,
    ) -> Dict[str, Any]:
        """Compare tracked keyword rankings with competitor visibility."""
        our_keywords: List[str] = []
        rows = db.query(Keyword).filter(Keyword.is_active.is_(True)).all()
        for row in rows:
            our_keywords.append(row.keyword)

        overlap_keywords: List[str] = []
        competitor_only: List[str] = []

        sample_keywords = our_keywords[:30]  # limit to avoid rate-limit issues
        for kw in sample_keywords:
            results = _google_custom_search(f"{kw}", num=10)
            if not results:
                results = _scrape_serp_results(kw, num=10)
                time.sleep(1)

            found_us = False
            found_them = False
            for r in results:
                rd = extract_domain(r.get("link", ""))
                if rd == self.our_domain:
                    found_us = True
                if rd == competitor_domain:
                    found_them = True

            if found_us and found_them:
                overlap_keywords.append(kw)
            elif found_them and not found_us:
                competitor_only.append(kw)

        return {
            "overlap_count": len(overlap_keywords),
            "overlap_keywords": overlap_keywords,
            "competitor_only_count": len(competitor_only),
            "competitor_only_keywords": competitor_only,
        }

    def _analyze_content(self, base_url: str) -> Dict[str, Any]:
        """Analyze content on the competitor's site."""
        pages = self._crawl_site_pages(base_url)
        blog_pages = [p for p in pages if p.get("type") == "blog"]
        service_pages = [p for p in pages if p.get("type") == "service"]
        landing_pages = [p for p in pages if p.get("type") == "landing_page"]

        total_word_count = sum(p.get("word_count", 0) for p in pages)
        avg_word_count = round(total_word_count / len(pages)) if pages else 0

        return {
            "total_pages": len(pages),
            "blog_posts": len(blog_pages),
            "service_pages": len(service_pages),
            "landing_pages": len(landing_pages),
            "average_word_count": avg_word_count,
            "pages": pages[:50],  # cap for storage
        }

    def _fetch_google_reviews(
        self, business_name: str, domain: str
    ) -> Dict[str, Any]:
        """Attempt to retrieve Google review data for a competitor."""
        query = f"{business_name} reviews"
        results = _google_custom_search(query, num=5)
        if not results:
            results = _scrape_serp_results(query, num=5)

        rating: Optional[float] = None
        count: Optional[int] = None

        for item in results:
            snippet = item.get("snippet", "")
            # Try to extract rating pattern like "4.8 stars" or "Rating: 4.8"
            rating_match = re.search(r'(\d\.\d)\s*(?:star|rating|out of)', snippet, re.I)
            count_match = re.search(r'(\d[\d,]*)\s*(?:review|rating)', snippet, re.I)
            if rating_match and rating is None:
                rating = float(rating_match.group(1))
            if count_match and count is None:
                count = int(count_match.group(1).replace(",", ""))

        return {
            "google_rating": rating,
            "review_count": count,
        }

    def _extract_services(self, base_url: str) -> List[str]:
        """Extract service names from a competitor's website."""
        services: List[str] = []
        resp = _safe_get(base_url, timeout=15)
        if resp is None:
            return services

        soup = BeautifulSoup(resp.text, "html.parser")

        service_keywords = [
            "notary", "apostille", "mobile notary", "loan signing",
            "real estate closing", "power of attorney", "document authentication",
            "embassy legalization", "remote online notarization",
            "certified translation", "foreign document", "hospital notary",
        ]

        text = soup.get_text(" ", strip=True).lower()
        for svc in service_keywords:
            if svc in text:
                services.append(svc.title())

        # Check navigation links for more service pages
        for a in soup.find_all("a", href=True):
            link_text = a.get_text(strip=True).lower()
            for svc in service_keywords:
                if svc in link_text and svc.title() not in services:
                    services.append(svc.title())

        return sorted(set(services))

    def _get_our_services(self) -> List[str]:
        """Return the list of services we offer (from site or hardcoded)."""
        services = self._extract_services(self.our_website)
        if not services:
            # Fallback from config keywords
            services = [
                "Notary Public", "Mobile Notary", "Apostille Services",
                "Document Authentication", "Embassy Legalization",
                "Power Of Attorney", "Loan Signing",
                "Real Estate Closing", "Foreign Document Notarization",
                "Certified Translation Notarization", "Remote Online Notarization",
            ]
        return services

    def _assess_technical_quality(self, url: str) -> Dict[str, Any]:
        """Assess the technical SEO quality of a competitor site."""
        issues: List[str] = []
        checks: Dict[str, bool] = {}

        resp = _safe_get(url, timeout=15)
        if resp is None:
            return {"score": 0, "issues": ["Site unreachable"], "checks": {}}

        # HTTPS
        checks["https"] = resp.url.startswith("https://")
        if not checks["https"]:
            issues.append("Site does not use HTTPS")

        soup = BeautifulSoup(resp.text, "html.parser")

        # Title tag
        checks["has_title"] = soup.title is not None and len(soup.title.string or "") > 0
        if not checks["has_title"]:
            issues.append("Missing or empty title tag")

        # Meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        checks["has_meta_description"] = meta_desc is not None
        if not checks["has_meta_description"]:
            issues.append("Missing meta description")

        # H1 tag
        h1s = soup.find_all("h1")
        checks["has_h1"] = len(h1s) > 0
        checks["single_h1"] = len(h1s) == 1
        if not checks["has_h1"]:
            issues.append("No H1 tag found")
        elif not checks["single_h1"]:
            issues.append(f"Multiple H1 tags found ({len(h1s)})")

        # Viewport meta (mobile-friendly indicator)
        viewport = soup.find("meta", attrs={"name": "viewport"})
        checks["has_viewport"] = viewport is not None
        if not checks["has_viewport"]:
            issues.append("Missing viewport meta tag (not mobile-optimized)")

        # Schema / structured data
        ld_json = soup.find_all("script", attrs={"type": "application/ld+json"})
        checks["has_schema"] = len(ld_json) > 0
        if not checks["has_schema"]:
            issues.append("No JSON-LD structured data found")

        # Images without alt
        images = soup.find_all("img")
        imgs_no_alt = [img for img in images if not img.get("alt")]
        checks["all_images_have_alt"] = len(imgs_no_alt) == 0
        if imgs_no_alt:
            issues.append(f"{len(imgs_no_alt)} images missing alt text")

        # Robots.txt
        robots_resp = _safe_get(urljoin(url, "/robots.txt"), timeout=10)
        checks["has_robots_txt"] = robots_resp is not None and robots_resp.status_code == 200

        # Sitemap
        sitemap_resp = _safe_get(urljoin(url, "/sitemap.xml"), timeout=10)
        checks["has_sitemap"] = sitemap_resp is not None and sitemap_resp.status_code == 200
        if not checks["has_sitemap"]:
            issues.append("No sitemap.xml found")

        # Page load size
        page_size_kb = len(resp.content) / 1024
        checks["reasonable_page_size"] = page_size_kb < 3000
        if not checks["reasonable_page_size"]:
            issues.append(f"Large page size: {page_size_kb:.0f} KB")

        passed = sum(1 for v in checks.values() if v)
        total = len(checks)
        score = round(passed / total * 100, 1) if total else 0

        return {
            "score": score,
            "passed": passed,
            "total_checks": total,
            "checks": checks,
            "issues": issues,
        }

    def _crawl_site_pages(self, base_url: str, max_pages: int = 50) -> List[Dict[str, Any]]:
        """Crawl a site starting from *base_url* and return page metadata.

        Follows internal links up to *max_pages*.
        """
        domain = extract_domain(base_url)
        visited: set[str] = set()
        to_visit: List[str] = [base_url]
        pages: List[Dict[str, Any]] = []

        while to_visit and len(pages) < max_pages:
            url = to_visit.pop(0)
            normalized = normalize_url(url)
            if normalized in visited:
                continue
            visited.add(normalized)

            resp = _safe_get(url, timeout=15)
            if resp is None:
                continue

            soup = BeautifulSoup(resp.text, "html.parser")

            title = soup.title.string.strip() if soup.title and soup.title.string else ""
            headings = [h.get_text(strip=True) for h in soup.find_all(["h1", "h2", "h3"])]
            word_count = len(soup.get_text(strip=True).split())

            page_type = self._classify_single_page(url, title, headings)

            pages.append({
                "url": url,
                "title": title,
                "type": page_type,
                "word_count": word_count,
                "topics": headings,
            })

            # Discover internal links
            for a in soup.find_all("a", href=True):
                href = urljoin(url, a["href"])
                href_domain = extract_domain(href)
                if href_domain == domain and normalize_url(href) not in visited:
                    to_visit.append(href)

        return pages

    def _classify_single_page(
        self, url: str, title: str, headings: List[str]
    ) -> str:
        """Heuristically classify a page as blog, service, landing, or other."""
        url_lower = url.lower()
        title_lower = title.lower()

        if any(kw in url_lower for kw in ("/blog", "/post", "/article", "/news")):
            return "blog"
        if any(kw in url_lower for kw in ("/service", "/notary", "/apostille", "/pricing")):
            return "service"
        if any(
            kw in url_lower
            for kw in (
                "/location", "/area", "/city", "/county",
                "near-me", "near_me",
            )
        ):
            return "landing_page"
        if any(kw in title_lower for kw in ("blog", "article", "news", "post")):
            return "blog"
        if any(
            kw in title_lower
            for kw in ("service", "notary", "apostille", "pricing", "cost")
        ):
            return "service"
        return "other"

    def _classify_pages(
        self, pages: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """Count pages by type."""
        counts: Dict[str, int] = defaultdict(int)
        for p in pages:
            counts[p.get("type", "other")] += 1
        return dict(counts)

    def _get_our_keyword_rankings(self, db: Any) -> Dict[str, Optional[int]]:
        """Retrieve the latest ranking position for each tracked keyword."""
        rankings: Dict[str, Optional[int]] = {}
        keywords = db.query(Keyword).filter(Keyword.is_active.is_(True)).all()
        for kw in keywords:
            latest_rank = (
                db.query(KeywordRanking)
                .filter(
                    KeywordRanking.keyword_id == kw.id,
                    KeywordRanking.search_engine == "google",
                )
                .order_by(desc(KeywordRanking.tracked_date))
                .first()
            )
            rankings[kw.keyword] = latest_rank.position if latest_rank else None
        return rankings

    def _estimate_competitor_keywords(
        self, domain: str
    ) -> Dict[str, Optional[int]]:
        """Estimate which of our tracked keywords the competitor ranks for."""
        rankings: Dict[str, Optional[int]] = {}
        db = SessionLocal()
        try:
            keywords = db.query(Keyword).filter(Keyword.is_active.is_(True)).all()
            sample = keywords[:30]

            for kw in sample:
                results = _google_custom_search(kw.keyword, num=10)
                if not results:
                    results = _scrape_serp_results(kw.keyword, num=10)
                    time.sleep(1)

                for idx, r in enumerate(results, start=1):
                    rd = extract_domain(r.get("link", ""))
                    if rd == domain:
                        rankings[kw.keyword] = idx
                        break
        finally:
            db.close()
        return rankings

    def _discover_competitor_backlinks(
        self, domain: str
    ) -> List[Dict[str, Any]]:
        """Discover backlinks pointing to *domain* via search heuristics."""
        backlinks: List[Dict[str, Any]] = []
        seen: set[str] = set()

        queries = [
            f'link:{domain}',
            f'"{domain}" -site:{domain}',
            f'intext:"{domain}" notary apostille',
        ]
        for query in queries:
            results = _google_custom_search(query, num=10)
            if not results:
                results = _scrape_serp_results(query, num=10)
                time.sleep(1)

            for r in results:
                src_domain = extract_domain(r.get("link", ""))
                if src_domain and src_domain != domain and src_domain not in seen:
                    seen.add(src_domain)
                    backlinks.append({
                        "source_domain": src_domain,
                        "source_url": r.get("link", ""),
                        "anchor_text": r.get("title", ""),
                        "domain_authority": _estimate_domain_authority(src_domain),
                    })

        return backlinks

    def _detect_changes(
        self,
        competitor: Competitor,
        latest: CompetitorAnalysis,
        previous: CompetitorAnalysis,
    ) -> List[Dict[str, Any]]:
        """Compare two analysis snapshots and return alert dicts."""
        alerts: List[Dict[str, Any]] = []

        # Ranking change
        if latest.organic_keywords and previous.organic_keywords:
            diff = (latest.organic_keywords or 0) - (previous.organic_keywords or 0)
            if abs(diff) >= 5:
                direction = "gained" if diff > 0 else "lost"
                alerts.append({
                    "severity": "warning" if diff > 0 else "info",
                    "title": f"{competitor.name} {direction} keyword rankings",
                    "message": (
                        f"{competitor.name} {direction} {abs(diff)} organic keyword "
                        f"rankings since the last analysis."
                    ),
                    "data": {
                        "competitor_id": competitor.id,
                        "change_type": "keyword_rankings",
                        "previous": previous.organic_keywords,
                        "current": latest.organic_keywords,
                    },
                })

        # Backlink change
        if latest.total_backlinks and previous.total_backlinks:
            bl_diff = (latest.total_backlinks or 0) - (previous.total_backlinks or 0)
            if bl_diff >= 5:
                alerts.append({
                    "severity": "warning",
                    "title": f"{competitor.name} acquired new backlinks",
                    "message": (
                        f"{competitor.name} gained ~{bl_diff} backlinks since "
                        f"the last analysis."
                    ),
                    "data": {
                        "competitor_id": competitor.id,
                        "change_type": "backlinks",
                        "previous": previous.total_backlinks,
                        "current": latest.total_backlinks,
                    },
                })

        # Review changes
        if latest.total_reviews and previous.total_reviews:
            rev_diff = (latest.total_reviews or 0) - (previous.total_reviews or 0)
            if rev_diff >= 3:
                alerts.append({
                    "severity": "info",
                    "title": f"{competitor.name} received new reviews",
                    "message": (
                        f"{competitor.name} gained {rev_diff} new Google reviews "
                        f"(now {latest.total_reviews} total, "
                        f"rating {latest.google_rating})."
                    ),
                    "data": {
                        "competitor_id": competitor.id,
                        "change_type": "reviews",
                        "previous_count": previous.total_reviews,
                        "current_count": latest.total_reviews,
                        "previous_rating": previous.google_rating,
                        "current_rating": latest.google_rating,
                    },
                })

        # Rating drop (opportunity for us)
        if latest.google_rating and previous.google_rating:
            rating_diff = (latest.google_rating or 0) - (previous.google_rating or 0)
            if rating_diff <= -0.3:
                alerts.append({
                    "severity": "info",
                    "title": f"{competitor.name} rating dropped",
                    "message": (
                        f"{competitor.name}'s Google rating dropped from "
                        f"{previous.google_rating} to {latest.google_rating}."
                    ),
                    "data": {
                        "competitor_id": competitor.id,
                        "change_type": "rating_drop",
                        "previous_rating": previous.google_rating,
                        "current_rating": latest.google_rating,
                    },
                })

        # New content
        prev_content = previous.recent_content if previous.recent_content else []
        curr_content = latest.recent_content if latest.recent_content else []
        prev_urls = {c.get("url") for c in prev_content if isinstance(c, dict)}
        new_pages = [c for c in curr_content if isinstance(c, dict) and c.get("url") not in prev_urls]
        if new_pages:
            alerts.append({
                "severity": "warning",
                "title": f"{competitor.name} published new content",
                "message": (
                    f"{competitor.name} published {len(new_pages)} new page(s): "
                    + ", ".join(p.get("title", p.get("url", "unknown")) for p in new_pages[:3])
                ),
                "data": {
                    "competitor_id": competitor.id,
                    "change_type": "new_content",
                    "new_pages": new_pages[:10],
                },
            })

        return alerts

    def _find_thin_content(self, base_url: str) -> List[Dict[str, Any]]:
        """Find pages on the competitor site with thin content (<300 words)."""
        pages = self._crawl_site_pages(base_url, max_pages=30)
        thin: List[Dict[str, Any]] = []
        for page in pages:
            if page.get("word_count", 0) < 300:
                thin.append({
                    "url": page["url"],
                    "title": page.get("title", ""),
                    "word_count": page.get("word_count", 0),
                })
        return thin

    def _find_underserved_areas(
        self, competitor: Competitor
    ) -> List[str]:
        """Return service areas where the competitor has weak coverage."""
        all_areas = []
        for tier_areas in SERVICE_AREAS.values():
            all_areas.extend(tier_areas)

        competitor_areas = competitor.service_areas or []
        competitor_areas_lower = [a.lower() for a in competitor_areas]

        underserved: List[str] = []
        comp_url = f"https://{competitor.domain}"
        resp = _safe_get(comp_url, timeout=15)
        site_text = ""
        if resp is not None:
            site_text = BeautifulSoup(resp.text, "html.parser").get_text(" ", strip=True).lower()

        for area in all_areas:
            label = _area_label(area).lower()
            city = area.get("city", "").lower()
            if label not in competitor_areas_lower and city not in site_text:
                underserved.append(_area_label(area))

        return underserved

    def _find_negative_reviews(
        self, business_name: str, domain: str
    ) -> List[Dict[str, Any]]:
        """Search for negative review signals about a competitor."""
        negative: List[Dict[str, Any]] = []
        queries = [
            f'"{business_name}" review complaint',
            f'"{business_name}" bad experience',
            f'"{domain}" 1 star review',
        ]

        for query in queries:
            results = _google_custom_search(query, num=5)
            if not results:
                results = _scrape_serp_results(query, num=5)
                time.sleep(1)

            for r in results:
                snippet = r.get("snippet", "").lower()
                themes: List[str] = []
                if any(w in snippet for w in ("slow", "late", "wait", "delay")):
                    themes.append("slow service")
                if any(w in snippet for w in ("rude", "unprofessional", "attitude")):
                    themes.append("unprofessional")
                if any(w in snippet for w in ("expensive", "overcharge", "price", "cost")):
                    themes.append("pricing concerns")
                if any(w in snippet for w in ("error", "mistake", "wrong", "incorrect")):
                    themes.append("errors/mistakes")

                if themes:
                    negative.append({
                        "source": r.get("link", ""),
                        "snippet": r.get("snippet", ""),
                        "theme": themes[0],
                        "all_themes": themes,
                    })

        return negative

    def _find_technical_issues(self, url: str) -> List[str]:
        """Return a list of technical SEO issues on a competitor site."""
        quality = self._assess_technical_quality(url)
        return quality.get("issues", [])

    def _check_schema_markup(self, url: str) -> Dict[str, Any]:
        """Check for missing schema types on a competitor site."""
        resp = _safe_get(url, timeout=15)
        found_types: List[str] = []

        if resp is not None:
            soup = BeautifulSoup(resp.text, "html.parser")
            for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
                try:
                    import json
                    data = json.loads(script.string or "{}")
                    if isinstance(data, dict):
                        found_types.append(data.get("@type", "Unknown"))
                    elif isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict):
                                found_types.append(item.get("@type", "Unknown"))
                except (json.JSONDecodeError, TypeError):
                    pass

        recommended = [
            "LocalBusiness", "ProfessionalService", "NotaryService",
            "FAQPage", "BreadcrumbList", "WebSite",
        ]
        missing = [t for t in recommended if t not in found_types]

        return {
            "found_types": found_types,
            "missing_types": missing,
            "has_any_schema": len(found_types) > 0,
        }

    def _calculate_weakness_score(
        self,
        thin_content: List[Any],
        underserved: List[str],
        negative_reviews: List[Any],
        tech_issues: List[str],
        schema_issues: Dict[str, Any],
    ) -> int:
        """Calculate a 0-100 weakness score (higher = more weaknesses)."""
        score = 0
        # Thin content: up to 25 points
        score += min(len(thin_content) * 5, 25)
        # Underserved areas: up to 25 points
        score += min(len(underserved) * 3, 25)
        # Negative reviews: up to 20 points
        score += min(len(negative_reviews) * 5, 20)
        # Technical issues: up to 15 points
        score += min(len(tech_issues) * 3, 15)
        # Schema gaps: up to 15 points
        missing_count = len(schema_issues.get("missing_types", []))
        score += min(missing_count * 3, 15)

        return min(score, 100)

    def _save_analysis(
        self,
        competitor_id: int,
        analysis: Dict[str, Any],
        db: Any,
    ) -> None:
        """Persist an analysis snapshot to the database."""
        try:
            keyword_data = analysis.get("keyword_overlap", {})
            content_data = analysis.get("content_analysis", {})
            reviews_data = analysis.get("google_reviews", {})
            backlink_data = analysis.get("backlink_profile", {})
            tech_data = analysis.get("technical_quality", {})

            record = CompetitorAnalysis(
                competitor_id=competitor_id,
                analysis_date=datetime.date.today(),
                domain_authority=analysis.get("domain_authority"),
                total_backlinks=backlink_data.get("estimated_total_backlinks"),
                referring_domains=backlink_data.get("estimated_referring_domains"),
                organic_keywords=keyword_data.get("overlap_count", 0)
                + keyword_data.get("competitor_only_count", 0),
                estimated_traffic=None,
                google_rating=reviews_data.get("google_rating"),
                total_reviews=reviews_data.get("review_count"),
                top_keywords=keyword_data.get("overlap_keywords", []),
                recent_content=content_data.get("pages", [])[:20],
                keyword_gaps=keyword_data.get("competitor_only_keywords", []),
                content_gaps=[],
                strengths=self._derive_strengths(analysis),
                weaknesses=self._derive_weaknesses(analysis),
            )
            db.add(record)
            db.commit()
            logger.debug("Saved analysis for competitor_id={}", competitor_id)
        except Exception as exc:
            db.rollback()
            logger.error("Failed to save analysis for competitor {}: {}", competitor_id, exc)

    def _derive_strengths(self, analysis: Dict[str, Any]) -> List[str]:
        """Derive competitor strengths from analysis data."""
        strengths: List[str] = []
        da = analysis.get("domain_authority", 0)
        if da >= 40:
            strengths.append(f"High domain authority ({da})")
        elif da >= 25:
            strengths.append(f"Moderate domain authority ({da})")

        reviews = analysis.get("google_reviews", {})
        if reviews.get("google_rating") and reviews["google_rating"] >= 4.5:
            strengths.append(f"Excellent Google rating ({reviews['google_rating']})")
        if reviews.get("review_count") and reviews["review_count"] >= 50:
            strengths.append(f"Strong review presence ({reviews['review_count']} reviews)")

        content = analysis.get("content_analysis", {})
        if content.get("blog_posts", 0) >= 10:
            strengths.append(f"Active blog ({content['blog_posts']} posts)")
        if content.get("total_pages", 0) >= 20:
            strengths.append(f"Large site ({content['total_pages']} pages)")

        tech = analysis.get("technical_quality", {})
        if tech.get("score", 0) >= 80:
            strengths.append(f"Good technical quality (score {tech['score']})")

        return strengths

    def _derive_weaknesses(self, analysis: Dict[str, Any]) -> List[str]:
        """Derive competitor weaknesses from analysis data."""
        weaknesses: List[str] = []
        da = analysis.get("domain_authority", 0)
        if da < 15:
            weaknesses.append(f"Low domain authority ({da})")

        reviews = analysis.get("google_reviews", {})
        if reviews.get("google_rating") and reviews["google_rating"] < 4.0:
            weaknesses.append(f"Below-average Google rating ({reviews['google_rating']})")
        if reviews.get("review_count") and reviews["review_count"] < 10:
            weaknesses.append(f"Few reviews ({reviews['review_count']})")

        content = analysis.get("content_analysis", {})
        if content.get("total_pages", 0) < 5:
            weaknesses.append("Very small website")
        if content.get("average_word_count", 0) < 300:
            weaknesses.append(f"Thin content (avg {content.get('average_word_count', 0)} words)")

        tech = analysis.get("technical_quality", {})
        if tech.get("score", 0) < 50:
            weaknesses.append(f"Poor technical quality (score {tech['score']})")
        for issue in tech.get("issues", [])[:3]:
            weaknesses.append(issue)

        svc = analysis.get("service_comparison", {})
        missing = svc.get("we_have_they_dont", [])
        if missing:
            weaknesses.append(
                f"Missing services we offer: {', '.join(missing[:3])}"
            )

        return weaknesses

    def _compute_seo_strength(
        self, analysis: Optional[CompetitorAnalysis]
    ) -> int:
        """Compute a 0-100 composite SEO-strength score from an analysis row."""
        if analysis is None:
            return 0

        score = 0.0

        # Domain authority: up to 30 points
        da = analysis.domain_authority or 0
        score += min(da / 100 * 30, 30)

        # Backlinks: up to 20 points
        bl = analysis.total_backlinks or 0
        if bl >= 100:
            score += 20
        elif bl >= 50:
            score += 15
        elif bl >= 20:
            score += 10
        elif bl >= 5:
            score += 5

        # Keywords: up to 20 points
        kw = analysis.organic_keywords or 0
        if kw >= 50:
            score += 20
        elif kw >= 20:
            score += 15
        elif kw >= 10:
            score += 10
        elif kw >= 3:
            score += 5

        # Reviews: up to 15 points
        rev = analysis.total_reviews or 0
        rating = analysis.google_rating or 0
        if rev >= 50 and rating >= 4.5:
            score += 15
        elif rev >= 20 and rating >= 4.0:
            score += 10
        elif rev >= 5:
            score += 5

        # Content / traffic proxy: up to 15 points
        traffic = analysis.estimated_traffic or 0
        if traffic >= 1000:
            score += 15
        elif traffic >= 500:
            score += 10
        elif traffic >= 100:
            score += 5
        else:
            # Fallback: use keyword count as a rough content signal
            if kw >= 15:
                score += 8
            elif kw >= 5:
                score += 4

        return min(round(score), 100)


# ===================================================================
# CLI entry-point
# ===================================================================


if __name__ == "__main__":
    import json

    logger.add(
        "logs/competitor_intel.log",
        rotation="10 MB",
        retention="30 days",
        level="DEBUG",
    )

    intel = CompetitorIntelligence()

    # Example: discover competitors in Alexandria, VA
    primary_area = SERVICE_AREAS["primary"][0]  # Alexandria, VA
    logger.info("=== Competitor Discovery ===")
    discovered = intel.discover_competitors(primary_area, service_type="all")
    print(f"\nDiscovered {len(discovered)} competitors in {_area_label(primary_area)}:")
    for comp in discovered[:10]:
        print(f"  - {comp['name']}  ({comp['domain']})")

    # Market overview
    logger.info("\n=== Market Overview ===")
    overview = intel.get_market_overview(primary_area)
    print(f"\nMarket overview for {overview.get('area', 'N/A')}:")
    print(f"  Competitors: {overview.get('competitor_count', 0)}")
    print(f"  Avg DA: {overview.get('average_domain_authority', 'N/A')}")
    print(f"  Difficulty: {overview.get('market_difficulty', 'N/A')}")

    # Competitor ranking
    logger.info("\n=== Competitor Rankings ===")
    rankings = intel.rank_competitors(primary_area)
    print("\nCompetitor rankings:")
    for entry in rankings[:10]:
        print(
            f"  #{entry['rank']}  {entry['name']}  "
            f"(score {entry['seo_strength_score']})"
        )

    # Full report
    logger.info("\n=== Competitor Report ===")
    report = intel.get_competitor_report()
    print(f"\nReport summary: {report.get('executive_summary', 'N/A')}")
    print(f"Action items: {len(report.get('action_items', []))}")
    for item in report.get("action_items", [])[:5]:
        print(f"  [{item['priority'].upper()}] {item['action']}")
