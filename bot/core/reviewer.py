"""
Code Reviewer Module
====================

High-level code review system that provides comprehensive feedback,
suggestions, and ensures code quality meets the 100% standard.
"""

import os
import re
import hashlib
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from bot.core.analyzer import CodeAnalyzer, AnalysisResult, Severity

console = Console()


class ReviewStatus(Enum):
    """Overall review status."""
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    NEEDS_ATTENTION = "needs_attention"
    REJECTED = "rejected"


@dataclass
class ReviewComment:
    """A single review comment."""
    file_path: str
    line_start: int
    line_end: int
    comment: str
    suggestion: str
    severity: str
    auto_fix_available: bool = False


@dataclass
class CodeReview:
    """Complete code review result."""
    status: ReviewStatus
    summary: str
    comments: list[ReviewComment] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    score: float = 0.0
    reviewed_at: datetime = field(default_factory=datetime.now)
    analysis: Optional[AnalysisResult] = None


class CodeReviewer:
    """
    Comprehensive code reviewer that ensures code quality is at 100%.

    Features:
    - Deep code analysis
    - Pattern-based issue detection
    - Best practice enforcement
    - Security vulnerability scanning
    - Performance optimization suggestions
    - Maintainability scoring
    """

    QUALITY_STANDARDS = {
        "min_score_for_approval": 85,
        "max_critical_issues": 0,
        "max_high_issues": 2,
        "require_tests": True,
        "require_documentation": True,
        "max_function_length": 50,
        "max_cyclomatic_complexity": 10,
        "max_file_length": 500,
    }

    def __init__(self, project_path: str, standards: Optional[dict] = None):
        self.project_path = Path(project_path)
        self.analyzer = CodeAnalyzer(project_path)
        self.standards = {**self.QUALITY_STANDARDS, **(standards or {})}
        self.review_history: list[CodeReview] = []

    def review(self, target: Optional[str] = None, strict: bool = True) -> CodeReview:
        """
        Perform a comprehensive code review.

        Args:
            target: Specific file or directory to review
            strict: Apply strict quality standards

        Returns:
            CodeReview with all findings and recommendations
        """
        console.print("[bold blue]Starting Code Review...[/bold blue]")

        # Run analysis
        analysis = self.analyzer.analyze(target)

        # Determine review status
        status = self._determine_status(analysis, strict)

        # Generate comments
        comments = self._generate_comments(analysis)

        # Identify improvements needed
        improvements = self._identify_improvements(analysis)

        # Identify strengths
        strengths = self._identify_strengths(analysis)

        # Create summary
        summary = self._create_summary(analysis, status)

        review = CodeReview(
            status=status,
            summary=summary,
            comments=comments,
            improvements=improvements,
            strengths=strengths,
            score=analysis.score,
            analysis=analysis,
        )

        self.review_history.append(review)
        return review

    def _determine_status(self, analysis: AnalysisResult, strict: bool) -> ReviewStatus:
        """Determine the overall review status based on analysis."""
        if analysis.critical_count > self.standards["max_critical_issues"]:
            return ReviewStatus.REJECTED

        if strict:
            if analysis.high_count > self.standards["max_high_issues"]:
                return ReviewStatus.CHANGES_REQUESTED
            if analysis.score < self.standards["min_score_for_approval"]:
                return ReviewStatus.CHANGES_REQUESTED

        if analysis.score >= 95:
            return ReviewStatus.APPROVED
        elif analysis.score >= self.standards["min_score_for_approval"]:
            return ReviewStatus.NEEDS_ATTENTION
        else:
            return ReviewStatus.CHANGES_REQUESTED

    def _generate_comments(self, analysis: AnalysisResult) -> list[ReviewComment]:
        """Generate review comments from analysis issues."""
        comments = []

        for issue in analysis.issues:
            comments.append(ReviewComment(
                file_path=issue.file_path,
                line_start=issue.line_number,
                line_end=issue.line_number,
                comment=issue.message,
                suggestion=issue.suggestion,
                severity=issue.severity.value,
                auto_fix_available=issue.auto_fixable,
            ))

        return comments

    def _identify_improvements(self, analysis: AnalysisResult) -> list[str]:
        """Identify areas for improvement."""
        improvements = []

        if analysis.critical_count > 0:
            improvements.append(
                f"Fix {analysis.critical_count} critical issue(s) immediately - "
                "these may cause crashes or security vulnerabilities"
            )

        if analysis.high_count > 0:
            improvements.append(
                f"Address {analysis.high_count} high-priority issue(s) - "
                "these affect code reliability"
            )

        if analysis.medium_count > 5:
            improvements.append(
                "Consider refactoring to address multiple medium-priority issues"
            )

        # Check for common improvement areas
        security_issues = [i for i in analysis.issues if i.category.value == "security"]
        if security_issues:
            improvements.append(
                f"Security review needed: {len(security_issues)} potential vulnerability(ies) found"
            )

        style_issues = [i for i in analysis.issues if i.category.value == "style"]
        if len(style_issues) > 10:
            improvements.append(
                "Run code formatter (black/prettier) to fix style inconsistencies"
            )

        return improvements

    def _identify_strengths(self, analysis: AnalysisResult) -> list[str]:
        """Identify code strengths."""
        strengths = []

        if analysis.critical_count == 0:
            strengths.append("No critical issues found")

        if analysis.score >= 90:
            strengths.append("High overall code quality score")

        security_issues = [i for i in analysis.issues if i.category.value == "security"]
        if not security_issues:
            strengths.append("No obvious security vulnerabilities detected")

        if analysis.total_lines > 0 and len(analysis.issues) / max(1, analysis.total_lines) < 0.01:
            strengths.append("Low issue density - clean codebase")

        return strengths

    def _create_summary(self, analysis: AnalysisResult, status: ReviewStatus) -> str:
        """Create a human-readable summary of the review."""
        status_messages = {
            ReviewStatus.APPROVED: "Code meets quality standards and is approved for merge.",
            ReviewStatus.CHANGES_REQUESTED: "Changes are required before this code can be approved.",
            ReviewStatus.NEEDS_ATTENTION: "Code is acceptable but could benefit from improvements.",
            ReviewStatus.REJECTED: "Code has critical issues that must be resolved.",
        }

        summary = f"""
## Code Review Summary

**Status:** {status.value.replace('_', ' ').title()}
**Score:** {analysis.score}/100

{status_messages[status]}

### Statistics
- Files Reviewed: {analysis.files_analyzed}
- Lines of Code: {analysis.total_lines}
- Critical Issues: {analysis.critical_count}
- High Issues: {analysis.high_count}
- Medium Issues: {analysis.medium_count}
- Low Issues: {analysis.low_count}
"""
        return summary.strip()

    def print_review(self, review: CodeReview) -> None:
        """Print formatted review to console."""
        # Status color
        status_colors = {
            ReviewStatus.APPROVED: "green",
            ReviewStatus.CHANGES_REQUESTED: "yellow",
            ReviewStatus.NEEDS_ATTENTION: "blue",
            ReviewStatus.REJECTED: "red",
        }
        color = status_colors[review.status]

        console.print(Panel(
            Markdown(review.summary),
            title=f"[{color}]Code Review[/{color}]",
            border_style=color,
        ))

        if review.strengths:
            console.print("\n[bold green]Strengths:[/bold green]")
            for strength in review.strengths:
                console.print(f"  [green]+[/green] {strength}")

        if review.improvements:
            console.print("\n[bold yellow]Improvements Needed:[/bold yellow]")
            for improvement in review.improvements:
                console.print(f"  [yellow]![/yellow] {improvement}")

        if review.comments:
            console.print(f"\n[bold]Review Comments ({len(review.comments)}):[/bold]")
            for comment in review.comments[:15]:  # Show first 15
                severity_color = {
                    "critical": "red",
                    "high": "orange1",
                    "medium": "yellow",
                    "low": "blue",
                    "info": "dim",
                }.get(comment.severity, "white")

                console.print(f"\n  [{severity_color}][{comment.severity.upper()}][/{severity_color}] "
                            f"{comment.file_path}:{comment.line_start}")
                console.print(f"    {comment.comment}")
                if comment.suggestion:
                    console.print(f"    [dim]Fix: {comment.suggestion}[/dim]")

    def ensure_100_percent_quality(self, target: Optional[str] = None) -> tuple[bool, CodeReview]:
        """
        Review code and ensure it meets 100% quality standards.

        Returns:
            Tuple of (meets_standard, review)
        """
        review = self.review(target, strict=True)

        meets_standard = (
            review.status == ReviewStatus.APPROVED and
            review.score >= 95 and
            review.analysis and
            review.analysis.critical_count == 0 and
            review.analysis.high_count == 0
        )

        if not meets_standard:
            console.print("\n[bold red]Code does not meet 100% quality standards[/bold red]")
            console.print("The following must be addressed:")

            if review.analysis:
                if review.analysis.critical_count > 0:
                    console.print(f"  - Fix {review.analysis.critical_count} critical issue(s)")
                if review.analysis.high_count > 0:
                    console.print(f"  - Fix {review.analysis.high_count} high-priority issue(s)")
                if review.score < 95:
                    console.print(f"  - Improve score from {review.score} to at least 95")
        else:
            console.print("\n[bold green]Code meets 100% quality standards![/bold green]")

        return meets_standard, review

    def compare_with_previous(self, current: CodeReview) -> dict:
        """Compare current review with previous to track improvement."""
        if len(self.review_history) < 2:
            return {"message": "No previous review to compare"}

        previous = self.review_history[-2]

        comparison = {
            "score_change": current.score - previous.score,
            "issues_change": (
                (current.analysis.critical_count if current.analysis else 0) -
                (previous.analysis.critical_count if previous.analysis else 0)
            ),
            "improved": current.score > previous.score,
        }

        if comparison["improved"]:
            console.print(f"[green]Improvement: Score increased by {comparison['score_change']:.1f} points[/green]")
        elif comparison["score_change"] < 0:
            console.print(f"[red]Regression: Score decreased by {abs(comparison['score_change']):.1f} points[/red]")

        return comparison


class ReviewBot:
    """
    Automated review bot that continuously monitors and reviews code.
    """

    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.reviewer = CodeReviewer(project_path)
        self.file_hashes: dict[str, str] = {}

    def _get_file_hash(self, file_path: Path) -> str:
        """Get hash of file contents."""
        try:
            with open(file_path, "rb") as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return ""

    def get_changed_files(self) -> list[Path]:
        """Get list of files that have changed since last review."""
        changed = []

        for file_path in self.project_path.rglob("*"):
            if file_path.is_file() and not self._should_ignore(file_path):
                current_hash = self._get_file_hash(file_path)
                stored_hash = self.file_hashes.get(str(file_path))

                if stored_hash != current_hash:
                    changed.append(file_path)
                    self.file_hashes[str(file_path)] = current_hash

        return changed

    def _should_ignore(self, path: Path) -> bool:
        """Check if path should be ignored."""
        ignore_patterns = ["__pycache__", "node_modules", ".git", "venv", ".venv"]
        return any(p in str(path) for p in ignore_patterns)

    def review_changes(self) -> list[CodeReview]:
        """Review only changed files."""
        changed = self.get_changed_files()
        reviews = []

        for file_path in changed:
            console.print(f"[blue]Reviewing changed file:[/blue] {file_path}")
            review = self.reviewer.review(str(file_path))
            reviews.append(review)

        return reviews

    def full_review(self) -> CodeReview:
        """Perform full project review."""
        return self.reviewer.review()
