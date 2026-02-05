"""
SEO Analyzer Module
===================

Comprehensive SEO analysis including on-page factors, technical SEO,
content analysis, and structured data validation.
"""

import re
from dataclasses import dataclass, field
from typing import Optional

import aiohttp
from bs4 import BeautifulSoup
from rich.console import Console
from rich.table import Table

console = Console()


@dataclass
class SEOIssue:
    """An SEO issue found during analysis."""
    category: str
    severity: str  # critical, high, medium, low
    title: str
    description: str
    recommendation: str


@dataclass
class SEOAnalysisResult:
    """Complete SEO analysis result."""
    url: str
    score: int = 100
    title: str = ""
    title_length: int = 0
    meta_description: str = ""
    meta_description_length: int = 0
    h1_count: int = 0
    h1_text: str = ""
    headings: dict = field(default_factory=dict)
    word_count: int = 0
    internal_links: int = 0
    external_links: int = 0
    images_total: int = 0
    images_with_alt: int = 0
    has_canonical: bool = False
    has_robots_meta: bool = False
    has_sitemap_link: bool = False
    has_schema: bool = False
    schema_types: list[str] = field(default_factory=list)
    issues: list[SEOIssue] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)


class SEOAnalyzer:
    """
    Analyze SEO factors for Common Notary Apostille website.

    Analyzes:
    - Title tags and meta descriptions
    - Heading structure
    - Content quality and keyword usage
    - Internal/external links
    - Structured data
    - Technical SEO factors
    """

    # Keywords relevant to notary and apostille services
    TARGET_KEYWORDS = [
        "apostille", "notary", "document", "authentication",
        "legalization", "certificate", "notarization", "mobile notary",
        "notary public", "attestation", "common apostille"
    ]

    def __init__(self):
        pass

    async def analyze(self, url: str) -> SEOAnalysisResult:
        """
        Perform comprehensive SEO analysis.

        Args:
            url: URL to analyze

        Returns:
            SEOAnalysisResult with all findings
        """
        result = SEOAnalysisResult(url=url)

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as response:
                    if response.status != 200:
                        result.issues.append(SEOIssue(
                            category="Technical",
                            severity="critical",
                            title="Page not accessible",
                            description=f"Page returned status {response.status}",
                            recommendation="Ensure page returns 200 status code",
                        ))
                        return result

                    html = await response.text()
                    soup = BeautifulSoup(html, "html.parser")

                    self._analyze_title(soup, result)
                    self._analyze_meta_description(soup, result)
                    self._analyze_headings(soup, result)
                    self._analyze_content(soup, result)
                    self._analyze_links(soup, url, result)
                    self._analyze_images(soup, result)
                    self._analyze_technical(soup, result)
                    self._analyze_schema(soup, result)
                    self._analyze_keywords(soup, result)

                    # Calculate score
                    self._calculate_score(result)

            except Exception as e:
                result.issues.append(SEOIssue(
                    category="Technical",
                    severity="critical",
                    title="Analysis failed",
                    description=str(e),
                    recommendation="Check URL and try again",
                ))

        return result

    def _analyze_title(self, soup: BeautifulSoup, result: SEOAnalysisResult) -> None:
        """Analyze page title."""
        title_tag = soup.find("title")

        if not title_tag or not title_tag.text.strip():
            result.issues.append(SEOIssue(
                category="Content",
                severity="critical",
                title="Missing page title",
                description="Page has no <title> tag",
                recommendation="Add unique, descriptive title (50-60 characters) with primary keyword",
            ))
            return

        result.title = title_tag.text.strip()
        result.title_length = len(result.title)

        if result.title_length < 30:
            result.issues.append(SEOIssue(
                category="Content",
                severity="medium",
                title="Title too short",
                description=f"Title is {result.title_length} characters",
                recommendation="Expand title to 50-60 characters",
            ))
        elif result.title_length > 60:
            result.issues.append(SEOIssue(
                category="Content",
                severity="low",
                title="Title may be truncated",
                description=f"Title is {result.title_length} characters",
                recommendation="Trim to under 60 characters",
            ))

        # Check for keyword in title
        title_lower = result.title.lower()
        has_keyword = any(kw in title_lower for kw in self.TARGET_KEYWORDS)
        if not has_keyword:
            result.issues.append(SEOIssue(
                category="Content",
                severity="medium",
                title="No target keyword in title",
                description="Title doesn't contain relevant keywords",
                recommendation="Include 'apostille', 'notary', or related term",
            ))

    def _analyze_meta_description(self, soup: BeautifulSoup, result: SEOAnalysisResult) -> None:
        """Analyze meta description."""
        meta_desc = soup.find("meta", attrs={"name": "description"})

        if not meta_desc or not meta_desc.get("content"):
            result.issues.append(SEOIssue(
                category="Content",
                severity="high",
                title="Missing meta description",
                description="Page has no meta description",
                recommendation="Add compelling description (150-160 characters)",
            ))
            return

        result.meta_description = meta_desc.get("content", "")
        result.meta_description_length = len(result.meta_description)

        if result.meta_description_length < 70:
            result.issues.append(SEOIssue(
                category="Content",
                severity="medium",
                title="Meta description too short",
                description=f"Description is {result.meta_description_length} characters",
                recommendation="Expand to 150-160 characters",
            ))
        elif result.meta_description_length > 160:
            result.issues.append(SEOIssue(
                category="Content",
                severity="low",
                title="Meta description may be truncated",
                description=f"Description is {result.meta_description_length} characters",
                recommendation="Trim to under 160 characters",
            ))

    def _analyze_headings(self, soup: BeautifulSoup, result: SEOAnalysisResult) -> None:
        """Analyze heading structure."""
        for i in range(1, 7):
            headings = soup.find_all(f"h{i}")
            result.headings[f"h{i}"] = len(headings)

        # H1 analysis
        h1_tags = soup.find_all("h1")
        result.h1_count = len(h1_tags)

        if result.h1_count == 0:
            result.issues.append(SEOIssue(
                category="Content",
                severity="high",
                title="Missing H1 heading",
                description="Page has no H1 tag",
                recommendation="Add one H1 with primary keyword",
            ))
        elif result.h1_count > 1:
            result.issues.append(SEOIssue(
                category="Content",
                severity="medium",
                title="Multiple H1 headings",
                description=f"Page has {result.h1_count} H1 tags",
                recommendation="Use only one H1 per page",
            ))
        else:
            result.h1_text = h1_tags[0].text.strip()

        # Check heading hierarchy
        if result.headings.get("h3", 0) > 0 and result.headings.get("h2", 0) == 0:
            result.issues.append(SEOIssue(
                category="Content",
                severity="low",
                title="Skipped heading level",
                description="H3 used without H2",
                recommendation="Maintain proper heading hierarchy",
            ))

    def _analyze_content(self, soup: BeautifulSoup, result: SEOAnalysisResult) -> None:
        """Analyze page content."""
        # Remove script and style elements
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()

        text = soup.get_text(separator=" ")
        words = text.split()
        result.word_count = len(words)

        if result.word_count < 300:
            result.issues.append(SEOIssue(
                category="Content",
                severity="medium",
                title="Thin content",
                description=f"Page has only {result.word_count} words",
                recommendation="Add more valuable content (aim for 500+ words)",
            ))

    def _analyze_links(self, soup: BeautifulSoup, base_url: str, result: SEOAnalysisResult) -> None:
        """Analyze internal and external links."""
        from urllib.parse import urlparse

        base_domain = urlparse(base_url).netloc

        for anchor in soup.find_all("a", href=True):
            href = anchor.get("href", "")

            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue

            parsed = urlparse(href)

            if not parsed.netloc or parsed.netloc == base_domain:
                result.internal_links += 1
            else:
                result.external_links += 1

                # Check for nofollow on external links
                rel = anchor.get("rel", [])
                if "nofollow" not in rel and "sponsored" not in rel:
                    # Could add warning about external links without nofollow
                    pass

        if result.internal_links < 3:
            result.issues.append(SEOIssue(
                category="Links",
                severity="medium",
                title="Few internal links",
                description=f"Only {result.internal_links} internal link(s)",
                recommendation="Add more internal links to improve navigation",
            ))

    def _analyze_images(self, soup: BeautifulSoup, result: SEOAnalysisResult) -> None:
        """Analyze images for SEO."""
        images = soup.find_all("img")
        result.images_total = len(images)

        for img in images:
            alt = img.get("alt", "").strip()
            if alt:
                result.images_with_alt += 1

        if result.images_total > 0:
            missing_alt = result.images_total - result.images_with_alt
            if missing_alt > 0:
                result.issues.append(SEOIssue(
                    category="Images",
                    severity="high" if missing_alt > result.images_total / 2 else "medium",
                    title="Images missing alt text",
                    description=f"{missing_alt} of {result.images_total} images lack alt text",
                    recommendation="Add descriptive alt text with keywords where appropriate",
                ))

    def _analyze_technical(self, soup: BeautifulSoup, result: SEOAnalysisResult) -> None:
        """Analyze technical SEO factors."""
        # Canonical URL
        canonical = soup.find("link", attrs={"rel": "canonical"})
        result.has_canonical = canonical is not None

        if not result.has_canonical:
            result.issues.append(SEOIssue(
                category="Technical",
                severity="medium",
                title="Missing canonical URL",
                description="No canonical link tag found",
                recommendation="Add canonical URL to prevent duplicate content",
            ))

        # Robots meta
        robots = soup.find("meta", attrs={"name": "robots"})
        result.has_robots_meta = robots is not None

        if robots:
            content = robots.get("content", "").lower()
            if "noindex" in content:
                result.issues.append(SEOIssue(
                    category="Technical",
                    severity="critical",
                    title="Page set to noindex",
                    description="Robots meta contains noindex",
                    recommendation="Remove noindex if page should be indexed",
                ))

        # Language
        html_tag = soup.find("html")
        if html_tag and not html_tag.get("lang"):
            result.issues.append(SEOIssue(
                category="Technical",
                severity="medium",
                title="Missing language attribute",
                description="HTML tag lacks lang attribute",
                recommendation="Add lang=\"en\" or appropriate language",
            ))

        # Open Graph
        og_title = soup.find("meta", attrs={"property": "og:title"})
        og_desc = soup.find("meta", attrs={"property": "og:description"})

        if not og_title or not og_desc:
            result.issues.append(SEOIssue(
                category="Social",
                severity="low",
                title="Missing Open Graph tags",
                description="Open Graph meta tags not fully implemented",
                recommendation="Add og:title, og:description, og:image for social sharing",
            ))

    def _analyze_schema(self, soup: BeautifulSoup, result: SEOAnalysisResult) -> None:
        """Analyze structured data / schema markup."""
        # Check for JSON-LD schema
        scripts = soup.find_all("script", attrs={"type": "application/ld+json"})

        if scripts:
            result.has_schema = True
            import json
            for script in scripts:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict):
                        schema_type = data.get("@type", "Unknown")
                        result.schema_types.append(schema_type)
                except Exception:
                    pass
        else:
            result.issues.append(SEOIssue(
                category="Technical",
                severity="medium",
                title="No structured data",
                description="Page has no JSON-LD schema markup",
                recommendation="Add LocalBusiness or Organization schema for notary services",
            ))

        # Recommend specific schemas for notary business
        if result.has_schema:
            recommended = ["LocalBusiness", "Organization", "Service"]
            missing = [s for s in recommended if s not in result.schema_types]
            if missing:
                result.issues.append(SEOIssue(
                    category="Technical",
                    severity="low",
                    title="Missing recommended schema types",
                    description=f"Consider adding: {', '.join(missing)}",
                    recommendation="Add LocalBusiness schema with service details",
                ))

    def _analyze_keywords(self, soup: BeautifulSoup, result: SEOAnalysisResult) -> None:
        """Analyze keyword usage."""
        text = soup.get_text().lower()

        # Count keyword occurrences
        keyword_counts = {}
        for keyword in self.TARGET_KEYWORDS:
            count = text.count(keyword.lower())
            if count > 0:
                keyword_counts[keyword] = count

        result.keywords = list(keyword_counts.keys())

        if not result.keywords:
            result.issues.append(SEOIssue(
                category="Content",
                severity="high",
                title="No target keywords found",
                description="Page doesn't contain relevant keywords",
                recommendation="Include 'apostille', 'notary', and related terms naturally",
            ))

    def _calculate_score(self, result: SEOAnalysisResult) -> None:
        """Calculate overall SEO score."""
        score = 100

        for issue in result.issues:
            penalty = {
                "critical": 25,
                "high": 15,
                "medium": 8,
                "low": 3,
            }.get(issue.severity, 0)
            score -= penalty

        result.score = max(0, min(100, score))

    def print_report(self, result: SEOAnalysisResult) -> None:
        """Print formatted SEO report."""
        console.print("\n[bold]SEO Analysis Report[/bold]")
        console.print("=" * 60)
        console.print(f"URL: {result.url}")
        console.print(f"Score: {result.score}/100")

        # Summary table
        table = Table(title="SEO Factors")
        table.add_column("Factor", style="cyan")
        table.add_column("Value")
        table.add_column("Status")

        def status(ok: bool) -> str:
            return "[green]OK[/green]" if ok else "[red]Issue[/red]"

        table.add_row("Title", result.title[:40] + "..." if len(result.title) > 40 else result.title,
                     status(30 <= result.title_length <= 60))
        table.add_row("Meta Description", f"{result.meta_description_length} chars",
                     status(70 <= result.meta_description_length <= 160))
        table.add_row("H1 Tags", str(result.h1_count), status(result.h1_count == 1))
        table.add_row("Word Count", str(result.word_count), status(result.word_count >= 300))
        table.add_row("Internal Links", str(result.internal_links), status(result.internal_links >= 3))
        table.add_row("Images with Alt", f"{result.images_with_alt}/{result.images_total}",
                     status(result.images_with_alt == result.images_total))
        table.add_row("Canonical URL", str(result.has_canonical), status(result.has_canonical))
        table.add_row("Structured Data", str(result.has_schema), status(result.has_schema))

        console.print(table)

        # Issues
        if result.issues:
            console.print("\n[bold]Issues Found:[/bold]")
            for issue in result.issues:
                color = {"critical": "red", "high": "orange1", "medium": "yellow", "low": "blue"}[issue.severity]
                console.print(f"\n  [{color}][{issue.severity.upper()}][/{color}] {issue.title}")
                console.print(f"    {issue.description}")
                console.print(f"    [dim]Fix: {issue.recommendation}[/dim]")
