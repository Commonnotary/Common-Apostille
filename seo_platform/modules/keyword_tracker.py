"""
Module 1: Keyword Research & Tracking Engine
=============================================

Tracks keyword rankings across Google, Bing, and other search engines for
Common Notary Apostille. Supports API-based tracking with graceful fallback
to SERP scraping when API keys are not configured.

Features:
    - Seed keyword database from config-driven service/geo combinations
    - Track rankings via Google Custom Search API and Bing Web Search API
    - SERP scraping fallback using requests + BeautifulSoup
    - Google autocomplete-based keyword suggestions
    - Weekly ranking reports with trend analysis
    - CSV export of ranking data
    - Top movers analysis (biggest gainers and losers)

Usage:
    from modules.keyword_tracker import KeywordTracker

    tracker = KeywordTracker()
    tracker.seed_keywords()
    tracker.track_all_keywords()
    report = tracker.generate_weekly_report()
"""

from __future__ import annotations

import csv
import datetime
import io
import json
import os
import random
import time
import urllib.parse
from typing import Any, Optional

import requests
from bs4 import BeautifulSoup
from loguru import logger
from sqlalchemy import func as sql_func
from sqlalchemy.orm import Session
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config.settings import (
    COMPANY,
    GEO_MODIFIERS,
    GOOGLE_API_KEY,
    GOOGLE_CSE_ID,
    SERVICE_AREAS,
    SERVICE_KEYWORDS,
)
from database.models import Keyword, KeywordRanking, SessionLocal

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BING_API_KEY: str = os.getenv("BING_API_KEY", "")

GOOGLE_CSE_ENDPOINT = "https://www.googleapis.com/customsearch/v1"
BING_SEARCH_ENDPOINT = "https://api.bing.microsoft.com/v7.0/search"
GOOGLE_SUGGEST_ENDPOINT = "http://suggestqueries.google.com/complete/search"

COMPANY_DOMAIN: str = urllib.parse.urlparse(COMPANY["website"]).netloc.replace("www.", "")

# Maximum number of results pages to inspect when looking for our domain
MAX_RESULT_PAGES = 5

# How many results per page (Google CSE max is 10)
RESULTS_PER_PAGE = 10

_USER_AGENTS = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3_1) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15"
    ),
    (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    ),
]


def _random_ua() -> str:
    """Return a random desktop User-Agent string."""
    return random.choice(_USER_AGENTS)


# ---------------------------------------------------------------------------
# KeywordTracker
# ---------------------------------------------------------------------------


class KeywordTracker:
    """Keyword research, ranking tracking, and trend analysis engine.

    This class manages the full lifecycle of keyword tracking:
    1. Seeding the database with service + geo keyword combinations
    2. Checking ranking positions across Google and Bing
    3. Falling back to SERP scraping when API keys are unavailable
    4. Generating reports and surfacing top movers
    5. Suggesting new keyword opportunities via Google autocomplete

    Parameters
    ----------
    session : sqlalchemy.orm.Session, optional
        An existing database session. If *None*, a new session is created
        automatically and managed internally.
    """

    def __init__(self, session: Optional[Session] = None) -> None:
        self._owns_session = session is None
        self.session: Session = session or SessionLocal()
        logger.info("KeywordTracker initialised (domain={})", COMPANY_DOMAIN)

    # ------------------------------------------------------------------
    # Context-manager support
    # ------------------------------------------------------------------

    def __enter__(self) -> "KeywordTracker":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: ANN001
        self.close()

    def close(self) -> None:
        """Flush pending changes and close the session if we own it."""
        if self._owns_session:
            try:
                self.session.close()
            except Exception:
                logger.exception("Error closing database session")

    # ------------------------------------------------------------------
    # 1. Seed keywords
    # ------------------------------------------------------------------

    def seed_keywords(self) -> int:
        """Populate the database with keyword + geo combinations from config.

        Skips keywords that already exist (matched on *keyword* text) to make
        the operation idempotent.

        Returns
        -------
        int
            The number of **new** keywords inserted.
        """
        logger.info("Seeding keyword database from configuration ...")

        existing: set[str] = {
            row[0]
            for row in self.session.query(Keyword.keyword).all()
        }

        new_count = 0

        for service_kw in SERVICE_KEYWORDS:
            # Base keyword (no geo modifier)
            if service_kw not in existing:
                self.session.add(Keyword(
                    keyword=service_kw,
                    service_type=service_kw,
                    geo_modifier=None,
                    priority="medium",
                    is_active=True,
                ))
                existing.add(service_kw)
                new_count += 1

            # Keyword + each geo modifier
            for geo in GEO_MODIFIERS:
                full_kw = f"{service_kw} {geo}"
                if full_kw in existing:
                    continue

                priority = "high" if geo in {
                    "Alexandria VA", "DMV", "Washington DC",
                    "Northern Virginia", "Roanoke VA",
                } else "medium"

                self.session.add(Keyword(
                    keyword=full_kw,
                    service_type=service_kw,
                    geo_modifier=geo,
                    priority=priority,
                    is_active=True,
                ))
                existing.add(full_kw)
                new_count += 1

        # Special high-intent keywords
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
            if kw not in existing:
                self.session.add(Keyword(
                    keyword=kw,
                    service_type="special",
                    geo_modifier=None,
                    priority="high",
                    is_active=True,
                ))
                existing.add(kw)
                new_count += 1

        self.session.commit()
        logger.success("Seeded {} new keywords (total in DB: {})", new_count, len(existing))
        return new_count

    # ------------------------------------------------------------------
    # 2. Google ranking via Custom Search API
    # ------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=15),
        retry=retry_if_exception_type(requests.exceptions.RequestException),
        reraise=True,
    )
    def _google_cse_search(self, query: str, start_index: int = 1) -> dict[str, Any]:
        """Execute a single Google Custom Search API request.

        Parameters
        ----------
        query : str
            The search query.
        start_index : int
            1-based result offset (1, 11, 21 ...).

        Returns
        -------
        dict
            The raw JSON response from the CSE API.

        Raises
        ------
        requests.exceptions.RequestException
            On network or HTTP errors (will be retried).
        ValueError
            If the API key or CSE ID is not configured.
        """
        if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
            raise ValueError("Google API key or CSE ID not configured")

        params = {
            "key": GOOGLE_API_KEY,
            "cx": GOOGLE_CSE_ID,
            "q": query,
            "start": start_index,
            "num": RESULTS_PER_PAGE,
        }
        resp = requests.get(GOOGLE_CSE_ENDPOINT, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def track_google_rankings(self, keyword: Keyword) -> Optional[KeywordRanking]:
        """Check the Google ranking position for a single keyword.

        Tries the Custom Search API first; falls back to SERP scraping if the
        API is not configured or the request fails.

        Parameters
        ----------
        keyword : Keyword
            A ``Keyword`` ORM instance.

        Returns
        -------
        KeywordRanking or None
            The newly created ranking record, or *None* on complete failure.
        """
        logger.debug("Tracking Google ranking for: {}", keyword.keyword)
        today = datetime.date.today()

        # Check whether we already tracked this keyword+engine today
        existing = (
            self.session.query(KeywordRanking)
            .filter(
                KeywordRanking.keyword_id == keyword.id,
                KeywordRanking.search_engine == "google",
                KeywordRanking.tracked_date == today,
            )
            .first()
        )
        if existing:
            logger.debug("Already tracked today, skipping (keyword_id={})", keyword.id)
            return existing

        # --- Attempt 1: Google Custom Search API ---
        try:
            return self._track_via_google_api(keyword, today)
        except ValueError:
            logger.info(
                "Google CSE API not configured; falling back to SERP scraping "
                "for '{}'", keyword.keyword,
            )
        except Exception:
            logger.warning(
                "Google CSE API failed for '{}'; falling back to SERP scraping",
                keyword.keyword,
                exc_info=True,
            )

        # --- Attempt 2: SERP scraping fallback ---
        try:
            return self._track_via_google_scrape(keyword, today)
        except Exception:
            logger.error(
                "Google SERP scraping also failed for '{}'",
                keyword.keyword,
                exc_info=True,
            )

        # Record a ranking with position=None to indicate "not found"
        return self._record_ranking(keyword.id, "google", today)

    def _track_via_google_api(
        self, keyword: Keyword, today: datetime.date
    ) -> KeywordRanking:
        """Track ranking by querying the Google Custom Search JSON API."""
        for page in range(MAX_RESULT_PAGES):
            start_index = page * RESULTS_PER_PAGE + 1
            data = self._google_cse_search(keyword.keyword, start_index=start_index)
            items = data.get("items", [])

            for idx, item in enumerate(items):
                link = item.get("link", "")
                if COMPANY_DOMAIN in link:
                    position = start_index + idx
                    logger.info(
                        "Google API: '{}' found at position {} ({})",
                        keyword.keyword, position, link,
                    )
                    return self._record_ranking(
                        keyword_id=keyword.id,
                        engine="google",
                        date=today,
                        position=position,
                        url_found=link,
                        snippet=item.get("snippet"),
                        page=page + 1,
                    )

            # If fewer results than a full page, no point continuing
            if len(items) < RESULTS_PER_PAGE:
                break

        logger.info("Google API: '{}' not found in top {}", keyword.keyword,
                     MAX_RESULT_PAGES * RESULTS_PER_PAGE)
        return self._record_ranking(keyword.id, "google", today)

    # ------------------------------------------------------------------
    # 3. Bing ranking via Web Search API
    # ------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=15),
        retry=retry_if_exception_type(requests.exceptions.RequestException),
        reraise=True,
    )
    def _bing_api_search(self, query: str, offset: int = 0) -> dict[str, Any]:
        """Execute a single Bing Web Search API request.

        Parameters
        ----------
        query : str
            The search query.
        offset : int
            0-based result offset.

        Returns
        -------
        dict
            The raw JSON response.

        Raises
        ------
        ValueError
            If ``BING_API_KEY`` is not configured.
        """
        if not BING_API_KEY:
            raise ValueError("Bing API key not configured")

        headers = {"Ocp-Apim-Subscription-Key": BING_API_KEY}
        params = {
            "q": query,
            "count": RESULTS_PER_PAGE,
            "offset": offset,
            "mkt": "en-US",
        }
        resp = requests.get(
            BING_SEARCH_ENDPOINT, headers=headers, params=params, timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def track_bing_rankings(self, keyword: Keyword) -> Optional[KeywordRanking]:
        """Check the Bing ranking position for a single keyword.

        Tries the Bing Web Search API first; falls back to SERP scraping when
        the API key is absent or the request fails.

        Parameters
        ----------
        keyword : Keyword
            A ``Keyword`` ORM instance.

        Returns
        -------
        KeywordRanking or None
            The newly created ranking record, or *None* on complete failure.
        """
        logger.debug("Tracking Bing ranking for: {}", keyword.keyword)
        today = datetime.date.today()

        existing = (
            self.session.query(KeywordRanking)
            .filter(
                KeywordRanking.keyword_id == keyword.id,
                KeywordRanking.search_engine == "bing",
                KeywordRanking.tracked_date == today,
            )
            .first()
        )
        if existing:
            logger.debug("Already tracked today, skipping (keyword_id={})", keyword.id)
            return existing

        # --- Attempt 1: Bing Web Search API ---
        try:
            return self._track_via_bing_api(keyword, today)
        except ValueError:
            logger.info(
                "Bing API not configured; falling back to SERP scraping for '{}'",
                keyword.keyword,
            )
        except Exception:
            logger.warning(
                "Bing API failed for '{}'; falling back to SERP scraping",
                keyword.keyword,
                exc_info=True,
            )

        # --- Attempt 2: SERP scraping fallback ---
        try:
            return self._track_via_bing_scrape(keyword, today)
        except Exception:
            logger.error(
                "Bing SERP scraping also failed for '{}'",
                keyword.keyword,
                exc_info=True,
            )

        return self._record_ranking(keyword.id, "bing", today)

    def _track_via_bing_api(
        self, keyword: Keyword, today: datetime.date
    ) -> KeywordRanking:
        """Track ranking by querying the Bing Web Search API."""
        for page in range(MAX_RESULT_PAGES):
            offset = page * RESULTS_PER_PAGE
            data = self._bing_api_search(keyword.keyword, offset=offset)
            web_pages = data.get("webPages", {}).get("value", [])

            for idx, result in enumerate(web_pages):
                url = result.get("url", "")
                if COMPANY_DOMAIN in url:
                    position = offset + idx + 1
                    logger.info(
                        "Bing API: '{}' found at position {} ({})",
                        keyword.keyword, position, url,
                    )
                    return self._record_ranking(
                        keyword_id=keyword.id,
                        engine="bing",
                        date=today,
                        position=position,
                        url_found=url,
                        snippet=result.get("snippet"),
                        page=page + 1,
                    )

            if len(web_pages) < RESULTS_PER_PAGE:
                break

        logger.info("Bing API: '{}' not found in top {}", keyword.keyword,
                     MAX_RESULT_PAGES * RESULTS_PER_PAGE)
        return self._record_ranking(keyword.id, "bing", today)

    # ------------------------------------------------------------------
    # 4. SERP scraping fallbacks
    # ------------------------------------------------------------------

    def _track_via_google_scrape(
        self, keyword: Keyword, today: datetime.date
    ) -> KeywordRanking:
        """Scrape Google search results as a fallback when the API is unavailable.

        Uses ``requests`` + ``BeautifulSoup`` to parse the organic result
        listing.  A polite delay is inserted between page fetches to reduce
        the risk of being rate-limited.

        Parameters
        ----------
        keyword : Keyword
            The keyword to search for.
        today : datetime.date
            The date to record.

        Returns
        -------
        KeywordRanking
            The resulting ranking record.
        """
        query_encoded = urllib.parse.quote_plus(keyword.keyword)

        for page in range(MAX_RESULT_PAGES):
            start = page * RESULTS_PER_PAGE
            url = (
                f"https://www.google.com/search?q={query_encoded}"
                f"&start={start}&num={RESULTS_PER_PAGE}&hl=en"
            )
            headers = {"User-Agent": _random_ua(), "Accept-Language": "en-US,en;q=0.9"}

            resp = requests.get(url, headers=headers, timeout=30)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")
            result_divs = soup.select("div.g")

            for idx, div in enumerate(result_divs):
                anchor = div.select_one("a[href]")
                if anchor is None:
                    continue
                href = anchor.get("href", "")
                if COMPANY_DOMAIN in href:
                    position = start + idx + 1
                    snippet_el = div.select_one("div.VwiC3b, span.aCOpRe")
                    snippet = snippet_el.get_text(strip=True) if snippet_el else None
                    logger.info(
                        "Google scrape: '{}' found at position {} ({})",
                        keyword.keyword, position, href,
                    )
                    return self._record_ranking(
                        keyword_id=keyword.id,
                        engine="google",
                        date=today,
                        position=position,
                        url_found=href,
                        snippet=snippet,
                        page=page + 1,
                    )

            # Polite crawl delay to avoid being blocked
            time.sleep(random.uniform(2.0, 5.0))

        logger.info("Google scrape: '{}' not found in top {}", keyword.keyword,
                     MAX_RESULT_PAGES * RESULTS_PER_PAGE)
        return self._record_ranking(keyword.id, "google", today)

    def _track_via_bing_scrape(
        self, keyword: Keyword, today: datetime.date
    ) -> KeywordRanking:
        """Scrape Bing search results as a fallback.

        Parameters
        ----------
        keyword : Keyword
            The keyword to search for.
        today : datetime.date
            The date to record.

        Returns
        -------
        KeywordRanking
            The resulting ranking record.
        """
        query_encoded = urllib.parse.quote_plus(keyword.keyword)

        for page in range(MAX_RESULT_PAGES):
            first = page * RESULTS_PER_PAGE + 1
            url = (
                f"https://www.bing.com/search?q={query_encoded}"
                f"&first={first}&count={RESULTS_PER_PAGE}"
            )
            headers = {"User-Agent": _random_ua(), "Accept-Language": "en-US,en;q=0.9"}

            resp = requests.get(url, headers=headers, timeout=30)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")
            results = soup.select("li.b_algo")

            for idx, li in enumerate(results):
                anchor = li.select_one("h2 a[href]")
                if anchor is None:
                    continue
                href = anchor.get("href", "")
                if COMPANY_DOMAIN in href:
                    position = (page * RESULTS_PER_PAGE) + idx + 1
                    snippet_el = li.select_one("div.b_caption p")
                    snippet = snippet_el.get_text(strip=True) if snippet_el else None
                    logger.info(
                        "Bing scrape: '{}' found at position {} ({})",
                        keyword.keyword, position, href,
                    )
                    return self._record_ranking(
                        keyword_id=keyword.id,
                        engine="bing",
                        date=today,
                        position=position,
                        url_found=href,
                        snippet=snippet,
                        page=page + 1,
                    )

            time.sleep(random.uniform(1.5, 4.0))

        logger.info("Bing scrape: '{}' not found in top {}", keyword.keyword,
                     MAX_RESULT_PAGES * RESULTS_PER_PAGE)
        return self._record_ranking(keyword.id, "bing", today)

    # ------------------------------------------------------------------
    # 5. Track all keywords
    # ------------------------------------------------------------------

    def track_all_keywords(self) -> dict[str, int]:
        """Run ranking checks for every active keyword across all engines.

        Returns
        -------
        dict
            A summary with counts keyed by ``"google_tracked"``,
            ``"bing_tracked"``, ``"errors"``.
        """
        keywords: list[Keyword] = (
            self.session.query(Keyword)
            .filter(Keyword.is_active.is_(True))
            .order_by(Keyword.priority.desc(), Keyword.id)
            .all()
        )

        total = len(keywords)
        logger.info("Starting ranking run for {} active keywords ...", total)

        stats = {"google_tracked": 0, "bing_tracked": 0, "errors": 0}

        for idx, kw in enumerate(keywords, 1):
            logger.info("[{}/{}] Tracking: {}", idx, total, kw.keyword)

            # --- Google ---
            try:
                result = self.track_google_rankings(kw)
                if result is not None:
                    stats["google_tracked"] += 1
            except Exception:
                stats["errors"] += 1
                logger.error("Unhandled error tracking Google for '{}'",
                             kw.keyword, exc_info=True)

            # --- Bing ---
            try:
                result = self.track_bing_rankings(kw)
                if result is not None:
                    stats["bing_tracked"] += 1
            except Exception:
                stats["errors"] += 1
                logger.error("Unhandled error tracking Bing for '{}'",
                             kw.keyword, exc_info=True)

            # Throttle between keywords to be respectful to APIs / search engines
            if idx < total:
                time.sleep(random.uniform(1.0, 3.0))

        logger.success(
            "Ranking run complete: Google={}, Bing={}, errors={}",
            stats["google_tracked"], stats["bing_tracked"], stats["errors"],
        )
        return stats

    # ------------------------------------------------------------------
    # 6. Ranking report
    # ------------------------------------------------------------------

    def get_ranking_report(self, period: str = "week") -> dict[str, Any]:
        """Generate a ranking report for the given period.

        Parameters
        ----------
        period : str
            One of ``"week"``, ``"month"``, or ``"quarter"``.

        Returns
        -------
        dict
            A structured report with ranking distributions, trend data, and
            top movers.
        """
        start_date, end_date = self._date_range(period)

        rankings = (
            self.session.query(KeywordRanking)
            .filter(
                KeywordRanking.tracked_date >= start_date,
                KeywordRanking.tracked_date <= end_date,
            )
            .all()
        )

        # Latest ranking per keyword per engine
        latest: dict[tuple[int, str], KeywordRanking] = {}
        for r in rankings:
            key = (r.keyword_id, r.search_engine)
            if key not in latest or r.tracked_date > latest[key].tracked_date:
                latest[key] = r

        positions = [r.position for r in latest.values() if r.position is not None]

        report: dict[str, Any] = {
            "period": period,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "total_keywords_tracked": len({r.keyword_id for r in rankings}),
            "total_ranking_checks": len(rankings),
            "keywords_in_top_3": sum(1 for p in positions if p <= 3),
            "keywords_in_top_10": sum(1 for p in positions if p <= 10),
            "keywords_in_top_20": sum(1 for p in positions if p <= 20),
            "keywords_not_ranking": sum(
                1 for r in latest.values() if r.position is None
            ),
            "average_position": (
                round(sum(positions) / len(positions), 1) if positions else None
            ),
            "by_engine": self._report_by_engine(latest),
            "top_movers": self.get_top_movers(period),
        }

        logger.info(
            "Ranking report ({} to {}): {} keywords, avg pos {}, top-10 {}",
            start_date, end_date,
            report["total_keywords_tracked"],
            report["average_position"],
            report["keywords_in_top_10"],
        )
        return report

    def _report_by_engine(
        self, latest: dict[tuple[int, str], KeywordRanking]
    ) -> dict[str, dict[str, Any]]:
        """Break down ranking stats per search engine."""
        engines: dict[str, list[Optional[int]]] = {}
        for (_, engine), ranking in latest.items():
            engines.setdefault(engine, []).append(ranking.position)

        result: dict[str, dict[str, Any]] = {}
        for engine, positions in engines.items():
            ranked = [p for p in positions if p is not None]
            result[engine] = {
                "total_tracked": len(positions),
                "ranked": len(ranked),
                "not_found": len(positions) - len(ranked),
                "in_top_3": sum(1 for p in ranked if p <= 3),
                "in_top_10": sum(1 for p in ranked if p <= 10),
                "in_top_20": sum(1 for p in ranked if p <= 20),
                "average_position": (
                    round(sum(ranked) / len(ranked), 1) if ranked else None
                ),
            }
        return result

    # ------------------------------------------------------------------
    # 7. Keyword suggestions via Google autocomplete
    # ------------------------------------------------------------------

    def suggest_new_keywords(self) -> list[dict[str, Any]]:
        """Discover new keyword opportunities using Google autocomplete.

        Queries Google Suggest for each base service keyword combined with
        relevant geo modifiers and collects the autocomplete suggestions.
        Already-tracked keywords are filtered out.

        Returns
        -------
        list of dict
            Each dict contains ``"suggestion"``, ``"source_keyword"``, and
            ``"geo_modifier"`` keys.
        """
        logger.info("Fetching keyword suggestions from Google autocomplete ...")

        existing_keywords: set[str] = {
            row[0].lower()
            for row in self.session.query(Keyword.keyword).all()
        }

        seed_phrases: list[tuple[str, Optional[str]]] = []
        for kw in SERVICE_KEYWORDS[:10]:  # Limit to avoid excessive requests
            seed_phrases.append((kw, None))
            for geo in GEO_MODIFIERS[:6]:  # Top geo modifiers only
                seed_phrases.append((f"{kw} {geo}", geo))

        suggestions: list[dict[str, Any]] = []
        seen: set[str] = set()

        for phrase, geo in seed_phrases:
            try:
                autocomplete = self._google_autocomplete(phrase)
                for suggestion in autocomplete:
                    normed = suggestion.lower().strip()
                    if normed in seen or normed in existing_keywords:
                        continue
                    seen.add(normed)
                    suggestions.append({
                        "suggestion": suggestion,
                        "source_keyword": phrase,
                        "geo_modifier": geo,
                    })
            except Exception:
                logger.warning("Autocomplete request failed for '{}'", phrase,
                               exc_info=True)

            time.sleep(random.uniform(0.5, 1.5))

        logger.info("Found {} new keyword suggestions", len(suggestions))
        return suggestions

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=1, max=8),
        retry=retry_if_exception_type(requests.exceptions.RequestException),
        reraise=True,
    )
    def _google_autocomplete(self, query: str) -> list[str]:
        """Fetch autocomplete suggestions from Google Suggest.

        Parameters
        ----------
        query : str
            The partial query to get suggestions for.

        Returns
        -------
        list of str
            Autocomplete suggestions.
        """
        params = {
            "client": "firefox",
            "q": query,
            "hl": "en",
            "gl": "us",
        }
        resp = requests.get(
            GOOGLE_SUGGEST_ENDPOINT,
            params=params,
            headers={"User-Agent": _random_ua()},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        # Response format: [query, [suggestions], ...]
        if isinstance(data, list) and len(data) >= 2 and isinstance(data[1], list):
            return [str(s) for s in data[1]]
        return []

    # ------------------------------------------------------------------
    # 8. Keyword trends
    # ------------------------------------------------------------------

    def get_keyword_trends(self, keyword_id: int) -> dict[str, Any]:
        """Retrieve historical ranking data for a single keyword.

        Parameters
        ----------
        keyword_id : int
            The primary key of the keyword.

        Returns
        -------
        dict
            Contains ``"keyword"``, ``"engines"`` (mapping engine name to a
            list of ``{"date", "position"}`` dicts), and ``"summary"`` with
            current / best / worst positions.
        """
        keyword = self.session.query(Keyword).get(keyword_id)
        if keyword is None:
            logger.warning("Keyword id={} not found", keyword_id)
            return {"error": f"Keyword {keyword_id} not found"}

        rankings = (
            self.session.query(KeywordRanking)
            .filter(KeywordRanking.keyword_id == keyword_id)
            .order_by(KeywordRanking.tracked_date.asc())
            .all()
        )

        engines: dict[str, list[dict[str, Any]]] = {}
        for r in rankings:
            engines.setdefault(r.search_engine, []).append({
                "date": r.tracked_date.isoformat(),
                "position": r.position,
                "url_found": r.url_found,
            })

        all_positions = [r.position for r in rankings if r.position is not None]

        summary: dict[str, Any] = {
            "total_data_points": len(rankings),
            "current_position": (
                rankings[-1].position if rankings else None
            ),
            "best_position": min(all_positions) if all_positions else None,
            "worst_position": max(all_positions) if all_positions else None,
            "average_position": (
                round(sum(all_positions) / len(all_positions), 1)
                if all_positions else None
            ),
        }

        return {
            "keyword_id": keyword_id,
            "keyword": keyword.keyword,
            "service_type": keyword.service_type,
            "geo_modifier": keyword.geo_modifier,
            "engines": engines,
            "summary": summary,
        }

    # ------------------------------------------------------------------
    # 9. Top movers
    # ------------------------------------------------------------------

    def get_top_movers(
        self, period: str = "week", limit: int = 10
    ) -> dict[str, list[dict[str, Any]]]:
        """Identify the keywords with the biggest ranking changes.

        Compares the most recent ranking to the previous period's ranking
        for each keyword and returns the biggest gainers and losers.

        Parameters
        ----------
        period : str
            ``"week"``, ``"month"``, or ``"quarter"``.
        limit : int
            Maximum number of gainers / losers to return.

        Returns
        -------
        dict
            Keys ``"gainers"`` and ``"losers"``, each a list of dicts with
            ``"keyword"``, ``"engine"``, ``"previous_position"``,
            ``"current_position"``, and ``"change"``.
        """
        start_date, end_date = self._date_range(period)
        prev_end = start_date - datetime.timedelta(days=1)
        prev_start = prev_end - (end_date - start_date)

        current_rankings = self._latest_rankings_in_range(start_date, end_date)
        previous_rankings = self._latest_rankings_in_range(prev_start, prev_end)

        changes: list[dict[str, Any]] = []

        for key, cur in current_rankings.items():
            prev = previous_rankings.get(key)
            if prev is None or cur.position is None:
                continue
            prev_pos = prev.position
            if prev_pos is None:
                continue

            change = prev_pos - cur.position  # positive = improved

            kw_obj = self.session.query(Keyword).get(key[0])
            kw_text = kw_obj.keyword if kw_obj else f"keyword_id={key[0]}"

            changes.append({
                "keyword_id": key[0],
                "keyword": kw_text,
                "engine": key[1],
                "previous_position": prev_pos,
                "current_position": cur.position,
                "change": change,
            })

        gainers = sorted(
            [c for c in changes if c["change"] > 0],
            key=lambda c: c["change"],
            reverse=True,
        )[:limit]

        losers = sorted(
            [c for c in changes if c["change"] < 0],
            key=lambda c: c["change"],
        )[:limit]

        return {"gainers": gainers, "losers": losers}

    def _latest_rankings_in_range(
        self, start: datetime.date, end: datetime.date
    ) -> dict[tuple[int, str], KeywordRanking]:
        """Return the most recent ranking per (keyword_id, engine) in a date range."""
        rankings = (
            self.session.query(KeywordRanking)
            .filter(
                KeywordRanking.tracked_date >= start,
                KeywordRanking.tracked_date <= end,
            )
            .order_by(KeywordRanking.tracked_date.desc())
            .all()
        )

        latest: dict[tuple[int, str], KeywordRanking] = {}
        for r in rankings:
            key = (r.keyword_id, r.search_engine)
            if key not in latest:
                latest[key] = r
        return latest

    # ------------------------------------------------------------------
    # 10. CSV export
    # ------------------------------------------------------------------

    def export_rankings_csv(self, period: str = "week") -> str:
        """Export ranking data for the given period as a CSV string.

        Parameters
        ----------
        period : str
            ``"week"``, ``"month"``, or ``"quarter"``.

        Returns
        -------
        str
            CSV-formatted string with columns: ``keyword``, ``service_type``,
            ``geo_modifier``, ``engine``, ``position``, ``url_found``,
            ``snippet``, ``page``, ``tracked_date``.
        """
        start_date, end_date = self._date_range(period)

        rows = (
            self.session.query(KeywordRanking, Keyword)
            .join(Keyword, KeywordRanking.keyword_id == Keyword.id)
            .filter(
                KeywordRanking.tracked_date >= start_date,
                KeywordRanking.tracked_date <= end_date,
            )
            .order_by(Keyword.keyword, KeywordRanking.tracked_date)
            .all()
        )

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "keyword", "service_type", "geo_modifier", "engine",
            "position", "url_found", "snippet", "page", "tracked_date",
        ])

        for ranking, kw in rows:
            writer.writerow([
                kw.keyword,
                kw.service_type,
                kw.geo_modifier or "",
                ranking.search_engine,
                ranking.position if ranking.position is not None else "N/A",
                ranking.url_found or "",
                (ranking.snippet or "")[:200],
                ranking.page or "",
                ranking.tracked_date.isoformat(),
            ])

        csv_content = output.getvalue()
        logger.info(
            "Exported {} ranking rows for period {} ({} to {})",
            len(rows), period, start_date, end_date,
        )
        return csv_content

    # ------------------------------------------------------------------
    # 11. Weekly report (structured dict)
    # ------------------------------------------------------------------

    def generate_weekly_report(self) -> dict[str, Any]:
        """Generate a comprehensive weekly ranking report.

        Returns
        -------
        dict
            A structured report containing:
            - ``total_keywords_tracked``
            - ``keywords_in_top_3``, ``keywords_in_top_10``,
              ``keywords_in_top_20``
            - ``biggest_gainers`` and ``biggest_losers``
            - ``new_keyword_opportunities``
            - ``average_position_trends`` (per-engine weekly averages)
            - ``engine_breakdown``
            - Metadata (``report_date``, ``period``, ``company``)
        """
        logger.info("Generating weekly ranking report ...")

        start_date, end_date = self._date_range("week")

        # --- Current-period latest rankings ---
        current_rankings = self._latest_rankings_in_range(start_date, end_date)
        positions = [
            r.position for r in current_rankings.values() if r.position is not None
        ]

        # --- Previous-period latest rankings (for trend comparison) ---
        prev_end = start_date - datetime.timedelta(days=1)
        prev_start = prev_end - datetime.timedelta(days=7)
        prev_rankings = self._latest_rankings_in_range(prev_start, prev_end)
        prev_positions = [
            r.position for r in prev_rankings.values() if r.position is not None
        ]

        # --- Top movers ---
        movers = self.get_top_movers("week", limit=5)

        # --- Keyword suggestions ---
        try:
            suggestions = self.suggest_new_keywords()[:15]
        except Exception:
            logger.warning("Could not fetch keyword suggestions for report",
                           exc_info=True)
            suggestions = []

        # --- Per-engine breakdown ---
        engine_breakdown: dict[str, dict[str, Any]] = {}
        for (kw_id, engine), ranking in current_rankings.items():
            bucket = engine_breakdown.setdefault(engine, {
                "tracked": 0, "ranked": 0, "positions": [],
            })
            bucket["tracked"] += 1
            if ranking.position is not None:
                bucket["ranked"] += 1
                bucket["positions"].append(ranking.position)

        for engine, data in engine_breakdown.items():
            pos_list = data.pop("positions")
            data["in_top_3"] = sum(1 for p in pos_list if p <= 3)
            data["in_top_10"] = sum(1 for p in pos_list if p <= 10)
            data["in_top_20"] = sum(1 for p in pos_list if p <= 20)
            data["average_position"] = (
                round(sum(pos_list) / len(pos_list), 1) if pos_list else None
            )

        # --- Average position trends ---
        avg_current = (
            round(sum(positions) / len(positions), 1) if positions else None
        )
        avg_previous = (
            round(sum(prev_positions) / len(prev_positions), 1)
            if prev_positions else None
        )
        position_trend_direction: Optional[str] = None
        position_trend_change: Optional[float] = None
        if avg_current is not None and avg_previous is not None:
            diff = avg_previous - avg_current  # positive = improvement
            position_trend_change = round(diff, 1)
            if diff > 0:
                position_trend_direction = "improving"
            elif diff < 0:
                position_trend_direction = "declining"
            else:
                position_trend_direction = "stable"

        report: dict[str, Any] = {
            "report_date": end_date.isoformat(),
            "period": "week",
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
            "company": COMPANY["name"],
            "domain": COMPANY_DOMAIN,

            # Core counts
            "total_keywords_tracked": len({
                k[0] for k in current_rankings
            }),
            "keywords_in_top_3": sum(1 for p in positions if p <= 3),
            "keywords_in_top_10": sum(1 for p in positions if p <= 10),
            "keywords_in_top_20": sum(1 for p in positions if p <= 20),
            "keywords_not_ranking": sum(
                1 for r in current_rankings.values() if r.position is None
            ),

            # Trends
            "average_position_current": avg_current,
            "average_position_previous": avg_previous,
            "average_position_trends": {
                "direction": position_trend_direction,
                "change": position_trend_change,
            },

            # Movers
            "biggest_gainers": movers["gainers"],
            "biggest_losers": movers["losers"],

            # Opportunities
            "new_keyword_opportunities": suggestions,

            # Per-engine details
            "engine_breakdown": engine_breakdown,
        }

        logger.success(
            "Weekly report generated: {} keywords tracked, avg pos {}, "
            "top-10 count {}",
            report["total_keywords_tracked"],
            avg_current,
            report["keywords_in_top_10"],
        )
        return report

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _record_ranking(
        self,
        keyword_id: int,
        engine: str,
        date: datetime.date,
        position: Optional[int] = None,
        url_found: Optional[str] = None,
        snippet: Optional[str] = None,
        page: Optional[int] = None,
    ) -> KeywordRanking:
        """Create and persist a ``KeywordRanking`` row.

        Parameters
        ----------
        keyword_id : int
            FK to the keyword.
        engine : str
            Search engine name (``"google"``, ``"bing"``).
        date : datetime.date
            The tracking date.
        position : int or None
            Ranking position, or *None* if not found.
        url_found : str or None
            The URL that appeared in results.
        snippet : str or None
            The snippet text from the SERP.
        page : int or None
            Which results page.

        Returns
        -------
        KeywordRanking
            The persisted ORM instance.
        """
        ranking = KeywordRanking(
            keyword_id=keyword_id,
            search_engine=engine,
            position=position,
            url_found=url_found,
            snippet=snippet,
            page=page,
            tracked_date=date,
        )
        self.session.add(ranking)
        self.session.commit()
        return ranking

    @staticmethod
    def _date_range(period: str) -> tuple[datetime.date, datetime.date]:
        """Return ``(start_date, end_date)`` for a named period.

        Parameters
        ----------
        period : str
            ``"week"``, ``"month"``, or ``"quarter"``.

        Returns
        -------
        tuple of datetime.date
        """
        today = datetime.date.today()
        days_map = {"week": 7, "month": 30, "quarter": 90}
        delta = days_map.get(period, 7)
        return today - datetime.timedelta(days=delta), today


# ---------------------------------------------------------------------------
# CLI / demo entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from database.models import init_db

    logger.add(
        "logs/keyword_tracker.log",
        rotation="10 MB",
        retention="30 days",
        level="DEBUG",
    )

    logger.info("=== Keyword Tracker - Demo Run ===")

    # Ensure tables exist
    init_db()

    with KeywordTracker() as tracker:
        # 1. Seed the keyword database
        new_count = tracker.seed_keywords()
        print(f"\nSeeded {new_count} new keywords into the database.\n")

        # 2. Show total keywords
        total = tracker.session.query(Keyword).count()
        active = (
            tracker.session.query(Keyword)
            .filter(Keyword.is_active.is_(True))
            .count()
        )
        print(f"Total keywords: {total}  |  Active: {active}\n")

        # 3. Track rankings for a sample keyword
        sample_kw = (
            tracker.session.query(Keyword)
            .filter(Keyword.priority == "high", Keyword.is_active.is_(True))
            .first()
        )
        if sample_kw:
            print(f"Tracking sample keyword: '{sample_kw.keyword}' ...")
            google_result = tracker.track_google_rankings(sample_kw)
            bing_result = tracker.track_bing_rankings(sample_kw)

            if google_result and google_result.position:
                print(f"  Google position: {google_result.position}")
            else:
                print("  Google position: not found in top results")

            if bing_result and bing_result.position:
                print(f"  Bing position:   {bing_result.position}")
            else:
                print("  Bing position:   not found in top results")

        # 4. Get keyword suggestions
        print("\nFetching keyword suggestions ...")
        suggestions = tracker.suggest_new_keywords()
        print(f"Found {len(suggestions)} new keyword ideas:")
        for s in suggestions[:10]:
            print(f"  - {s['suggestion']}  (from: {s['source_keyword']})")

        # 5. Generate the weekly report
        print("\nGenerating weekly report ...")
        report = tracker.generate_weekly_report()
        print(f"\n{'=' * 60}")
        print(f"  WEEKLY RANKING REPORT - {report['report_date']}")
        print(f"  {report['company']} ({report['domain']})")
        print(f"{'=' * 60}")
        print(f"  Keywords tracked:  {report['total_keywords_tracked']}")
        print(f"  In top  3:         {report['keywords_in_top_3']}")
        print(f"  In top 10:         {report['keywords_in_top_10']}")
        print(f"  In top 20:         {report['keywords_in_top_20']}")
        print(f"  Not ranking:       {report['keywords_not_ranking']}")
        print(f"  Avg position:      {report['average_position_current']}")
        trend = report["average_position_trends"]
        if trend["direction"]:
            print(f"  Trend:             {trend['direction']} ({trend['change']:+.1f})")
        print(f"{'=' * 60}")

        if report["biggest_gainers"]:
            print("\n  Biggest Gainers:")
            for g in report["biggest_gainers"]:
                print(f"    {g['keyword']} ({g['engine']}): "
                      f"{g['previous_position']} -> {g['current_position']} "
                      f"(+{g['change']})")

        if report["biggest_losers"]:
            print("\n  Biggest Losers:")
            for l in report["biggest_losers"]:
                print(f"    {l['keyword']} ({l['engine']}): "
                      f"{l['previous_position']} -> {l['current_position']} "
                      f"({l['change']})")

        if report["new_keyword_opportunities"]:
            print(f"\n  New Keyword Opportunities ({len(report['new_keyword_opportunities'])}):")
            for opp in report["new_keyword_opportunities"][:5]:
                print(f"    - {opp['suggestion']}")

        # 6. CSV export
        print("\nExporting rankings to CSV ...")
        csv_data = tracker.export_rankings_csv("week")
        lines = csv_data.strip().split("\n")
        print(f"Exported {len(lines) - 1} ranking rows.")

    logger.info("=== Demo run complete ===")
