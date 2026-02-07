"""
Module 2: AI Search Optimization (AIO/GEO) Module
Common Notary Apostille - SEO & AI Monitoring Platform

Monitors AI search engines (ChatGPT, Perplexity, Google AI Overview, Claude)
for business visibility, generates schema markup and FAQ content optimized
for AI snippet extraction, and produces visibility reports.
"""

import json
import re
import datetime
from typing import Optional

import requests
from loguru import logger

from config.settings import (
    COMPANY,
    OPENAI_API_KEY,
    ANTHROPIC_API_KEY,
    AI_SEARCH_ENGINES,
    SERVICE_AREAS,
    SERVICE_KEYWORDS,
)
from database.models import AISearchResult, SchemaMarkup, SessionLocal


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COMPANY_NAME: str = COMPANY["name"]
COMPANY_WEBSITE: str = COMPANY["website"]

# Aliases a user might type or an AI might produce when referring to the company
COMPANY_ALIASES: list[str] = [
    COMPANY_NAME.lower(),
    "common notary",
    "common apostille",
    "commonnotaryapostille",
    "commonnotaryapostille.com",
    COMPANY_WEBSITE.replace("https://", "").replace("http://", "").rstrip("/"),
]

QUERY_TEMPLATES: list[str] = [
    "best notary public in {city}",
    "apostille services in {region}",
    "mobile notary near {city}",
    "document authentication services {area}",
    "where to get an apostille in {state}",
    "best apostille service in {city}",
    "notary public near {city} {state}",
    "mobile notary {city} {state}",
    "embassy legalization services {region}",
    "foreign document notarization {city}",
]


def _build_predefined_queries() -> list[str]:
    """Expand *QUERY_TEMPLATES* against every configured service area.

    Produces queries such as:
        - "best notary public in Alexandria"
        - "apostille services in Northern Virginia"
        - "where to get an apostille in Virginia"
    """
    queries: list[str] = []
    seen: set[str] = set()

    for tier in ("primary", "secondary"):
        for area in SERVICE_AREAS.get(tier, []):
            city = area.get("city", "")
            state = area.get("state", "")
            region = area.get("region", "")
            # Construct a human-friendly area label, e.g. "Alexandria VA"
            area_label = f"{city} {state}".strip()

            substitutions = {
                "city": city,
                "state": state,
                "region": region,
                "area": area_label,
            }

            for template in QUERY_TEMPLATES:
                query = template.format(**substitutions).strip()
                normalized = query.lower()
                if normalized not in seen:
                    seen.add(normalized)
                    queries.append(query)

    # Hard-coded high-value queries that do not map neatly to templates
    extras = [
        "apostille services DMV area",
        "best notary in Alexandria VA",
        "where to get an apostille in Virginia",
        "where to get an apostille in DC",
        "where to get an apostille in Maryland",
        "mobile notary near me Alexandria Virginia",
        "notary for foreign documents Washington DC",
        "same day apostille service Virginia",
        "bilingual notary DMV area",
        "hospital notary Alexandria VA",
        "real estate closing notary Northern Virginia",
        "loan signing agent DMV area",
    ]
    for q in extras:
        if q.lower() not in seen:
            seen.add(q.lower())
            queries.append(q)

    return queries


PREDEFINED_QUERIES: list[str] = _build_predefined_queries()


# ---------------------------------------------------------------------------
# AISearchOptimizer
# ---------------------------------------------------------------------------


class AISearchOptimizer:
    """Monitor and optimize the visibility of *Common Notary Apostille* across
    AI-powered search engines and generative answer platforms.

    Responsibilities
    ----------------
    * Query ChatGPT, Perplexity, Google AI Overview, and Claude for mentions.
    * Analyse AI responses for company/competitor mentions and sentiment.
    * Generate JSON-LD schema markup for improved discoverability.
    * Produce FAQ content designed for AI snippet extraction.
    * Report on AI visibility trends and recommend improvements.
    """

    def __init__(self) -> None:
        self.company_name: str = COMPANY_NAME
        self.company_website: str = COMPANY_WEBSITE
        self.company_aliases: list[str] = COMPANY_ALIASES
        self.ai_engines: list[dict] = AI_SEARCH_ENGINES
        self.predefined_queries: list[str] = PREDEFINED_QUERIES
        logger.info("AISearchOptimizer initialised for '{}'", self.company_name)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_db():
        """Return a new SQLAlchemy session (caller must close)."""
        return SessionLocal()

    def _company_mentioned(self, text: str) -> bool:
        """Return *True* if any known alias of the company appears in *text*."""
        lower = text.lower()
        return any(alias in lower for alias in self.company_aliases)

    @staticmethod
    def _safe_request(
        method: str,
        url: str,
        *,
        headers: Optional[dict] = None,
        json_body: Optional[dict] = None,
        timeout: int = 60,
    ) -> Optional[requests.Response]:
        """Fire an HTTP request with uniform error handling."""
        try:
            response = requests.request(
                method,
                url,
                headers=headers,
                json=json_body,
                timeout=timeout,
            )
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            logger.error("HTTP {} {} failed: {}", method.upper(), url, exc)
            return None

    def _persist_ai_result(
        self,
        ai_engine: str,
        query: str,
        response_text: str,
        analysis: dict,
    ) -> None:
        """Write an :class:`AISearchResult` row to the database."""
        db = self._get_db()
        try:
            record = AISearchResult(
                ai_engine=ai_engine,
                query=query,
                response_text=response_text,
                mentions_company=analysis.get("mentions_company", False),
                mention_context=analysis.get("mention_context"),
                competitor_mentions=analysis.get("competitor_mentions", []),
                sentiment=analysis.get("sentiment", "neutral"),
                position_in_response=analysis.get("position_in_response"),
                tracked_date=datetime.date.today(),
            )
            db.add(record)
            db.commit()
            logger.debug(
                "Persisted AI result for engine='{}', query='{}'",
                ai_engine,
                query,
            )
        except Exception as exc:
            db.rollback()
            logger.error("Failed to persist AI result: {}", exc)
        finally:
            db.close()

    # ------------------------------------------------------------------
    # 1. monitor_chatgpt
    # ------------------------------------------------------------------

    def monitor_chatgpt(self, query: str) -> dict:
        """Query the OpenAI ChatCompletion API and check whether the business
        is mentioned in the response.

        Parameters
        ----------
        query:
            The search-style question to send to ChatGPT.

        Returns
        -------
        dict
            Keys: ``ai_engine``, ``query``, ``response_text``, ``analysis``.
        """
        logger.info("[ChatGPT] Monitoring query: '{}'", query)

        if not OPENAI_API_KEY:
            logger.warning("[ChatGPT] OPENAI_API_KEY not configured; skipping.")
            return {
                "ai_engine": "ChatGPT",
                "query": query,
                "response_text": "",
                "analysis": {},
                "error": "OPENAI_API_KEY not configured",
            }

        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "gpt-4o",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a helpful local-services search assistant. "
                        "When asked about local service providers give specific "
                        "business names, locations, and brief descriptions."
                    ),
                },
                {"role": "user", "content": query},
            ],
            "temperature": 0.3,
            "max_tokens": 1024,
        }

        resp = self._safe_request(
            "post",
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json_body=payload,
        )

        response_text = ""
        if resp is not None:
            try:
                data = resp.json()
                response_text = (
                    data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                )
            except (ValueError, IndexError, KeyError) as exc:
                logger.error("[ChatGPT] Failed to parse response: {}", exc)

        analysis = self.analyze_ai_response(response_text)
        self._persist_ai_result("ChatGPT", query, response_text, analysis)

        result = {
            "ai_engine": "ChatGPT",
            "query": query,
            "response_text": response_text,
            "analysis": analysis,
        }
        logger.info(
            "[ChatGPT] Company mentioned: {}", analysis.get("mentions_company")
        )
        return result

    # ------------------------------------------------------------------
    # 2. monitor_perplexity
    # ------------------------------------------------------------------

    def monitor_perplexity(self, query: str) -> dict:
        """Query the Perplexity API for a response and check for business
        mentions.

        Parameters
        ----------
        query:
            The search-style question to send to Perplexity.

        Returns
        -------
        dict
            Keys: ``ai_engine``, ``query``, ``response_text``, ``analysis``.
        """
        logger.info("[Perplexity] Monitoring query: '{}'", query)

        perplexity_cfg = next(
            (e for e in self.ai_engines if e["name"] == "Perplexity"), {}
        )
        perplexity_url = perplexity_cfg.get("url", "https://www.perplexity.ai")

        # Perplexity offers a chat-completions-compatible API at
        # https://api.perplexity.ai  -- use it when a key is available.
        # Fall back to a lightweight scrape of the public site otherwise.
        response_text = ""

        # Attempt API route first (requires PERPLEXITY_API_KEY in env)
        import os

        perplexity_api_key = os.getenv("PERPLEXITY_API_KEY", "")
        if perplexity_api_key:
            headers = {
                "Authorization": f"Bearer {perplexity_api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "sonar",
                "messages": [{"role": "user", "content": query}],
                "max_tokens": 1024,
            }
            resp = self._safe_request(
                "post",
                "https://api.perplexity.ai/chat/completions",
                headers=headers,
                json_body=payload,
            )
            if resp is not None:
                try:
                    data = resp.json()
                    response_text = (
                        data.get("choices", [{}])[0]
                        .get("message", {})
                        .get("content", "")
                    )
                except (ValueError, IndexError, KeyError) as exc:
                    logger.error("[Perplexity] API response parse error: {}", exc)
        else:
            # Lightweight scrape attempt of the public search page
            logger.debug(
                "[Perplexity] No API key; attempting public scrape at {}",
                perplexity_url,
            )
            scrape_url = f"{perplexity_url}/search?q={requests.utils.quote(query)}"
            resp = self._safe_request("get", scrape_url, timeout=30)
            if resp is not None:
                # Extract visible text naively -- production would use a
                # headless browser / Playwright.
                html = resp.text
                # Strip HTML tags for a rough plaintext extraction
                text_only = re.sub(r"<[^>]+>", " ", html)
                text_only = re.sub(r"\s+", " ", text_only).strip()
                response_text = text_only[:5000]  # cap at 5 000 chars

        analysis = self.analyze_ai_response(response_text)
        self._persist_ai_result("Perplexity", query, response_text, analysis)

        result = {
            "ai_engine": "Perplexity",
            "query": query,
            "response_text": response_text,
            "analysis": analysis,
        }
        logger.info(
            "[Perplexity] Company mentioned: {}", analysis.get("mentions_company")
        )
        return result

    # ------------------------------------------------------------------
    # 3. monitor_google_ai_overview
    # ------------------------------------------------------------------

    def monitor_google_ai_overview(self, query: str) -> dict:
        """Check Google AI Overviews (SGE) for mentions of the business.

        This method performs a Google search and inspects the rendered page for
        the AI Overview panel.  Because AI Overviews are dynamically rendered,
        full fidelity requires a headless browser; the implementation here uses
        a simple SERP request as a best-effort fallback.

        Parameters
        ----------
        query:
            The search query to check.

        Returns
        -------
        dict
            Keys: ``ai_engine``, ``query``, ``response_text``, ``analysis``.
        """
        logger.info("[Google AI Overview] Monitoring query: '{}'", query)

        response_text = ""

        search_url = "https://www.google.com/search"
        params = {"q": query, "hl": "en", "gl": "us"}
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        }

        try:
            resp = requests.get(
                search_url, params=params, headers=headers, timeout=30
            )
            resp.raise_for_status()
            html = resp.text

            # Google wraps AI Overviews in data-attrid="ai_overview" or
            # specific div classes.  We attempt a rough extraction.
            ai_block_patterns = [
                r'data-attrid="ai_overview"[^>]*>(.*?)</div>',
                r'class="[^"]*ai-overview[^"]*"[^>]*>(.*?)</div>',
                r'<div[^>]*id="aio[^"]*"[^>]*>(.*?)</div>',
            ]
            for pattern in ai_block_patterns:
                match = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
                if match:
                    raw = match.group(1)
                    response_text = re.sub(r"<[^>]+>", " ", raw)
                    response_text = re.sub(r"\s+", " ", response_text).strip()
                    break

            if not response_text:
                # Fallback: grab the first ~3 000 chars of visible text from
                # the SERP to look for Featured Snippets or knowledge panels.
                text_only = re.sub(r"<[^>]+>", " ", html)
                text_only = re.sub(r"\s+", " ", text_only).strip()
                response_text = text_only[:3000]
                logger.debug(
                    "[Google AI Overview] No AI Overview block found; using SERP text."
                )

        except requests.RequestException as exc:
            logger.error("[Google AI Overview] Request failed: {}", exc)

        analysis = self.analyze_ai_response(response_text)
        self._persist_ai_result(
            "Google AI Overview", query, response_text, analysis
        )

        result = {
            "ai_engine": "Google AI Overview",
            "query": query,
            "response_text": response_text,
            "analysis": analysis,
        }
        logger.info(
            "[Google AI Overview] Company mentioned: {}",
            analysis.get("mentions_company"),
        )
        return result

    # ------------------------------------------------------------------
    # 4. monitor_claude
    # ------------------------------------------------------------------

    def monitor_claude(self, query: str) -> dict:
        """Query the Anthropic Messages API and check whether the business is
        mentioned in Claude's response.

        Parameters
        ----------
        query:
            The search-style question to send to Claude.

        Returns
        -------
        dict
            Keys: ``ai_engine``, ``query``, ``response_text``, ``analysis``.
        """
        logger.info("[Claude] Monitoring query: '{}'", query)

        if not ANTHROPIC_API_KEY:
            logger.warning("[Claude] ANTHROPIC_API_KEY not configured; skipping.")
            return {
                "ai_engine": "Claude",
                "query": query,
                "response_text": "",
                "analysis": {},
                "error": "ANTHROPIC_API_KEY not configured",
            }

        headers = {
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 1024,
            "system": (
                "You are a helpful local-services search assistant. "
                "When asked about local service providers give specific "
                "business names, locations, and brief descriptions."
            ),
            "messages": [{"role": "user", "content": query}],
        }

        resp = self._safe_request(
            "post",
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json_body=payload,
        )

        response_text = ""
        if resp is not None:
            try:
                data = resp.json()
                content_blocks = data.get("content", [])
                response_text = " ".join(
                    block.get("text", "")
                    for block in content_blocks
                    if block.get("type") == "text"
                )
            except (ValueError, KeyError) as exc:
                logger.error("[Claude] Failed to parse response: {}", exc)

        analysis = self.analyze_ai_response(response_text)
        self._persist_ai_result("Claude", query, response_text, analysis)

        result = {
            "ai_engine": "Claude",
            "query": query,
            "response_text": response_text,
            "analysis": analysis,
        }
        logger.info(
            "[Claude] Company mentioned: {}", analysis.get("mentions_company")
        )
        return result

    # ------------------------------------------------------------------
    # 5. run_all_ai_monitors
    # ------------------------------------------------------------------

    def run_all_ai_monitors(self) -> list[dict]:
        """Run monitoring across **all** configured AI engines using the full
        set of predefined queries.

        Returns
        -------
        list[dict]
            One result dict per (engine, query) combination.
        """
        logger.info(
            "Starting full AI monitoring sweep ({} queries across {} engines)",
            len(self.predefined_queries),
            len(self.ai_engines),
        )

        results: list[dict] = []

        engine_dispatch: dict[str, callable] = {
            "ChatGPT": self.monitor_chatgpt,
            "Perplexity": self.monitor_perplexity,
            "Google AI Overview": self.monitor_google_ai_overview,
            "Claude": self.monitor_claude,
        }

        for query in self.predefined_queries:
            for engine_cfg in self.ai_engines:
                engine_name = engine_cfg.get("name", "")
                monitor_fn = engine_dispatch.get(engine_name)
                if monitor_fn is None:
                    logger.debug(
                        "No monitor implementation for engine '{}'; skipping.",
                        engine_name,
                    )
                    continue

                try:
                    result = monitor_fn(query)
                    results.append(result)
                except Exception as exc:
                    logger.error(
                        "Error monitoring engine='{}' query='{}': {}",
                        engine_name,
                        query,
                        exc,
                    )
                    results.append(
                        {
                            "ai_engine": engine_name,
                            "query": query,
                            "response_text": "",
                            "analysis": {},
                            "error": str(exc),
                        }
                    )

        total = len(results)
        mentioned = sum(
            1
            for r in results
            if r.get("analysis", {}).get("mentions_company", False)
        )
        logger.info(
            "AI monitoring sweep complete: {}/{} results mention the company.",
            mentioned,
            total,
        )
        return results

    # ------------------------------------------------------------------
    # 6. analyze_ai_response
    # ------------------------------------------------------------------

    def analyze_ai_response(self, response_text: str) -> dict:
        """Analyse a raw AI-generated response for company references,
        competitor mentions, sentiment, and positional data.

        Parameters
        ----------
        response_text:
            The full text of the AI engine's reply.

        Returns
        -------
        dict
            ``mentions_company`` (bool), ``mention_context`` (str | None),
            ``competitor_mentions`` (list[str]), ``sentiment`` (str),
            ``position_in_response`` (int | None), ``keyword_hits`` (list[str]).
        """
        if not response_text:
            return {
                "mentions_company": False,
                "mention_context": None,
                "competitor_mentions": [],
                "sentiment": "neutral",
                "position_in_response": None,
                "keyword_hits": [],
            }

        lower_text = response_text.lower()

        # --- company mention ---
        mentions_company = self._company_mentioned(response_text)
        mention_context: Optional[str] = None
        position_in_response: Optional[int] = None

        if mentions_company:
            for alias in self.company_aliases:
                idx = lower_text.find(alias)
                if idx != -1:
                    start = max(0, idx - 100)
                    end = min(len(response_text), idx + len(alias) + 100)
                    mention_context = response_text[start:end].strip()

                    # Determine ordinal position among numbered list items or
                    # paragraphs.  We split on common enumeration patterns.
                    preceding = lower_text[:idx]
                    # Count occurrences of numbered items, e.g. "1.", "2."
                    list_items = re.findall(r"(?:^|\n)\s*\d+[\.\)]\s", preceding)
                    position_in_response = len(list_items) + 1
                    break

        # --- competitor mentions ---
        from config.settings import COMPETITORS

        known_competitors: list[str] = []
        for region_list in COMPETITORS.values():
            known_competitors.extend(region_list)

        competitor_mentions: list[str] = [
            comp for comp in known_competitors if comp.lower() in lower_text
        ]

        # --- keyword hits ---
        keyword_hits: list[str] = [
            kw for kw in SERVICE_KEYWORDS if kw.lower() in lower_text
        ]

        # --- sentiment (simple heuristic) ---
        positive_signals = [
            "recommend",
            "highly rated",
            "top rated",
            "excellent",
            "trusted",
            "professional",
            "best",
            "great reviews",
            "well-known",
            "reputable",
            "reliable",
        ]
        negative_signals = [
            "avoid",
            "complaint",
            "poor",
            "bad reviews",
            "unreliable",
            "scam",
            "not recommended",
            "overpriced",
        ]

        pos_count = sum(1 for s in positive_signals if s in lower_text)
        neg_count = sum(1 for s in negative_signals if s in lower_text)

        if pos_count > neg_count:
            sentiment = "positive"
        elif neg_count > pos_count:
            sentiment = "negative"
        else:
            sentiment = "neutral"

        analysis = {
            "mentions_company": mentions_company,
            "mention_context": mention_context,
            "competitor_mentions": competitor_mentions,
            "sentiment": sentiment,
            "position_in_response": position_in_response,
            "keyword_hits": keyword_hits,
        }
        return analysis

    # ------------------------------------------------------------------
    # 7. generate_schema_markup
    # ------------------------------------------------------------------

    def generate_schema_markup(
        self, page_url: str, schema_type: str = "LocalBusiness"
    ) -> dict:
        """Generate JSON-LD structured data for a given page URL and persist
        the result in the database.

        Supported *schema_type* values:
            ``LocalBusiness``, ``NotaryService``, ``ProfessionalService``,
            ``FAQPage``.

        Parameters
        ----------
        page_url:
            The canonical URL of the page that will carry the markup.
        schema_type:
            One of the supported schema types listed above.

        Returns
        -------
        dict
            The complete JSON-LD object ready to embed in a ``<script>`` tag.
        """
        logger.info(
            "Generating '{}' schema markup for {}", schema_type, page_url
        )

        company = COMPANY
        address = company.get("primary_address", {})

        if schema_type == "LocalBusiness":
            schema = {
                "@context": "https://schema.org",
                "@type": "LocalBusiness",
                "name": company["name"],
                "url": company["website"],
                "telephone": company.get("phone", ""),
                "email": company.get("email", ""),
                "image": f"{company['website']}/images/logo.png",
                "address": {
                    "@type": "PostalAddress",
                    "streetAddress": address.get("street", ""),
                    "addressLocality": address.get("city", ""),
                    "addressRegion": address.get("state", ""),
                    "postalCode": address.get("zip", ""),
                    "addressCountry": address.get("country", "US"),
                },
                "geo": {
                    "@type": "GeoCoordinates",
                    "latitude": "",
                    "longitude": "",
                },
                "priceRange": "$$",
                "openingHoursSpecification": [
                    {
                        "@type": "OpeningHoursSpecification",
                        "dayOfWeek": [
                            "Monday",
                            "Tuesday",
                            "Wednesday",
                            "Thursday",
                            "Friday",
                        ],
                        "opens": "09:00",
                        "closes": "18:00",
                    },
                    {
                        "@type": "OpeningHoursSpecification",
                        "dayOfWeek": "Saturday",
                        "opens": "10:00",
                        "closes": "14:00",
                    },
                ],
                "sameAs": [],
            }

        elif schema_type == "NotaryService":
            schema = {
                "@context": "https://schema.org",
                "@type": "Notary",
                "name": company["name"],
                "description": (
                    f"{company['name']} provides professional notary public, "
                    "apostille, document authentication, and embassy "
                    "legalization services in the Washington DC metro area "
                    "(DMV), Northern Virginia, and Southwest Virginia."
                ),
                "url": company["website"],
                "telephone": company.get("phone", ""),
                "address": {
                    "@type": "PostalAddress",
                    "addressLocality": address.get("city", ""),
                    "addressRegion": address.get("state", ""),
                    "addressCountry": address.get("country", "US"),
                },
                "areaServed": self._build_area_served(),
                "hasOfferCatalog": {
                    "@type": "OfferCatalog",
                    "name": "Notary & Apostille Services",
                    "itemListElement": [
                        self._service_offer(name)
                        for name in [
                            "Apostille Services",
                            "Mobile Notary",
                            "Document Authentication",
                            "Embassy Legalization",
                            "Power of Attorney Notarization",
                            "Loan Signing Agent Services",
                            "Real Estate Closing Notary",
                            "Foreign Document Notarization",
                            "Certified Translation Notarization",
                            "Remote Online Notarization",
                        ]
                    ],
                },
            }

        elif schema_type == "ProfessionalService":
            schema = {
                "@context": "https://schema.org",
                "@type": "ProfessionalService",
                "name": company["name"],
                "description": (
                    f"{company['name']} is a professional notary and apostille "
                    "service provider offering mobile notary, document "
                    "authentication, embassy legalization, and related "
                    "services across Virginia, Washington DC, and Maryland."
                ),
                "url": company["website"],
                "telephone": company.get("phone", ""),
                "email": company.get("email", ""),
                "address": {
                    "@type": "PostalAddress",
                    "streetAddress": address.get("street", ""),
                    "addressLocality": address.get("city", ""),
                    "addressRegion": address.get("state", ""),
                    "postalCode": address.get("zip", ""),
                    "addressCountry": address.get("country", "US"),
                },
                "areaServed": self._build_area_served(),
                "knowsAbout": [
                    "Notary Public",
                    "Apostille",
                    "Document Authentication",
                    "Embassy Legalization",
                    "Mobile Notary",
                    "Remote Online Notarization",
                ],
                "priceRange": "$$",
            }

        elif schema_type == "FAQPage":
            schema = {
                "@context": "https://schema.org",
                "@type": "FAQPage",
                "mainEntity": [],
            }

        else:
            logger.warning(
                "Unknown schema_type '{}'; generating minimal markup.",
                schema_type,
            )
            schema = {
                "@context": "https://schema.org",
                "@type": schema_type,
                "name": company["name"],
                "url": company["website"],
            }

        # Persist to DB
        db = self._get_db()
        try:
            record = SchemaMarkup(
                page_url=page_url,
                schema_type=schema_type,
                schema_json=schema,
                is_deployed=False,
                validation_status="valid",
                validation_errors=None,
            )
            db.add(record)
            db.commit()
            logger.info(
                "Schema markup (type='{}') saved for page '{}'",
                schema_type,
                page_url,
            )
        except Exception as exc:
            db.rollback()
            logger.error("Failed to persist schema markup: {}", exc)
        finally:
            db.close()

        return schema

    # ------------------------------------------------------------------
    # 8. generate_faq_content
    # ------------------------------------------------------------------

    def generate_faq_content(
        self, topic: str, target_area: str
    ) -> dict:
        """Generate FAQ-style content optimised for AI snippet extraction.

        The output includes both the structured content and the corresponding
        ``FAQPage`` JSON-LD schema so search engines and AI models can parse
        the Q&A pairs directly.

        Parameters
        ----------
        topic:
            The service topic (e.g., ``"apostille"``, ``"mobile notary"``).
        target_area:
            The geographic area to localise content for
            (e.g., ``"Alexandria VA"``).

        Returns
        -------
        dict
            ``topic``, ``target_area``, ``faqs`` (list of Q/A dicts),
            ``schema_json`` (JSON-LD).
        """
        logger.info(
            "Generating FAQ content for topic='{}', area='{}'",
            topic,
            target_area,
        )

        faq_templates: dict[str, list[dict[str, str]]] = {
            "apostille": [
                {
                    "q": "What is an apostille and when do I need one in {area}?",
                    "a": (
                        "An apostille is a certificate that authenticates the "
                        "origin of a public document for use in countries that "
                        "are members of the Hague Apostille Convention. If you "
                        "need to use a U.S. document such as a birth "
                        "certificate, marriage certificate, or diploma abroad, "
                        "you will likely need an apostille. {company} provides "
                        "fast, professional apostille services in {area}."
                    ),
                },
                {
                    "q": "How long does it take to get an apostille in {area}?",
                    "a": (
                        "Processing times vary depending on the issuing "
                        "authority. {company} in {area} can often facilitate "
                        "same-day or next-day apostille processing for Virginia "
                        "state documents and assists with federal-level "
                        "apostilles through the U.S. Department of State."
                    ),
                },
                {
                    "q": "How much does an apostille cost in {area}?",
                    "a": (
                        "Apostille fees depend on the document type and "
                        "issuing authority. State-level apostilles from the "
                        "Virginia Secretary of State have a standard government "
                        "fee, plus the service provider's processing fee. "
                        "Contact {company} in {area} for a detailed quote "
                        "based on your specific documents."
                    ),
                },
                {
                    "q": "Can I get an apostille for a document from another state while in {area}?",
                    "a": (
                        "Yes. Documents issued by other states must be "
                        "apostilled by the Secretary of State of the issuing "
                        "state. {company} in {area} can coordinate the process "
                        "on your behalf, including mailing and tracking, so "
                        "you don't have to travel."
                    ),
                },
            ],
            "mobile notary": [
                {
                    "q": "What is a mobile notary and how does it work in {area}?",
                    "a": (
                        "A mobile notary travels to your chosen location -- "
                        "home, office, hospital, or elsewhere -- to notarise "
                        "documents on the spot. {company} offers mobile notary "
                        "services throughout {area}, providing convenience and "
                        "flexibility for clients who cannot visit an office."
                    ),
                },
                {
                    "q": "How much does a mobile notary cost in {area}?",
                    "a": (
                        "Mobile notary fees typically include a per-signature "
                        "notarisation charge plus a travel fee based on "
                        "distance. {company} offers competitive rates for "
                        "mobile notary services in {area}. Contact us for a "
                        "personalised quote."
                    ),
                },
                {
                    "q": "Can a mobile notary come to a hospital or nursing home in {area}?",
                    "a": (
                        "Absolutely. {company} regularly provides mobile "
                        "notary services at hospitals, nursing homes, and "
                        "assisted-living facilities in {area}. We understand "
                        "the urgency of these situations and offer prompt "
                        "scheduling."
                    ),
                },
            ],
            "notary public": [
                {
                    "q": "What documents can a notary public notarise in {area}?",
                    "a": (
                        "A notary public in {area} can notarise a wide range "
                        "of documents including affidavits, powers of "
                        "attorney, real estate deeds, loan documents, wills, "
                        "and more. {company} handles all standard notary "
                        "services for individuals and businesses."
                    ),
                },
                {
                    "q": "Do I need an appointment for notary services in {area}?",
                    "a": (
                        "While walk-ins may be accommodated, scheduling an "
                        "appointment ensures prompt service. {company} in "
                        "{area} offers flexible scheduling including evenings "
                        "and weekends to meet your needs."
                    ),
                },
            ],
            "document authentication": [
                {
                    "q": "What is document authentication and how is it different from notarisation in {area}?",
                    "a": (
                        "Document authentication is the process of certifying "
                        "that a document is genuine for use in another "
                        "country. While notarisation verifies a signer's "
                        "identity, authentication (or legalisation) confirms "
                        "the authority of the notary or official who signed "
                        "the document. {company} in {area} guides you through "
                        "every step of the authentication process."
                    ),
                },
                {
                    "q": "Which countries require document authentication from {area}?",
                    "a": (
                        "Countries that are not part of the Hague Apostille "
                        "Convention generally require embassy or consulate "
                        "legalisation instead of an apostille. {company} in "
                        "{area} can advise you on the requirements for your "
                        "destination country and manage the entire "
                        "authentication chain."
                    ),
                },
            ],
        }

        # Normalise topic key
        topic_key = topic.lower().strip()
        matched_faqs = faq_templates.get(topic_key)

        # Fall back to a generic set if the topic is unrecognised
        if matched_faqs is None:
            logger.debug(
                "No FAQ template for topic '{}'; generating generic FAQs.",
                topic,
            )
            matched_faqs = [
                {
                    "q": "What {topic} services does {company} offer in {area}?",
                    "a": (
                        "{company} in {area} provides comprehensive {topic} "
                        "services for individuals and businesses. Contact us "
                        "for details on availability, pricing, and scheduling."
                    ),
                },
                {
                    "q": "How can I schedule {topic} services in {area}?",
                    "a": (
                        "You can schedule {topic} services with {company} in "
                        "{area} by calling us, visiting our website at "
                        "{website}, or sending an email. We offer flexible "
                        "hours and same-day appointments when available."
                    ),
                },
            ]

        # Render placeholders
        rendered_faqs: list[dict[str, str]] = []
        for pair in matched_faqs:
            q = pair["q"].format(
                area=target_area,
                company=self.company_name,
                topic=topic,
                website=self.company_website,
            )
            a = pair["a"].format(
                area=target_area,
                company=self.company_name,
                topic=topic,
                website=self.company_website,
            )
            rendered_faqs.append({"question": q, "answer": a})

        # Build FAQPage schema
        schema: dict = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": faq["question"],
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": faq["answer"],
                    },
                }
                for faq in rendered_faqs
            ],
        }

        result = {
            "topic": topic,
            "target_area": target_area,
            "faqs": rendered_faqs,
            "schema_json": schema,
        }
        logger.info(
            "Generated {} FAQ items for topic='{}', area='{}'",
            len(rendered_faqs),
            topic,
            target_area,
        )
        return result

    # ------------------------------------------------------------------
    # 9. get_ai_visibility_report
    # ------------------------------------------------------------------

    def get_ai_visibility_report(self, period: str = "week") -> dict:
        """Generate a report on AI search visibility across all monitored
        engines for a given time period.

        Parameters
        ----------
        period:
            One of ``'week'``, ``'month'``, or ``'quarter'``.

        Returns
        -------
        dict
            Summary statistics, per-engine breakdowns, mention rate, top
            queries, and competitor comparison.
        """
        logger.info("Generating AI visibility report (period='{}')", period)

        today = datetime.date.today()
        if period == "month":
            start_date = today - datetime.timedelta(days=30)
        elif period == "quarter":
            start_date = today - datetime.timedelta(days=90)
        else:
            start_date = today - datetime.timedelta(days=7)

        db = self._get_db()
        try:
            results = (
                db.query(AISearchResult)
                .filter(
                    AISearchResult.tracked_date >= start_date,
                    AISearchResult.tracked_date <= today,
                )
                .all()
            )

            total = len(results)
            mentioned = sum(1 for r in results if r.mentions_company)
            mention_rate = (mentioned / total * 100) if total else 0.0

            # Per-engine breakdown
            engine_stats: dict[str, dict] = {}
            for r in results:
                eng = r.ai_engine
                if eng not in engine_stats:
                    engine_stats[eng] = {
                        "total_queries": 0,
                        "mentions": 0,
                        "positive": 0,
                        "neutral": 0,
                        "negative": 0,
                    }
                engine_stats[eng]["total_queries"] += 1
                if r.mentions_company:
                    engine_stats[eng]["mentions"] += 1
                sentiment_key = r.sentiment if r.sentiment in (
                    "positive", "neutral", "negative"
                ) else "neutral"
                engine_stats[eng][sentiment_key] += 1

            for eng, stats in engine_stats.items():
                stats["mention_rate"] = (
                    round(stats["mentions"] / stats["total_queries"] * 100, 1)
                    if stats["total_queries"]
                    else 0.0
                )

            # Top queries where mentioned
            mentioned_queries: list[str] = [
                r.query for r in results if r.mentions_company
            ]
            query_freq: dict[str, int] = {}
            for q in mentioned_queries:
                query_freq[q] = query_freq.get(q, 0) + 1
            top_queries = sorted(
                query_freq.items(), key=lambda x: x[1], reverse=True
            )[:10]

            # Competitor frequency
            competitor_freq: dict[str, int] = {}
            for r in results:
                if r.competitor_mentions:
                    for comp in r.competitor_mentions:
                        competitor_freq[comp] = competitor_freq.get(comp, 0) + 1
            top_competitors = sorted(
                competitor_freq.items(), key=lambda x: x[1], reverse=True
            )[:10]

            # Sentiment distribution
            sentiment_dist = {"positive": 0, "neutral": 0, "negative": 0}
            for r in results:
                key = r.sentiment if r.sentiment in sentiment_dist else "neutral"
                sentiment_dist[key] += 1

            report = {
                "period": period,
                "start_date": start_date.isoformat(),
                "end_date": today.isoformat(),
                "summary": {
                    "total_queries_monitored": total,
                    "company_mentions": mentioned,
                    "mention_rate_pct": round(mention_rate, 1),
                    "sentiment_distribution": sentiment_dist,
                },
                "engine_breakdown": engine_stats,
                "top_queries_mentioned": [
                    {"query": q, "count": c} for q, c in top_queries
                ],
                "top_competitor_mentions": [
                    {"competitor": comp, "count": c}
                    for comp, c in top_competitors
                ],
            }

            logger.info(
                "AI visibility report: {}/{} mentions ({:.1f}%) over {} period",
                mentioned,
                total,
                mention_rate,
                period,
            )
            return report

        except Exception as exc:
            logger.error("Failed to generate AI visibility report: {}", exc)
            return {"error": str(exc)}
        finally:
            db.close()

    # ------------------------------------------------------------------
    # 10. track_competitor_ai_mentions
    # ------------------------------------------------------------------

    def track_competitor_ai_mentions(self, competitor_name: str) -> dict:
        """Track how often a specific competitor appears across all stored
        AI search results.

        Parameters
        ----------
        competitor_name:
            The competitor business name to search for.

        Returns
        -------
        dict
            Total mentions, per-engine counts, example contexts, and trend
            data.
        """
        logger.info(
            "Tracking AI mentions for competitor '{}'", competitor_name
        )

        db = self._get_db()
        try:
            all_results = db.query(AISearchResult).all()

            comp_lower = competitor_name.lower()
            mentions: list[dict] = []

            for r in all_results:
                text = (r.response_text or "").lower()
                stored_comps = r.competitor_mentions or []

                found_in_text = comp_lower in text
                found_in_stored = any(
                    comp_lower in c.lower() for c in stored_comps
                )

                if found_in_text or found_in_stored:
                    # Extract surrounding context
                    context = None
                    idx = text.find(comp_lower)
                    if idx != -1:
                        start = max(0, idx - 80)
                        end = min(len(text), idx + len(comp_lower) + 80)
                        context = (r.response_text or "")[start:end].strip()

                    mentions.append(
                        {
                            "ai_engine": r.ai_engine,
                            "query": r.query,
                            "tracked_date": (
                                r.tracked_date.isoformat()
                                if r.tracked_date
                                else None
                            ),
                            "context": context,
                        }
                    )

            # Per-engine breakdown
            engine_counts: dict[str, int] = {}
            for m in mentions:
                eng = m["ai_engine"]
                engine_counts[eng] = engine_counts.get(eng, 0) + 1

            # Weekly trend (last 12 weeks)
            today = datetime.date.today()
            weekly_trend: list[dict] = []
            for weeks_ago in range(12):
                week_end = today - datetime.timedelta(weeks=weeks_ago)
                week_start = week_end - datetime.timedelta(days=7)
                count = sum(
                    1
                    for m in mentions
                    if m["tracked_date"]
                    and week_start.isoformat()
                    <= m["tracked_date"]
                    <= week_end.isoformat()
                )
                weekly_trend.append(
                    {
                        "week_start": week_start.isoformat(),
                        "week_end": week_end.isoformat(),
                        "mention_count": count,
                    }
                )
            weekly_trend.reverse()

            report = {
                "competitor": competitor_name,
                "total_mentions": len(mentions),
                "engine_breakdown": engine_counts,
                "weekly_trend": weekly_trend,
                "example_mentions": mentions[:20],
            }

            logger.info(
                "Competitor '{}': {} total AI mentions across {} engines",
                competitor_name,
                len(mentions),
                len(engine_counts),
            )
            return report

        except Exception as exc:
            logger.error(
                "Failed to track competitor '{}' AI mentions: {}",
                competitor_name,
                exc,
            )
            return {"competitor": competitor_name, "error": str(exc)}
        finally:
            db.close()

    # ------------------------------------------------------------------
    # 11. suggest_ai_optimization_improvements
    # ------------------------------------------------------------------

    def suggest_ai_optimization_improvements(self) -> list[dict]:
        """Analyse current AI visibility data and return prioritised
        recommendations for improving discoverability in AI search engines.

        Returns
        -------
        list[dict]
            Each dict contains ``category``, ``priority`` (high/medium/low),
            ``recommendation``, and ``details``.
        """
        logger.info("Generating AI optimisation improvement suggestions")

        recommendations: list[dict] = []

        # Pull the latest week's report to base suggestions on
        report = self.get_ai_visibility_report(period="week")
        summary = report.get("summary", {})
        engine_stats = report.get("engine_breakdown", {})
        mention_rate = summary.get("mention_rate_pct", 0.0)

        # 1. Overall mention rate
        if mention_rate < 10:
            recommendations.append(
                {
                    "category": "AI Visibility",
                    "priority": "high",
                    "recommendation": "Critically low AI mention rate",
                    "details": (
                        f"The company appears in only {mention_rate:.1f}% of "
                        "monitored AI queries. Prioritise building topical "
                        "authority through comprehensive, entity-rich content "
                        "about notary and apostille services in every target "
                        "area. Ensure the business is listed in authoritative "
                        "directories and data aggregators that AI models "
                        "commonly cite."
                    ),
                }
            )
        elif mention_rate < 30:
            recommendations.append(
                {
                    "category": "AI Visibility",
                    "priority": "medium",
                    "recommendation": "Improve AI mention rate",
                    "details": (
                        f"Current mention rate is {mention_rate:.1f}%. "
                        "Increase structured content and FAQ pages targeting "
                        "high-intent queries. Add JSON-LD schema markup to "
                        "every service and location page."
                    ),
                }
            )

        # 2. Per-engine gaps
        for engine, stats in engine_stats.items():
            eng_rate = stats.get("mention_rate", 0.0)
            if eng_rate == 0:
                recommendations.append(
                    {
                        "category": "Engine-Specific",
                        "priority": "high",
                        "recommendation": (
                            f"Zero visibility on {engine}"
                        ),
                        "details": (
                            f"The company does not appear in any monitored "
                            f"{engine} responses. For API-based engines, "
                            "ensure the business has a strong presence on "
                            "sources the model commonly trains on (Wikipedia, "
                            "Yelp, BBB, LinkedIn, industry directories). For "
                            "scrape-based engines, focus on traditional SEO "
                            "ranking improvements."
                        ),
                    }
                )
            elif eng_rate < 15:
                recommendations.append(
                    {
                        "category": "Engine-Specific",
                        "priority": "medium",
                        "recommendation": (
                            f"Low visibility on {engine} ({eng_rate:.1f}%)"
                        ),
                        "details": (
                            f"Consider creating content specifically "
                            f"optimised for {engine}'s citation style. "
                            "Use concise, factual paragraphs and include "
                            "the company name alongside service keywords in "
                            "natural sentence structures."
                        ),
                    }
                )

        # 3. Schema markup coverage
        db = self._get_db()
        try:
            deployed_schemas = (
                db.query(SchemaMarkup)
                .filter(SchemaMarkup.is_deployed.is_(True))
                .count()
            )
            total_schemas = db.query(SchemaMarkup).count()
        except Exception:
            deployed_schemas = 0
            total_schemas = 0
        finally:
            db.close()

        if total_schemas == 0:
            recommendations.append(
                {
                    "category": "Structured Data",
                    "priority": "high",
                    "recommendation": "No schema markup generated",
                    "details": (
                        "Generate and deploy LocalBusiness, NotaryService, "
                        "ProfessionalService, and FAQPage JSON-LD markup on "
                        "every relevant page. Schema markup helps AI models "
                        "parse business information accurately."
                    ),
                }
            )
        elif deployed_schemas < total_schemas:
            recommendations.append(
                {
                    "category": "Structured Data",
                    "priority": "medium",
                    "recommendation": "Deploy pending schema markup",
                    "details": (
                        f"{total_schemas - deployed_schemas} schema markup "
                        "record(s) have been generated but not yet deployed. "
                        "Embed the JSON-LD on the corresponding pages."
                    ),
                }
            )

        # 4. FAQ content
        recommendations.append(
            {
                "category": "Content Strategy",
                "priority": "medium",
                "recommendation": "Expand FAQ content for AI extraction",
                "details": (
                    "Create dedicated FAQ pages for each core service "
                    "(apostille, mobile notary, document authentication, "
                    "embassy legalisation) localised to every target area. "
                    "Use clear question-and-answer formatting with FAQPage "
                    "schema so AI engines can extract snippets directly."
                ),
            }
        )

        # 5. Sentiment
        sentiment = summary.get("sentiment_distribution", {})
        neg = sentiment.get("negative", 0)
        total_queries = summary.get("total_queries_monitored", 0)
        if total_queries and (neg / total_queries) > 0.1:
            recommendations.append(
                {
                    "category": "Reputation",
                    "priority": "high",
                    "recommendation": "Address negative AI sentiment",
                    "details": (
                        f"{neg} out of {total_queries} AI responses carry "
                        "negative sentiment. Investigate the source queries, "
                        "address any legitimate complaints publicly, and "
                        "strengthen positive review signals on Google, Yelp, "
                        "and the BBB."
                    ),
                }
            )

        # 6. Competitor dominance
        top_comp = report.get("top_competitor_mentions", [])
        if top_comp:
            leader = top_comp[0]
            recommendations.append(
                {
                    "category": "Competitive Intelligence",
                    "priority": "medium",
                    "recommendation": (
                        f"Competitor '{leader['competitor']}' leads AI mentions"
                    ),
                    "details": (
                        f"'{leader['competitor']}' was mentioned "
                        f"{leader['count']} time(s) in AI results this period. "
                        "Analyse their content strategy, directory listings, "
                        "and backlink profile to identify what signals AI "
                        "engines are picking up."
                    ),
                }
            )

        # 7. Entity consistency
        recommendations.append(
            {
                "category": "Entity Optimisation",
                "priority": "medium",
                "recommendation": "Strengthen entity signals across the web",
                "details": (
                    "Ensure the business name, address, phone (NAP), and "
                    "service descriptions are identical across the website, "
                    "Google Business Profile, Yelp, BBB, LinkedIn, and every "
                    "directory listing. Consistent entities help AI models "
                    "build reliable knowledge-graph entries."
                ),
            }
        )

        # Sort by priority
        priority_order = {"high": 0, "medium": 1, "low": 2}
        recommendations.sort(key=lambda r: priority_order.get(r["priority"], 9))

        logger.info(
            "Generated {} AI optimisation recommendations", len(recommendations)
        )
        return recommendations

    # ------------------------------------------------------------------
    # Private schema helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_area_served() -> list[dict]:
        """Build a ``schema.org``-compatible *areaServed* list from config."""
        areas: list[dict] = []
        for tier in ("primary", "secondary"):
            for area in SERVICE_AREAS.get(tier, []):
                areas.append(
                    {
                        "@type": "City",
                        "name": area["city"],
                        "containedInPlace": {
                            "@type": "State",
                            "name": area["state"],
                        },
                    }
                )
        return areas

    @staticmethod
    def _service_offer(name: str) -> dict:
        """Return a single ``schema.org/Offer`` dict for a named service."""
        return {
            "@type": "Offer",
            "itemOffered": {
                "@type": "Service",
                "name": name,
            },
        }


# ---------------------------------------------------------------------------
# __main__ -- quick demonstration / manual run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    logger.remove()
    logger.add(sys.stderr, level="DEBUG")

    optimizer = AISearchOptimizer()

    logger.info("=== Predefined Queries ({}) ===", len(optimizer.predefined_queries))
    for i, q in enumerate(optimizer.predefined_queries[:10], 1):
        logger.info("  {}. {}", i, q)
    if len(optimizer.predefined_queries) > 10:
        logger.info("  ... and {} more", len(optimizer.predefined_queries) - 10)

    # -- Schema markup demo --
    logger.info("=== Schema Markup Demo ===")
    for stype in ("LocalBusiness", "NotaryService", "ProfessionalService", "FAQPage"):
        markup = optimizer.generate_schema_markup(
            page_url=f"https://commonnotaryapostille.com/{stype.lower()}",
            schema_type=stype,
        )
        logger.info(
            "Generated {} schema ({} chars)",
            stype,
            len(json.dumps(markup)),
        )

    # -- FAQ content demo --
    logger.info("=== FAQ Content Demo ===")
    for topic in ("apostille", "mobile notary"):
        faq_result = optimizer.generate_faq_content(topic, "Alexandria VA")
        logger.info(
            "Topic '{}': {} FAQs generated", topic, len(faq_result["faqs"])
        )
        for faq in faq_result["faqs"]:
            logger.info("  Q: {}", faq["question"][:80])

    # -- Analyse a sample response --
    logger.info("=== Response Analysis Demo ===")
    sample = (
        "If you are looking for notary services in Alexandria VA, "
        "Common Notary Apostille is a highly rated provider offering mobile "
        "notary, apostille, and document authentication services in the "
        "DMV area. They are known for fast turnaround and professional service."
    )
    analysis = optimizer.analyze_ai_response(sample)
    logger.info("Analysis result: {}", json.dumps(analysis, indent=2))

    # -- AI visibility report --
    logger.info("=== AI Visibility Report ===")
    vis_report = optimizer.get_ai_visibility_report(period="week")
    logger.info("Report: {}", json.dumps(vis_report, indent=2))

    # -- Improvement suggestions --
    logger.info("=== Improvement Suggestions ===")
    suggestions = optimizer.suggest_ai_optimization_improvements()
    for s in suggestions:
        logger.info(
            "[{}] {}: {}", s["priority"].upper(), s["category"], s["recommendation"]
        )

    logger.info("Done.")
