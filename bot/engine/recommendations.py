"""
Recommendation Engine Module
============================

Intelligent recommendation system that analyzes code and website
analysis results to provide prioritized, actionable improvements.
"""

import json
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown

console = Console()


class RecommendationPriority(Enum):
    """Priority levels for recommendations."""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4
    SUGGESTION = 5


class RecommendationCategory(Enum):
    """Categories of recommendations."""
    SECURITY = "security"
    PERFORMANCE = "performance"
    CODE_QUALITY = "code_quality"
    ACCESSIBILITY = "accessibility"
    SEO = "seo"
    USER_EXPERIENCE = "user_experience"
    MAINTAINABILITY = "maintainability"
    BEST_PRACTICE = "best_practice"


@dataclass
class Recommendation:
    """A single recommendation."""
    id: str
    title: str
    description: str
    category: RecommendationCategory
    priority: RecommendationPriority
    impact: str
    effort: str  # low, medium, high
    action_items: list[str] = field(default_factory=list)
    resources: list[str] = field(default_factory=list)
    estimated_improvement: str = ""
    related_issues: list[str] = field(default_factory=list)
    auto_fixable: bool = False

    @property
    def priority_score(self) -> float:
        """Calculate priority score for sorting."""
        effort_multiplier = {"low": 1.5, "medium": 1.0, "high": 0.7}.get(self.effort, 1.0)
        return (6 - self.priority.value) * effort_multiplier


@dataclass
class RecommendationReport:
    """Complete recommendation report."""
    generated_at: datetime = field(default_factory=datetime.now)
    total_recommendations: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    recommendations: list[Recommendation] = field(default_factory=list)
    quick_wins: list[Recommendation] = field(default_factory=list)
    estimated_score_improvement: float = 0.0


class RecommendationEngine:
    """
    Generate intelligent recommendations based on analysis results.

    Features:
    - Prioritizes recommendations by impact and effort
    - Identifies quick wins
    - Provides actionable steps
    - Tracks recommendation history
    - Learns from implementation results
    """

    # Knowledge base of recommendations
    RECOMMENDATION_TEMPLATES = {
        # Security recommendations
        "SEC001": {
            "title": "Enable HTTPS",
            "description": "Your website is not using HTTPS encryption",
            "category": RecommendationCategory.SECURITY,
            "priority": RecommendationPriority.CRITICAL,
            "impact": "Protects user data, improves SEO, builds trust",
            "effort": "medium",
            "action_items": [
                "Obtain SSL certificate (free via Let's Encrypt)",
                "Configure server to redirect HTTP to HTTPS",
                "Update internal links to use HTTPS",
                "Update sitemap and canonical URLs",
            ],
            "resources": [
                "https://letsencrypt.org/getting-started/",
                "https://web.dev/why-https-matters/",
            ],
            "estimated_improvement": "Immediate security improvement, +5% SEO boost",
        },
        "SEC002": {
            "title": "Add Security Headers",
            "description": "Missing important security headers",
            "category": RecommendationCategory.SECURITY,
            "priority": RecommendationPriority.HIGH,
            "impact": "Prevents XSS, clickjacking, and other attacks",
            "effort": "low",
            "action_items": [
                "Add Content-Security-Policy header",
                "Add X-Frame-Options: SAMEORIGIN",
                "Add X-Content-Type-Options: nosniff",
                "Add Strict-Transport-Security header",
            ],
            "resources": [
                "https://securityheaders.com/",
                "https://owasp.org/www-project-secure-headers/",
            ],
        },
        "SEC003": {
            "title": "Fix Hardcoded Credentials",
            "description": "Credentials or API keys found in code",
            "category": RecommendationCategory.SECURITY,
            "priority": RecommendationPriority.CRITICAL,
            "impact": "Prevents unauthorized access and data breaches",
            "effort": "medium",
            "action_items": [
                "Remove hardcoded credentials from code",
                "Use environment variables for secrets",
                "Implement proper secrets management",
                "Rotate compromised credentials",
                "Add secrets to .gitignore",
            ],
        },

        # Performance recommendations
        "PERF001": {
            "title": "Optimize Images",
            "description": "Large images are slowing down page load",
            "category": RecommendationCategory.PERFORMANCE,
            "priority": RecommendationPriority.HIGH,
            "impact": "Faster page loads, better user experience",
            "effort": "medium",
            "action_items": [
                "Compress images using tools like ImageOptim or Squoosh",
                "Use WebP format with fallbacks",
                "Implement lazy loading for below-fold images",
                "Add width and height attributes",
                "Consider using a CDN",
            ],
            "estimated_improvement": "30-50% reduction in page size",
        },
        "PERF002": {
            "title": "Enable Caching",
            "description": "Resources not being cached effectively",
            "category": RecommendationCategory.PERFORMANCE,
            "priority": RecommendationPriority.HIGH,
            "impact": "Faster repeat visits, reduced server load",
            "effort": "low",
            "action_items": [
                "Set Cache-Control headers for static assets",
                "Use versioned filenames for cache busting",
                "Implement service worker for offline support",
            ],
        },
        "PERF003": {
            "title": "Reduce JavaScript Bundle Size",
            "description": "Large JavaScript files blocking page render",
            "category": RecommendationCategory.PERFORMANCE,
            "priority": RecommendationPriority.MEDIUM,
            "impact": "Faster time to interactive",
            "effort": "high",
            "action_items": [
                "Analyze bundle with webpack-bundle-analyzer",
                "Implement code splitting",
                "Remove unused dependencies",
                "Use dynamic imports for non-critical code",
            ],
        },

        # Code Quality recommendations
        "CODE001": {
            "title": "Reduce Code Complexity",
            "description": "Functions with high cyclomatic complexity found",
            "category": RecommendationCategory.CODE_QUALITY,
            "priority": RecommendationPriority.MEDIUM,
            "impact": "Easier maintenance, fewer bugs",
            "effort": "high",
            "action_items": [
                "Break down large functions into smaller ones",
                "Extract repeated logic into helper functions",
                "Use early returns to reduce nesting",
                "Consider strategy pattern for complex conditionals",
            ],
        },
        "CODE002": {
            "title": "Add Type Hints",
            "description": "Functions missing type annotations",
            "category": RecommendationCategory.CODE_QUALITY,
            "priority": RecommendationPriority.LOW,
            "impact": "Better IDE support, catch bugs early",
            "effort": "medium",
            "action_items": [
                "Add type hints to function parameters and returns",
                "Use mypy for static type checking",
                "Add types to class attributes",
            ],
            "auto_fixable": True,
        },
        "CODE003": {
            "title": "Improve Documentation",
            "description": "Functions missing docstrings",
            "category": RecommendationCategory.CODE_QUALITY,
            "priority": RecommendationPriority.LOW,
            "impact": "Better code understanding, easier onboarding",
            "effort": "medium",
            "action_items": [
                "Add docstrings to all public functions",
                "Document parameters and return values",
                "Include usage examples for complex functions",
            ],
        },

        # Accessibility recommendations
        "A11Y001": {
            "title": "Add Alt Text to Images",
            "description": "Images missing alternative text",
            "category": RecommendationCategory.ACCESSIBILITY,
            "priority": RecommendationPriority.HIGH,
            "impact": "Screen reader users can understand images",
            "effort": "low",
            "action_items": [
                "Add descriptive alt text to all meaningful images",
                "Use alt=\"\" for decorative images",
                "Avoid text like 'image of' - just describe content",
            ],
            "estimated_improvement": "WCAG Level A compliance",
        },
        "A11Y002": {
            "title": "Improve Keyboard Navigation",
            "description": "Interactive elements not keyboard accessible",
            "category": RecommendationCategory.ACCESSIBILITY,
            "priority": RecommendationPriority.HIGH,
            "impact": "Users who can't use mouse can navigate",
            "effort": "medium",
            "action_items": [
                "Ensure all interactive elements are focusable",
                "Add visible focus indicators",
                "Implement skip navigation link",
                "Test tab order is logical",
            ],
        },
        "A11Y003": {
            "title": "Add Form Labels",
            "description": "Form inputs missing labels",
            "category": RecommendationCategory.ACCESSIBILITY,
            "priority": RecommendationPriority.HIGH,
            "impact": "Screen readers can identify form fields",
            "effort": "low",
            "action_items": [
                "Add <label> element for each input",
                "Use aria-label for visually hidden labels",
                "Mark required fields with aria-required",
            ],
            "auto_fixable": True,
        },

        # SEO recommendations
        "SEO001": {
            "title": "Optimize Meta Tags",
            "description": "Missing or suboptimal meta tags",
            "category": RecommendationCategory.SEO,
            "priority": RecommendationPriority.HIGH,
            "impact": "Better search rankings and click-through rates",
            "effort": "low",
            "action_items": [
                "Add unique title (50-60 chars) with primary keyword",
                "Add meta description (150-160 chars)",
                "Include relevant keywords naturally",
                "Add Open Graph tags for social sharing",
            ],
        },
        "SEO002": {
            "title": "Add Structured Data",
            "description": "No schema markup found",
            "category": RecommendationCategory.SEO,
            "priority": RecommendationPriority.MEDIUM,
            "impact": "Rich snippets in search results",
            "effort": "medium",
            "action_items": [
                "Add LocalBusiness schema for notary service",
                "Include service areas and hours",
                "Add FAQ schema if applicable",
                "Validate with Google Rich Results Test",
            ],
            "resources": [
                "https://schema.org/LocalBusiness",
                "https://search.google.com/test/rich-results",
            ],
        },
        "SEO003": {
            "title": "Improve Heading Structure",
            "description": "Suboptimal heading hierarchy",
            "category": RecommendationCategory.SEO,
            "priority": RecommendationPriority.MEDIUM,
            "impact": "Better content understanding by search engines",
            "effort": "low",
            "action_items": [
                "Use single H1 with main keyword",
                "Structure content with H2-H6 hierarchy",
                "Include keywords in headings naturally",
            ],
        },

        # Maintainability recommendations
        "MAINT001": {
            "title": "Remove Duplicate Code",
            "description": "Similar code patterns found in multiple places",
            "category": RecommendationCategory.MAINTAINABILITY,
            "priority": RecommendationPriority.MEDIUM,
            "impact": "Easier maintenance, consistent behavior",
            "effort": "medium",
            "action_items": [
                "Identify duplicate code patterns",
                "Extract into shared functions or utilities",
                "Consider creating a common module",
            ],
        },
        "MAINT002": {
            "title": "Add Unit Tests",
            "description": "Low test coverage detected",
            "category": RecommendationCategory.MAINTAINABILITY,
            "priority": RecommendationPriority.MEDIUM,
            "impact": "Catch bugs early, safer refactoring",
            "effort": "high",
            "action_items": [
                "Write tests for critical business logic",
                "Aim for 80% code coverage",
                "Add integration tests for key workflows",
                "Set up CI/CD to run tests automatically",
            ],
        },
    }

    def __init__(self, project_path: str, history_file: Optional[str] = None):
        self.project_path = Path(project_path)
        self.history_file = Path(history_file) if history_file else self.project_path / ".recommendations_history.json"
        self.history: list[dict] = []
        self._load_history()

    def _load_history(self) -> None:
        """Load recommendation history from file."""
        if self.history_file.exists():
            try:
                with open(self.history_file) as f:
                    self.history = json.load(f)
            except Exception:
                self.history = []

    def _save_history(self) -> None:
        """Save recommendation history to file."""
        try:
            with open(self.history_file, "w") as f:
                json.dump(self.history, f, indent=2, default=str)
        except Exception:
            pass

    def generate_recommendations(
        self,
        code_analysis: Optional[dict] = None,
        website_audit: Optional[dict] = None,
        custom_rules: Optional[list[dict]] = None
    ) -> RecommendationReport:
        """
        Generate recommendations based on analysis results.

        Args:
            code_analysis: Results from code analyzer
            website_audit: Results from website auditor
            custom_rules: Additional custom recommendation rules

        Returns:
            RecommendationReport with prioritized recommendations
        """
        report = RecommendationReport()
        recommendations = []

        # Process code analysis results
        if code_analysis:
            recommendations.extend(self._process_code_analysis(code_analysis))

        # Process website audit results
        if website_audit:
            recommendations.extend(self._process_website_audit(website_audit))

        # Apply custom rules
        if custom_rules:
            recommendations.extend(self._apply_custom_rules(custom_rules))

        # Sort by priority score
        recommendations.sort(key=lambda r: r.priority_score, reverse=True)

        # Identify quick wins (high impact, low effort)
        quick_wins = [
            r for r in recommendations
            if r.effort == "low" and r.priority.value <= 3
        ]

        # Populate report
        report.recommendations = recommendations
        report.quick_wins = quick_wins[:5]
        report.total_recommendations = len(recommendations)

        for rec in recommendations:
            if rec.priority == RecommendationPriority.CRITICAL:
                report.critical_count += 1
            elif rec.priority == RecommendationPriority.HIGH:
                report.high_count += 1
            elif rec.priority == RecommendationPriority.MEDIUM:
                report.medium_count += 1
            elif rec.priority == RecommendationPriority.LOW:
                report.low_count += 1

        # Estimate score improvement
        report.estimated_score_improvement = self._estimate_improvement(recommendations)

        # Save to history
        self._add_to_history(report)

        return report

    def _process_code_analysis(self, analysis: dict) -> list[Recommendation]:
        """Generate recommendations from code analysis."""
        recommendations = []

        issues = analysis.get("issues", [])

        # Security issues
        security_issues = [i for i in issues if i.get("category") == "security"]
        if security_issues:
            cred_issues = [i for i in security_issues if "password" in i.get("message", "").lower()
                         or "api_key" in i.get("message", "").lower()]
            if cred_issues:
                rec = self._create_recommendation("SEC003", related_issues=[
                    f"{i['file']}:{i['line']}" for i in cred_issues
                ])
                recommendations.append(rec)

        # Complexity issues
        metrics = analysis.get("metrics", {})
        if metrics.get("average_complexity", 0) > 8:
            recommendations.append(self._create_recommendation("CODE001"))

        # Documentation
        if metrics.get("documentation_coverage", 100) < 50:
            recommendations.append(self._create_recommendation("CODE003"))

        return recommendations

    def _process_website_audit(self, audit: dict) -> list[Recommendation]:
        """Generate recommendations from website audit."""
        recommendations = []

        scores = audit.get("scores", {})
        issues = audit.get("issues", {})

        # Security
        if scores.get("security", 100) < 80:
            if not audit.get("base_url", "").startswith("https://"):
                recommendations.append(self._create_recommendation("SEC001"))
            recommendations.append(self._create_recommendation("SEC002"))

        # Performance
        if scores.get("performance", 100) < 70:
            recommendations.append(self._create_recommendation("PERF001"))
            recommendations.append(self._create_recommendation("PERF002"))

        # SEO
        if scores.get("seo", 100) < 70:
            recommendations.append(self._create_recommendation("SEO001"))
            recommendations.append(self._create_recommendation("SEO002"))
            recommendations.append(self._create_recommendation("SEO003"))

        # Accessibility
        if scores.get("accessibility", 100) < 70:
            recommendations.append(self._create_recommendation("A11Y001"))
            recommendations.append(self._create_recommendation("A11Y002"))
            recommendations.append(self._create_recommendation("A11Y003"))

        return recommendations

    def _apply_custom_rules(self, rules: list[dict]) -> list[Recommendation]:
        """Apply custom recommendation rules."""
        recommendations = []

        for rule in rules:
            rec = Recommendation(
                id=rule.get("id", f"CUSTOM{len(recommendations)}"),
                title=rule.get("title", "Custom Recommendation"),
                description=rule.get("description", ""),
                category=RecommendationCategory[rule.get("category", "BEST_PRACTICE").upper()],
                priority=RecommendationPriority[rule.get("priority", "MEDIUM").upper()],
                impact=rule.get("impact", ""),
                effort=rule.get("effort", "medium"),
                action_items=rule.get("action_items", []),
                resources=rule.get("resources", []),
            )
            recommendations.append(rec)

        return recommendations

    def _create_recommendation(
        self,
        template_id: str,
        related_issues: Optional[list[str]] = None
    ) -> Recommendation:
        """Create recommendation from template."""
        template = self.RECOMMENDATION_TEMPLATES.get(template_id, {})

        return Recommendation(
            id=template_id,
            title=template.get("title", ""),
            description=template.get("description", ""),
            category=template.get("category", RecommendationCategory.BEST_PRACTICE),
            priority=template.get("priority", RecommendationPriority.MEDIUM),
            impact=template.get("impact", ""),
            effort=template.get("effort", "medium"),
            action_items=template.get("action_items", []),
            resources=template.get("resources", []),
            estimated_improvement=template.get("estimated_improvement", ""),
            related_issues=related_issues or [],
            auto_fixable=template.get("auto_fixable", False),
        )

    def _estimate_improvement(self, recommendations: list[Recommendation]) -> float:
        """Estimate potential score improvement from recommendations."""
        improvement = 0.0

        for rec in recommendations:
            base_improvement = {
                RecommendationPriority.CRITICAL: 15,
                RecommendationPriority.HIGH: 10,
                RecommendationPriority.MEDIUM: 5,
                RecommendationPriority.LOW: 2,
                RecommendationPriority.SUGGESTION: 1,
            }.get(rec.priority, 0)

            improvement += base_improvement

        return min(40, improvement)  # Cap at 40 points improvement

    def _add_to_history(self, report: RecommendationReport) -> None:
        """Add report to history."""
        entry = {
            "date": report.generated_at.isoformat(),
            "total": report.total_recommendations,
            "critical": report.critical_count,
            "high": report.high_count,
            "recommendations": [r.id for r in report.recommendations],
        }
        self.history.append(entry)
        self._save_history()

    def mark_implemented(self, recommendation_id: str) -> None:
        """Mark a recommendation as implemented."""
        if self.history:
            if "implemented" not in self.history[-1]:
                self.history[-1]["implemented"] = []
            self.history[-1]["implemented"].append({
                "id": recommendation_id,
                "date": datetime.now().isoformat(),
            })
            self._save_history()

    def print_report(self, report: RecommendationReport) -> None:
        """Print formatted recommendation report."""
        console.print("\n[bold]Improvement Recommendations[/bold]")
        console.print("=" * 60)

        # Summary
        table = Table(title="Summary")
        table.add_column("Priority", style="cyan")
        table.add_column("Count")

        table.add_row("[red]Critical[/red]", str(report.critical_count))
        table.add_row("[orange1]High[/orange1]", str(report.high_count))
        table.add_row("[yellow]Medium[/yellow]", str(report.medium_count))
        table.add_row("[blue]Low[/blue]", str(report.low_count))
        table.add_row("[bold]Total[/bold]", str(report.total_recommendations))

        console.print(table)

        if report.estimated_score_improvement > 0:
            console.print(f"\n[green]Estimated improvement: +{report.estimated_score_improvement:.0f} points[/green]")

        # Quick wins
        if report.quick_wins:
            console.print("\n[bold green]Quick Wins (High Impact, Low Effort):[/bold green]")
            for rec in report.quick_wins:
                console.print(f"\n  [{rec.id}] {rec.title}")
                console.print(f"    {rec.description}")
                console.print(f"    [dim]Impact: {rec.impact}[/dim]")

        # All recommendations by priority
        console.print("\n[bold]All Recommendations:[/bold]")

        for priority in [RecommendationPriority.CRITICAL, RecommendationPriority.HIGH,
                        RecommendationPriority.MEDIUM, RecommendationPriority.LOW]:
            recs = [r for r in report.recommendations if r.priority == priority]
            if recs:
                color = {
                    RecommendationPriority.CRITICAL: "red",
                    RecommendationPriority.HIGH: "orange1",
                    RecommendationPriority.MEDIUM: "yellow",
                    RecommendationPriority.LOW: "blue",
                }[priority]

                console.print(f"\n[{color}]{priority.name}:[/{color}]")

                for rec in recs:
                    console.print(f"\n  [{rec.id}] {rec.title}")
                    console.print(f"    {rec.description}")
                    console.print(f"    Category: {rec.category.value}")
                    console.print(f"    Effort: {rec.effort}")

                    if rec.action_items:
                        console.print("    Action Items:")
                        for item in rec.action_items[:3]:
                            console.print(f"      - {item}")
