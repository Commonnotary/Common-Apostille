"""Personalization service for extracting relevant snippets from firm websites."""

import re
from typing import Optional, Tuple, List
from urllib.parse import urlparse
import logging

import httpx
from bs4 import BeautifulSoup

from ..config import get_settings, PRACTICE_AREA_KEYWORDS
from ..models.lead import Lead
from ..utils.rate_limiter import get_rate_limiter
from ..utils.robots_checker import get_robots_checker

logger = logging.getLogger(__name__)


class Personalizer:
    """
    Service for generating personalized outreach snippets.

    Extracts factual information from firm websites to create
    personalized, credible opening lines. Never invents or hallucinates
    information - always cites the source text.
    """

    # Keywords that indicate relevant content for personalization
    RELEVANCE_KEYWORDS = [
        # Practice areas
        'estate planning', 'estate plan', 'trusts', 'trust', 'wills', 'will',
        'power of attorney', 'poa', 'probate', 'estate administration',
        'elder law', 'medicaid', 'guardianship', 'conservatorship',
        'family law', 'adoption', 'prenuptial',
        # Client focus
        'families', 'family', 'seniors', 'elderly', 'individuals',
        'business owners', 'entrepreneurs', 'high-net-worth',
        # Service style
        'personalized', 'client-focused', 'compassionate', 'experienced',
        'mobile', 'flexible', 'convenient', 'in-home', 'house calls'
    ]

    # Minimum snippet length (too short = not useful)
    MIN_SNIPPET_LENGTH = 20
    # Maximum snippet length (too long = overwhelming)
    MAX_SNIPPET_LENGTH = 200

    def __init__(self):
        self.settings = get_settings()
        self.rate_limiter = get_rate_limiter()
        self.robots_checker = get_robots_checker()

    def _fetch_page(self, url: str) -> Optional[str]:
        """Fetch a webpage with rate limiting and robots.txt compliance."""
        if not self.robots_checker.can_fetch_sync(url):
            logger.warning(f"robots.txt disallows: {url}")
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
                    }
                )
                response.raise_for_status()
                return response.text
        except Exception as e:
            logger.warning(f"Error fetching {url}: {e}")
            return None

    def _extract_text_blocks(self, html: str) -> List[Tuple[str, str]]:
        """
        Extract text blocks from HTML with their source context.

        Returns list of (text, source_context) tuples.
        """
        soup = BeautifulSoup(html, 'lxml')

        # Remove script, style, nav, footer elements
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            tag.decompose()

        blocks = []

        # Extract from specific content areas
        content_selectors = [
            'main',
            'article',
            '[class*="content"]',
            '[class*="about"]',
            '[class*="services"]',
            '[class*="practice"]',
            '[id*="content"]',
            '[id*="about"]',
        ]

        for selector in content_selectors:
            for element in soup.select(selector):
                text = element.get_text(separator=' ', strip=True)
                if text and len(text) > 50:
                    blocks.append((text, f"from {selector} section"))

        # Also get paragraph text
        for p in soup.find_all('p'):
            text = p.get_text(strip=True)
            if text and len(text) > 30:
                # Try to get context from parent
                parent = p.parent
                context = "paragraph"
                if parent and parent.name:
                    parent_class = parent.get('class', [])
                    if parent_class:
                        context = f"paragraph in {parent_class[0]}"
                blocks.append((text, context))

        # Get list items that might describe services
        for li in soup.find_all('li'):
            text = li.get_text(strip=True)
            if text and len(text) > 20:
                blocks.append((text, "list item"))

        return blocks

    def _score_text_relevance(self, text: str) -> Tuple[float, List[str]]:
        """
        Score how relevant a text block is for personalization.

        Returns (score, matched_keywords)
        """
        text_lower = text.lower()
        matched = []

        for keyword in self.RELEVANCE_KEYWORDS:
            if keyword in text_lower:
                matched.append(keyword)

        # Score based on keyword density and count
        if not matched:
            return 0.0, []

        score = min(1.0, len(matched) * 0.15)

        # Bonus for practice area keywords
        for area_keywords in PRACTICE_AREA_KEYWORDS.values():
            for kw in area_keywords:
                if kw.lower() in text_lower and kw.lower() not in matched:
                    score += 0.1
                    matched.append(kw)

        return min(1.0, score), matched

    def _extract_best_snippet(self, text: str, keywords: List[str]) -> str:
        """
        Extract the most relevant snippet from a text block.

        Tries to find a sentence containing the matched keywords.
        """
        # Split into sentences
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return text[:self.MAX_SNIPPET_LENGTH]

        # Score each sentence
        best_sentence = None
        best_score = 0

        for sentence in sentences:
            if len(sentence) < self.MIN_SNIPPET_LENGTH:
                continue

            sentence_lower = sentence.lower()
            score = sum(1 for kw in keywords if kw.lower() in sentence_lower)

            # Prefer sentences with "we" or "our" (about the firm)
            if ' we ' in sentence_lower or 'our ' in sentence_lower:
                score += 0.5

            # Prefer medium-length sentences
            if 50 <= len(sentence) <= 150:
                score += 0.3

            if score > best_score:
                best_score = score
                best_sentence = sentence

        if best_sentence:
            # Clean up the sentence
            snippet = best_sentence.strip()
            if len(snippet) > self.MAX_SNIPPET_LENGTH:
                # Truncate at word boundary
                snippet = snippet[:self.MAX_SNIPPET_LENGTH].rsplit(' ', 1)[0] + '...'
            return snippet

        # Fallback: use first relevant sentence
        for sentence in sentences:
            if len(sentence) >= self.MIN_SNIPPET_LENGTH:
                snippet = sentence[:self.MAX_SNIPPET_LENGTH]
                if len(sentence) > self.MAX_SNIPPET_LENGTH:
                    snippet = snippet.rsplit(' ', 1)[0] + '...'
                return snippet

        return text[:self.MAX_SNIPPET_LENGTH]

    def extract_personalization(
        self,
        lead: Lead,
        force_refresh: bool = False
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Extract a personalization snippet for a lead from their website.

        Returns:
            Tuple of (snippet, source_url, source_text)
            - snippet: The personalized opening line
            - source_url: URL where the info was found
            - source_text: Original text used (for verification)

        Returns (None, None, None) if no good snippet found.
        """
        # Skip if already personalized (unless force refresh)
        if not force_refresh and lead.personalization_snippet:
            return (
                lead.personalization_snippet,
                lead.snippet_source_url,
                lead.snippet_source_text
            )

        # Need a website to scrape
        if not lead.firm_website:
            logger.debug(f"No website for {lead.display_name}, skipping personalization")
            return None, None, None

        # Fetch the website
        html = self._fetch_page(lead.firm_website)
        if not html:
            return None, None, None

        # Extract text blocks
        blocks = self._extract_text_blocks(html)
        if not blocks:
            logger.debug(f"No text blocks found for {lead.display_name}")
            return None, None, None

        # Score and rank blocks
        scored_blocks = []
        for text, context in blocks:
            score, keywords = self._score_text_relevance(text)
            if score > 0:
                scored_blocks.append((score, text, context, keywords))

        if not scored_blocks:
            logger.debug(f"No relevant content found for {lead.display_name}")
            return None, None, None

        # Sort by score descending
        scored_blocks.sort(key=lambda x: x[0], reverse=True)

        # Use the best block
        best_score, best_text, best_context, best_keywords = scored_blocks[0]

        # Extract a snippet
        source_text = best_text[:500]  # Keep more of original for reference
        snippet_raw = self._extract_best_snippet(best_text, best_keywords)

        # Format as a personalization line
        snippet = self._format_snippet(snippet_raw, lead)

        logger.info(
            f"Generated personalization for {lead.display_name}: "
            f"score={best_score:.2f}, keywords={best_keywords[:3]}"
        )

        return snippet, lead.firm_website, source_text

    def _format_snippet(self, raw_snippet: str, lead: Lead) -> str:
        """
        Format a raw snippet into a personalization line.

        Creates natural-sounding references like:
        "I noticed your firm helps families with estate planning and trusts"
        """
        # Clean up the snippet
        snippet = raw_snippet.strip()

        # Remove leading "We" if present to rephrase
        if snippet.lower().startswith('we '):
            snippet = snippet[3:]
        elif snippet.lower().startswith('our '):
            snippet = 'your ' + snippet[4:]

        # Detect what the snippet is about
        snippet_lower = snippet.lower()

        if any(kw in snippet_lower for kw in ['estate planning', 'trusts', 'wills', 'poa', 'power of attorney']):
            prefix = "I noticed your firm helps clients with"
        elif any(kw in snippet_lower for kw in ['elder law', 'medicaid', 'senior', 'elderly']):
            prefix = "I saw that you focus on"
        elif any(kw in snippet_lower for kw in ['probate', 'estate administration']):
            prefix = "I see your firm handles"
        elif any(kw in snippet_lower for kw in ['family', 'families']):
            prefix = "I noticed you work with families on"
        else:
            prefix = "I saw on your website that"

        # Combine and clean up
        personalized = f"{prefix} {snippet}"

        # Ensure it ends properly
        if not personalized.endswith(('.', '!', '?')):
            personalized = personalized.rstrip(',;:') + '.'

        # Limit length
        if len(personalized) > 250:
            personalized = personalized[:247].rsplit(' ', 1)[0] + '...'

        return personalized

    def personalize_lead(self, lead: Lead, force_refresh: bool = False) -> Lead:
        """
        Add personalization to a lead.

        Modifies the lead in place and returns it.
        """
        snippet, source_url, source_text = self.extract_personalization(
            lead, force_refresh=force_refresh
        )

        if snippet:
            lead.personalization_snippet = snippet
            lead.snippet_source_url = source_url
            lead.snippet_source_text = source_text

        return lead

    def personalize_leads(
        self,
        leads: List[Lead],
        force_refresh: bool = False
    ) -> List[Lead]:
        """Personalize multiple leads."""
        for lead in leads:
            self.personalize_lead(lead, force_refresh=force_refresh)
        return leads

    def generate_fallback_snippet(self, lead: Lead) -> str:
        """
        Generate a generic but relevant snippet when website scraping fails.

        Uses available lead data (practice areas, city, etc.) to create
        a reasonable opener without making claims about the firm.
        """
        parts = []

        # Use practice areas if available
        if lead.practice_areas:
            areas = lead.practice_areas_list[:2]  # First two
            if areas:
                areas_text = ' and '.join(areas).lower()
                parts.append(f"Given your work in {areas_text}")

        # Use location
        if lead.city:
            if lead.region:
                from ..config import REGIONS
                region_name = REGIONS.get(lead.region.value, {}).get('name', lead.city)
                parts.append(f"serving clients in {region_name}")

        if parts:
            return ', '.join(parts) + ', I wanted to reach out.'

        # Ultimate fallback - very generic
        return "I wanted to introduce myself and our notary services."
