"""
Website Auditor Module
======================

Comprehensive website analysis for performance, SEO, accessibility,
security, and user experience. Provides actionable recommendations.
"""

import asyncio
import re
import json
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum

import aiohttp
from bs4 import BeautifulSoup
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress

console = Console()


class AuditCategory(Enum):
    """Categories of website audit."""
    PERFORMANCE = "performance"
    SEO = "seo"
    ACCESSIBILITY = "accessibility"
    SECURITY = "security"
    BEST_PRACTICES = "best_practices"
    USER_EXPERIENCE = "user_experience"


class IssueSeverity(Enum):
    """Severity levels for audit issues."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class AuditIssue:
    """A single audit finding."""
    category: AuditCategory
    severity: IssueSeverity
    title: str
    description: str
    recommendation: str
    url: str = ""
    element: str = ""
    impact: str = ""


@dataclass
class PageAudit:
    """Audit results for a single page."""
    url: str
    status_code: int
    load_time: float
    page_size: int
    issues: list[AuditIssue] = field(default_factory=list)
    meta_data: dict = field(default_factory=dict)
    links: list[str] = field(default_factory=list)
    images: list[dict] = field(default_factory=list)
    scripts: list[str] = field(default_factory=list)
    stylesheets: list[str] = field(default_factory=list)


@dataclass
class WebsiteAuditResult:
    """Complete website audit result."""
    base_url: str
    pages_audited: int = 0
    total_issues: int = 0
    critical_issues: int = 0
    high_issues: int = 0
    medium_issues: int = 0
    low_issues: int = 0
    scores: dict = field(default_factory=dict)
    pages: list[PageAudit] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    audited_at: datetime = field(default_factory=datetime.now)

    @property
    def overall_score(self) -> float:
        """Calculate overall score."""
        if not self.scores:
            return 0.0
        return sum(self.scores.values()) / len(self.scores)


class WebsiteAuditor:
    """
    Comprehensive website auditor for Common Notary Apostille.

    Analyzes:
    - Page performance and load times
    - SEO factors (meta tags, headings, content)
    - Accessibility compliance
    - Security headers and best practices
    - Mobile responsiveness
    - User experience factors
    """

    DEFAULT_HEADERS = {
        "User-Agent": "CommonApostilleBot/1.0 (Website Auditor)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    def __init__(
        self,
        base_url: str,
        max_pages: int = 50,
        timeout: int = 30,
        follow_external: bool = False
    ):
        self.base_url = base_url.rstrip("/")
        self.max_pages = max_pages
        self.timeout = timeout
        self.follow_external = follow_external
        self.visited_urls: set[str] = set()
        self.result = WebsiteAuditResult(base_url=base_url)

    async def audit(self, urls: Optional[list[str]] = None) -> WebsiteAuditResult:
        """
        Run comprehensive website audit.

        Args:
            urls: Specific URLs to audit (uses base_url if not provided)

        Returns:
            WebsiteAuditResult with all findings
        """
        console.print(f"[bold blue]Starting Website Audit: {self.base_url}[/bold blue]")

        urls_to_audit = urls or [self.base_url]

        async with aiohttp.ClientSession(
            headers=self.DEFAULT_HEADERS,
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        ) as session:
            with Progress() as progress:
                task = progress.add_task("[cyan]Auditing pages...", total=len(urls_to_audit))

                for url in urls_to_audit:
                    if len(self.visited_urls) >= self.max_pages:
                        break

                    if url not in self.visited_urls:
                        page_audit = await self._audit_page(session, url)
                        if page_audit:
                            self.result.pages.append(page_audit)
                            self.visited_urls.add(url)

                            # Discover more pages to audit
                            new_urls = [
                                link for link in page_audit.links
                                if link not in self.visited_urls
                                and self._is_internal_url(link)
                            ]
                            urls_to_audit.extend(new_urls[:10])

                    progress.update(task, advance=1)

        self._calculate_scores()
        self._generate_recommendations()
        self._count_issues()

        return self.result

    async def _audit_page(self, session: aiohttp.ClientSession, url: str) -> Optional[PageAudit]:
        """Audit a single page."""
        try:
            start_time = asyncio.get_event_loop().time()

            async with session.get(url) as response:
                load_time = asyncio.get_event_loop().time() - start_time
                content = await response.text()
                page_size = len(content.encode("utf-8"))

                page_audit = PageAudit(
                    url=url,
                    status_code=response.status,
                    load_time=load_time,
                    page_size=page_size,
                )

                if response.status == 200:
                    soup = BeautifulSoup(content, "html.parser")

                    # Extract page data
                    self._extract_meta_data(soup, page_audit)
                    self._extract_links(soup, url, page_audit)
                    self._extract_images(soup, page_audit)
                    self._extract_resources(soup, page_audit)

                    # Run audits
                    self._audit_performance(page_audit, response)
                    self._audit_seo(soup, page_audit)
                    self._audit_accessibility(soup, page_audit)
                    self._audit_security(response, page_audit)
                    self._audit_best_practices(soup, page_audit)

                return page_audit

        except asyncio.TimeoutError:
            console.print(f"[yellow]Timeout: {url}[/yellow]")
        except Exception as e:
            console.print(f"[red]Error auditing {url}: {e}[/red]")

        return None

    def _is_internal_url(self, url: str) -> bool:
        """Check if URL is internal to the website."""
        parsed = urlparse(url)
        base_parsed = urlparse(self.base_url)
        return parsed.netloc == base_parsed.netloc or not parsed.netloc

    def _extract_meta_data(self, soup: BeautifulSoup, page_audit: PageAudit) -> None:
        """Extract meta information from page."""
        # Title
        title_tag = soup.find("title")
        page_audit.meta_data["title"] = title_tag.text.strip() if title_tag else ""

        # Meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        page_audit.meta_data["description"] = meta_desc.get("content", "") if meta_desc else ""

        # Meta keywords
        meta_keywords = soup.find("meta", attrs={"name": "keywords"})
        page_audit.meta_data["keywords"] = meta_keywords.get("content", "") if meta_keywords else ""

        # Canonical URL
        canonical = soup.find("link", attrs={"rel": "canonical"})
        page_audit.meta_data["canonical"] = canonical.get("href", "") if canonical else ""

        # Open Graph
        og_tags = soup.find_all("meta", attrs={"property": re.compile(r"^og:")})
        page_audit.meta_data["og"] = {
            tag.get("property"): tag.get("content") for tag in og_tags
        }

        # Headings structure
        page_audit.meta_data["headings"] = {
            f"h{i}": len(soup.find_all(f"h{i}")) for i in range(1, 7)
        }

    def _extract_links(self, soup: BeautifulSoup, base_url: str, page_audit: PageAudit) -> None:
        """Extract all links from page."""
        links = []
        for anchor in soup.find_all("a", href=True):
            href = anchor.get("href", "")
            if href and not href.startswith(("#", "javascript:", "mailto:", "tel:")):
                full_url = urljoin(base_url, href)
                links.append(full_url)

        page_audit.links = list(set(links))

    def _extract_images(self, soup: BeautifulSoup, page_audit: PageAudit) -> None:
        """Extract image information."""
        for img in soup.find_all("img"):
            page_audit.images.append({
                "src": img.get("src", ""),
                "alt": img.get("alt", ""),
                "width": img.get("width"),
                "height": img.get("height"),
                "loading": img.get("loading"),
            })

    def _extract_resources(self, soup: BeautifulSoup, page_audit: PageAudit) -> None:
        """Extract scripts and stylesheets."""
        for script in soup.find_all("script", src=True):
            page_audit.scripts.append(script.get("src", ""))

        for link in soup.find_all("link", rel="stylesheet"):
            page_audit.stylesheets.append(link.get("href", ""))

    def _audit_performance(self, page_audit: PageAudit, response: aiohttp.ClientResponse) -> None:
        """Audit page performance."""
        # Load time check
        if page_audit.load_time > 3.0:
            page_audit.issues.append(AuditIssue(
                category=AuditCategory.PERFORMANCE,
                severity=IssueSeverity.HIGH,
                title="Slow page load time",
                description=f"Page took {page_audit.load_time:.2f}s to load",
                recommendation="Optimize server response time, enable caching, and minimize resources",
                url=page_audit.url,
                impact="Poor user experience and potential SEO penalty",
            ))
        elif page_audit.load_time > 1.5:
            page_audit.issues.append(AuditIssue(
                category=AuditCategory.PERFORMANCE,
                severity=IssueSeverity.MEDIUM,
                title="Moderate page load time",
                description=f"Page took {page_audit.load_time:.2f}s to load",
                recommendation="Consider optimizing images and enabling compression",
                url=page_audit.url,
            ))

        # Page size check
        if page_audit.page_size > 3_000_000:  # 3MB
            page_audit.issues.append(AuditIssue(
                category=AuditCategory.PERFORMANCE,
                severity=IssueSeverity.HIGH,
                title="Large page size",
                description=f"Page size is {page_audit.page_size / 1_000_000:.2f}MB",
                recommendation="Compress images, minify CSS/JS, and remove unused code",
                url=page_audit.url,
            ))

        # Too many scripts
        if len(page_audit.scripts) > 15:
            page_audit.issues.append(AuditIssue(
                category=AuditCategory.PERFORMANCE,
                severity=IssueSeverity.MEDIUM,
                title="Too many JavaScript files",
                description=f"Page loads {len(page_audit.scripts)} scripts",
                recommendation="Bundle scripts and use code splitting",
                url=page_audit.url,
            ))

    def _audit_seo(self, soup: BeautifulSoup, page_audit: PageAudit) -> None:
        """Audit SEO factors."""
        meta = page_audit.meta_data

        # Title checks
        if not meta.get("title"):
            page_audit.issues.append(AuditIssue(
                category=AuditCategory.SEO,
                severity=IssueSeverity.CRITICAL,
                title="Missing page title",
                description="Page has no <title> tag",
                recommendation="Add a unique, descriptive title (50-60 characters)",
                url=page_audit.url,
                impact="Major SEO impact - title is crucial for rankings",
            ))
        elif len(meta.get("title", "")) < 30:
            page_audit.issues.append(AuditIssue(
                category=AuditCategory.SEO,
                severity=IssueSeverity.MEDIUM,
                title="Title too short",
                description=f"Title is only {len(meta['title'])} characters",
                recommendation="Expand title to 50-60 characters with relevant keywords",
                url=page_audit.url,
            ))
        elif len(meta.get("title", "")) > 60:
            page_audit.issues.append(AuditIssue(
                category=AuditCategory.SEO,
                severity=IssueSeverity.LOW,
                title="Title too long",
                description=f"Title is {len(meta['title'])} characters (may be truncated)",
                recommendation="Keep title under 60 characters",
                url=page_audit.url,
            ))

        # Meta description
        if not meta.get("description"):
            page_audit.issues.append(AuditIssue(
                category=AuditCategory.SEO,
                severity=IssueSeverity.HIGH,
                title="Missing meta description",
                description="Page has no meta description",
                recommendation="Add a compelling meta description (150-160 characters)",
                url=page_audit.url,
            ))
        elif len(meta.get("description", "")) < 70:
            page_audit.issues.append(AuditIssue(
                category=AuditCategory.SEO,
                severity=IssueSeverity.MEDIUM,
                title="Meta description too short",
                description=f"Description is only {len(meta['description'])} characters",
                recommendation="Expand to 150-160 characters",
                url=page_audit.url,
            ))

        # Heading structure
        headings = meta.get("headings", {})
        if headings.get("h1", 0) == 0:
            page_audit.issues.append(AuditIssue(
                category=AuditCategory.SEO,
                severity=IssueSeverity.HIGH,
                title="Missing H1 heading",
                description="Page has no H1 heading",
                recommendation="Add exactly one H1 heading with primary keyword",
                url=page_audit.url,
            ))
        elif headings.get("h1", 0) > 1:
            page_audit.issues.append(AuditIssue(
                category=AuditCategory.SEO,
                severity=IssueSeverity.MEDIUM,
                title="Multiple H1 headings",
                description=f"Page has {headings['h1']} H1 headings",
                recommendation="Use only one H1 per page",
                url=page_audit.url,
            ))

        # Canonical URL
        if not meta.get("canonical"):
            page_audit.issues.append(AuditIssue(
                category=AuditCategory.SEO,
                severity=IssueSeverity.MEDIUM,
                title="Missing canonical URL",
                description="No canonical link defined",
                recommendation="Add canonical link to prevent duplicate content issues",
                url=page_audit.url,
            ))

    def _audit_accessibility(self, soup: BeautifulSoup, page_audit: PageAudit) -> None:
        """Audit accessibility compliance."""
        # Check for lang attribute
        html_tag = soup.find("html")
        if html_tag and not html_tag.get("lang"):
            page_audit.issues.append(AuditIssue(
                category=AuditCategory.ACCESSIBILITY,
                severity=IssueSeverity.HIGH,
                title="Missing language attribute",
                description="HTML tag missing lang attribute",
                recommendation='Add lang="en" or appropriate language code',
                url=page_audit.url,
            ))

        # Check images for alt text
        images_without_alt = [img for img in page_audit.images if not img.get("alt")]
        if images_without_alt:
            page_audit.issues.append(AuditIssue(
                category=AuditCategory.ACCESSIBILITY,
                severity=IssueSeverity.HIGH,
                title="Images missing alt text",
                description=f"{len(images_without_alt)} image(s) missing alt attribute",
                recommendation="Add descriptive alt text to all images",
                url=page_audit.url,
                impact="Screen readers cannot describe images to visually impaired users",
            ))

        # Check for form labels
        inputs = soup.find_all("input", type=lambda t: t not in ["hidden", "submit", "button"])
        inputs_without_labels = []
        for input_elem in inputs:
            input_id = input_elem.get("id")
            has_label = (
                input_elem.get("aria-label") or
                input_elem.get("aria-labelledby") or
                (input_id and soup.find("label", {"for": input_id}))
            )
            if not has_label:
                inputs_without_labels.append(input_elem)

        if inputs_without_labels:
            page_audit.issues.append(AuditIssue(
                category=AuditCategory.ACCESSIBILITY,
                severity=IssueSeverity.HIGH,
                title="Form inputs missing labels",
                description=f"{len(inputs_without_labels)} input(s) without proper labels",
                recommendation="Add <label> elements or aria-label attributes",
                url=page_audit.url,
            ))

        # Check for skip links
        skip_link = soup.find("a", href="#main") or soup.find("a", {"class": re.compile(r"skip")})
        if not skip_link:
            page_audit.issues.append(AuditIssue(
                category=AuditCategory.ACCESSIBILITY,
                severity=IssueSeverity.LOW,
                title="Missing skip navigation link",
                description="No skip-to-main-content link found",
                recommendation="Add skip link for keyboard users",
                url=page_audit.url,
            ))

        # Check color contrast (basic check for inline styles)
        low_contrast = soup.find_all(style=re.compile(r"color:\s*#[a-fA-F0-9]{3,6}"))
        if low_contrast:
            page_audit.issues.append(AuditIssue(
                category=AuditCategory.ACCESSIBILITY,
                severity=IssueSeverity.INFO,
                title="Review color contrast",
                description="Inline color styles found - verify contrast ratios",
                recommendation="Ensure 4.5:1 contrast ratio for normal text, 3:1 for large text",
                url=page_audit.url,
            ))

    def _audit_security(self, response: aiohttp.ClientResponse, page_audit: PageAudit) -> None:
        """Audit security headers and practices."""
        headers = response.headers

        # HTTPS check
        if not page_audit.url.startswith("https://"):
            page_audit.issues.append(AuditIssue(
                category=AuditCategory.SECURITY,
                severity=IssueSeverity.CRITICAL,
                title="Not using HTTPS",
                description="Page is served over HTTP",
                recommendation="Enable HTTPS for all pages",
                url=page_audit.url,
                impact="Data transmitted insecurely, SEO penalty",
            ))

        # Security headers
        security_headers = {
            "Strict-Transport-Security": (IssueSeverity.HIGH, "Enable HSTS to force HTTPS"),
            "Content-Security-Policy": (IssueSeverity.MEDIUM, "Add CSP to prevent XSS attacks"),
            "X-Content-Type-Options": (IssueSeverity.MEDIUM, "Add 'nosniff' to prevent MIME type sniffing"),
            "X-Frame-Options": (IssueSeverity.MEDIUM, "Prevent clickjacking with frame options"),
            "X-XSS-Protection": (IssueSeverity.LOW, "Enable browser XSS protection"),
        }

        for header, (severity, recommendation) in security_headers.items():
            if header not in headers:
                page_audit.issues.append(AuditIssue(
                    category=AuditCategory.SECURITY,
                    severity=severity,
                    title=f"Missing {header} header",
                    description=f"Security header {header} not set",
                    recommendation=recommendation,
                    url=page_audit.url,
                ))

    def _audit_best_practices(self, soup: BeautifulSoup, page_audit: PageAudit) -> None:
        """Audit general best practices."""
        # Check for viewport meta tag
        viewport = soup.find("meta", attrs={"name": "viewport"})
        if not viewport:
            page_audit.issues.append(AuditIssue(
                category=AuditCategory.BEST_PRACTICES,
                severity=IssueSeverity.HIGH,
                title="Missing viewport meta tag",
                description="No viewport meta tag for responsive design",
                recommendation='Add <meta name="viewport" content="width=device-width, initial-scale=1">',
                url=page_audit.url,
            ))

        # Check for favicon
        favicon = soup.find("link", rel=re.compile(r"icon"))
        if not favicon:
            page_audit.issues.append(AuditIssue(
                category=AuditCategory.BEST_PRACTICES,
                severity=IssueSeverity.LOW,
                title="Missing favicon",
                description="No favicon defined",
                recommendation="Add a favicon for brand recognition",
                url=page_audit.url,
            ))

        # Check for deprecated HTML
        deprecated_tags = soup.find_all(["font", "center", "marquee", "blink"])
        if deprecated_tags:
            page_audit.issues.append(AuditIssue(
                category=AuditCategory.BEST_PRACTICES,
                severity=IssueSeverity.MEDIUM,
                title="Deprecated HTML elements found",
                description=f"Found {len(deprecated_tags)} deprecated elements",
                recommendation="Replace with modern CSS styling",
                url=page_audit.url,
            ))

        # Check for console.log in inline scripts
        for script in soup.find_all("script"):
            if script.string and "console.log" in script.string:
                page_audit.issues.append(AuditIssue(
                    category=AuditCategory.BEST_PRACTICES,
                    severity=IssueSeverity.LOW,
                    title="Console.log in production",
                    description="Inline script contains console.log",
                    recommendation="Remove debug statements in production",
                    url=page_audit.url,
                ))
                break

    def _calculate_scores(self) -> None:
        """Calculate scores for each category."""
        categories = {
            AuditCategory.PERFORMANCE: [],
            AuditCategory.SEO: [],
            AuditCategory.ACCESSIBILITY: [],
            AuditCategory.SECURITY: [],
            AuditCategory.BEST_PRACTICES: [],
        }

        # Collect issues by category
        for page in self.result.pages:
            for issue in page.issues:
                categories[issue.category].append(issue)

        # Calculate score for each category
        for category, issues in categories.items():
            base_score = 100

            for issue in issues:
                penalty = {
                    IssueSeverity.CRITICAL: 25,
                    IssueSeverity.HIGH: 15,
                    IssueSeverity.MEDIUM: 8,
                    IssueSeverity.LOW: 3,
                    IssueSeverity.INFO: 0,
                }[issue.severity]
                base_score -= penalty

            self.result.scores[category.value] = max(0, min(100, base_score))

    def _generate_recommendations(self) -> None:
        """Generate prioritized recommendations."""
        # Collect all issues
        all_issues = []
        for page in self.result.pages:
            all_issues.extend(page.issues)

        # Group by severity
        critical = [i for i in all_issues if i.severity == IssueSeverity.CRITICAL]
        high = [i for i in all_issues if i.severity == IssueSeverity.HIGH]

        if critical:
            self.result.recommendations.append(
                f"URGENT: Fix {len(critical)} critical issue(s) immediately"
            )
            for issue in critical[:3]:
                self.result.recommendations.append(f"  - {issue.title}: {issue.recommendation}")

        if high:
            self.result.recommendations.append(
                f"HIGH PRIORITY: Address {len(high)} high-priority issue(s)"
            )

        # Category-specific recommendations
        scores = self.result.scores
        if scores.get("performance", 100) < 70:
            self.result.recommendations.append(
                "Performance: Optimize images, enable caching, and minimize resources"
            )
        if scores.get("seo", 100) < 70:
            self.result.recommendations.append(
                "SEO: Add missing meta tags, improve heading structure, add canonical URLs"
            )
        if scores.get("accessibility", 100) < 70:
            self.result.recommendations.append(
                "Accessibility: Add alt text, form labels, and improve keyboard navigation"
            )
        if scores.get("security", 100) < 70:
            self.result.recommendations.append(
                "Security: Enable HTTPS and add security headers"
            )

    def _count_issues(self) -> None:
        """Count issues by severity."""
        for page in self.result.pages:
            for issue in page.issues:
                self.result.total_issues += 1
                if issue.severity == IssueSeverity.CRITICAL:
                    self.result.critical_issues += 1
                elif issue.severity == IssueSeverity.HIGH:
                    self.result.high_issues += 1
                elif issue.severity == IssueSeverity.MEDIUM:
                    self.result.medium_issues += 1
                elif issue.severity == IssueSeverity.LOW:
                    self.result.low_issues += 1

        self.result.pages_audited = len(self.result.pages)

    def print_report(self) -> None:
        """Print formatted audit report."""
        console.print("\n[bold]Website Audit Report[/bold]")
        console.print("=" * 60)
        console.print(f"URL: {self.result.base_url}")
        console.print(f"Pages Audited: {self.result.pages_audited}")
        console.print(f"Audit Date: {self.result.audited_at.strftime('%Y-%m-%d %H:%M')}")

        # Scores table
        table = Table(title="Category Scores")
        table.add_column("Category", style="cyan")
        table.add_column("Score", style="green")
        table.add_column("Status")

        for category, score in self.result.scores.items():
            status = (
                "[green]Good[/green]" if score >= 80
                else "[yellow]Needs Work[/yellow]" if score >= 60
                else "[red]Poor[/red]"
            )
            table.add_row(category.replace("_", " ").title(), f"{score}/100", status)

        table.add_row(
            "[bold]Overall[/bold]",
            f"[bold]{self.result.overall_score:.0f}/100[/bold]",
            ""
        )

        console.print(table)

        # Issue summary
        console.print("\n[bold]Issues Summary:[/bold]")
        console.print(f"  [red]Critical:[/red] {self.result.critical_issues}")
        console.print(f"  [orange1]High:[/orange1] {self.result.high_issues}")
        console.print(f"  [yellow]Medium:[/yellow] {self.result.medium_issues}")
        console.print(f"  [blue]Low:[/blue] {self.result.low_issues}")

        # Recommendations
        if self.result.recommendations:
            console.print("\n[bold]Top Recommendations:[/bold]")
            for rec in self.result.recommendations[:10]:
                console.print(f"  - {rec}")

    def export_report(self, output_path: str) -> None:
        """Export audit report to JSON file."""
        data = {
            "base_url": self.result.base_url,
            "audited_at": self.result.audited_at.isoformat(),
            "pages_audited": self.result.pages_audited,
            "overall_score": self.result.overall_score,
            "scores": self.result.scores,
            "issues": {
                "total": self.result.total_issues,
                "critical": self.result.critical_issues,
                "high": self.result.high_issues,
                "medium": self.result.medium_issues,
                "low": self.result.low_issues,
            },
            "recommendations": self.result.recommendations,
            "pages": [
                {
                    "url": page.url,
                    "status_code": page.status_code,
                    "load_time": page.load_time,
                    "issues": [
                        {
                            "category": issue.category.value,
                            "severity": issue.severity.value,
                            "title": issue.title,
                            "description": issue.description,
                            "recommendation": issue.recommendation,
                        }
                        for issue in page.issues
                    ],
                }
                for page in self.result.pages
            ],
        }

        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)

        console.print(f"[green]Report exported to {output_path}[/green]")
