#!/usr/bin/env python3
"""
CLI Entry Point for SEO & AI Monitoring Platform
Common Notary Apostille

Usage:
    python cli.py [command] [options]

Commands:
    init            Initialize database and seed keywords
    track           Run keyword tracking
    ai-monitor      Run AI search monitoring
    local-seo       Run local SEO checks
    content         Generate content suggestions
    audit           Run technical SEO audit
    backlinks       Check backlinks
    competitors     Run competitor analysis
    report          Generate reports
    alerts          Process and view alerts
    dashboard       Launch Streamlit dashboard
    run-all         Run all modules
"""

import sys
import os
import click
from loguru import logger

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import LOG_FILE, LOG_LEVEL

# Configure logging
logger.add(LOG_FILE, rotation="10 MB", level=LOG_LEVEL, retention="30 days")


@click.group()
@click.version_option(version="1.0.0", prog_name="SEO Platform - Common Notary Apostille")
def cli():
    """SEO & AI Monitoring Platform for Common Notary Apostille."""
    pass


@cli.command()
def init():
    """Initialize the database and seed initial data."""
    from database.models import init_db
    from modules.keyword_tracker import KeywordTracker

    click.echo("Initializing database...")
    init_db()
    click.echo("Database initialized.")

    click.echo("Seeding keywords...")
    tracker = KeywordTracker()
    count = tracker.seed_keywords()
    click.echo(f"Seeded {count} keywords.")

    click.echo("Initialization complete.")


@cli.command()
@click.option("--engine", "-e", default="all", help="Search engine: google, bing, all")
@click.option("--keyword", "-k", default=None, help="Track specific keyword")
def track(engine, keyword):
    """Run keyword ranking tracking."""
    from modules.keyword_tracker import KeywordTracker

    tracker = KeywordTracker()

    if keyword:
        click.echo(f"Tracking keyword: {keyword}")
        result = tracker.track_google_rankings(keyword)
        click.echo(f"Result: Position {result.get('position', 'N/A')}")
    else:
        click.echo("Running full keyword tracking...")
        results = tracker.track_all_keywords()
        click.echo(f"Tracked {len(results)} keywords.")

    report = tracker.generate_weekly_report()
    click.echo(f"\nWeekly Report Summary:")
    click.echo(f"  Total keywords: {report.get('total_keywords', 0)}")
    click.echo(f"  Top 3: {report.get('keywords_in_top_3', 0)}")
    click.echo(f"  Top 10: {report.get('keywords_in_top_10', 0)}")
    click.echo(f"  Top 20: {report.get('keywords_in_top_20', 0)}")


@cli.command("ai-monitor")
@click.option("--engine", "-e", default="all", help="AI engine: chatgpt, perplexity, google_ai, claude, all")
def ai_monitor(engine):
    """Run AI search monitoring."""
    from modules.ai_search_optimizer import AISearchOptimizer

    optimizer = AISearchOptimizer()

    click.echo("Running AI search monitoring...")
    results = optimizer.run_all_ai_monitors()
    click.echo(f"Monitored {len(results)} queries across AI engines.")

    report = optimizer.get_ai_visibility_report()
    click.echo(f"\nAI Visibility Report:")
    for engine_name, data in report.get("by_engine", {}).items():
        click.echo(f"  {engine_name}: {data.get('mention_rate', 0):.0%} mention rate")


@cli.command("local-seo")
@click.option("--area", "-a", default=None, help="Specific service area to check")
def local_seo(area):
    """Run local SEO checks."""
    from modules.local_seo_manager import LocalSEOManager

    manager = LocalSEOManager()

    if area:
        click.echo(f"Checking local SEO for: {area}")
        report = manager.get_local_seo_report(area)
    else:
        click.echo("Running local SEO checks for all areas...")
        report = manager.get_overall_local_dashboard()

    click.echo(f"Local SEO check complete.")
    click.echo(f"  NAP Consistency: {report.get('nap_consistency_score', 'N/A')}%")
    click.echo(f"  Citation Count: {report.get('total_citations', 0)}")


@cli.command()
@click.option("--type", "-t", "content_type", default="blog",
              help="Content type: blog, landing_page, faq")
@click.option("--count", "-c", default=10, help="Number of ideas to generate")
def content(content_type, count):
    """Generate content suggestions."""
    from modules.content_strategy import ContentStrategyEngine

    engine = ContentStrategyEngine()

    click.echo(f"Generating {count} {content_type} ideas...")
    ideas = engine.generate_blog_ideas(count=count)

    click.echo(f"\nGenerated {len(ideas)} content ideas:")
    for i, idea in enumerate(ideas[:count], 1):
        click.echo(f"  {i}. {idea.get('title', 'Untitled')}")
        click.echo(f"     Target: {idea.get('target_keyword', 'N/A')} | Area: {idea.get('target_area', 'N/A')}")


@cli.command()
@click.option("--url", "-u", default=None, help="Specific URL to audit")
@click.option("--full", is_flag=True, help="Run full site audit")
def audit(url, full):
    """Run technical SEO audit."""
    from modules.technical_auditor import TechnicalSEOAuditor

    auditor = TechnicalSEOAuditor()

    if url:
        click.echo(f"Auditing page: {url}")
        result = auditor.check_page_speed(url)
        click.echo(f"PageSpeed Score: {result.get('score', 'N/A')}")
    elif full:
        click.echo("Running full technical audit...")
        report = auditor.run_full_audit()
        click.echo(f"\nAudit Complete:")
        click.echo(f"  Overall Score: {report.get('overall_score', 'N/A')}/100")
        click.echo(f"  Pages Crawled: {report.get('pages_crawled', 0)}")
        click.echo(f"  Critical Issues: {report.get('critical_issues', 0)}")
        click.echo(f"  Warnings: {report.get('warnings', 0)}")
    else:
        click.echo("Running quick technical audit...")
        report = auditor.run_full_audit()
        click.echo(f"Audit complete. Score: {report.get('overall_score', 'N/A')}/100")


@cli.command()
@click.option("--check-toxic", is_flag=True, help="Check for toxic backlinks")
def backlinks(check_toxic):
    """Monitor and analyze backlinks."""
    from modules.backlink_builder import BacklinkBuilder

    builder = BacklinkBuilder()

    click.echo("Monitoring backlinks...")
    builder.monitor_backlinks()

    if check_toxic:
        click.echo("Checking for toxic backlinks...")
        toxic = builder.detect_toxic_backlinks()
        click.echo(f"Found {len(toxic)} potentially toxic backlinks.")

    opportunities = builder.find_opportunities()
    click.echo(f"\nFound {len(opportunities)} link building opportunities.")

    report = builder.get_backlink_report()
    click.echo(f"Total Backlinks: {report.get('total_backlinks', 0)}")
    click.echo(f"Referring Domains: {report.get('referring_domains', 0)}")


@cli.command()
@click.option("--area", "-a", default=None, help="Market area to analyze")
@click.option("--discover", is_flag=True, help="Discover new competitors")
def competitors(area, discover):
    """Run competitor analysis."""
    from modules.competitor_intel import CompetitorIntelligence

    intel = CompetitorIntelligence()

    if discover:
        click.echo(f"Discovering competitors in {area or 'all areas'}...")
        found = intel.discover_competitors(area or "DMV")
        click.echo(f"Found {len(found)} competitors.")

    click.echo("Running competitor analysis...")
    report = intel.get_competitor_report()

    click.echo(f"\nCompetitor Intelligence Report:")
    click.echo(f"  Competitors Tracked: {report.get('total_competitors', 0)}")
    click.echo(f"  Markets Covered: {report.get('markets', [])}")


@cli.command()
@click.option("--type", "-t", "report_type", default="weekly",
              help="Report type: weekly, monthly_ai, technical")
@click.option("--pdf", is_flag=True, help="Generate PDF report")
@click.option("--email", is_flag=True, help="Send report via email")
def report(report_type, pdf, email):
    """Generate SEO reports."""
    from modules.reporting import ReportingEngine

    engine = ReportingEngine()

    if report_type == "weekly":
        click.echo("Generating weekly SEO report...")
        data = engine.generate_weekly_seo_report()
    elif report_type == "monthly_ai":
        click.echo("Generating monthly AI visibility report...")
        data = engine.generate_monthly_ai_report()
    else:
        click.echo(f"Generating {report_type} report...")
        data = engine.generate_weekly_seo_report()

    if pdf:
        click.echo("Generating PDF...")
        path = engine.generate_pdf_report(data, report_type)
        click.echo(f"PDF saved to: {path}")

    if email:
        click.echo("Sending email report...")
        engine.send_email_report(data.get("file_path"), None)
        click.echo("Email sent.")

    click.echo("Report generation complete.")


@cli.command()
@click.option("--unread", is_flag=True, help="Show only unread alerts")
def alerts(unread):
    """View and process alerts."""
    from modules.reporting import AlertManager

    manager = AlertManager()

    click.echo("Processing alerts...")
    manager_module = __import__("modules.reporting", fromlist=["ReportingEngine"])
    engine = manager_module.ReportingEngine()
    engine.process_all_alerts()

    summary = manager.get_alert_summary()
    click.echo(f"\nAlert Summary:")
    click.echo(f"  Critical: {summary.get('critical', 0)}")
    click.echo(f"  Warnings: {summary.get('warning', 0)}")
    click.echo(f"  Info: {summary.get('info', 0)}")
    click.echo(f"  Unread: {summary.get('unread', 0)}")

    if unread:
        unread_alerts = manager.get_unread_alerts()
        for alert in unread_alerts:
            click.echo(f"\n  [{alert.severity.upper()}] {alert.title}")
            click.echo(f"    {alert.message}")


@cli.command()
@click.option("--port", "-p", default=8501, help="Port for Streamlit dashboard")
def dashboard(port):
    """Launch the Streamlit web dashboard."""
    import subprocess
    dashboard_path = os.path.join(os.path.dirname(__file__), "dashboard", "app.py")
    click.echo(f"Launching dashboard on port {port}...")
    subprocess.run([
        "streamlit", "run", dashboard_path,
        "--server.port", str(port),
        "--server.headless", "true"
    ])


@cli.command("run-all")
def run_all():
    """Run all modules sequentially."""
    click.echo("=" * 60)
    click.echo("SEO & AI Monitoring Platform - Full Run")
    click.echo("Common Notary Apostille")
    click.echo("=" * 60)

    modules = [
        ("Keyword Tracking", lambda: _run_module("keyword_tracker", "KeywordTracker", "track_all_keywords")),
        ("AI Search Monitoring", lambda: _run_module("ai_search_optimizer", "AISearchOptimizer", "run_all_ai_monitors")),
        ("Local SEO Check", lambda: _run_module("local_seo_manager", "LocalSEOManager", "get_overall_local_dashboard")),
        ("Content Suggestions", lambda: _run_module("content_strategy", "ContentStrategyEngine", "generate_blog_ideas")),
        ("Technical Audit", lambda: _run_module("technical_auditor", "TechnicalSEOAuditor", "run_full_audit")),
        ("Backlink Analysis", lambda: _run_module("backlink_builder", "BacklinkBuilder", "monitor_backlinks")),
        ("Competitor Analysis", lambda: _run_module("competitor_intel", "CompetitorIntelligence", "get_competitor_report")),
        ("Report Generation", lambda: _run_module("reporting", "ReportingEngine", "generate_weekly_seo_report")),
        ("Alert Processing", lambda: _run_module("reporting", "ReportingEngine", "process_all_alerts")),
    ]

    for name, func in modules:
        click.echo(f"\n{'─' * 40}")
        click.echo(f"Running: {name}")
        try:
            result = func()
            click.echo(f"  ✓ Complete")
        except Exception as e:
            click.echo(f"  ✗ Error: {e}")
            logger.error(f"Module {name} failed: {e}")

    click.echo(f"\n{'=' * 60}")
    click.echo("Full run complete.")


def _run_module(module_name: str, class_name: str, method_name: str):
    """Helper to dynamically import and run a module method."""
    module = __import__(f"modules.{module_name}", fromlist=[class_name])
    cls = getattr(module, class_name)
    instance = cls()
    method = getattr(instance, method_name)
    return method()


if __name__ == "__main__":
    cli()
