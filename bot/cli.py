"""
Command Line Interface for Common Apostille Bot
================================================

Main CLI entry point for the code review and improvement bot.
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from bot.core.analyzer import CodeAnalyzer
from bot.core.reviewer import CodeReviewer, ReviewBot
from bot.core.metrics import CodeMetrics
from bot.core.fixer import CodeFixer
from bot.web.auditor import WebsiteAuditor
from bot.web.seo import SEOAnalyzer
from bot.web.accessibility import AccessibilityChecker
from bot.web.performance import PerformanceAnalyzer
from bot.engine.recommendations import RecommendationEngine
from bot.engine.self_improve import SelfImprover

console = Console()


@click.group()
@click.version_option(version="1.0.0", prog_name="Common Apostille Bot")
def main():
    """
    Common Apostille Code Review & Improvement Bot

    A comprehensive tool for ensuring code quality, website performance,
    and continuous improvement for Common Notary Apostille.
    """
    pass


# ============================================================================
# Code Analysis Commands
# ============================================================================

@main.group()
def code():
    """Code analysis and review commands."""
    pass


@code.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), help="Export report to file")
@click.option("--format", "-f", type=click.Choice(["json", "text"]), default="text")
def analyze(path: str, output: Optional[str], format: str):
    """Analyze code for errors, issues, and quality problems."""
    console.print(f"[bold blue]Analyzing code in: {path}[/bold blue]")

    analyzer = CodeAnalyzer(path)
    result = analyzer.analyze()

    if format == "text" or not output:
        analyzer.print_report()

    if output:
        analyzer.export_report(output, format)
        console.print(f"\n[green]Report exported to {output}[/green]")

    # Return exit code based on results
    if result.critical_count > 0:
        sys.exit(2)
    elif result.high_count > 0:
        sys.exit(1)
    sys.exit(0)


@code.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--strict", is_flag=True, help="Apply strict quality standards")
def review(path: str, strict: bool):
    """Perform comprehensive code review."""
    console.print(f"[bold blue]Reviewing code in: {path}[/bold blue]")

    reviewer = CodeReviewer(path)
    result = reviewer.review(strict=strict)
    reviewer.print_review(result)

    # Check if meets 100% quality
    if result.score < 95:
        console.print("\n[yellow]Tip: Run 'apostille-bot code ensure-quality' for detailed improvement guidance[/yellow]")


@code.command("ensure-quality")
@click.argument("path", default=".", type=click.Path(exists=True))
def ensure_quality(path: str):
    """Ensure code meets 100% quality standards."""
    console.print(f"[bold blue]Checking if code meets 100% quality standards...[/bold blue]")

    reviewer = CodeReviewer(path)
    meets_standard, result = reviewer.ensure_100_percent_quality()

    if not meets_standard:
        sys.exit(1)


@code.command()
@click.argument("path", default=".", type=click.Path(exists=True))
def metrics(path: str):
    """Calculate code metrics (complexity, maintainability, etc.)."""
    console.print(f"[bold blue]Calculating metrics for: {path}[/bold blue]")

    metrics_calc = CodeMetrics(path)
    result = metrics_calc.calculate()
    metrics_calc.print_report(result)

    grade = metrics_calc.get_quality_grade(result)
    console.print(f"\n[bold]Overall Grade: {grade}[/bold]")


@code.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--auto", is_flag=True, help="Automatically apply fixes")
@click.option("--preview/--no-preview", default=True, help="Show preview before applying")
def fix(path: str, auto: bool, preview: bool):
    """Automatically fix code issues."""
    console.print(f"[bold blue]Fixing issues in: {path}[/bold blue]")

    fixer = CodeFixer(path)

    if Path(path).is_file():
        result = fixer.fix_file(path, preview=preview, auto_apply=auto)
    else:
        result = fixer.fix_project(preview=preview)

    console.print(f"\n[bold]Fix Summary:[/bold]")
    console.print(f"  Total fixes available: {result.total_fixes}")
    console.print(f"  Fixes applied: {result.applied_fixes}")
    console.print(f"  Fixes skipped: {result.skipped_fixes}")


# ============================================================================
# Website Audit Commands
# ============================================================================

@main.group()
def website():
    """Website analysis and audit commands."""
    pass


@website.command()
@click.argument("url")
@click.option("--max-pages", "-m", default=10, help="Maximum pages to audit")
@click.option("--output", "-o", type=click.Path(), help="Export report to file")
def audit(url: str, max_pages: int, output: Optional[str]):
    """Run comprehensive website audit."""
    console.print(f"[bold blue]Auditing website: {url}[/bold blue]")

    auditor = WebsiteAuditor(url, max_pages=max_pages)
    result = asyncio.run(auditor.audit())
    auditor.print_report()

    if output:
        auditor.export_report(output)


@website.command()
@click.argument("url")
def seo(url: str):
    """Analyze SEO factors."""
    console.print(f"[bold blue]Analyzing SEO for: {url}[/bold blue]")

    analyzer = SEOAnalyzer()
    result = asyncio.run(analyzer.analyze(url))
    analyzer.print_report(result)


@website.command()
@click.argument("url")
def accessibility(url: str):
    """Check accessibility compliance (WCAG 2.1)."""
    console.print(f"[bold blue]Checking accessibility for: {url}[/bold blue]")

    checker = AccessibilityChecker()
    result = asyncio.run(checker.check(url))
    checker.print_report(result)


@website.command()
@click.argument("url")
def performance(url: str):
    """Analyze website performance."""
    console.print(f"[bold blue]Analyzing performance for: {url}[/bold blue]")

    analyzer = PerformanceAnalyzer(url)
    metrics = asyncio.run(analyzer.analyze())
    analyzer.print_report(metrics)


# ============================================================================
# Recommendations Commands
# ============================================================================

@main.group()
def recommend():
    """Recommendation and improvement commands."""
    pass


@recommend.command("generate")
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--website", "-w", help="Website URL to include in analysis")
def generate_recommendations(path: str, website: Optional[str]):
    """Generate improvement recommendations."""
    console.print(f"[bold blue]Generating recommendations...[/bold blue]")

    # Run code analysis
    analyzer = CodeAnalyzer(path)
    code_result = analyzer.analyze()

    code_analysis = {
        "issues": [
            {
                "file": i.file_path,
                "line": i.line_number,
                "message": i.message,
                "severity": i.severity.value,
                "category": i.category.value,
                "rule_id": i.rule_id,
            }
            for i in code_result.issues
        ],
        "metrics": {
            "files": code_result.files_analyzed,
            "lines": code_result.total_lines,
            "score": code_result.score,
        }
    }

    # Run website audit if URL provided
    website_audit = None
    if website:
        auditor = WebsiteAuditor(website, max_pages=5)
        audit_result = asyncio.run(auditor.audit())
        website_audit = {
            "base_url": website,
            "scores": audit_result.scores,
            "issues": {
                "critical": audit_result.critical_issues,
                "high": audit_result.high_issues,
            }
        }

    # Generate recommendations
    engine = RecommendationEngine(path)
    report = engine.generate_recommendations(
        code_analysis=code_analysis,
        website_audit=website_audit
    )

    engine.print_report(report)


# ============================================================================
# Self-Improvement Commands
# ============================================================================

@main.group()
def learn():
    """Self-improvement and learning commands."""
    pass


@learn.command()
@click.argument("path", default=".", type=click.Path(exists=True))
def status(path: str):
    """Show learning status and metrics."""
    data_dir = Path(path) / "data" / "learning"
    improver = SelfImprover(str(data_dir))
    improver.print_status()


@learn.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--type", "-t", "target_type", required=True,
              type=click.Choice(["issue", "recommendation", "review"]))
@click.option("--id", "-i", "target_id", required=True, help="ID of the target")
@click.option("--feedback", "-f", required=True,
              type=click.Choice(["positive", "negative", "suggestion"]))
@click.option("--comment", "-c", default="", help="Additional comment")
@click.option("--accurate/--inaccurate", default=True, help="Was it accurate?")
def feedback(path: str, target_type: str, target_id: str, feedback: str,
             comment: str, accurate: bool):
    """Provide feedback to help the bot improve."""
    data_dir = Path(path) / "data" / "learning"
    improver = SelfImprover(str(data_dir))

    improver.record_feedback(
        target_type=target_type,
        target_id=target_id,
        feedback_type=feedback,
        was_accurate=accurate,
        comment=comment
    )


@learn.command()
@click.argument("path", default=".", type=click.Path(exists=True))
def train(path: str):
    """Run a training cycle to improve the bot."""
    data_dir = Path(path) / "data" / "learning"
    improver = SelfImprover(str(data_dir))
    improver.train()


@learn.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.argument("output", type=click.Path())
def export(path: str, output: str):
    """Export learning data for backup."""
    data_dir = Path(path) / "data" / "learning"
    improver = SelfImprover(str(data_dir))
    improver.export_learning_data(output)


# ============================================================================
# Watch/Monitor Commands
# ============================================================================

@main.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--interval", "-i", default=30, help="Check interval in seconds")
def watch(path: str, interval: int):
    """Watch for code changes and review automatically."""
    import time

    console.print(f"[bold blue]Watching for changes in: {path}[/bold blue]")
    console.print(f"[dim]Checking every {interval} seconds. Press Ctrl+C to stop.[/dim]")

    bot = ReviewBot(path)

    try:
        while True:
            reviews = bot.review_changes()
            if reviews:
                for review in reviews:
                    console.print(f"\n[yellow]Changes detected![/yellow]")
                    bot.reviewer.print_review(review)
            time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[dim]Watching stopped.[/dim]")


# ============================================================================
# Full Analysis Command
# ============================================================================

@main.command("full-analysis")
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--website", "-w", help="Website URL to audit")
@click.option("--output", "-o", type=click.Path(), help="Export full report")
def full_analysis(path: str, website: Optional[str], output: Optional[str]):
    """Run complete analysis (code + website + recommendations)."""
    console.print("[bold blue]Running Full Analysis[/bold blue]")
    console.print("=" * 60)

    # 1. Code Analysis
    console.print("\n[bold]1. Code Analysis[/bold]")
    analyzer = CodeAnalyzer(path)
    code_result = analyzer.analyze()
    analyzer.print_report()

    # 2. Code Metrics
    console.print("\n[bold]2. Code Metrics[/bold]")
    metrics_calc = CodeMetrics(path)
    metrics_result = metrics_calc.calculate()
    metrics_calc.print_report(metrics_result)

    # 3. Website Audit (if URL provided)
    website_result = None
    if website:
        console.print("\n[bold]3. Website Audit[/bold]")
        auditor = WebsiteAuditor(website, max_pages=10)
        website_result = asyncio.run(auditor.audit())
        auditor.print_report()

    # 4. Recommendations
    console.print("\n[bold]4. Recommendations[/bold]")
    engine = RecommendationEngine(path)

    code_analysis = {
        "issues": [
            {
                "file": i.file_path,
                "line": i.line_number,
                "message": i.message,
                "severity": i.severity.value,
                "category": i.category.value,
            }
            for i in code_result.issues
        ],
        "metrics": {
            "files": code_result.files_analyzed,
            "score": code_result.score,
            "average_complexity": metrics_result.average_complexity,
            "documentation_coverage": metrics_result.documentation_coverage,
        }
    }

    website_audit = None
    if website_result:
        website_audit = {
            "base_url": website,
            "scores": website_result.scores,
            "issues": {
                "total": website_result.total_issues,
                "critical": website_result.critical_issues,
                "high": website_result.high_issues,
            }
        }

    recommendations = engine.generate_recommendations(
        code_analysis=code_analysis,
        website_audit=website_audit
    )
    engine.print_report(recommendations)

    # Summary
    console.print("\n" + "=" * 60)
    console.print("[bold]Analysis Complete![/bold]")
    console.print(f"  Code Quality Score: {code_result.score}/100")
    console.print(f"  Code Grade: {metrics_calc.get_quality_grade(metrics_result)}")
    if website_result:
        console.print(f"  Website Score: {website_result.overall_score:.0f}/100")
    console.print(f"  Recommendations: {recommendations.total_recommendations}")

    if output:
        # Export combined report
        import json
        report = {
            "code_score": code_result.score,
            "code_grade": metrics_calc.get_quality_grade(metrics_result),
            "website_score": website_result.overall_score if website_result else None,
            "recommendations_count": recommendations.total_recommendations,
        }
        with open(output, "w") as f:
            json.dump(report, f, indent=2)
        console.print(f"\n[green]Report exported to {output}[/green]")


if __name__ == "__main__":
    main()
