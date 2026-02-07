"""
Module 4: Content Strategy & Auto-Generation
SEO & AI Monitoring Platform - Common Notary Apostille

Generates SEO-optimized content including blog posts, landing pages,
FAQ pages, meta tags, and content calendars targeting service areas
across the DMV (DC, Maryland, Virginia), Roanoke, and Southwest Virginia.
"""

import datetime
import json
import math
import re
import textwrap
from collections import Counter
from typing import Any, Optional

from loguru import logger

try:
    import openai

    _OPENAI_AVAILABLE = True
except ImportError:
    _OPENAI_AVAILABLE = False
    logger.warning("openai package not installed; falling back to template-based generation")

from config.settings import (
    COMPANY,
    GEO_MODIFIERS,
    OPENAI_API_KEY,
    SERVICE_AREAS,
    SERVICE_KEYWORDS,
)
from database.models import ContentCalendar, ContentIdea, SessionLocal

# ---------------------------------------------------------------------------
# Pre-defined topic templates (50+)
# Each entry contains a title template, content type, search intent,
# and a list of target keywords.  The placeholder ``{area}`` is
# replaced at generation time with a concrete service area name.
# ---------------------------------------------------------------------------

TOPIC_TEMPLATES: list[dict[str, Any]] = [
    # --- Service-specific guides: Apostille ---
    {
        "title": "How to Get an Apostille in {area}: Step-by-Step Guide",
        "content_type": "blog",
        "search_intent": "informational",
        "keywords": ["apostille services", "how to get an apostille", "apostille {area}"],
    },
    {
        "title": "Apostille Services in {area}: Costs, Timeline & Requirements",
        "content_type": "blog",
        "search_intent": "commercial",
        "keywords": ["apostille services {area}", "apostille cost", "apostille requirements"],
    },
    {
        "title": "What Documents Need an Apostille in {area}?",
        "content_type": "blog",
        "search_intent": "informational",
        "keywords": ["apostille documents", "apostille requirements"],
    },
    {
        "title": "Federal vs. State Apostille: Which One Do You Need?",
        "content_type": "blog",
        "search_intent": "informational",
        "keywords": ["federal apostille", "state apostille", "apostille difference"],
    },
    {
        "title": "Apostille for Birth Certificates in {area}: Complete Guide",
        "content_type": "blog",
        "search_intent": "informational",
        "keywords": ["apostille birth certificate", "birth certificate apostille {area}"],
    },
    {
        "title": "How Long Does an Apostille Take in {area}?",
        "content_type": "blog",
        "search_intent": "informational",
        "keywords": ["apostille processing time", "apostille timeline {area}"],
    },
    # --- Service-specific guides: Notary ---
    {
        "title": "Mobile Notary Services in {area}: What You Need to Know",
        "content_type": "blog",
        "search_intent": "commercial",
        "keywords": ["mobile notary {area}", "mobile notary services", "notary near me"],
    },
    {
        "title": "How to Find a Reliable Notary Public in {area}",
        "content_type": "blog",
        "search_intent": "commercial",
        "keywords": ["notary public {area}", "notary near me", "find a notary"],
    },
    {
        "title": "Remote Online Notarization in {area}: Is It Right for You?",
        "content_type": "blog",
        "search_intent": "informational",
        "keywords": ["remote online notarization", "RON {area}", "online notary"],
    },
    {
        "title": "Emergency Notary Services in {area}: 24/7 Availability",
        "content_type": "blog",
        "search_intent": "transactional",
        "keywords": ["emergency notary {area}", "24 hour notary", "after hours notary"],
    },
    {
        "title": "Hospital & Nursing Home Notary Services in {area}",
        "content_type": "blog",
        "search_intent": "commercial",
        "keywords": ["hospital notary {area}", "nursing home notary", "bedside notary"],
    },
    {
        "title": "What Does a Notary Public Do? A Complete Guide for {area} Residents",
        "content_type": "blog",
        "search_intent": "informational",
        "keywords": ["what does a notary do", "notary public services", "notary explained"],
    },
    # --- Service-specific guides: POA & Legal Documents ---
    {
        "title": "Power of Attorney Notarization for Foreign Documents",
        "content_type": "blog",
        "search_intent": "informational",
        "keywords": ["power of attorney notarization", "POA notary", "foreign documents notary"],
    },
    {
        "title": "Getting a Power of Attorney Notarized in {area}",
        "content_type": "blog",
        "search_intent": "commercial",
        "keywords": ["power of attorney {area}", "POA notarization {area}"],
    },
    {
        "title": "Notarizing Legal Documents for International Use in {area}",
        "content_type": "blog",
        "search_intent": "informational",
        "keywords": ["international document notarization", "foreign document notary {area}"],
    },
    {
        "title": "Affidavit Notarization in {area}: What You Need to Bring",
        "content_type": "blog",
        "search_intent": "informational",
        "keywords": ["affidavit notarization", "notarize affidavit {area}"],
    },
    # --- Service-specific guides: Document Authentication & Legalization ---
    {
        "title": "International Document Authentication in the DMV Area",
        "content_type": "blog",
        "search_intent": "informational",
        "keywords": ["document authentication", "international document authentication DMV"],
    },
    {
        "title": "Embassy Legalization vs. Apostille: Key Differences Explained",
        "content_type": "blog",
        "search_intent": "informational",
        "keywords": ["embassy legalization", "apostille vs legalization", "document legalization"],
    },
    {
        "title": "When Do You Need an Apostille vs. Authentication?",
        "content_type": "blog",
        "search_intent": "informational",
        "keywords": ["apostille vs authentication", "document authentication", "when to get apostille"],
    },
    {
        "title": "Embassy Legalization Services in {area}: Complete Guide",
        "content_type": "blog",
        "search_intent": "commercial",
        "keywords": ["embassy legalization {area}", "embassy legalization services"],
    },
    # --- Service-specific guides: Real Estate & Loan Signing ---
    {
        "title": "Real Estate Closing Notary Services in {area}",
        "content_type": "blog",
        "search_intent": "commercial",
        "keywords": ["real estate closing notary {area}", "closing notary", "real estate notary"],
    },
    {
        "title": "Loan Signing Agent Services in the {area} Area",
        "content_type": "blog",
        "search_intent": "commercial",
        "keywords": ["loan signing agent {area}", "loan signing services", "mortgage notary"],
    },
    {
        "title": "What to Expect During a Real Estate Closing in {area}",
        "content_type": "blog",
        "search_intent": "informational",
        "keywords": ["real estate closing {area}", "closing process", "what to expect closing"],
    },
    # --- Service-specific guides: Translation & Bilingual ---
    {
        "title": "Spanish Document Notarization Services in {area}",
        "content_type": "blog",
        "search_intent": "commercial",
        "keywords": ["Spanish notary {area}", "bilingual notary", "Spanish document notarization"],
    },
    {
        "title": "Certified Translation Notarization in {area}: Requirements & Process",
        "content_type": "blog",
        "search_intent": "informational",
        "keywords": [
            "certified translation notarization",
            "translation notary {area}",
            "notarize translation",
        ],
    },
    {
        "title": "Bilingual Notary Services: Why Language Matters for Your Documents",
        "content_type": "blog",
        "search_intent": "informational",
        "keywords": ["bilingual notary", "Spanish notary", "language services notary"],
    },
    # --- Location-specific landing page templates ---
    {
        "title": "Notary & Apostille Services in {area}",
        "content_type": "landing_page",
        "search_intent": "transactional",
        "keywords": ["notary {area}", "apostille {area}", "notary services {area}"],
    },
    {
        "title": "Mobile Notary in {area} - Same Day Service Available",
        "content_type": "landing_page",
        "search_intent": "transactional",
        "keywords": ["mobile notary {area}", "same day notary {area}", "notary near me"],
    },
    {
        "title": "Apostille Service in {area} - Fast & Reliable",
        "content_type": "landing_page",
        "search_intent": "transactional",
        "keywords": ["apostille {area}", "apostille service {area}", "fast apostille"],
    },
    # --- How-to guides ---
    {
        "title": "How to Notarize a Document in {area}: Everything You Need to Know",
        "content_type": "blog",
        "search_intent": "informational",
        "keywords": ["how to notarize document", "notarize document {area}"],
    },
    {
        "title": "How to Get a Document Authenticated for Use Abroad",
        "content_type": "blog",
        "search_intent": "informational",
        "keywords": ["document authentication abroad", "authenticate document", "use abroad"],
    },
    {
        "title": "How to Prepare for a Mobile Notary Visit in {area}",
        "content_type": "blog",
        "search_intent": "informational",
        "keywords": ["prepare for notary", "mobile notary visit", "mobile notary {area}"],
    },
    {
        "title": "How to Get Your Diploma Apostilled for Use Overseas",
        "content_type": "blog",
        "search_intent": "informational",
        "keywords": ["diploma apostille", "apostille diploma", "education document apostille"],
    },
    {
        "title": "How to Notarize Documents at a Hospital or Care Facility in {area}",
        "content_type": "blog",
        "search_intent": "informational",
        "keywords": ["hospital notary", "care facility notary", "bedside notary {area}"],
    },
    # --- Comparison / information articles ---
    {
        "title": "Notary Public vs. Notario: Understanding the Difference",
        "content_type": "blog",
        "search_intent": "informational",
        "keywords": ["notary vs notario", "notario fraud", "notary public difference"],
    },
    {
        "title": "Apostille vs. Embassy Legalization: Which Do You Need?",
        "content_type": "blog",
        "search_intent": "informational",
        "keywords": ["apostille vs legalization", "hague convention", "non-hague countries"],
    },
    {
        "title": "In-Office Notary vs. Mobile Notary: Pros and Cons",
        "content_type": "blog",
        "search_intent": "informational",
        "keywords": ["mobile notary vs office", "notary comparison", "mobile notary benefits"],
    },
    {
        "title": "Online Notarization vs. In-Person Notarization in {area}",
        "content_type": "blog",
        "search_intent": "informational",
        "keywords": ["online notarization vs in-person", "RON vs in-person", "notarization options"],
    },
    {
        "title": "Virginia vs. DC vs. Maryland Notary Requirements: A Comparison",
        "content_type": "blog",
        "search_intent": "informational",
        "keywords": [
            "notary requirements Virginia",
            "notary requirements DC",
            "notary requirements Maryland",
        ],
    },
    {
        "title": "Hague Convention Countries: Complete List and What It Means for Apostilles",
        "content_type": "blog",
        "search_intent": "informational",
        "keywords": ["hague convention countries", "hague apostille", "apostille countries list"],
    },
    # --- Seasonal / timely content ideas ---
    {
        "title": "Tax Season Notarization: Documents You May Need Notarized in {area}",
        "content_type": "blog",
        "search_intent": "informational",
        "keywords": ["tax season notary", "tax document notarization", "IRS notary"],
    },
    {
        "title": "Back-to-School: Getting Transcripts Apostilled for Study Abroad",
        "content_type": "blog",
        "search_intent": "informational",
        "keywords": ["study abroad apostille", "transcript apostille", "school documents apostille"],
    },
    {
        "title": "Wedding Season: Marriage Certificate Apostille Guide for {area}",
        "content_type": "blog",
        "search_intent": "informational",
        "keywords": [
            "marriage certificate apostille",
            "wedding document notary",
            "marriage apostille {area}",
        ],
    },
    {
        "title": "Year-End Checklist: Legal Documents to Notarize Before the New Year",
        "content_type": "blog",
        "search_intent": "informational",
        "keywords": ["year-end notary", "legal documents checklist", "end of year notarization"],
    },
    {
        "title": "Immigration Season: Apostille and Notarization for Visa Applications",
        "content_type": "blog",
        "search_intent": "informational",
        "keywords": ["visa apostille", "immigration notary", "visa document notarization"],
    },
    {
        "title": "Military PCS Season: Notary Services for Relocating Families in {area}",
        "content_type": "blog",
        "search_intent": "commercial",
        "keywords": ["military notary {area}", "PCS notary", "military relocation notary"],
    },
    # --- FAQ page templates ---
    {
        "title": "Apostille FAQ: Your Top Questions Answered ({area})",
        "content_type": "faq",
        "search_intent": "informational",
        "keywords": ["apostille FAQ", "apostille questions", "apostille {area}"],
    },
    {
        "title": "Mobile Notary FAQ for {area} Residents",
        "content_type": "faq",
        "search_intent": "informational",
        "keywords": ["notary FAQ", "mobile notary questions", "notary {area}"],
    },
    {
        "title": "Document Authentication FAQ: Embassy Legalization & More",
        "content_type": "faq",
        "search_intent": "informational",
        "keywords": ["document authentication FAQ", "legalization questions"],
    },
    # --- Niche / long-tail topics ---
    {
        "title": "Notarizing Documents for Elderly or Home-Bound Clients in {area}",
        "content_type": "blog",
        "search_intent": "commercial",
        "keywords": ["elderly notary {area}", "home-bound notary", "senior notary services"],
    },
    {
        "title": "Corporate Notary Services in {area}: Board Resolutions & More",
        "content_type": "blog",
        "search_intent": "commercial",
        "keywords": ["corporate notary {area}", "board resolution notary", "business notary"],
    },
    {
        "title": "Adoption Document Notarization and Apostille Services in {area}",
        "content_type": "blog",
        "search_intent": "commercial",
        "keywords": ["adoption notary", "adoption apostille {area}", "adoption documents"],
    },
    {
        "title": "I-9 Employment Verification Notary Services in {area}",
        "content_type": "blog",
        "search_intent": "commercial",
        "keywords": ["I-9 notary {area}", "employment verification notary", "I-9 form notarization"],
    },
    {
        "title": "Jail & Prison Notary Services in {area}: How It Works",
        "content_type": "blog",
        "search_intent": "informational",
        "keywords": ["jail notary {area}", "prison notary", "incarcerated notary services"],
    },
    {
        "title": "Notarizing a Will or Trust in {area}: What You Need to Know",
        "content_type": "blog",
        "search_intent": "informational",
        "keywords": ["notarize will {area}", "trust notarization", "estate planning notary"],
    },
    {
        "title": "Title Transfer Notarization in {area}: Vehicle & Property",
        "content_type": "blog",
        "search_intent": "commercial",
        "keywords": ["title transfer notary {area}", "vehicle title notary", "property transfer notary"],
    },
]

# ---------------------------------------------------------------------------
# Flesch-Kincaid readability helpers
# ---------------------------------------------------------------------------

_SYLLABLE_OVERRIDES: dict[str, int] = {
    "notary": 3,
    "apostille": 3,
    "authentication": 6,
    "legalization": 5,
    "notarization": 5,
}


def _count_syllables(word: str) -> int:
    """Estimate the number of syllables in a single English word."""
    word = word.lower().strip()
    if word in _SYLLABLE_OVERRIDES:
        return _SYLLABLE_OVERRIDES[word]
    if len(word) <= 3:
        return 1
    word = re.sub(r"(?:es|ed|e)$", "", word) or word
    vowel_groups = re.findall(r"[aeiouy]+", word)
    return max(1, len(vowel_groups))


def _flesch_kincaid_grade(text: str) -> float:
    """Return the Flesch-Kincaid Grade Level for *text*."""
    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
    words = re.findall(r"[a-zA-Z']+", text)
    if not sentences or not words:
        return 0.0
    total_syllables = sum(_count_syllables(w) for w in words)
    grade = (
        0.39 * (len(words) / len(sentences))
        + 11.8 * (total_syllables / len(words))
        - 15.59
    )
    return round(max(0.0, grade), 2)


def _flesch_reading_ease(text: str) -> float:
    """Return the Flesch Reading Ease score (0-100, higher is easier)."""
    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
    words = re.findall(r"[a-zA-Z']+", text)
    if not sentences or not words:
        return 0.0
    total_syllables = sum(_count_syllables(w) for w in words)
    score = (
        206.835
        - 1.015 * (len(words) / len(sentences))
        - 84.6 * (total_syllables / len(words))
    )
    return round(max(0.0, min(100.0, score)), 2)


# ---------------------------------------------------------------------------
# ContentStrategyEngine
# ---------------------------------------------------------------------------


class ContentStrategyEngine:
    """Generates and manages SEO-optimized content for Common Notary Apostille.

    Content targets the DMV area (DC, Maryland, Virginia), Roanoke, and
    Southwest Virginia with service-specific and location-specific pages,
    blog posts, FAQ pages, and supporting meta data.
    """

    def __init__(self) -> None:
        self.company: dict[str, Any] = COMPANY
        self.service_areas: dict[str, list[dict[str, str]]] = SERVICE_AREAS
        self.service_keywords: list[str] = SERVICE_KEYWORDS
        self.geo_modifiers: list[str] = GEO_MODIFIERS
        self.openai_api_key: str = OPENAI_API_KEY
        self._openai_client: Any | None = None

        if _OPENAI_AVAILABLE and self.openai_api_key:
            try:
                self._openai_client = openai.OpenAI(api_key=self.openai_api_key)
                logger.info("OpenAI client initialized successfully")
            except Exception as exc:
                logger.warning("Failed to initialize OpenAI client: {}", exc)
        else:
            logger.info(
                "OpenAI client not available; using template-based content generation"
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_all_areas(self) -> list[dict[str, str]]:
        """Return a flat list of all service areas with their tier."""
        areas: list[dict[str, str]] = []
        for tier, area_list in self.service_areas.items():
            for area in area_list:
                areas.append({**area, "tier": tier})
        return areas

    def _area_label(self, area: dict[str, str]) -> str:
        """Return a human-readable label like ``Alexandria, VA``."""
        return f"{area['city']}, {area['state']}"

    def _format_area_short(self, area: dict[str, str]) -> str:
        """Short area string, e.g. ``Alexandria VA``."""
        return f"{area['city']} {area['state']}"

    def _call_openai(self, prompt: str, max_tokens: int = 2000) -> Optional[str]:
        """Call the OpenAI chat completions API with a system + user prompt.

        Returns ``None`` when the API is unavailable or on error so that
        callers can fall through to a template-based alternative.
        """
        if self._openai_client is None:
            return None
        try:
            response = self._openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert SEO content writer specializing in "
                            "notary public and apostille services.  You write clear, "
                            "authoritative, locally-relevant content optimized for "
                            "search engines."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
                temperature=0.7,
            )
            return response.choices[0].message.content
        except Exception as exc:
            logger.error("OpenAI API call failed: {}", exc)
            return None

    def _save_content_idea(self, idea: dict[str, Any]) -> Optional[int]:
        """Persist a content idea to the database and return its id."""
        db = SessionLocal()
        try:
            record = ContentIdea(
                title=idea.get("title", ""),
                content_type=idea.get("content_type", "blog"),
                target_keyword=idea.get("target_keyword", ""),
                target_area=idea.get("target_area", ""),
                draft_content=idea.get("draft_content"),
                meta_title=idea.get("meta_title"),
                meta_description=idea.get("meta_description"),
                headers=idea.get("headers"),
                word_count=idea.get("word_count"),
                readability_score=idea.get("readability_score"),
                seo_score=idea.get("seo_score"),
                status=idea.get("status", "idea"),
                scheduled_date=idea.get("scheduled_date"),
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            logger.info("Saved content idea id={}: {}", record.id, record.title)
            return record.id
        except Exception as exc:
            db.rollback()
            logger.error("Failed to save content idea: {}", exc)
            return None
        finally:
            db.close()

    # ------------------------------------------------------------------
    # 1. generate_blog_ideas
    # ------------------------------------------------------------------

    def generate_blog_ideas(self, count: int = 20) -> list[dict[str, Any]]:
        """Generate SEO-optimized blog post ideas targeting each service area.

        Returns up to *count* ideas, each containing ``title``,
        ``content_type``, ``search_intent``, ``target_keywords``, and
        ``target_area``.

        Args:
            count: Maximum number of ideas to return. Defaults to 20.

        Returns:
            A list of dictionaries, one per content idea.
        """
        logger.info("Generating up to {} blog ideas", count)

        ideas: list[dict[str, Any]] = []
        areas = self._get_all_areas()

        for template in TOPIC_TEMPLATES:
            if len(ideas) >= count:
                break

            # Templates with {area} get expanded across areas
            if "{area}" in template["title"]:
                for area in areas:
                    if len(ideas) >= count:
                        break
                    area_label = self._area_label(area)
                    area_short = self._format_area_short(area)
                    title = template["title"].replace("{area}", area_label)
                    keywords = [
                        kw.replace("{area}", area_short)
                        for kw in template["keywords"]
                    ]
                    ideas.append(
                        {
                            "title": title,
                            "content_type": template["content_type"],
                            "search_intent": template["search_intent"],
                            "target_keywords": keywords,
                            "target_area": area_label,
                        }
                    )
            else:
                # Area-agnostic topic
                ideas.append(
                    {
                        "title": template["title"],
                        "content_type": template["content_type"],
                        "search_intent": template["search_intent"],
                        "target_keywords": template["keywords"],
                        "target_area": "All Areas",
                    }
                )

        ideas = ideas[:count]
        logger.info("Generated {} blog ideas", len(ideas))
        return ideas

    # ------------------------------------------------------------------
    # 2. generate_blog_draft
    # ------------------------------------------------------------------

    def generate_blog_draft(
        self,
        title: str,
        target_keyword: str,
        target_area: str,
    ) -> dict[str, Any]:
        """Generate a full SEO-optimized blog draft.

        Attempts to use the OpenAI API first; falls back to a rich
        template-based draft when the API is unavailable.

        Args:
            title: The blog post title (used as H1).
            target_keyword: Primary keyword to optimize for.
            target_area: Geographic area the post targets.

        Returns:
            A dictionary with ``title``, ``content``, ``headers``,
            ``word_count``, ``meta_title``, ``meta_description``,
            ``internal_links``, and ``seo_score``.
        """
        logger.info(
            "Generating blog draft: title='{}', keyword='{}', area='{}'",
            title,
            target_keyword,
            target_area,
        )

        prompt = textwrap.dedent(f"""\
            Write a comprehensive, SEO-optimized blog post for a notary and apostille
            services company called "{self.company['name']}".

            Title (H1): {title}
            Primary keyword: {target_keyword}
            Target area: {target_area}
            Company website: {self.company['website']}

            Requirements:
            - 1,200-1,800 words
            - Use the primary keyword naturally 4-6 times
            - Include H2 and H3 sub-headings with keyword variations
            - Write an engaging introduction that includes the keyword in the first paragraph
            - Include a clear call-to-action referencing {self.company['name']}
            - Reference the target geographic area naturally throughout
            - Suggest 3 internal linking opportunities to other service pages
            - Use short paragraphs (2-3 sentences) for readability
            - Include a brief FAQ section at the end with 3 questions
            - Maintain an authoritative but approachable tone

            Format the output as plain text with Markdown-style headers (# H1, ## H2, ### H3).
        """)

        ai_content = self._call_openai(prompt, max_tokens=3000)

        if ai_content:
            content = ai_content
            logger.info("Blog draft generated via OpenAI API")
        else:
            content = self._template_blog_draft(title, target_keyword, target_area)
            logger.info("Blog draft generated via template fallback")

        headers = self._extract_headers(content)
        word_count = len(re.findall(r"\S+", content))
        meta = self.generate_meta_tags(content, target_keyword)

        internal_links = [
            f"{self.company['website']}/apostille-services",
            f"{self.company['website']}/mobile-notary",
            f"{self.company['website']}/contact",
        ]

        draft: dict[str, Any] = {
            "title": title,
            "content": content,
            "headers": headers,
            "word_count": word_count,
            "meta_title": meta["meta_title"],
            "meta_description": meta["meta_description"],
            "internal_links": internal_links,
            "seo_score": self.analyze_content_quality(content)["seo_score"],
        }

        self._save_content_idea(
            {
                "title": title,
                "content_type": "blog",
                "target_keyword": target_keyword,
                "target_area": target_area,
                "draft_content": content,
                "meta_title": draft["meta_title"],
                "meta_description": draft["meta_description"],
                "headers": headers,
                "word_count": word_count,
                "seo_score": draft["seo_score"],
                "status": "drafted",
            }
        )

        return draft

    def _template_blog_draft(
        self, title: str, target_keyword: str, target_area: str
    ) -> str:
        """Build a template-based blog draft when OpenAI is unavailable."""
        company = self.company["name"]
        website = self.company["website"]
        return textwrap.dedent(f"""\
            # {title}

            If you are looking for professional {target_keyword} in {target_area}, you
            have come to the right place. {company} provides trusted, convenient, and
            affordable services to individuals and businesses throughout the region.

            Whether you need a document notarized for personal use or authenticated for
            international purposes, understanding the process can save you time, money,
            and stress. This guide covers everything you need to know about
            {target_keyword} in the {target_area} area.

            ## Why {target_keyword.title()} Matters

            Notarization and apostille services play a critical role in verifying the
            authenticity of legal documents. From real estate transactions and powers of
            attorney to birth certificates destined for use abroad, proper notarization
            ensures your documents are legally recognized.

            In {target_area}, residents and businesses frequently need these services for
            a wide range of personal and professional transactions.

            ## How {company} Can Help

            {company} offers a full suite of notary and apostille solutions across
            {target_area} and the surrounding areas. Our services include:

            - **Mobile Notary** -- we come to your location for maximum convenience
            - **Apostille Services** -- state and federal apostille processing
            - **Document Authentication** -- embassy legalization and authentication
            - **Power of Attorney** -- notarization of POA documents, including
              international POAs
            - **Loan Signing** -- professional loan signing agent services
            - **Real Estate Closings** -- on-site notary for property transactions

            ### Our Process

            1. **Contact us** -- call or visit [{website}]({website}) to schedule your
               appointment.
            2. **Provide documents** -- let us know which documents need notarization or
               apostille.
            3. **Meet with a notary** -- we meet you at your home, office, hospital, or
               any convenient location in {target_area}.
            4. **Receive your documents** -- completed and ready for use, domestically or
               internationally.

            ## Understanding {target_keyword.title()} Requirements in {target_area}

            Requirements can vary depending on the document type and its intended use.
            Here are a few important points to keep in mind:

            - **Valid government-issued ID** is required for all notarizations.
            - **Documents must be unsigned** until you are in the presence of the notary.
            - **Apostilles** are issued by the state Secretary of State (or equivalent)
              for Hague Convention countries.
            - **Embassy legalization** is required for countries that are not part of the
              Hague Convention.

            ### Common Documents That Need {target_keyword.title()}

            - Birth and marriage certificates
            - Academic transcripts and diplomas
            - Powers of attorney
            - Affidavits and sworn statements
            - Corporate documents and resolutions
            - Real estate deeds and contracts

            ## Frequently Asked Questions

            ### How much does {target_keyword} cost in {target_area}?

            Costs vary depending on the service. Standard notarizations typically start at
            a competitive rate, and apostille processing fees depend on whether a state or
            federal apostille is needed. Contact {company} for a free quote.

            ### Can you come to my location in {target_area}?

            Yes! {company} offers mobile notary services throughout {target_area}. We can
            meet you at your home, office, hospital, or any convenient location.

            ### How long does the process take?

            Standard notarizations can be completed in a single visit. Apostille
            processing times vary by state but typically take 3-10 business days. Expedited
            options are available.

            ## Get Started Today

            Ready to get your documents notarized or apostilled in {target_area}? Contact
            {company} today for fast, reliable, and professional service.

            - **Website:** [{website}]({website})
            - **Phone:** {self.company.get('phone', 'Call us today')}

            *{company} proudly serves {target_area} and the surrounding communities with
            expert notary public and apostille services.*
        """)

    @staticmethod
    def _extract_headers(content: str) -> list[dict[str, str]]:
        """Extract Markdown-style headers from *content*."""
        headers: list[dict[str, str]] = []
        for match in re.finditer(r"^(#{1,6})\s+(.+)$", content, re.MULTILINE):
            level = len(match.group(1))
            headers.append({"level": f"H{level}", "text": match.group(2).strip()})
        return headers

    # ------------------------------------------------------------------
    # 3. generate_landing_page_content
    # ------------------------------------------------------------------

    def generate_landing_page_content(
        self, service: str, area: dict[str, str]
    ) -> dict[str, Any]:
        """Create location-specific landing page content with schema markup.

        Args:
            service: The service name (e.g. ``"apostille services"``).
            area: A service area dict with ``city``, ``state``, ``region`` keys.

        Returns:
            A dictionary with ``title``, ``content``, ``meta_title``,
            ``meta_description``, ``schema_markup``, and ``headers``.
        """
        area_label = self._area_label(area)
        logger.info("Generating landing page: service='{}', area='{}'", service, area_label)

        title = f"{service.title()} in {area_label} | {self.company['name']}"
        company = self.company["name"]
        website = self.company["website"]

        prompt = textwrap.dedent(f"""\
            Write a high-converting landing page for "{service}" in {area_label} for
            the company "{company}" ({website}).

            Requirements:
            - 600-900 words
            - Strong H1 that includes the service and location
            - 3-4 H2 sections covering: what the service is, why choose us, service
              area details, and a call to action
            - Include trust signals (years of experience, professionalism, convenience)
            - Reference the specific city/region naturally
            - Include a bulleted list of included services
            - End with a strong call-to-action
        """)

        ai_content = self._call_openai(prompt, max_tokens=1500)

        if ai_content:
            content = ai_content
        else:
            content = textwrap.dedent(f"""\
                # {service.title()} in {area_label}

                Looking for reliable {service} in {area_label}? {company} provides
                professional, convenient, and affordable {service} to residents and
                businesses in {area['city']} and the surrounding {area.get('region', '')}
                area.

                ## Our {service.title()} Include

                - Mobile notary services -- we come to you
                - Same-day and next-day appointments available
                - Competitive and transparent pricing
                - Experienced, commission-active notaries
                - Bilingual services available (English/Spanish)

                ## Why Choose {company} in {area_label}?

                We understand that your time is valuable. That is why we offer flexible
                scheduling, including evenings and weekends, and will travel to any
                location in {area['city']} and {area.get('region', 'the surrounding area')}.

                Our notaries are fully commissioned, insured, and experienced in handling
                a wide variety of documents -- from simple notarizations to complex
                international apostilles and embassy legalizations.

                ## Serving {area['city']} and {area.get('region', 'Surrounding Areas')}

                {company} is proud to serve clients throughout {area_label} and the
                broader {area.get('region', '')} region.  Whether you are at home, at
                work, in a hospital, or at a care facility, we bring our services to you.

                ## Get Started Today

                Contact {company} to schedule your {service} appointment in {area_label}.

                - **Website:** [{website}]({website})
                - **Phone:** {self.company.get('phone', 'Call us today')}
            """)

        meta = self.generate_meta_tags(content, f"{service} {self._format_area_short(area)}")

        schema_markup = {
            "@context": "https://schema.org",
            "@type": "LocalBusiness",
            "name": company,
            "url": website,
            "telephone": self.company.get("phone", ""),
            "description": f"Professional {service} in {area_label}. {company} offers "
            f"reliable and convenient notary and apostille services.",
            "address": {
                "@type": "PostalAddress",
                "addressLocality": area["city"],
                "addressRegion": area["state"],
                "addressCountry": "US",
            },
            "areaServed": {
                "@type": "City",
                "name": area["city"],
                "containedInPlace": {
                    "@type": "State",
                    "name": area["state"],
                },
            },
            "hasOfferCatalog": {
                "@type": "OfferCatalog",
                "name": service.title(),
                "itemListElement": [
                    {
                        "@type": "Offer",
                        "itemOffered": {
                            "@type": "Service",
                            "name": service.title(),
                        },
                    }
                ],
            },
        }

        result: dict[str, Any] = {
            "title": title,
            "content": content,
            "meta_title": meta["meta_title"],
            "meta_description": meta["meta_description"],
            "schema_markup": schema_markup,
            "headers": self._extract_headers(content),
        }

        self._save_content_idea(
            {
                "title": title,
                "content_type": "landing_page",
                "target_keyword": f"{service} {self._format_area_short(area)}",
                "target_area": area_label,
                "draft_content": content,
                "meta_title": result["meta_title"],
                "meta_description": result["meta_description"],
                "headers": result["headers"],
                "word_count": len(re.findall(r"\S+", content)),
                "status": "drafted",
            }
        )

        logger.info("Landing page generated for {} in {}", service, area_label)
        return result

    # ------------------------------------------------------------------
    # 4. generate_faq_page
    # ------------------------------------------------------------------

    _FAQ_BANK: dict[str, list[dict[str, str]]] = {
        "apostille": [
            {
                "q": "What is an apostille?",
                "a": (
                    "An apostille is a certificate issued by a designated authority that "
                    "authenticates the origin of a public document for use in another "
                    "country that is a member of the Hague Apostille Convention."
                ),
            },
            {
                "q": "Which documents can be apostilled?",
                "a": (
                    "Common documents that can be apostilled include birth certificates, "
                    "marriage certificates, court orders, diplomas, transcripts, powers "
                    "of attorney, corporate documents, and notarized documents."
                ),
            },
            {
                "q": "How long does the apostille process take?",
                "a": (
                    "Processing times vary by state. In Virginia, standard apostille "
                    "processing typically takes 5-10 business days. Expedited and "
                    "same-day processing may be available for an additional fee."
                ),
            },
            {
                "q": "How much does an apostille cost?",
                "a": (
                    "Costs depend on the state and type of document. State apostille "
                    "fees vary, and service fees from an apostille agent are additional. "
                    "Contact us for a detailed quote."
                ),
            },
            {
                "q": "What is the difference between an apostille and embassy legalization?",
                "a": (
                    "An apostille is used for countries that are part of the Hague "
                    "Convention. Embassy legalization (also called authentication) is "
                    "required for countries that are not members. The legalization "
                    "process typically takes longer and involves additional steps."
                ),
            },
            {
                "q": "Can I get an apostille for a federal document?",
                "a": (
                    "Yes. Federal documents such as FBI background checks, patent "
                    "documents, and federal court records require an apostille from the "
                    "U.S. Department of State rather than a state authority."
                ),
            },
        ],
        "notary": [
            {
                "q": "What does a notary public do?",
                "a": (
                    "A notary public is a state-commissioned official who serves as an "
                    "impartial witness to the signing of important documents. The notary "
                    "verifies the identity of signers, ensures they are signing "
                    "voluntarily, and applies an official seal."
                ),
            },
            {
                "q": "What identification do I need for notarization?",
                "a": (
                    "You need a valid, government-issued photo ID such as a driver's "
                    "license, state ID, passport, or military ID. The ID must be current "
                    "and not expired."
                ),
            },
            {
                "q": "Can a notary come to my home?",
                "a": (
                    "Yes! Mobile notary services allow a notary to come to your home, "
                    "office, hospital, or any convenient location. Additional travel fees "
                    "may apply."
                ),
            },
            {
                "q": "Do I need to sign the document before the notary arrives?",
                "a": (
                    "No. You should not sign the document until you are in the physical "
                    "presence of the notary. The notary must witness your signature."
                ),
            },
            {
                "q": "What is remote online notarization (RON)?",
                "a": (
                    "Remote online notarization allows documents to be notarized via a "
                    "secure video call. Virginia was the first state to authorize RON, "
                    "and it is now available in many states. It offers convenience for "
                    "signers who cannot meet in person."
                ),
            },
            {
                "q": "How much does mobile notary service cost?",
                "a": (
                    "Mobile notary fees include the state-regulated notarization fee "
                    "plus a travel fee that depends on distance. Contact us for a "
                    "transparent quote for your location."
                ),
            },
        ],
        "document_authentication": [
            {
                "q": "What is document authentication?",
                "a": (
                    "Document authentication (also called legalization) is the process "
                    "of certifying a document for use in a foreign country that is not "
                    "a member of the Hague Apostille Convention."
                ),
            },
            {
                "q": "Which countries require embassy legalization instead of an apostille?",
                "a": (
                    "Countries that have not joined the Hague Convention require embassy "
                    "legalization. Common examples include Canada, China, the UAE, and "
                    "several Middle Eastern and Asian countries. Check with the "
                    "destination country's embassy for specific requirements."
                ),
            },
            {
                "q": "How long does embassy legalization take?",
                "a": (
                    "Embassy legalization can take anywhere from a few days to several "
                    "weeks, depending on the embassy's processing times and workload. "
                    "Plan ahead to avoid delays."
                ),
            },
            {
                "q": "What documents need authentication for international use?",
                "a": (
                    "Common documents include birth certificates, marriage certificates, "
                    "divorce decrees, diplomas, transcripts, corporate documents, powers "
                    "of attorney, and commercial invoices."
                ),
            },
        ],
        "general": [
            {
                "q": "What areas do you serve?",
                "a": (
                    "We serve the entire DMV area including Washington DC, Northern "
                    "Virginia (Alexandria, Arlington, Fairfax, Loudoun County), "
                    "Maryland (Montgomery County, Prince George's County), as well as "
                    "Roanoke, Salem, Blacksburg, Christiansburg, and Lynchburg in "
                    "Southwest Virginia."
                ),
            },
            {
                "q": "Do you offer same-day service?",
                "a": (
                    "Yes, we offer same-day and next-day appointments for most services, "
                    "subject to availability. Contact us as early as possible to secure "
                    "your preferred time."
                ),
            },
            {
                "q": "Do you offer bilingual services?",
                "a": (
                    "Yes, we offer bilingual notary services in English and Spanish. "
                    "This is especially helpful for clients who need documents notarized "
                    "for use in Spanish-speaking countries."
                ),
            },
        ],
    }

    def generate_faq_page(self, topic: str, area: str) -> dict[str, Any]:
        """Produce an FAQ page optimized for voice search and AI answer extraction.

        Uses a question-and-answer format with FAQPage schema markup so that
        search engines can display rich results and AI assistants can extract
        direct answers.

        Args:
            topic: The FAQ topic (e.g. ``"apostille"``, ``"notary"``).
            area: Target geographic area label (e.g. ``"Alexandria, VA"``).

        Returns:
            A dictionary with ``title``, ``content``, ``schema_markup``,
            ``meta_title``, ``meta_description``, and ``questions``.
        """
        logger.info("Generating FAQ page: topic='{}', area='{}'", topic, area)

        topic_key = topic.lower().replace(" ", "_")
        faqs = list(self._FAQ_BANK.get(topic_key, self._FAQ_BANK["general"]))

        # Always append the general "areas served" questions
        if topic_key != "general":
            faqs.extend(self._FAQ_BANK["general"])

        # Localize answers with the area name
        localized_faqs: list[dict[str, str]] = []
        for faq in faqs:
            localized_q = faq["q"]
            localized_a = faq["a"]
            if "{area}" in localized_a:
                localized_a = localized_a.replace("{area}", area)
            localized_faqs.append({"question": localized_q, "answer": localized_a})

        title = f"{topic.title()} FAQ | {self.company['name']} - {area}"

        # Build content
        lines = [f"# {topic.title()} - Frequently Asked Questions ({area})\n"]
        for faq in localized_faqs:
            lines.append(f"## {faq['question']}\n")
            lines.append(f"{faq['answer']}\n")
        lines.append(
            f"\n---\n\nHave more questions? Contact {self.company['name']} today at "
            f"{self.company['website']} or call {self.company.get('phone', 'us')}.\n"
        )
        content = "\n".join(lines)

        # FAQPage schema markup
        schema_markup = {
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
                for faq in localized_faqs
            ],
        }

        meta = self.generate_meta_tags(content, f"{topic} FAQ {area}")

        result: dict[str, Any] = {
            "title": title,
            "content": content,
            "schema_markup": schema_markup,
            "meta_title": meta["meta_title"],
            "meta_description": meta["meta_description"],
            "questions": localized_faqs,
        }

        self._save_content_idea(
            {
                "title": title,
                "content_type": "faq",
                "target_keyword": f"{topic} FAQ",
                "target_area": area,
                "draft_content": content,
                "meta_title": result["meta_title"],
                "meta_description": result["meta_description"],
                "headers": self._extract_headers(content),
                "word_count": len(re.findall(r"\S+", content)),
                "status": "drafted",
            }
        )

        logger.info("FAQ page generated with {} questions for {}", len(localized_faqs), area)
        return result

    # ------------------------------------------------------------------
    # 5. generate_meta_tags
    # ------------------------------------------------------------------

    def generate_meta_tags(
        self, content: str, target_keyword: str
    ) -> dict[str, Any]:
        """Auto-generate meta title, meta description, and header tag recommendations.

        Args:
            content: The full page/post content.
            target_keyword: The primary keyword to include in the meta tags.

        Returns:
            A dictionary with ``meta_title`` (under 60 chars),
            ``meta_description`` (under 160 chars), and
            ``header_recommendations``.
        """
        logger.debug("Generating meta tags for keyword '{}'", target_keyword)

        # --- Meta title (under 60 characters) ---
        company_short = self.company["name"]
        base_title = f"{target_keyword.title()} | {company_short}"
        if len(base_title) > 60:
            # Try without company name
            base_title = target_keyword.title()
            if len(base_title) > 60:
                base_title = base_title[:57] + "..."
        meta_title = base_title

        # --- Meta description (under 160 characters) ---
        # Pull from the first meaningful paragraph of content
        paragraphs = [
            p.strip()
            for p in content.split("\n")
            if p.strip() and not p.strip().startswith("#") and len(p.strip()) > 40
        ]
        if paragraphs:
            raw_desc = paragraphs[0]
            # Strip markdown formatting
            raw_desc = re.sub(r"[*_\[\]()#`]", "", raw_desc).strip()
        else:
            raw_desc = (
                f"Professional {target_keyword} from {company_short}. "
                f"Serving the DMV area, Roanoke, and Southwest Virginia."
            )

        if len(raw_desc) > 160:
            # Truncate at the last full word before 157 chars + "..."
            raw_desc = raw_desc[:157].rsplit(" ", 1)[0] + "..."
        meta_description = raw_desc

        # --- Header recommendations ---
        existing_headers = self._extract_headers(content)
        h1_count = sum(1 for h in existing_headers if h["level"] == "H1")
        h2_count = sum(1 for h in existing_headers if h["level"] == "H2")

        recommendations: list[str] = []
        if h1_count == 0:
            recommendations.append(
                f"Add an H1 tag that includes the target keyword '{target_keyword}'."
            )
        elif h1_count > 1:
            recommendations.append(
                "Use only one H1 tag per page. Move additional H1s to H2."
            )

        keyword_in_h1 = any(
            target_keyword.lower() in h["text"].lower()
            for h in existing_headers
            if h["level"] == "H1"
        )
        if not keyword_in_h1 and h1_count > 0:
            recommendations.append(
                f"Include the target keyword '{target_keyword}' in the H1 tag."
            )

        if h2_count < 2:
            recommendations.append(
                "Add at least 2-3 H2 sub-headings to improve content structure and SEO."
            )

        if not recommendations:
            recommendations.append("Header structure looks good. No changes needed.")

        return {
            "meta_title": meta_title,
            "meta_description": meta_description,
            "header_recommendations": recommendations,
        }

    # ------------------------------------------------------------------
    # 6. create_content_calendar
    # ------------------------------------------------------------------

    def create_content_calendar(self, months: int = 3) -> list[dict[str, Any]]:
        """Generate a content calendar with a publishing schedule.

        Distributes blog posts (weekly), landing pages (bi-weekly), FAQ
        updates (monthly), and seasonal content across the requested
        time span.

        Args:
            months: Number of months to plan. Defaults to 3.

        Returns:
            A list of calendar entries, each with ``scheduled_date``,
            ``content_type``, ``title``, ``target_platform``, ``status``,
            and ``notes``.
        """
        logger.info("Creating {}-month content calendar", months)

        ideas = self.generate_blog_ideas(count=200)
        blog_ideas = [i for i in ideas if i["content_type"] == "blog"]
        landing_ideas = [i for i in ideas if i["content_type"] == "landing_page"]
        faq_ideas = [i for i in ideas if i["content_type"] == "faq"]

        calendar: list[dict[str, Any]] = []
        start_date = datetime.date.today()
        end_date = start_date + datetime.timedelta(days=months * 30)

        blog_idx = 0
        landing_idx = 0
        faq_idx = 0

        current = start_date
        week_number = 0

        while current <= end_date:
            # Blog post every Tuesday
            if current.weekday() == 1:  # Tuesday
                if blog_idx < len(blog_ideas):
                    idea = blog_ideas[blog_idx]
                    calendar.append(
                        {
                            "scheduled_date": current.isoformat(),
                            "content_type": "blog",
                            "title": idea["title"],
                            "target_platform": "website",
                            "status": "scheduled",
                            "target_area": idea.get("target_area", "All Areas"),
                            "notes": f"Keywords: {', '.join(idea.get('target_keywords', [])[:3])}",
                        }
                    )
                    blog_idx += 1

            # Landing page every other Thursday
            if current.weekday() == 3 and week_number % 2 == 0:  # Thursday, bi-weekly
                if landing_idx < len(landing_ideas):
                    idea = landing_ideas[landing_idx]
                    calendar.append(
                        {
                            "scheduled_date": current.isoformat(),
                            "content_type": "landing_page",
                            "title": idea["title"],
                            "target_platform": "website",
                            "status": "scheduled",
                            "target_area": idea.get("target_area", "All Areas"),
                            "notes": "New location-specific landing page",
                        }
                    )
                    landing_idx += 1

            # FAQ update first Wednesday of each month
            if current.weekday() == 2 and current.day <= 7:  # First Wednesday
                if faq_idx < len(faq_ideas):
                    idea = faq_ideas[faq_idx]
                    calendar.append(
                        {
                            "scheduled_date": current.isoformat(),
                            "content_type": "faq",
                            "title": idea["title"],
                            "target_platform": "website",
                            "status": "scheduled",
                            "target_area": idea.get("target_area", "All Areas"),
                            "notes": "FAQ page update for voice search optimization",
                        }
                    )
                    faq_idx += 1

            # Seasonal content ideas on specific dates
            seasonal = self._get_seasonal_content(current)
            if seasonal:
                calendar.append(seasonal)

            if current.weekday() == 6:  # Sunday marks end of week
                week_number += 1

            current += datetime.timedelta(days=1)

        # Persist to database
        db = SessionLocal()
        try:
            for entry in calendar:
                record = ContentCalendar(
                    scheduled_date=datetime.date.fromisoformat(entry["scheduled_date"]),
                    content_type=entry["content_type"],
                    title=entry["title"],
                    target_platform=entry.get("target_platform", "website"),
                    status=entry.get("status", "scheduled"),
                    notes=entry.get("notes", ""),
                )
                db.add(record)
            db.commit()
            logger.info("Saved {} calendar entries to database", len(calendar))
        except Exception as exc:
            db.rollback()
            logger.error("Failed to save content calendar: {}", exc)
        finally:
            db.close()

        logger.info("Content calendar created with {} entries over {} months", len(calendar), months)
        return calendar

    @staticmethod
    def _get_seasonal_content(date: datetime.date) -> Optional[dict[str, Any]]:
        """Return a seasonal content entry if *date* matches a seasonal trigger."""
        seasonal_triggers: list[dict[str, Any]] = [
            {
                "month": 1,
                "day": 15,
                "title": "New Year, New Documents: Start the Year with Proper Notarization",
                "notes": "Seasonal: New Year planning content",
            },
            {
                "month": 2,
                "day": 1,
                "title": "Tax Season Is Coming: Documents You May Need Notarized",
                "notes": "Seasonal: Tax season preparation",
            },
            {
                "month": 3,
                "day": 15,
                "title": "Spring Break Travel? Make Sure Your Documents Are Apostilled",
                "notes": "Seasonal: Spring travel preparation",
            },
            {
                "month": 5,
                "day": 1,
                "title": "Graduation Season: Getting Diplomas Apostilled for Study Abroad",
                "notes": "Seasonal: Graduation / study abroad",
            },
            {
                "month": 6,
                "day": 1,
                "title": "Wedding Season: Marriage Certificate Apostille Guide",
                "notes": "Seasonal: Summer wedding season",
            },
            {
                "month": 7,
                "day": 15,
                "title": "Military PCS Season: Notary Services for Relocating Families",
                "notes": "Seasonal: Military PCS moves",
            },
            {
                "month": 8,
                "day": 15,
                "title": "Back-to-School: Transcript Apostille for International Students",
                "notes": "Seasonal: Back-to-school",
            },
            {
                "month": 10,
                "day": 1,
                "title": "Year-End Planning: Legal Documents to Notarize Before December",
                "notes": "Seasonal: Year-end legal prep",
            },
            {
                "month": 11,
                "day": 15,
                "title": "Holiday Travel: Apostille and Notarization Deadlines to Know",
                "notes": "Seasonal: Holiday travel deadlines",
            },
        ]
        for trigger in seasonal_triggers:
            if date.month == trigger["month"] and date.day == trigger["day"]:
                return {
                    "scheduled_date": date.isoformat(),
                    "content_type": "blog",
                    "title": trigger["title"],
                    "target_platform": "website",
                    "status": "scheduled",
                    "target_area": "All Areas",
                    "notes": trigger["notes"],
                }
        return None

    # ------------------------------------------------------------------
    # 7. analyze_content_quality
    # ------------------------------------------------------------------

    def analyze_content_quality(self, content: str) -> dict[str, Any]:
        """Score content for SEO quality.

        Evaluates readability (Flesch-Kincaid), keyword density, word
        count, header structure, and internal link suggestions.

        Args:
            content: The full text content to analyze.

        Returns:
            A dictionary with ``word_count``, ``readability_grade``,
            ``reading_ease``, ``keyword_density``, ``header_analysis``,
            ``internal_links_found``, ``seo_score``, and
            ``recommendations``.
        """
        logger.debug("Analyzing content quality ({} characters)", len(content))

        words = re.findall(r"[a-zA-Z']+", content)
        word_count = len(words)

        readability_grade = _flesch_kincaid_grade(content)
        reading_ease = _flesch_reading_ease(content)

        # Keyword density for top service keywords
        lower_content = content.lower()
        keyword_density: dict[str, float] = {}
        for kw in self.service_keywords:
            occurrences = lower_content.count(kw.lower())
            density = (occurrences / max(word_count, 1)) * 100 if occurrences else 0.0
            if occurrences > 0:
                keyword_density[kw] = round(density, 3)

        # Header analysis
        headers = self._extract_headers(content)
        h1_count = sum(1 for h in headers if h["level"] == "H1")
        h2_count = sum(1 for h in headers if h["level"] == "H2")
        h3_count = sum(1 for h in headers if h["level"] == "H3")

        # Internal links (markdown-style)
        internal_links_found = len(
            re.findall(
                re.escape(self.company.get("website", "commonnotaryapostille.com")),
                content,
            )
        )

        # --- Scoring ---
        score = 0.0
        max_score = 100.0
        recommendations: list[str] = []

        # Word count (0-20 points)
        if word_count >= 1200:
            score += 20
        elif word_count >= 800:
            score += 15
        elif word_count >= 500:
            score += 10
        elif word_count >= 300:
            score += 5
        else:
            recommendations.append(
                f"Content is only {word_count} words. Aim for at least 800-1,200 words "
                "for competitive SEO."
            )

        # Readability (0-20 points) -- aim for grade level 6-10
        if 6 <= readability_grade <= 10:
            score += 20
        elif 4 <= readability_grade <= 12:
            score += 15
        else:
            score += 5
            recommendations.append(
                f"Readability grade is {readability_grade}. Aim for grade level 6-10 "
                "for a broad audience."
            )

        # Header structure (0-20 points)
        if h1_count == 1:
            score += 8
        elif h1_count == 0:
            recommendations.append("Add an H1 heading that includes your target keyword.")
        else:
            score += 3
            recommendations.append("Use only one H1 per page.")

        if h2_count >= 3:
            score += 8
        elif h2_count >= 1:
            score += 5
        else:
            recommendations.append("Add H2 sub-headings to break up the content.")

        if h3_count >= 1:
            score += 4
        else:
            recommendations.append("Consider adding H3 sub-headings for deeper structure.")

        # Keyword presence (0-20 points)
        if keyword_density:
            max_density = max(keyword_density.values())
            if 0.5 <= max_density <= 2.5:
                score += 20
            elif max_density > 0:
                score += 10
                if max_density > 2.5:
                    recommendations.append(
                        "Keyword density is high. Reduce keyword stuffing for a more "
                        "natural tone."
                    )
                else:
                    recommendations.append(
                        "Keyword density is low. Use the target keyword a few more "
                        "times naturally."
                    )
        else:
            recommendations.append(
                "No target service keywords detected. Include relevant keywords "
                "naturally in the content."
            )

        # Internal links (0-20 points)
        if internal_links_found >= 3:
            score += 20
        elif internal_links_found >= 1:
            score += 10
            recommendations.append(
                "Add more internal links to service pages (aim for 3+)."
            )
        else:
            recommendations.append(
                f"Add internal links to {self.company['website']} and relevant service "
                "pages."
            )

        seo_score = round((score / max_score) * 100, 1)

        if not recommendations:
            recommendations.append(
                "Content meets all major SEO quality benchmarks. Great work!"
            )

        result = {
            "word_count": word_count,
            "readability_grade": readability_grade,
            "reading_ease": reading_ease,
            "reading_ease_label": self._reading_ease_label(reading_ease),
            "keyword_density": keyword_density,
            "header_analysis": {
                "h1_count": h1_count,
                "h2_count": h2_count,
                "h3_count": h3_count,
                "headers": headers,
            },
            "internal_links_found": internal_links_found,
            "seo_score": seo_score,
            "recommendations": recommendations,
        }

        logger.info(
            "Content quality: {} words, grade {}, SEO score {}",
            word_count,
            readability_grade,
            seo_score,
        )
        return result

    @staticmethod
    def _reading_ease_label(score: float) -> str:
        """Return a human-readable label for a Flesch Reading Ease score."""
        if score >= 80:
            return "Easy"
        if score >= 60:
            return "Standard"
        if score >= 40:
            return "Fairly Difficult"
        if score >= 20:
            return "Difficult"
        return "Very Difficult"

    # ------------------------------------------------------------------
    # 8. get_content_gaps
    # ------------------------------------------------------------------

    def get_content_gaps(self) -> dict[str, Any]:
        """Compare existing content to competitors to find topic gaps.

        Queries the database for all published and drafted content ideas,
        then compares against the full topic template library and competitor
        analyses to identify uncovered topics.

        Returns:
            A dictionary with ``missing_topics``, ``underserved_areas``,
            ``competitor_topics_we_lack``, and ``recommendations``.
        """
        logger.info("Analyzing content gaps")

        db = SessionLocal()
        try:
            existing_records = db.query(ContentIdea).filter(
                ContentIdea.status.in_(["drafted", "reviewed", "published"])
            ).all()
            existing_titles = {r.title.lower() for r in existing_records}
            existing_areas = {r.target_area for r in existing_records if r.target_area}
        except Exception as exc:
            logger.error("Failed to query existing content: {}", exc)
            existing_titles = set()
            existing_areas = set()
        finally:
            db.close()

        # Find topics from our template library that have no matching content
        all_areas = self._get_all_areas()
        missing_topics: list[dict[str, str]] = []

        for template in TOPIC_TEMPLATES:
            if "{area}" in template["title"]:
                for area in all_areas:
                    rendered_title = template["title"].replace(
                        "{area}", self._area_label(area)
                    )
                    if rendered_title.lower() not in existing_titles:
                        missing_topics.append(
                            {
                                "title": rendered_title,
                                "content_type": template["content_type"],
                                "area": self._area_label(area),
                            }
                        )
            else:
                if template["title"].lower() not in existing_titles:
                    missing_topics.append(
                        {
                            "title": template["title"],
                            "content_type": template["content_type"],
                            "area": "All Areas",
                        }
                    )

        # Find areas with little or no content
        all_area_labels = {self._area_label(a) for a in all_areas}
        underserved_areas = sorted(all_area_labels - existing_areas)

        # Competitor topic gaps (from CompetitorAnalysis.content_gaps in DB)
        competitor_gaps: list[str] = []
        db = SessionLocal()
        try:
            from database.models import CompetitorAnalysis

            analyses = (
                db.query(CompetitorAnalysis)
                .order_by(CompetitorAnalysis.analysis_date.desc())
                .limit(10)
                .all()
            )
            for analysis in analyses:
                if analysis.content_gaps:
                    gaps = analysis.content_gaps
                    if isinstance(gaps, list):
                        competitor_gaps.extend(gaps)
                    elif isinstance(gaps, dict):
                        competitor_gaps.extend(gaps.values())
        except Exception as exc:
            logger.warning("Could not load competitor analyses: {}", exc)
        finally:
            db.close()

        competitor_gaps = list(set(competitor_gaps))

        recommendations: list[str] = []
        if underserved_areas:
            recommendations.append(
                f"Create content for underserved areas: {', '.join(underserved_areas[:5])}."
            )
        if missing_topics:
            recommendations.append(
                f"There are {len(missing_topics)} topic templates with no matching content."
            )
        if competitor_gaps:
            recommendations.append(
                f"Competitors cover {len(competitor_gaps)} topics we have not addressed."
            )

        result = {
            "missing_topics": missing_topics[:50],
            "total_missing": len(missing_topics),
            "underserved_areas": underserved_areas,
            "competitor_topics_we_lack": competitor_gaps[:20],
            "recommendations": recommendations,
        }

        logger.info(
            "Content gap analysis: {} missing topics, {} underserved areas",
            len(missing_topics),
            len(underserved_areas),
        )
        return result

    # ------------------------------------------------------------------
    # 9. suggest_content_updates
    # ------------------------------------------------------------------

    def suggest_content_updates(self) -> list[dict[str, Any]]:
        """Find existing content that could be refreshed or updated for better rankings.

        Examines all drafted/published content in the database and flags
        pieces that are old, have low SEO scores, short word counts, or
        missing meta data.

        Returns:
            A list of dictionaries, each with ``content_id``, ``title``,
            ``reasons``, and ``priority``.
        """
        logger.info("Scanning for content update opportunities")

        suggestions: list[dict[str, Any]] = []
        db = SessionLocal()
        try:
            records = (
                db.query(ContentIdea)
                .filter(ContentIdea.status.in_(["drafted", "reviewed", "published"]))
                .all()
            )

            now = datetime.datetime.utcnow()

            for record in records:
                reasons: list[str] = []
                priority = "low"

                # Age check -- content older than 6 months should be reviewed
                if record.updated_at:
                    age_days = (now - record.updated_at).days
                elif record.created_at:
                    age_days = (now - record.created_at).days
                else:
                    age_days = 0

                if age_days > 365:
                    reasons.append(
                        f"Content is over a year old ({age_days} days). "
                        "Refresh with current information."
                    )
                    priority = "high"
                elif age_days > 180:
                    reasons.append(
                        f"Content is {age_days} days old. Consider updating statistics "
                        "and adding new information."
                    )
                    if priority != "high":
                        priority = "medium"

                # SEO score check
                if record.seo_score is not None and record.seo_score < 60:
                    reasons.append(
                        f"SEO score is low ({record.seo_score}). Improve keyword usage, "
                        "headers, and internal links."
                    )
                    priority = "high"

                # Word count check
                if record.word_count is not None and record.word_count < 500:
                    reasons.append(
                        f"Word count is low ({record.word_count}). Expand content to "
                        "at least 800 words."
                    )
                    if priority != "high":
                        priority = "medium"

                # Missing meta data
                if not record.meta_title:
                    reasons.append("Missing meta title. Add an optimized title tag.")
                if not record.meta_description:
                    reasons.append("Missing meta description. Add a compelling description under 160 characters.")

                # Missing readability score
                if record.readability_score is None and record.draft_content:
                    reasons.append(
                        "No readability score. Run a content quality analysis."
                    )

                if reasons:
                    suggestions.append(
                        {
                            "content_id": record.id,
                            "title": record.title,
                            "content_type": record.content_type,
                            "current_status": record.status,
                            "reasons": reasons,
                            "priority": priority,
                        }
                    )

        except Exception as exc:
            logger.error("Failed to scan for content updates: {}", exc)
        finally:
            db.close()

        # Sort by priority
        priority_order = {"high": 0, "medium": 1, "low": 2}
        suggestions.sort(key=lambda s: priority_order.get(s["priority"], 3))

        logger.info("Found {} content pieces needing updates", len(suggestions))
        return suggestions


# ---------------------------------------------------------------------------
# __main__ block
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    logger.remove()
    logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level:<8} | {message}")

    engine = ContentStrategyEngine()

    print("=" * 72)
    print("  Content Strategy Engine - Common Notary Apostille")
    print("=" * 72)

    # 1. Blog ideas
    print("\n--- Blog Ideas (top 10) ---")
    ideas = engine.generate_blog_ideas(count=10)
    for i, idea in enumerate(ideas, 1):
        print(f"  {i}. [{idea['content_type'].upper()}] {idea['title']}")
        print(f"     Keywords: {', '.join(idea['target_keywords'][:3])}")
        print(f"     Intent: {idea['search_intent']}  |  Area: {idea['target_area']}")

    # 2. Blog draft
    print("\n--- Blog Draft (sample) ---")
    draft = engine.generate_blog_draft(
        title="How to Get an Apostille in Virginia: Step-by-Step Guide",
        target_keyword="apostille services Virginia",
        target_area="Alexandria, VA",
    )
    print(f"  Title: {draft['title']}")
    print(f"  Word count: {draft['word_count']}")
    print(f"  SEO score: {draft['seo_score']}")
    print(f"  Meta title: {draft['meta_title']}")
    print(f"  Meta desc: {draft['meta_description'][:80]}...")
    print(f"  Headers: {len(draft['headers'])} found")

    # 3. Landing page
    print("\n--- Landing Page (sample) ---")
    lp = engine.generate_landing_page_content(
        service="apostille services",
        area={"city": "Alexandria", "state": "VA", "region": "Northern Virginia"},
    )
    print(f"  Title: {lp['title']}")
    print(f"  Meta title: {lp['meta_title']}")
    print(f"  Schema type: {lp['schema_markup']['@type']}")

    # 4. FAQ page
    print("\n--- FAQ Page (sample) ---")
    faq = engine.generate_faq_page(topic="apostille", area="Alexandria, VA")
    print(f"  Title: {faq['title']}")
    print(f"  Questions: {len(faq['questions'])}")
    print(f"  Schema entities: {len(faq['schema_markup']['mainEntity'])}")

    # 5. Meta tags
    print("\n--- Meta Tags (from draft) ---")
    meta = engine.generate_meta_tags(draft["content"], "apostille services Virginia")
    print(f"  Meta title ({len(meta['meta_title'])} chars): {meta['meta_title']}")
    print(f"  Meta desc ({len(meta['meta_description'])} chars): {meta['meta_description'][:80]}...")
    print(f"  Header recommendations: {len(meta['header_recommendations'])}")
    for rec in meta["header_recommendations"]:
        print(f"    - {rec}")

    # 6. Content calendar
    print("\n--- Content Calendar (1 month preview) ---")
    calendar = engine.create_content_calendar(months=1)
    for entry in calendar[:10]:
        print(f"  {entry['scheduled_date']}  [{entry['content_type'].upper():>14}]  {entry['title'][:60]}")
    if len(calendar) > 10:
        print(f"  ... and {len(calendar) - 10} more entries")

    # 7. Content quality
    print("\n--- Content Quality Analysis ---")
    quality = engine.analyze_content_quality(draft["content"])
    print(f"  Word count: {quality['word_count']}")
    print(f"  Readability grade: {quality['readability_grade']}")
    print(f"  Reading ease: {quality['reading_ease']} ({quality['reading_ease_label']})")
    print(f"  SEO score: {quality['seo_score']}")
    print(f"  Keywords found: {len(quality['keyword_density'])}")
    print(f"  Internal links: {quality['internal_links_found']}")
    for rec in quality["recommendations"]:
        print(f"    - {rec}")

    # 8. Content gaps
    print("\n--- Content Gaps ---")
    gaps = engine.get_content_gaps()
    print(f"  Total missing topics: {gaps['total_missing']}")
    print(f"  Underserved areas: {len(gaps['underserved_areas'])}")
    if gaps["underserved_areas"]:
        print(f"    {', '.join(gaps['underserved_areas'][:5])}")
    for rec in gaps["recommendations"]:
        print(f"    - {rec}")

    # 9. Content update suggestions
    print("\n--- Content Update Suggestions ---")
    updates = engine.suggest_content_updates()
    if updates:
        for upd in updates[:5]:
            print(f"  [{upd['priority'].upper()}] {upd['title']}")
            for reason in upd["reasons"]:
                print(f"    - {reason}")
    else:
        print("  No content updates suggested at this time.")

    print("\n" + "=" * 72)
    print("  Content Strategy Engine complete.")
    print("=" * 72)
