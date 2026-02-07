"""
Module 5: Technical SEO Auditor
SEO & AI Monitoring Platform - Common Notary Apostille

Performs comprehensive technical SEO audits including site crawling, page speed
analysis, mobile responsiveness checks, sitemap/robots.txt validation, SSL
verification, canonical tag auditing, internal link analysis, and image
optimization checks.

Usage:
    auditor = TechnicalSEOAuditor()
    report = auditor.run_full_audit()
    print(report)
"""

import datetime
import hashlib
import re
import ssl
import socket
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from loguru import logger
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from config.settings import COMPANY, PAGESPEED_API_KEY
from database.models import TechnicalAudit, PageAudit, SessionLocal

# ---------------------------------------------------------------------------
# Severity constants
# ---------------------------------------------------------------------------
CRITICAL = "critical"
WARNING = "warning"
INFO = "info"

# ---------------------------------------------------------------------------
# Default headers for HTTP requests
# ---------------------------------------------------------------------------
DEFAULT_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# PageSpeed Insights API endpoint
PAGESPEED_API_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


class TechnicalSEOAuditor:
    """Comprehensive technical SEO auditor for *Common Notary Apostille*.

    Crawls the website, evaluates Core Web Vitals via Google PageSpeed
    Insights, validates sitemaps and robots.txt, audits SSL certificates,
    canonical tags, internal linking, and images, then produces a scored
    and prioritised report.

    Attributes:
        site_url: The root URL of the website to audit.
        pagespeed_api_key: Google PageSpeed Insights API key.
        crawled_pages: Accumulated page-level audit data from the last crawl.
        issues: Accumulated issues discovered during the audit.
        audit_id: Database primary key for the current audit run.
    """

    def __init__(
        self,
        site_url: Optional[str] = None,
        pagespeed_api_key: Optional[str] = None,
    ) -> None:
        """Initialise the auditor.

        Args:
            site_url: The website root URL.  Falls back to the configured
                ``COMPANY["website"]`` when *None*.
            pagespeed_api_key: Google PageSpeed API key.  Falls back to
                ``PAGESPEED_API_KEY`` from settings when *None*.
        """
        self.site_url: str = (site_url or COMPANY.get("website", "")).rstrip("/")
        self.pagespeed_api_key: str = pagespeed_api_key or PAGESPEED_API_KEY
        self.domain: str = urlparse(self.site_url).netloc.lower().replace("www.", "")
        self.crawled_pages: list[dict[str, Any]] = []
        self.issues: list[dict[str, Any]] = []
        self.audit_id: Optional[int] = None
        self._visited_urls: set[str] = set()
        self._session = requests.Session()
        self._session.headers.update(DEFAULT_HEADERS)

        logger.info(
            "TechnicalSEOAuditor initialised for {} (domain: {})",
            self.site_url,
            self.domain,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _normalise_url(self, url: str) -> str:
        """Normalise a URL for deduplication."""
        parsed = urlparse(url.lower().strip())
        path = parsed.path.rstrip("/") or "/"
        return f"{parsed.scheme}://{parsed.netloc}{path}"

    def _is_internal(self, url: str) -> bool:
        """Return *True* when *url* belongs to the audited domain."""
        try:
            parsed = urlparse(url)
            host = parsed.netloc.lower().replace("www.", "")
            return host == self.domain or host == ""
        except Exception:
            return False

    def _add_issue(
        self,
        severity: str,
        category: str,
        message: str,
        url: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """Record an issue found during the audit.

        Args:
            severity: One of ``CRITICAL``, ``WARNING``, or ``INFO``.
            category: Short label such as ``"meta_tags"`` or ``"images"``.
            message: Human-readable description of the issue.
            url: The page URL the issue relates to (if applicable).
            details: Arbitrary extra data.
        """
        issue: dict[str, Any] = {
            "severity": severity,
            "category": category,
            "message": message,
            "url": url,
            "details": details or {},
            "timestamp": datetime.datetime.utcnow().isoformat(),
        }
        self.issues.append(issue)
        log_method = {
            CRITICAL: logger.error,
            WARNING: logger.warning,
            INFO: logger.info,
        }.get(severity, logger.debug)
        log_method("[{}] {} - {}", severity.upper(), category, message)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
        reraise=True,
    )
    def _fetch(
        self,
        url: str,
        timeout: int = 30,
        allow_redirects: bool = True,
    ) -> requests.Response:
        """Fetch a URL with automatic retries on transient errors.

        Args:
            url: Target URL.
            timeout: Request timeout in seconds.
            allow_redirects: Follow HTTP redirects when *True*.

        Returns:
            The ``requests.Response`` object.

        Raises:
            requests.RequestException: After exhausting retries.
        """
        return self._session.get(
            url,
            timeout=timeout,
            allow_redirects=allow_redirects,
        )

    # ------------------------------------------------------------------
    # 1. crawl_site
    # ------------------------------------------------------------------

    def crawl_site(
        self,
        start_url: Optional[str] = None,
        max_pages: int = 100,
    ) -> list[dict[str, Any]]:
        """Crawl the website starting from *start_url*.

        Performs a breadth-first crawl, collecting on-page SEO signals for
        every reachable internal page up to *max_pages*.

        Args:
            start_url: The page to begin crawling from.  Defaults to the
                configured site URL.
            max_pages: Maximum number of pages to crawl.

        Returns:
            A list of dicts, one per crawled page, containing URL, status
            code, title, meta description, heading tags, word count, load
            time, page size, canonical / robots meta, images missing alt
            text, link counts, and any broken links found.
        """
        start_url = start_url or self.site_url
        logger.info("Starting crawl from {} (max {} pages)", start_url, max_pages)

        self.crawled_pages = []
        self._visited_urls = set()
        queue: list[str] = [self._normalise_url(start_url)]

        while queue and len(self.crawled_pages) < max_pages:
            current_url = queue.pop(0)
            normalised = self._normalise_url(current_url)

            if normalised in self._visited_urls:
                continue
            self._visited_urls.add(normalised)

            page_data = self._crawl_single_page(current_url)
            if page_data is None:
                continue

            self.crawled_pages.append(page_data)
            logger.debug(
                "Crawled {}/{}: {} [{}]",
                len(self.crawled_pages),
                max_pages,
                current_url,
                page_data.get("status_code"),
            )

            # Enqueue discovered internal links
            for link in page_data.get("internal_link_urls", []):
                norm_link = self._normalise_url(link)
                if norm_link not in self._visited_urls:
                    queue.append(link)

        logger.info("Crawl complete: {} pages crawled", len(self.crawled_pages))
        return self.crawled_pages

    def _crawl_single_page(self, url: str) -> Optional[dict[str, Any]]:
        """Fetch and analyse a single page.

        Returns:
            A dict of on-page metrics or *None* when the page cannot be
            fetched at all.
        """
        page_data: dict[str, Any] = {"url": url}

        try:
            start_time = time.monotonic()
            response = self._fetch(url, timeout=30)
            elapsed_ms = int((time.monotonic() - start_time) * 1000)

            page_data["status_code"] = response.status_code
            page_data["load_time_ms"] = elapsed_ms
            page_data["page_size_kb"] = round(len(response.content) / 1024, 2)

            if response.status_code >= 400:
                self._add_issue(
                    CRITICAL if response.status_code >= 500 else WARNING,
                    "http_status",
                    f"Page returned HTTP {response.status_code}",
                    url=url,
                )
                return page_data

            content_type = response.headers.get("Content-Type", "")
            if "text/html" not in content_type:
                return page_data

            soup = BeautifulSoup(response.text, "lxml")
            self._extract_meta(soup, page_data, url)
            self._extract_headings(soup, page_data, url)
            self._extract_content_stats(soup, page_data)
            self._extract_canonical(soup, page_data, url)
            self._extract_robots_meta(soup, page_data)
            self._extract_images(soup, page_data, url)
            self._extract_links(soup, page_data, url)

        except requests.RequestException as exc:
            logger.warning("Failed to fetch {}: {}", url, exc)
            page_data["status_code"] = 0
            page_data["error"] = str(exc)
            self._add_issue(
                CRITICAL,
                "connectivity",
                f"Could not fetch page: {exc}",
                url=url,
            )
            return page_data

        return page_data

    # -- extraction helpers used by _crawl_single_page --

    def _extract_meta(
        self,
        soup: BeautifulSoup,
        page_data: dict[str, Any],
        url: str,
    ) -> None:
        """Extract page title and meta description."""
        title_tag = soup.find("title")
        page_data["page_title"] = title_tag.get_text(strip=True) if title_tag else ""
        if not page_data["page_title"]:
            self._add_issue(WARNING, "meta_tags", "Missing page title", url=url)
        elif len(page_data["page_title"]) > 60:
            self._add_issue(
                INFO,
                "meta_tags",
                f"Title too long ({len(page_data['page_title'])} chars, recommended <= 60)",
                url=url,
            )

        meta_desc_tag = soup.find("meta", attrs={"name": "description"})
        page_data["meta_description"] = (
            meta_desc_tag["content"].strip() if meta_desc_tag and meta_desc_tag.get("content") else ""
        )
        if not page_data["meta_description"]:
            self._add_issue(WARNING, "meta_tags", "Missing meta description", url=url)
        elif len(page_data["meta_description"]) > 160:
            self._add_issue(
                INFO,
                "meta_tags",
                f"Meta description too long ({len(page_data['meta_description'])} chars, recommended <= 160)",
                url=url,
            )

    def _extract_headings(
        self,
        soup: BeautifulSoup,
        page_data: dict[str, Any],
        url: str,
    ) -> None:
        """Extract H1, H2, H3 headings and flag issues."""
        page_data["h1_tags"] = [h.get_text(strip=True) for h in soup.find_all("h1")]
        page_data["h2_tags"] = [h.get_text(strip=True) for h in soup.find_all("h2")]
        page_data["h3_tags"] = [h.get_text(strip=True) for h in soup.find_all("h3")]

        if not page_data["h1_tags"]:
            self._add_issue(WARNING, "headings", "Missing H1 tag", url=url)
        elif len(page_data["h1_tags"]) > 1:
            self._add_issue(
                WARNING,
                "headings",
                f"Multiple H1 tags found ({len(page_data['h1_tags'])})",
                url=url,
            )

    def _extract_content_stats(
        self,
        soup: BeautifulSoup,
        page_data: dict[str, Any],
    ) -> None:
        """Calculate word count from visible text."""
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        page_data["word_count"] = len(text.split())

    def _extract_canonical(
        self,
        soup: BeautifulSoup,
        page_data: dict[str, Any],
        url: str,
    ) -> None:
        """Extract the canonical link tag."""
        canonical = soup.find("link", attrs={"rel": "canonical"})
        if canonical and canonical.get("href"):
            page_data["has_canonical"] = True
            page_data["canonical_url"] = canonical["href"].strip()
        else:
            page_data["has_canonical"] = False
            page_data["canonical_url"] = ""
            self._add_issue(INFO, "canonical", "Missing canonical tag", url=url)

    def _extract_robots_meta(
        self,
        soup: BeautifulSoup,
        page_data: dict[str, Any],
    ) -> None:
        """Extract the robots meta tag."""
        robots = soup.find("meta", attrs={"name": re.compile(r"^robots$", re.I)})
        if robots and robots.get("content"):
            page_data["has_robots_meta"] = True
            page_data["robots_meta"] = robots["content"].strip()
        else:
            page_data["has_robots_meta"] = False
            page_data["robots_meta"] = ""

    def _extract_images(
        self,
        soup: BeautifulSoup,
        page_data: dict[str, Any],
        url: str,
    ) -> None:
        """Identify images that lack alt text."""
        images = soup.find_all("img")
        missing_alt: list[str] = []
        for img in images:
            alt = (img.get("alt") or "").strip()
            if not alt:
                src = img.get("src", img.get("data-src", "unknown"))
                missing_alt.append(src)

        page_data["total_images"] = len(images)
        page_data["images_without_alt"] = len(missing_alt)
        page_data["images_without_alt_list"] = missing_alt

        if missing_alt:
            self._add_issue(
                WARNING,
                "images",
                f"{len(missing_alt)} image(s) missing alt text",
                url=url,
                details={"sources": missing_alt[:10]},
            )

    def _extract_links(
        self,
        soup: BeautifulSoup,
        page_data: dict[str, Any],
        url: str,
    ) -> None:
        """Count internal/external links and detect broken links."""
        anchors = soup.find_all("a", href=True)
        internal_urls: list[str] = []
        external_urls: list[str] = []
        broken_links: list[dict[str, Any]] = []

        for a in anchors:
            href = a["href"].strip()
            # Skip anchors, javascript, mailto, tel
            if href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue

            absolute = urljoin(url, href)
            if self._is_internal(absolute):
                internal_urls.append(absolute)
            else:
                external_urls.append(absolute)

        page_data["internal_links"] = len(internal_urls)
        page_data["external_links"] = len(external_urls)
        page_data["internal_link_urls"] = internal_urls
        page_data["external_link_urls"] = external_urls

        # Check a sample of links for broken ones (limit to prevent slowness)
        sample_links = (internal_urls + external_urls)[:20]
        for link in sample_links:
            try:
                resp = self._session.head(link, timeout=10, allow_redirects=True)
                if resp.status_code >= 400:
                    broken_links.append({"url": link, "status_code": resp.status_code})
            except requests.RequestException:
                broken_links.append({"url": link, "status_code": 0})

        page_data["broken_links"] = broken_links
        if broken_links:
            self._add_issue(
                WARNING,
                "links",
                f"{len(broken_links)} broken link(s) found on page",
                url=url,
                details={"broken": broken_links},
            )

    # ------------------------------------------------------------------
    # 2. check_page_speed
    # ------------------------------------------------------------------

    def check_page_speed(self, url: Optional[str] = None) -> dict[str, Any]:
        """Check Core Web Vitals via Google PageSpeed Insights API.

        Queries both mobile and desktop strategies and returns LCP, FID/INP,
        CLS, overall scores, and Google-provided recommendations.

        Args:
            url: The page to test.  Defaults to the site homepage.

        Returns:
            A dict with keys ``mobile``, ``desktop``, ``core_web_vitals``,
            and ``recommendations``.
        """
        url = url or self.site_url
        logger.info("Checking page speed for {}", url)

        results: dict[str, Any] = {
            "url": url,
            "mobile": {},
            "desktop": {},
            "core_web_vitals": {},
            "recommendations": [],
        }

        if not self.pagespeed_api_key:
            logger.warning("No PageSpeed API key configured; skipping API call")
            self._add_issue(
                WARNING,
                "page_speed",
                "PageSpeed Insights API key not configured",
                url=url,
            )
            return results

        for strategy in ("mobile", "desktop"):
            try:
                data = self._fetch_pagespeed(url, strategy)
                results[strategy] = self._parse_pagespeed(data, strategy)
            except Exception as exc:
                logger.error("PageSpeed {} check failed for {}: {}", strategy, url, exc)
                self._add_issue(
                    WARNING,
                    "page_speed",
                    f"PageSpeed {strategy} check failed: {exc}",
                    url=url,
                )

        # Merge Core Web Vitals (prefer mobile values as primary)
        mobile_cwv = results["mobile"].get("core_web_vitals", {})
        desktop_cwv = results["desktop"].get("core_web_vitals", {})
        results["core_web_vitals"] = {
            "mobile": mobile_cwv,
            "desktop": desktop_cwv,
        }

        # Merge recommendations (deduplicate)
        seen_recs: set[str] = set()
        for strat in ("mobile", "desktop"):
            for rec in results[strat].get("recommendations", []):
                key = rec.get("title", "")
                if key and key not in seen_recs:
                    seen_recs.add(key)
                    results["recommendations"].append(rec)

        # Flag low scores
        for strategy in ("mobile", "desktop"):
            score = results[strategy].get("score")
            if score is not None and score < 50:
                self._add_issue(
                    CRITICAL,
                    "page_speed",
                    f"Low {strategy} PageSpeed score: {score}/100",
                    url=url,
                    details={"score": score, "strategy": strategy},
                )
            elif score is not None and score < 80:
                self._add_issue(
                    WARNING,
                    "page_speed",
                    f"Below-average {strategy} PageSpeed score: {score}/100",
                    url=url,
                    details={"score": score, "strategy": strategy},
                )

        return results

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
        reraise=True,
    )
    def _fetch_pagespeed(self, url: str, strategy: str) -> dict[str, Any]:
        """Call the PageSpeed Insights API.

        Args:
            url: Page URL to test.
            strategy: ``"mobile"`` or ``"desktop"``.

        Returns:
            Raw JSON response from the API.
        """
        params: dict[str, str] = {
            "url": url,
            "strategy": strategy,
            "key": self.pagespeed_api_key,
            "category": "performance",
        }
        resp = requests.get(PAGESPEED_API_URL, params=params, timeout=60)
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _parse_pagespeed(data: dict[str, Any], strategy: str) -> dict[str, Any]:
        """Parse a PageSpeed Insights API response.

        Returns:
            Dict with ``score``, ``core_web_vitals``, and
            ``recommendations``.
        """
        result: dict[str, Any] = {
            "strategy": strategy,
            "score": None,
            "core_web_vitals": {},
            "recommendations": [],
        }

        # Lighthouse score
        categories = data.get("lighthouseResult", {}).get("categories", {})
        perf = categories.get("performance", {})
        raw_score = perf.get("score")
        if raw_score is not None:
            result["score"] = int(raw_score * 100)

        # Core Web Vitals from field data
        loading = data.get("loadingExperience", {})
        metrics = loading.get("metrics", {})

        cwv_mapping = {
            "LARGEST_CONTENTFUL_PAINT_MS": "lcp",
            "FIRST_INPUT_DELAY_MS": "fid",
            "INTERACTION_TO_NEXT_PAINT": "inp",
            "CUMULATIVE_LAYOUT_SHIFT_SCORE": "cls",
        }
        for api_key, label in cwv_mapping.items():
            metric_data = metrics.get(api_key, {})
            percentile = metric_data.get("percentile")
            category = metric_data.get("category", "N/A")
            if percentile is not None:
                result["core_web_vitals"][label] = {
                    "value": percentile,
                    "category": category,
                }

        # Lab data fallback (Lighthouse audits)
        audits = data.get("lighthouseResult", {}).get("audits", {})
        lab_metrics = {
            "largest-contentful-paint": "lcp_lab",
            "total-blocking-time": "tbt_lab",
            "cumulative-layout-shift": "cls_lab",
            "speed-index": "speed_index",
            "first-contentful-paint": "fcp",
            "interactive": "tti",
        }
        for audit_key, label in lab_metrics.items():
            audit = audits.get(audit_key, {})
            if "numericValue" in audit:
                result["core_web_vitals"][label] = {
                    "value": round(audit["numericValue"], 2),
                    "display": audit.get("displayValue", ""),
                    "score": audit.get("score"),
                }

        # Recommendations (opportunities)
        for audit_id, audit_obj in audits.items():
            score = audit_obj.get("score")
            if score is not None and score < 0.9 and audit_obj.get("details", {}).get("type") == "opportunity":
                result["recommendations"].append({
                    "title": audit_obj.get("title", audit_id),
                    "description": audit_obj.get("description", ""),
                    "savings_ms": audit_obj.get("details", {}).get("overallSavingsMs"),
                    "savings_bytes": audit_obj.get("details", {}).get("overallSavingsBytes"),
                    "score": score,
                })

        return result

    # ------------------------------------------------------------------
    # 3. check_mobile_responsiveness
    # ------------------------------------------------------------------

    def check_mobile_responsiveness(self, url: Optional[str] = None) -> dict[str, Any]:
        """Check mobile-friendliness through viewport and content analysis.

        Fetches the page with a mobile User-Agent and inspects the viewport
        meta tag, tap-target sizing hints, and font-size readability.

        Args:
            url: Page to check.  Defaults to the site homepage.

        Returns:
            A dict describing viewport config, mobile usability signals,
            and any issues found.
        """
        url = url or self.site_url
        logger.info("Checking mobile responsiveness for {}", url)

        result: dict[str, Any] = {
            "url": url,
            "is_mobile_friendly": True,
            "viewport": {},
            "issues": [],
        }

        mobile_headers = {
            **DEFAULT_HEADERS,
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
            ),
        }

        try:
            resp = self._session.get(url, headers=mobile_headers, timeout=30)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            # Viewport meta tag
            viewport = soup.find("meta", attrs={"name": "viewport"})
            if viewport and viewport.get("content"):
                vp_content = viewport["content"]
                result["viewport"]["tag"] = vp_content
                result["viewport"]["has_width_device"] = "width=device-width" in vp_content
                result["viewport"]["has_initial_scale"] = "initial-scale" in vp_content

                if "user-scalable=no" in vp_content or "maximum-scale=1" in vp_content:
                    result["issues"].append({
                        "severity": WARNING,
                        "message": "Viewport prevents user zoom (user-scalable=no or maximum-scale=1)",
                    })

                if not result["viewport"]["has_width_device"]:
                    result["issues"].append({
                        "severity": WARNING,
                        "message": "Viewport missing width=device-width",
                    })
                    result["is_mobile_friendly"] = False
            else:
                result["viewport"]["tag"] = None
                result["viewport"]["has_width_device"] = False
                result["viewport"]["has_initial_scale"] = False
                result["is_mobile_friendly"] = False
                result["issues"].append({
                    "severity": CRITICAL,
                    "message": "No viewport meta tag found - page is not mobile-friendly",
                })

            # Check for horizontal scroll indicators (fixed-width elements)
            fixed_width_patterns = soup.find_all(
                style=re.compile(r"width\s*:\s*\d{4,}px", re.I),
            )
            if fixed_width_patterns:
                result["issues"].append({
                    "severity": WARNING,
                    "message": (
                        f"Found {len(fixed_width_patterns)} element(s) with large "
                        "fixed-width inline styles that may cause horizontal scrolling"
                    ),
                })

            # Check for Flash or other non-mobile plugins
            plugins = soup.find_all(["embed", "object", "applet"])
            if plugins:
                result["is_mobile_friendly"] = False
                result["issues"].append({
                    "severity": CRITICAL,
                    "message": f"Found {len(plugins)} non-mobile-compatible plugin element(s)",
                })

            # Check for responsive images
            images = soup.find_all("img")
            imgs_no_responsive = [
                img.get("src", "unknown")
                for img in images
                if not img.get("srcset") and not img.get("sizes")
            ]
            if imgs_no_responsive and len(imgs_no_responsive) > len(images) * 0.5:
                result["issues"].append({
                    "severity": INFO,
                    "message": (
                        f"{len(imgs_no_responsive)}/{len(images)} images lack "
                        "srcset/sizes for responsive delivery"
                    ),
                })

            # Check for media queries in linked stylesheets (basic heuristic)
            stylesheets = soup.find_all("link", rel="stylesheet")
            inline_styles = soup.find_all("style")
            has_media_query = False
            for style in inline_styles:
                if style.string and "@media" in style.string:
                    has_media_query = True
                    break
            if not has_media_query and not stylesheets:
                result["issues"].append({
                    "severity": INFO,
                    "message": "No CSS media queries or external stylesheets detected",
                })

            # Augment with PageSpeed mobile data if available
            if self.pagespeed_api_key:
                try:
                    psi_data = self._fetch_pagespeed(url, "mobile")
                    psi_result = self._parse_pagespeed(psi_data, "mobile")
                    result["pagespeed_mobile_score"] = psi_result.get("score")
                except Exception as exc:
                    logger.debug("Could not fetch PageSpeed for mobile check: {}", exc)

        except requests.RequestException as exc:
            logger.error("Mobile check failed for {}: {}", url, exc)
            result["is_mobile_friendly"] = False
            result["issues"].append({
                "severity": CRITICAL,
                "message": f"Could not fetch page for mobile check: {exc}",
            })

        if not result["is_mobile_friendly"]:
            self._add_issue(
                CRITICAL,
                "mobile",
                "Page is not mobile-friendly",
                url=url,
                details={"issues": result["issues"]},
            )
        elif result["issues"]:
            for issue in result["issues"]:
                self._add_issue(
                    issue["severity"],
                    "mobile",
                    issue["message"],
                    url=url,
                )

        return result

    # ------------------------------------------------------------------
    # 4. validate_sitemap
    # ------------------------------------------------------------------

    def validate_sitemap(
        self,
        sitemap_url: Optional[str] = None,
    ) -> dict[str, Any]:
        """Fetch and validate sitemap.xml.

        Checks for valid XML structure, ensures all listed URLs resolve,
        validates ``<lastmod>`` dates, and cross-references crawled pages.

        Args:
            sitemap_url: URL of the sitemap.  Defaults to
                ``{site_url}/sitemap.xml``.

        Returns:
            A dict summarising the sitemap validation results.
        """
        sitemap_url = sitemap_url or f"{self.site_url}/sitemap.xml"
        logger.info("Validating sitemap at {}", sitemap_url)

        result: dict[str, Any] = {
            "sitemap_url": sitemap_url,
            "exists": False,
            "is_valid_xml": False,
            "total_urls": 0,
            "broken_urls": [],
            "missing_lastmod": [],
            "invalid_lastmod": [],
            "urls_not_in_sitemap": [],
            "issues": [],
        }

        # Fetch sitemap
        try:
            resp = self._fetch(sitemap_url, timeout=30)
            if resp.status_code != 200:
                result["issues"].append(f"Sitemap returned HTTP {resp.status_code}")
                self._add_issue(
                    CRITICAL,
                    "sitemap",
                    f"Sitemap not accessible (HTTP {resp.status_code})",
                    url=sitemap_url,
                )
                return result
            result["exists"] = True
        except requests.RequestException as exc:
            self._add_issue(
                CRITICAL,
                "sitemap",
                f"Could not fetch sitemap: {exc}",
                url=sitemap_url,
            )
            return result

        # Parse XML
        try:
            root = ET.fromstring(resp.content)
            result["is_valid_xml"] = True
        except ET.ParseError as exc:
            result["issues"].append(f"Invalid XML: {exc}")
            self._add_issue(
                CRITICAL,
                "sitemap",
                f"Sitemap has invalid XML: {exc}",
                url=sitemap_url,
            )
            return result

        # Handle namespace
        ns = ""
        match = re.match(r"\{(.+?)\}", root.tag)
        if match:
            ns = match.group(1)
        ns_prefix = f"{{{ns}}}" if ns else ""

        # Check for sitemap index
        sitemap_entries = root.findall(f"{ns_prefix}sitemap")
        if sitemap_entries:
            logger.info("Sitemap index found with {} child sitemaps", len(sitemap_entries))
            result["is_sitemap_index"] = True
            result["child_sitemaps"] = []
            for entry in sitemap_entries:
                loc = entry.find(f"{ns_prefix}loc")
                if loc is not None and loc.text:
                    result["child_sitemaps"].append(loc.text.strip())
            return result

        # Process URL entries
        url_entries = root.findall(f"{ns_prefix}url")
        result["total_urls"] = len(url_entries)
        sitemap_urls: set[str] = set()

        for entry in url_entries:
            loc = entry.find(f"{ns_prefix}loc")
            lastmod = entry.find(f"{ns_prefix}lastmod")

            if loc is None or not loc.text:
                continue

            page_url = loc.text.strip()
            sitemap_urls.add(self._normalise_url(page_url))

            # Validate lastmod
            if lastmod is None or not lastmod.text:
                result["missing_lastmod"].append(page_url)
            else:
                try:
                    datetime.datetime.fromisoformat(lastmod.text.strip().replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    result["invalid_lastmod"].append({
                        "url": page_url,
                        "lastmod": lastmod.text.strip(),
                    })

        # Spot-check a sample of sitemap URLs for broken links
        sample_size = min(20, len(sitemap_urls))
        sample_urls = list(sitemap_urls)[:sample_size]
        for s_url in sample_urls:
            try:
                head = self._session.head(s_url, timeout=10, allow_redirects=True)
                if head.status_code >= 400:
                    result["broken_urls"].append({
                        "url": s_url,
                        "status_code": head.status_code,
                    })
            except requests.RequestException:
                result["broken_urls"].append({"url": s_url, "status_code": 0})

        # Cross-reference with crawled pages
        if self.crawled_pages:
            crawled_urls = {self._normalise_url(p["url"]) for p in self.crawled_pages}
            not_in_sitemap = crawled_urls - sitemap_urls
            result["urls_not_in_sitemap"] = list(not_in_sitemap)

        # Issue logging
        if not result["total_urls"]:
            self._add_issue(CRITICAL, "sitemap", "Sitemap contains no URLs", url=sitemap_url)

        if result["broken_urls"]:
            self._add_issue(
                WARNING,
                "sitemap",
                f"{len(result['broken_urls'])} broken URL(s) in sitemap",
                url=sitemap_url,
                details={"broken": result["broken_urls"]},
            )

        if result["missing_lastmod"]:
            self._add_issue(
                INFO,
                "sitemap",
                f"{len(result['missing_lastmod'])} URL(s) missing <lastmod>",
                url=sitemap_url,
            )

        if result["urls_not_in_sitemap"]:
            self._add_issue(
                WARNING,
                "sitemap",
                f"{len(result['urls_not_in_sitemap'])} crawled page(s) not found in sitemap",
                url=sitemap_url,
                details={"missing": result["urls_not_in_sitemap"][:20]},
            )

        logger.info(
            "Sitemap validation complete: {} URLs, {} broken, {} missing lastmod",
            result["total_urls"],
            len(result["broken_urls"]),
            len(result["missing_lastmod"]),
        )
        return result

    # ------------------------------------------------------------------
    # 5. validate_robots_txt
    # ------------------------------------------------------------------

    def validate_robots_txt(
        self,
        url: Optional[str] = None,
    ) -> dict[str, Any]:
        """Fetch and validate robots.txt.

        Checks existence, ensures important pages are not blocked, looks
        for a ``Sitemap:`` directive, and reports unusual directives.

        Args:
            url: The site root from which ``/robots.txt`` is resolved.
                Defaults to the configured site URL.

        Returns:
            A dict summarising the robots.txt validation results.
        """
        base = url or self.site_url
        robots_url = f"{base.rstrip('/')}/robots.txt"
        logger.info("Validating robots.txt at {}", robots_url)

        result: dict[str, Any] = {
            "robots_url": robots_url,
            "exists": False,
            "content": "",
            "has_sitemap_directive": False,
            "sitemap_urls": [],
            "user_agents": [],
            "disallow_rules": [],
            "allow_rules": [],
            "blocks_important_pages": False,
            "blocked_important": [],
            "issues": [],
        }

        try:
            resp = self._fetch(robots_url, timeout=15)
            if resp.status_code != 200:
                self._add_issue(
                    WARNING,
                    "robots_txt",
                    f"robots.txt returned HTTP {resp.status_code}",
                    url=robots_url,
                )
                return result
            result["exists"] = True
            result["content"] = resp.text
        except requests.RequestException as exc:
            self._add_issue(
                WARNING,
                "robots_txt",
                f"Could not fetch robots.txt: {exc}",
                url=robots_url,
            )
            return result

        # Parse directives
        current_ua: Optional[str] = None
        important_paths = ["/", "/services", "/contact", "/about", "/apostille", "/notary"]

        for line in result["content"].splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split(":", 1)
            if len(parts) != 2:
                continue

            directive = parts[0].strip().lower()
            value = parts[1].strip()

            if directive == "user-agent":
                current_ua = value
                if value not in result["user_agents"]:
                    result["user_agents"].append(value)
            elif directive == "disallow":
                result["disallow_rules"].append({
                    "user_agent": current_ua,
                    "path": value,
                })
                # Check if blocking important pages
                if value and value != "/":
                    for imp in important_paths:
                        if imp.startswith(value) and current_ua in ("*", None):
                            result["blocks_important_pages"] = True
                            result["blocked_important"].append({
                                "path": value,
                                "affects": imp,
                            })
                elif value == "/" and current_ua == "*":
                    result["blocks_important_pages"] = True
                    result["blocked_important"].append({
                        "path": "/",
                        "affects": "ENTIRE SITE",
                    })
            elif directive == "allow":
                result["allow_rules"].append({
                    "user_agent": current_ua,
                    "path": value,
                })
            elif directive == "sitemap":
                result["has_sitemap_directive"] = True
                result["sitemap_urls"].append(value)

        # Flag issues
        if not result["has_sitemap_directive"]:
            self._add_issue(
                WARNING,
                "robots_txt",
                "robots.txt does not reference a sitemap",
                url=robots_url,
            )
            result["issues"].append("Missing Sitemap directive")

        if result["blocks_important_pages"]:
            self._add_issue(
                CRITICAL,
                "robots_txt",
                "robots.txt blocks important pages",
                url=robots_url,
                details={"blocked": result["blocked_important"]},
            )
            result["issues"].append("Blocks important pages")

        if not result["disallow_rules"]:
            result["issues"].append("No Disallow rules - consider restricting admin/staging paths")
            self._add_issue(
                INFO,
                "robots_txt",
                "No Disallow rules found; consider restricting admin/staging paths",
                url=robots_url,
            )

        logger.info(
            "robots.txt validation complete: exists={}, sitemap={}, blocks_important={}",
            result["exists"],
            result["has_sitemap_directive"],
            result["blocks_important_pages"],
        )
        return result

    # ------------------------------------------------------------------
    # 6. check_ssl
    # ------------------------------------------------------------------

    def check_ssl(self, url: Optional[str] = None) -> dict[str, Any]:
        """Verify SSL certificate validity and check for mixed content.

        Args:
            url: The page URL to check.  Defaults to the site URL.

        Returns:
            A dict with certificate details, expiry information, and any
            mixed content issues.
        """
        url = url or self.site_url
        parsed = urlparse(url)
        hostname = parsed.hostname or self.domain
        port = parsed.port or 443
        logger.info("Checking SSL for {} ({}:{})", url, hostname, port)

        result: dict[str, Any] = {
            "url": url,
            "hostname": hostname,
            "ssl_valid": False,
            "certificate": {},
            "expiry_date": None,
            "days_until_expiry": None,
            "issuer": "",
            "mixed_content": [],
            "issues": [],
        }

        # Certificate check
        try:
            context = ssl.create_default_context()
            with socket.create_connection((hostname, port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()

            result["ssl_valid"] = True
            result["certificate"] = {
                "subject": dict(x[0] for x in cert.get("subject", ())),
                "issuer": dict(x[0] for x in cert.get("issuer", ())),
                "serial_number": cert.get("serialNumber", ""),
                "version": cert.get("version"),
            }

            # Expiry
            not_after = cert.get("notAfter", "")
            if not_after:
                expiry = datetime.datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
                result["expiry_date"] = expiry.isoformat()
                days_left = (expiry - datetime.datetime.utcnow()).days
                result["days_until_expiry"] = days_left

                if days_left < 0:
                    self._add_issue(CRITICAL, "ssl", "SSL certificate has EXPIRED", url=url)
                    result["ssl_valid"] = False
                elif days_left < 14:
                    self._add_issue(
                        CRITICAL,
                        "ssl",
                        f"SSL certificate expires in {days_left} days",
                        url=url,
                    )
                elif days_left < 30:
                    self._add_issue(
                        WARNING,
                        "ssl",
                        f"SSL certificate expires in {days_left} days",
                        url=url,
                    )

            issuer = result["certificate"].get("issuer", {})
            result["issuer"] = issuer.get("organizationName", issuer.get("commonName", ""))

        except ssl.SSLCertVerificationError as exc:
            result["ssl_valid"] = False
            result["issues"].append(f"SSL verification failed: {exc}")
            self._add_issue(
                CRITICAL,
                "ssl",
                f"SSL certificate verification failed: {exc}",
                url=url,
            )
        except (socket.error, OSError) as exc:
            result["issues"].append(f"Could not connect for SSL check: {exc}")
            self._add_issue(
                CRITICAL,
                "ssl",
                f"Could not connect for SSL check: {exc}",
                url=url,
            )
            return result

        # Mixed content check
        try:
            resp = self._fetch(url, timeout=30)
            if resp.status_code == 200 and "text/html" in resp.headers.get("Content-Type", ""):
                soup = BeautifulSoup(resp.text, "lxml")
                mixed: list[dict[str, str]] = []

                resource_tags = [
                    ("img", "src"),
                    ("script", "src"),
                    ("link", "href"),
                    ("video", "src"),
                    ("audio", "src"),
                    ("source", "src"),
                    ("iframe", "src"),
                ]

                for tag_name, attr in resource_tags:
                    for tag in soup.find_all(tag_name):
                        src_val = tag.get(attr, "")
                        if src_val.startswith("http://"):
                            mixed.append({
                                "tag": tag_name,
                                "attribute": attr,
                                "url": src_val,
                            })

                result["mixed_content"] = mixed
                if mixed:
                    self._add_issue(
                        WARNING,
                        "ssl",
                        f"{len(mixed)} mixed content resource(s) loaded over HTTP",
                        url=url,
                        details={"resources": mixed[:10]},
                    )
        except requests.RequestException as exc:
            logger.debug("Could not check mixed content for {}: {}", url, exc)

        return result

    # ------------------------------------------------------------------
    # 7. check_canonical_tags
    # ------------------------------------------------------------------

    def check_canonical_tags(
        self,
        pages: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        """Audit canonical tags across all pages for duplicate content issues.

        Args:
            pages: A list of crawled page dicts (from :meth:`crawl_site`).
                Defaults to ``self.crawled_pages``.

        Returns:
            A dict summarising canonical tag issues including missing tags,
            self-referencing canonicals, and duplicate canonical targets.
        """
        pages = pages if pages is not None else self.crawled_pages
        logger.info("Auditing canonical tags across {} pages", len(pages))

        result: dict[str, Any] = {
            "total_pages": len(pages),
            "missing_canonical": [],
            "self_referencing": [],
            "pointing_elsewhere": [],
            "canonical_chains": [],
            "duplicate_canonicals": {},
            "issues": [],
        }

        canonical_map: dict[str, list[str]] = defaultdict(list)

        for page in pages:
            url = page.get("url", "")
            has_canonical = page.get("has_canonical", False)
            canonical_url = page.get("canonical_url", "")

            if not has_canonical or not canonical_url:
                result["missing_canonical"].append(url)
                continue

            norm_url = self._normalise_url(url)
            norm_canonical = self._normalise_url(canonical_url)

            if norm_url == norm_canonical:
                result["self_referencing"].append(url)
            else:
                result["pointing_elsewhere"].append({
                    "page": url,
                    "canonical_target": canonical_url,
                })

            canonical_map[norm_canonical].append(url)

        # Find duplicates (multiple pages pointing to the same canonical)
        for target, sources in canonical_map.items():
            if len(sources) > 1:
                result["duplicate_canonicals"][target] = sources

        # Issue logging
        if result["missing_canonical"]:
            self._add_issue(
                WARNING,
                "canonical",
                f"{len(result['missing_canonical'])} page(s) missing canonical tags",
                details={"pages": result["missing_canonical"][:10]},
            )

        if result["duplicate_canonicals"]:
            for target, sources in result["duplicate_canonicals"].items():
                self._add_issue(
                    INFO,
                    "canonical",
                    f"{len(sources)} pages share canonical target {target}",
                    details={"sources": sources},
                )

        if result["pointing_elsewhere"]:
            self._add_issue(
                INFO,
                "canonical",
                f"{len(result['pointing_elsewhere'])} page(s) have canonical pointing to a different URL",
                details={"pages": [p["page"] for p in result["pointing_elsewhere"][:10]]},
            )

        logger.info(
            "Canonical audit: {} missing, {} self-ref, {} cross-canonical, {} duplicate targets",
            len(result["missing_canonical"]),
            len(result["self_referencing"]),
            len(result["pointing_elsewhere"]),
            len(result["duplicate_canonicals"]),
        )
        return result

    # ------------------------------------------------------------------
    # 8. audit_internal_linking
    # ------------------------------------------------------------------

    def audit_internal_linking(
        self,
        pages: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        """Analyse internal linking structure.

        Identifies orphan pages, pages with too few/many links, and
        suggests improvements.

        Args:
            pages: A list of crawled page dicts (from :meth:`crawl_site`).
                Defaults to ``self.crawled_pages``.

        Returns:
            A dict with linking statistics, orphan pages, hub pages,
            and suggestions.
        """
        pages = pages if pages is not None else self.crawled_pages
        logger.info("Auditing internal linking across {} pages", len(pages))

        result: dict[str, Any] = {
            "total_pages": len(pages),
            "orphan_pages": [],
            "pages_low_internal_links": [],
            "pages_high_internal_links": [],
            "hub_pages": [],
            "average_internal_links": 0.0,
            "link_distribution": {},
            "suggestions": [],
        }

        # Build inbound link map
        all_page_urls: set[str] = {self._normalise_url(p["url"]) for p in pages}
        inbound_counts: dict[str, int] = defaultdict(int)
        outbound_counts: dict[str, int] = {}

        for page in pages:
            page_norm = self._normalise_url(page["url"])
            internal_links = page.get("internal_link_urls", [])
            outbound_counts[page_norm] = len(internal_links)

            for link in internal_links:
                norm_link = self._normalise_url(link)
                if norm_link in all_page_urls:
                    inbound_counts[norm_link] += 1

        # Orphan pages (no inbound internal links aside from self)
        for page_url in all_page_urls:
            if inbound_counts.get(page_url, 0) == 0:
                # Homepage won't usually have internal inbound from crawl
                if page_url != self._normalise_url(self.site_url):
                    result["orphan_pages"].append(page_url)

        # Low/high outbound
        total_outbound = 0
        for page in pages:
            page_norm = self._normalise_url(page["url"])
            count = page.get("internal_links", 0) or 0
            total_outbound += count

            if count < 3 and page_norm != self._normalise_url(self.site_url):
                result["pages_low_internal_links"].append({
                    "url": page["url"],
                    "internal_links": count,
                })
            elif count > 100:
                result["pages_high_internal_links"].append({
                    "url": page["url"],
                    "internal_links": count,
                })

        result["average_internal_links"] = (
            round(total_outbound / len(pages), 1) if pages else 0.0
        )

        # Hub pages (most outbound)
        pages_sorted = sorted(pages, key=lambda p: p.get("internal_links", 0) or 0, reverse=True)
        result["hub_pages"] = [
            {"url": p["url"], "internal_links": p.get("internal_links", 0)}
            for p in pages_sorted[:5]
        ]

        # Distribution
        ranges = {"0": 0, "1-5": 0, "6-10": 0, "11-20": 0, "21-50": 0, "51+": 0}
        for page in pages:
            c = page.get("internal_links", 0) or 0
            if c == 0:
                ranges["0"] += 1
            elif c <= 5:
                ranges["1-5"] += 1
            elif c <= 10:
                ranges["6-10"] += 1
            elif c <= 20:
                ranges["11-20"] += 1
            elif c <= 50:
                ranges["21-50"] += 1
            else:
                ranges["51+"] += 1
        result["link_distribution"] = ranges

        # Suggestions
        if result["orphan_pages"]:
            result["suggestions"].append(
                f"Add internal links to {len(result['orphan_pages'])} orphan page(s) "
                "to improve discoverability and crawl efficiency."
            )
            self._add_issue(
                WARNING,
                "internal_linking",
                f"{len(result['orphan_pages'])} orphan page(s) with no inbound internal links",
                details={"pages": result["orphan_pages"][:10]},
            )

        if result["pages_low_internal_links"]:
            result["suggestions"].append(
                f"{len(result['pages_low_internal_links'])} page(s) have fewer than 3 internal "
                "links. Add contextual links to related service pages."
            )
            self._add_issue(
                INFO,
                "internal_linking",
                f"{len(result['pages_low_internal_links'])} page(s) with very few internal links",
            )

        if result["pages_high_internal_links"]:
            result["suggestions"].append(
                f"{len(result['pages_high_internal_links'])} page(s) have over 100 internal links. "
                "Consider pruning to keep link equity concentrated."
            )

        logger.info(
            "Internal linking audit: {} orphan, avg {:.1f} links/page",
            len(result["orphan_pages"]),
            result["average_internal_links"],
        )
        return result

    # ------------------------------------------------------------------
    # 9. audit_images
    # ------------------------------------------------------------------

    def audit_images(
        self,
        pages: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        """Check all images for alt tags, compression, sizing, and WebP.

        Args:
            pages: A list of crawled page dicts (from :meth:`crawl_site`).
                Defaults to ``self.crawled_pages``.

        Returns:
            A dict with per-image findings (alt text, size, format) and
            aggregated statistics.
        """
        pages = pages if pages is not None else self.crawled_pages
        logger.info("Auditing images across {} pages", len(pages))

        result: dict[str, Any] = {
            "total_images": 0,
            "images_without_alt": 0,
            "large_images": [],
            "non_webp_images": [],
            "images_without_dimensions": [],
            "image_details": [],
            "issues": [],
        }

        seen_images: set[str] = set()

        for page in pages:
            page_url = page.get("url", "")
            result["images_without_alt"] += page.get("images_without_alt", 0)

            # Re-fetch the page to inspect individual images
            try:
                resp = self._fetch(page_url, timeout=20)
                if resp.status_code != 200:
                    continue
                soup = BeautifulSoup(resp.text, "lxml")
            except requests.RequestException:
                continue

            for img in soup.find_all("img"):
                src = img.get("src") or img.get("data-src") or ""
                if not src or src.startswith("data:"):
                    continue
                absolute_src = urljoin(page_url, src)

                if absolute_src in seen_images:
                    continue
                seen_images.add(absolute_src)
                result["total_images"] += 1

                detail: dict[str, Any] = {
                    "src": absolute_src,
                    "page": page_url,
                    "has_alt": bool((img.get("alt") or "").strip()),
                    "alt_text": (img.get("alt") or "").strip(),
                    "has_width": img.get("width") is not None,
                    "has_height": img.get("height") is not None,
                    "format": "",
                    "size_kb": None,
                }

                # Determine format from URL
                path_lower = urlparse(absolute_src).path.lower()
                if path_lower.endswith(".webp"):
                    detail["format"] = "webp"
                elif path_lower.endswith(".png"):
                    detail["format"] = "png"
                elif path_lower.endswith((".jpg", ".jpeg")):
                    detail["format"] = "jpeg"
                elif path_lower.endswith(".gif"):
                    detail["format"] = "gif"
                elif path_lower.endswith(".svg"):
                    detail["format"] = "svg"
                else:
                    detail["format"] = "unknown"

                # Check image file size via HEAD request
                try:
                    head = self._session.head(absolute_src, timeout=10, allow_redirects=True)
                    content_length = head.headers.get("Content-Length")
                    if content_length:
                        size_kb = int(content_length) / 1024
                        detail["size_kb"] = round(size_kb, 1)
                        if size_kb > 200:
                            result["large_images"].append({
                                "src": absolute_src,
                                "size_kb": round(size_kb, 1),
                                "page": page_url,
                            })

                    # Detect format from content-type header if not from URL
                    ct = head.headers.get("Content-Type", "")
                    if detail["format"] == "unknown":
                        if "webp" in ct:
                            detail["format"] = "webp"
                        elif "png" in ct:
                            detail["format"] = "png"
                        elif "jpeg" in ct or "jpg" in ct:
                            detail["format"] = "jpeg"
                        elif "gif" in ct:
                            detail["format"] = "gif"
                        elif "svg" in ct:
                            detail["format"] = "svg"
                except requests.RequestException:
                    pass

                # Not WebP (skip SVGs - they are already optimised)
                if detail["format"] not in ("webp", "svg", "unknown"):
                    result["non_webp_images"].append({
                        "src": absolute_src,
                        "format": detail["format"],
                        "page": page_url,
                    })

                if not detail["has_width"] or not detail["has_height"]:
                    result["images_without_dimensions"].append({
                        "src": absolute_src,
                        "page": page_url,
                    })

                result["image_details"].append(detail)

        # Issue logging
        if result["images_without_alt"] > 0:
            self._add_issue(
                WARNING,
                "images",
                f"{result['images_without_alt']} image(s) across all pages missing alt text",
            )

        if result["large_images"]:
            self._add_issue(
                WARNING,
                "images",
                f"{len(result['large_images'])} image(s) exceed 200 KB - consider compression",
                details={"images": result["large_images"][:10]},
            )

        if result["non_webp_images"]:
            self._add_issue(
                INFO,
                "images",
                f"{len(result['non_webp_images'])} image(s) not in WebP format - "
                "serving WebP can reduce file size by 25-35%",
                details={"images": result["non_webp_images"][:10]},
            )

        if result["images_without_dimensions"]:
            self._add_issue(
                INFO,
                "images",
                f"{len(result['images_without_dimensions'])} image(s) missing explicit "
                "width/height attributes (may cause CLS)",
                details={"images": result["images_without_dimensions"][:10]},
            )

        logger.info(
            "Image audit: {} total, {} no alt, {} large, {} non-WebP",
            result["total_images"],
            result["images_without_alt"],
            len(result["large_images"]),
            len(result["non_webp_images"]),
        )
        return result

    # ------------------------------------------------------------------
    # 10. run_full_audit
    # ------------------------------------------------------------------

    def run_full_audit(self) -> dict[str, Any]:
        """Run a complete technical SEO audit.

        Executes every audit step in sequence and returns a unified result
        dict with prioritised recommendations.

        Returns:
            A dict containing the results of every sub-audit, an overall
            score, issue counts by severity, and prioritised recommendations.
        """
        logger.info("=== Starting full technical SEO audit for {} ===", self.site_url)
        self.issues = []
        audit_start = time.monotonic()

        results: dict[str, Any] = {
            "site_url": self.site_url,
            "audit_timestamp": datetime.datetime.utcnow().isoformat(),
            "crawl": {},
            "page_speed": {},
            "mobile": {},
            "sitemap": {},
            "robots_txt": {},
            "ssl": {},
            "canonical_tags": {},
            "internal_linking": {},
            "images": {},
            "overall_score": 0.0,
            "issues_summary": {},
            "recommendations": [],
        }

        # 1. Crawl site
        logger.info("Step 1/9: Crawling site")
        results["crawl"] = {
            "pages": self.crawl_site(),
            "total_pages": len(self.crawled_pages),
        }

        # 2. Page speed (homepage)
        logger.info("Step 2/9: Checking page speed")
        results["page_speed"] = self.check_page_speed()

        # 3. Mobile responsiveness
        logger.info("Step 3/9: Checking mobile responsiveness")
        results["mobile"] = self.check_mobile_responsiveness()

        # 4. Sitemap validation
        logger.info("Step 4/9: Validating sitemap")
        results["sitemap"] = self.validate_sitemap()

        # 5. Robots.txt validation
        logger.info("Step 5/9: Validating robots.txt")
        results["robots_txt"] = self.validate_robots_txt()

        # 6. SSL check
        logger.info("Step 6/9: Checking SSL certificate")
        results["ssl"] = self.check_ssl()

        # 7. Canonical tags
        logger.info("Step 7/9: Auditing canonical tags")
        results["canonical_tags"] = self.check_canonical_tags()

        # 8. Internal linking
        logger.info("Step 8/9: Auditing internal linking")
        results["internal_linking"] = self.audit_internal_linking()

        # 9. Images
        logger.info("Step 9/9: Auditing images")
        results["images"] = self.audit_images()

        # Calculate score and prioritise
        results["overall_score"] = self._calculate_overall_score(results)
        results["issues_summary"] = self._summarise_issues()
        results["recommendations"] = self._prioritise_recommendations()

        elapsed = round(time.monotonic() - audit_start, 1)
        logger.info(
            "=== Full audit complete in {}s | Score: {}/100 | "
            "Critical: {} | Warnings: {} | Info: {} ===",
            elapsed,
            results["overall_score"],
            results["issues_summary"].get("critical", 0),
            results["issues_summary"].get("warning", 0),
            results["issues_summary"].get("info", 0),
        )

        # Save to database
        self._save_audit(results)

        return results

    # ------------------------------------------------------------------
    # 11. get_audit_report
    # ------------------------------------------------------------------

    def get_audit_report(
        self,
        audit_results: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Generate a comprehensive technical SEO audit report.

        If *audit_results* is not supplied, the method will run
        :meth:`run_full_audit` first.

        Args:
            audit_results: Pre-computed audit dict (from :meth:`run_full_audit`).

        Returns:
            A formatted report dict with executive summary, section scores,
            and prioritised action items.
        """
        if audit_results is None:
            audit_results = self.run_full_audit()

        logger.info("Generating audit report")

        # Section scores (0-100)
        section_scores = self._compute_section_scores(audit_results)

        report: dict[str, Any] = {
            "title": f"Technical SEO Audit Report - {COMPANY.get('name', 'Website')}",
            "generated_at": datetime.datetime.utcnow().isoformat(),
            "site_url": self.site_url,
            "overall_score": audit_results.get("overall_score", 0),
            "executive_summary": self._build_executive_summary(audit_results, section_scores),
            "section_scores": section_scores,
            "sections": {
                "crawl_summary": {
                    "score": section_scores.get("crawlability", 0),
                    "pages_crawled": len(self.crawled_pages),
                    "status_code_distribution": self._status_code_distribution(),
                    "average_load_time_ms": self._average_load_time(),
                    "average_page_size_kb": self._average_page_size(),
                    "average_word_count": self._average_word_count(),
                },
                "page_speed": {
                    "score": section_scores.get("performance", 0),
                    "data": audit_results.get("page_speed", {}),
                },
                "mobile": {
                    "score": section_scores.get("mobile", 0),
                    "data": audit_results.get("mobile", {}),
                },
                "sitemap": {
                    "score": section_scores.get("sitemap", 0),
                    "data": audit_results.get("sitemap", {}),
                },
                "robots_txt": {
                    "score": section_scores.get("robots_txt", 0),
                    "data": audit_results.get("robots_txt", {}),
                },
                "ssl": {
                    "score": section_scores.get("ssl", 0),
                    "data": audit_results.get("ssl", {}),
                },
                "canonical_tags": {
                    "score": section_scores.get("canonical", 0),
                    "data": audit_results.get("canonical_tags", {}),
                },
                "internal_linking": {
                    "score": section_scores.get("internal_linking", 0),
                    "data": audit_results.get("internal_linking", {}),
                },
                "images": {
                    "score": section_scores.get("images", 0),
                    "data": audit_results.get("images", {}),
                },
            },
            "all_issues": self.issues,
            "prioritised_fixes": audit_results.get("recommendations", []),
        }

        return report

    # ------------------------------------------------------------------
    # 12. compare_audits
    # ------------------------------------------------------------------

    def compare_audits(
        self,
        audit_id_1: int,
        audit_id_2: int,
    ) -> dict[str, Any]:
        """Compare two audits to show progress over time.

        Args:
            audit_id_1: Database ID of the earlier (baseline) audit.
            audit_id_2: Database ID of the later (current) audit.

        Returns:
            A dict showing deltas for overall score, issue counts,
            page counts, and per-section scores.
        """
        logger.info("Comparing audit #{} with audit #{}", audit_id_1, audit_id_2)

        db = SessionLocal()
        try:
            audit_1: Optional[TechnicalAudit] = db.query(TechnicalAudit).get(audit_id_1)
            audit_2: Optional[TechnicalAudit] = db.query(TechnicalAudit).get(audit_id_2)

            if not audit_1 or not audit_2:
                missing = []
                if not audit_1:
                    missing.append(str(audit_id_1))
                if not audit_2:
                    missing.append(str(audit_id_2))
                logger.error("Audit(s) not found: {}", ", ".join(missing))
                return {"error": f"Audit(s) not found: {', '.join(missing)}"}

            data_1 = audit_1.audit_data or {}
            data_2 = audit_2.audit_data or {}

            def _delta(a: Optional[float], b: Optional[float]) -> Optional[float]:
                if a is not None and b is not None:
                    return round(b - a, 2)
                return None

            comparison: dict[str, Any] = {
                "baseline_audit_id": audit_id_1,
                "current_audit_id": audit_id_2,
                "baseline_date": (
                    audit_1.audit_date.isoformat() if audit_1.audit_date else None
                ),
                "current_date": (
                    audit_2.audit_date.isoformat() if audit_2.audit_date else None
                ),
                "overall_score": {
                    "baseline": audit_1.overall_score,
                    "current": audit_2.overall_score,
                    "delta": _delta(audit_1.overall_score, audit_2.overall_score),
                },
                "pages_crawled": {
                    "baseline": audit_1.pages_crawled,
                    "current": audit_2.pages_crawled,
                    "delta": _delta(
                        float(audit_1.pages_crawled or 0),
                        float(audit_2.pages_crawled or 0),
                    ),
                },
                "issues": {
                    "total": {
                        "baseline": audit_1.issues_found,
                        "current": audit_2.issues_found,
                        "delta": _delta(
                            float(audit_1.issues_found or 0),
                            float(audit_2.issues_found or 0),
                        ),
                    },
                    "critical": {
                        "baseline": audit_1.critical_issues,
                        "current": audit_2.critical_issues,
                        "delta": _delta(
                            float(audit_1.critical_issues or 0),
                            float(audit_2.critical_issues or 0),
                        ),
                    },
                    "warnings": {
                        "baseline": audit_1.warnings,
                        "current": audit_2.warnings,
                        "delta": _delta(
                            float(audit_1.warnings or 0),
                            float(audit_2.warnings or 0),
                        ),
                    },
                },
                "section_scores": {},
                "resolved_issues": [],
                "new_issues": [],
            }

            # Compare section-level data when available
            recs_1 = set()
            recs_2 = set()
            for rec in (audit_1.recommendations or []):
                recs_1.add(rec.get("message", ""))
            for rec in (audit_2.recommendations or []):
                recs_2.add(rec.get("message", ""))

            comparison["resolved_issues"] = list(recs_1 - recs_2)
            comparison["new_issues"] = list(recs_2 - recs_1)

            # Section scores comparison from stored audit_data
            for section_key in (
                "crawlability", "performance", "mobile", "sitemap",
                "robots_txt", "ssl", "canonical", "internal_linking", "images",
            ):
                score_1 = (data_1.get("section_scores") or {}).get(section_key)
                score_2 = (data_2.get("section_scores") or {}).get(section_key)
                comparison["section_scores"][section_key] = {
                    "baseline": score_1,
                    "current": score_2,
                    "delta": _delta(
                        float(score_1) if score_1 is not None else None,
                        float(score_2) if score_2 is not None else None,
                    ),
                }

            return comparison

        finally:
            db.close()

    # ------------------------------------------------------------------
    # Private scoring / reporting helpers
    # ------------------------------------------------------------------

    def _calculate_overall_score(self, results: dict[str, Any]) -> float:
        """Derive a 0-100 overall score from the audit results."""
        scores: list[float] = []

        # Crawl health: penalise for 4xx/5xx pages
        if self.crawled_pages:
            ok_pages = sum(
                1 for p in self.crawled_pages
                if (p.get("status_code") or 0) < 400
            )
            scores.append(ok_pages / len(self.crawled_pages) * 100)

        # SSL
        ssl_data = results.get("ssl", {})
        scores.append(100.0 if ssl_data.get("ssl_valid") else 0.0)

        # Mobile
        mobile_data = results.get("mobile", {})
        scores.append(100.0 if mobile_data.get("is_mobile_friendly") else 0.0)

        # Sitemap
        sitemap_data = results.get("sitemap", {})
        sitemap_score = 0.0
        if sitemap_data.get("exists"):
            sitemap_score += 40
        if sitemap_data.get("is_valid_xml"):
            sitemap_score += 30
        if not sitemap_data.get("broken_urls"):
            sitemap_score += 30
        scores.append(sitemap_score)

        # Robots.txt
        robots_data = results.get("robots_txt", {})
        robots_score = 0.0
        if robots_data.get("exists"):
            robots_score += 40
        if robots_data.get("has_sitemap_directive"):
            robots_score += 30
        if not robots_data.get("blocks_important_pages"):
            robots_score += 30
        scores.append(robots_score)

        # PageSpeed (average of mobile and desktop)
        ps_data = results.get("page_speed", {})
        mobile_ps = ps_data.get("mobile", {}).get("score")
        desktop_ps = ps_data.get("desktop", {}).get("score")
        ps_scores = [s for s in [mobile_ps, desktop_ps] if s is not None]
        if ps_scores:
            scores.append(sum(ps_scores) / len(ps_scores))

        # Issue penalty (more critical issues -> lower score)
        issue_summary = self._summarise_issues()
        critical = issue_summary.get("critical", 0)
        warnings = issue_summary.get("warning", 0)
        penalty = min(critical * 5 + warnings * 2, 30)

        raw = sum(scores) / len(scores) if scores else 0.0
        return round(max(raw - penalty, 0), 1)

    def _summarise_issues(self) -> dict[str, int]:
        """Count issues by severity."""
        summary: dict[str, int] = {CRITICAL: 0, WARNING: 0, INFO: 0}
        for issue in self.issues:
            sev = issue.get("severity", INFO)
            summary[sev] = summary.get(sev, 0) + 1
        summary["total"] = sum(summary.values())
        return summary

    def _prioritise_recommendations(self) -> list[dict[str, Any]]:
        """Return issues sorted by severity, then category."""
        severity_order = {CRITICAL: 0, WARNING: 1, INFO: 2}
        sorted_issues = sorted(
            self.issues,
            key=lambda i: (severity_order.get(i.get("severity", INFO), 3), i.get("category", "")),
        )

        recommendations: list[dict[str, Any]] = []
        seen: set[str] = set()
        for issue in sorted_issues:
            key = f"{issue['severity']}:{issue['category']}:{issue['message']}"
            if key not in seen:
                seen.add(key)
                recommendations.append({
                    "priority": issue["severity"],
                    "category": issue["category"],
                    "message": issue["message"],
                    "url": issue.get("url"),
                    "details": issue.get("details", {}),
                })
        return recommendations

    def _compute_section_scores(self, results: dict[str, Any]) -> dict[str, float]:
        """Compute per-section scores on a 0-100 scale."""
        sections: dict[str, float] = {}

        # Crawlability
        if self.crawled_pages:
            ok = sum(1 for p in self.crawled_pages if (p.get("status_code") or 0) < 400)
            sections["crawlability"] = round(ok / len(self.crawled_pages) * 100, 1)
        else:
            sections["crawlability"] = 0.0

        # Performance (PageSpeed average)
        ps = results.get("page_speed", {})
        mobile_s = ps.get("mobile", {}).get("score")
        desktop_s = ps.get("desktop", {}).get("score")
        ps_vals = [v for v in [mobile_s, desktop_s] if v is not None]
        sections["performance"] = round(sum(ps_vals) / len(ps_vals), 1) if ps_vals else 0.0

        # Mobile
        sections["mobile"] = 100.0 if results.get("mobile", {}).get("is_mobile_friendly") else 0.0

        # Sitemap
        sm = results.get("sitemap", {})
        sm_score = 0.0
        if sm.get("exists"):
            sm_score += 30
        if sm.get("is_valid_xml"):
            sm_score += 30
        if not sm.get("broken_urls"):
            sm_score += 20
        if not sm.get("urls_not_in_sitemap"):
            sm_score += 20
        sections["sitemap"] = sm_score

        # Robots.txt
        rb = results.get("robots_txt", {})
        rb_score = 0.0
        if rb.get("exists"):
            rb_score += 40
        if rb.get("has_sitemap_directive"):
            rb_score += 30
        if not rb.get("blocks_important_pages"):
            rb_score += 30
        sections["robots_txt"] = rb_score

        # SSL
        sections["ssl"] = 100.0 if results.get("ssl", {}).get("ssl_valid") else 0.0

        # Canonical
        ct = results.get("canonical_tags", {})
        total = ct.get("total_pages", 1)
        missing = len(ct.get("missing_canonical", []))
        sections["canonical"] = round(max((total - missing) / total * 100, 0), 1) if total else 0.0

        # Internal linking
        il = results.get("internal_linking", {})
        orphan_count = len(il.get("orphan_pages", []))
        page_count = il.get("total_pages", 1)
        sections["internal_linking"] = round(
            max((page_count - orphan_count) / page_count * 100, 0), 1,
        ) if page_count else 0.0

        # Images
        imgs = results.get("images", {})
        total_imgs = imgs.get("total_images", 1) or 1
        alt_missing = imgs.get("images_without_alt", 0)
        large = len(imgs.get("large_images", []))
        img_deductions = (alt_missing / total_imgs * 50) + (large / total_imgs * 30)
        sections["images"] = round(max(100 - img_deductions, 0), 1)

        return sections

    def _build_executive_summary(
        self,
        results: dict[str, Any],
        section_scores: dict[str, float],
    ) -> str:
        """Build a human-readable executive summary paragraph."""
        score = results.get("overall_score", 0)
        issues = self._summarise_issues()
        pages = len(self.crawled_pages)

        grade = "excellent" if score >= 90 else (
            "good" if score >= 75 else (
                "fair" if score >= 50 else "poor"
            )
        )

        summary_lines = [
            f"Technical SEO audit of {COMPANY.get('name', self.site_url)} completed on "
            f"{datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}.",
            f"Overall health score: {score}/100 ({grade}).",
            f"Crawled {pages} page(s).",
            f"Found {issues.get('total', 0)} issue(s): "
            f"{issues.get(CRITICAL, 0)} critical, {issues.get(WARNING, 0)} warnings, "
            f"{issues.get(INFO, 0)} informational.",
        ]

        # Highlight weakest sections
        worst = sorted(section_scores.items(), key=lambda x: x[1])[:3]
        if worst:
            weak_parts = [f"{name} ({score_val}/100)" for name, score_val in worst if score_val < 80]
            if weak_parts:
                summary_lines.append(
                    f"Weakest areas: {', '.join(weak_parts)}."
                )

        return " ".join(summary_lines)

    # -- aggregate stat helpers --

    def _status_code_distribution(self) -> dict[str, int]:
        dist: dict[str, int] = defaultdict(int)
        for p in self.crawled_pages:
            code = p.get("status_code", 0)
            bucket = f"{code // 100}xx" if code else "error"
            dist[bucket] += 1
        return dict(dist)

    def _average_load_time(self) -> float:
        times = [p["load_time_ms"] for p in self.crawled_pages if p.get("load_time_ms")]
        return round(sum(times) / len(times), 1) if times else 0.0

    def _average_page_size(self) -> float:
        sizes = [p["page_size_kb"] for p in self.crawled_pages if p.get("page_size_kb")]
        return round(sum(sizes) / len(sizes), 1) if sizes else 0.0

    def _average_word_count(self) -> int:
        counts = [p["word_count"] for p in self.crawled_pages if p.get("word_count")]
        return int(sum(counts) / len(counts)) if counts else 0

    # ------------------------------------------------------------------
    # Database persistence
    # ------------------------------------------------------------------

    def _save_audit(self, results: dict[str, Any]) -> Optional[int]:
        """Persist audit results to the database.

        Returns:
            The new ``TechnicalAudit.id``, or *None* on failure.
        """
        db = SessionLocal()
        try:
            issues_summary = self._summarise_issues()

            # Store section scores inside audit_data for comparison
            results_copy = {
                k: v for k, v in results.items()
                if k not in ("crawl",)  # skip heavy crawl page list
            }
            results_copy["section_scores"] = self._compute_section_scores(results)

            audit = TechnicalAudit(
                audit_date=datetime.datetime.utcnow(),
                overall_score=results.get("overall_score", 0),
                pages_crawled=len(self.crawled_pages),
                issues_found=issues_summary.get("total", 0),
                critical_issues=issues_summary.get(CRITICAL, 0),
                warnings=issues_summary.get(WARNING, 0),
                audit_data=results_copy,
                recommendations=results.get("recommendations", []),
            )
            db.add(audit)
            db.flush()

            # Save per-page audits
            for page in self.crawled_pages:
                page_audit = PageAudit(
                    audit_id=audit.id,
                    url=page.get("url", ""),
                    status_code=page.get("status_code"),
                    page_title=page.get("page_title", "")[:500],
                    meta_description=page.get("meta_description", "")[:1000],
                    h1_tags=page.get("h1_tags", []),
                    h2_tags=page.get("h2_tags", []),
                    word_count=page.get("word_count"),
                    load_time_ms=page.get("load_time_ms"),
                    page_size_kb=page.get("page_size_kb"),
                    has_canonical=page.get("has_canonical", False),
                    canonical_url=page.get("canonical_url", ""),
                    has_robots_meta=page.get("has_robots_meta", False),
                    robots_meta=page.get("robots_meta", ""),
                    images_without_alt=page.get("images_without_alt", 0),
                    internal_links=page.get("internal_links", 0),
                    external_links=page.get("external_links", 0),
                    broken_links=page.get("broken_links", []),
                    issues=[
                        i for i in self.issues if i.get("url") == page.get("url")
                    ],
                )
                db.add(page_audit)

            db.commit()
            self.audit_id = audit.id
            logger.info("Audit saved to database with id={}", audit.id)
            return audit.id

        except Exception as exc:
            db.rollback()
            logger.error("Failed to save audit to database: {}", exc)
            return None
        finally:
            db.close()


# ======================================================================
# __main__
# ======================================================================

if __name__ == "__main__":
    import json
    import sys

    logger.remove()
    logger.add(
        sys.stderr,
        level="INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level:<8}</level> | {message}",
    )

    auditor = TechnicalSEOAuditor()

    logger.info("Running full technical SEO audit for {}", COMPANY.get("name", ""))
    report = auditor.get_audit_report()

    # Print executive summary to console
    print("\n" + "=" * 72)
    print(report.get("title", "Technical SEO Audit Report"))
    print("=" * 72)
    print(f"\nOverall Score: {report.get('overall_score', 'N/A')}/100")
    print(f"\n{report.get('executive_summary', '')}\n")

    print("Section Scores:")
    for section, score in report.get("section_scores", {}).items():
        bar_len = int(score / 5)
        bar = "#" * bar_len + "-" * (20 - bar_len)
        print(f"  {section:<20s} [{bar}] {score}/100")

    print(f"\nPrioritised Fixes ({len(report.get('prioritised_fixes', []))}):")
    for idx, fix in enumerate(report.get("prioritised_fixes", [])[:15], 1):
        sev = fix.get("priority", "info").upper()
        print(f"  {idx:>2}. [{sev:<8s}] {fix.get('message', '')}")

    # Dump full JSON report to file
    from config.settings import REPORTS_DIR

    report_path = REPORTS_DIR / f"technical_audit_{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    # Remove non-serialisable crawl page lists from the report before writing
    report_for_file = {
        k: v for k, v in report.items()
        if k != "sections" or True  # keep sections but trim heavy data
    }
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(report_for_file, fh, indent=2, default=str)

    print(f"\nFull report saved to {report_path}")
