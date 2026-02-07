"""
Celery task scheduler for the SEO & AI Monitoring Platform.
Common Notary Apostille

Manages all recurring automated tasks including keyword tracking,
AI search monitoring, technical audits, backlink checks, competitor
analysis, content suggestions, report generation, local SEO checks,
alert processing, and website uptime monitoring.

Usage:
    Start the worker:
        celery -A seo_platform.scheduler.celery_app worker \
            --loglevel=info -Q alerts,tracking,reporting

    Start the beat scheduler:
        celery -A seo_platform.scheduler.celery_app beat \
            --loglevel=info

    Start both (development only):
        celery -A seo_platform.scheduler.celery_app worker \
            --beat --loglevel=info -Q alerts,tracking,reporting
"""

import datetime
import traceback

from celery import Celery
from celery.schedules import crontab, timedelta
from loguru import logger

from config.settings import (
    CELERY_BROKER_URL,
    CELERY_RESULT_BACKEND,
    SCHEDULE,
)

# ---------------------------------------------------------------------------
# Celery application
# ---------------------------------------------------------------------------

app = Celery("seo_platform")

app.conf.update(
    # Broker & backend
    broker_url=CELERY_BROKER_URL,
    result_backend=CELERY_RESULT_BACKEND,

    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Timezone
    timezone="America/New_York",
    enable_utc=True,

    # Retry policy -- exponential backoff defaults for all tasks
    task_default_retry_delay=60,          # 1 minute initial delay
    task_max_retries=3,
    task_acks_late=True,
    worker_prefetch_multiplier=1,

    # Priority queues: alerts > tracking > reporting
    task_queues={
        "alerts": {
            "exchange": "alerts",
            "routing_key": "alerts",
            "queue_arguments": {"x-max-priority": 10},
        },
        "tracking": {
            "exchange": "tracking",
            "routing_key": "tracking",
            "queue_arguments": {"x-max-priority": 5},
        },
        "reporting": {
            "exchange": "reporting",
            "routing_key": "reporting",
            "queue_arguments": {"x-max-priority": 1},
        },
    },
    task_default_queue="tracking",

    # Route tasks to queues
    task_routes={
        "seo_platform.scheduler.celery_app.process_alerts": {"queue": "alerts"},
        "seo_platform.scheduler.celery_app.check_website_uptime": {"queue": "alerts"},
        "seo_platform.scheduler.celery_app.track_keywords": {"queue": "tracking"},
        "seo_platform.scheduler.celery_app.monitor_ai_search": {"queue": "tracking"},
        "seo_platform.scheduler.celery_app.run_technical_audit": {"queue": "tracking"},
        "seo_platform.scheduler.celery_app.check_backlinks": {"queue": "tracking"},
        "seo_platform.scheduler.celery_app.analyze_competitors": {"queue": "tracking"},
        "seo_platform.scheduler.celery_app.generate_content_suggestions": {"queue": "tracking"},
        "seo_platform.scheduler.celery_app.check_local_seo": {"queue": "tracking"},
        "seo_platform.scheduler.celery_app.generate_weekly_report": {"queue": "reporting"},
    },

    # Result expiration -- keep results for 24 hours
    result_expires=86400,
)

# ---------------------------------------------------------------------------
# Beat schedule -- automated recurring tasks
# ---------------------------------------------------------------------------

app.conf.beat_schedule = {
    # Keyword tracking -- every Monday at 6:00 AM ET
    "track-keywords-weekly": {
        "task": "seo_platform.scheduler.celery_app.track_keywords",
        "schedule": crontab(hour=6, minute=0, day_of_week="monday"),
        "options": {"queue": "tracking", "priority": 5},
    },

    # AI search monitoring -- every Wednesday at 6:00 AM ET
    "monitor-ai-search-weekly": {
        "task": "seo_platform.scheduler.celery_app.monitor_ai_search",
        "schedule": crontab(hour=6, minute=0, day_of_week="wednesday"),
        "options": {"queue": "tracking", "priority": 5},
    },

    # Technical SEO audit -- 1st of every month at 3:00 AM ET
    "run-technical-audit-monthly": {
        "task": "seo_platform.scheduler.celery_app.run_technical_audit",
        "schedule": crontab(hour=3, minute=0, day_of_month="1"),
        "options": {"queue": "tracking", "priority": 4},
    },

    # Backlink check -- every Friday at 6:00 AM ET
    "check-backlinks-weekly": {
        "task": "seo_platform.scheduler.celery_app.check_backlinks",
        "schedule": crontab(hour=6, minute=0, day_of_week="friday"),
        "options": {"queue": "tracking", "priority": 5},
    },

    # Competitor analysis -- every other Monday at 7:00 AM ET
    # Celery crontab does not natively support bi-weekly; we schedule every
    # Monday and let the task body skip alternate weeks via an epoch check.
    "analyze-competitors-biweekly": {
        "task": "seo_platform.scheduler.celery_app.analyze_competitors",
        "schedule": crontab(hour=7, minute=0, day_of_week="monday"),
        "options": {"queue": "tracking", "priority": 3},
    },

    # Content suggestions -- every Tuesday at 6:00 AM ET
    "generate-content-suggestions-weekly": {
        "task": "seo_platform.scheduler.celery_app.generate_content_suggestions",
        "schedule": crontab(hour=6, minute=0, day_of_week="tuesday"),
        "options": {"queue": "tracking", "priority": 3},
    },

    # Weekly report -- every Sunday at 8:00 PM ET
    "generate-weekly-report": {
        "task": "seo_platform.scheduler.celery_app.generate_weekly_report",
        "schedule": crontab(hour=20, minute=0, day_of_week="sunday"),
        "options": {"queue": "reporting", "priority": 1},
    },

    # Local SEO check -- every Thursday at 6:00 AM ET
    "check-local-seo-weekly": {
        "task": "seo_platform.scheduler.celery_app.check_local_seo",
        "schedule": crontab(hour=6, minute=0, day_of_week="thursday"),
        "options": {"queue": "tracking", "priority": 5},
    },

    # Alert processing -- every 4 hours
    "process-alerts-periodic": {
        "task": "seo_platform.scheduler.celery_app.process_alerts",
        "schedule": timedelta(hours=4),
        "options": {"queue": "alerts", "priority": 10},
    },

    # Website uptime check -- every 5 minutes
    "check-website-uptime-frequent": {
        "task": "seo_platform.scheduler.celery_app.check_website_uptime",
        "schedule": timedelta(minutes=5),
        "options": {"queue": "alerts", "priority": 9},
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _store_task_result(task_name: str, status: str, result_data: dict) -> None:
    """Persist a task execution record to the database."""
    from database.models import SessionLocal, Alert
    session = SessionLocal()
    try:
        if status == "success":
            logger.info(
                "Task '{}' completed successfully | result_keys={}",
                task_name,
                list(result_data.keys()) if isinstance(result_data, dict) else "N/A",
            )
        else:
            alert = Alert(
                alert_type="task_failure",
                severity="critical",
                title=f"Scheduled task failed: {task_name}",
                message=result_data.get("error", "Unknown error"),
                data=result_data,
            )
            session.add(alert)
            session.commit()
            logger.error("Task '{}' FAILED -- alert created | error={}", task_name, result_data.get("error"))
    except Exception:
        session.rollback()
        logger.exception("Failed to store task result for '{}'", task_name)
    finally:
        session.close()


def _is_biweekly_run() -> bool:
    """Return True on even ISO weeks so the competitor analysis task runs
    every other Monday."""
    return datetime.date.today().isocalendar()[1] % 2 == 0


# ---------------------------------------------------------------------------
# Task definitions
# ---------------------------------------------------------------------------

@app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def track_keywords(self):
    """Track keyword rankings across all search engines."""
    task_name = "track_keywords"
    logger.info("Starting scheduled task: {}", task_name)
    try:
        from modules.keyword_tracker import KeywordTracker
        tracker = KeywordTracker()
        result = tracker.track_all()
        _store_task_result(task_name, "success", result or {})
        return {"status": "success", "task": task_name, "result": result}
    except Exception as exc:
        logger.exception("Task '{}' raised an exception", task_name)
        _store_task_result(task_name, "failure", {
            "error": str(exc),
            "traceback": traceback.format_exc(),
        })
        raise self.retry(exc=exc)


@app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def monitor_ai_search(self):
    """Monitor AI search engines for brand mentions and rankings."""
    task_name = "monitor_ai_search"
    logger.info("Starting scheduled task: {}", task_name)
    try:
        from modules.ai_search_monitor import AISearchMonitor
        monitor = AISearchMonitor()
        result = monitor.monitor_all()
        _store_task_result(task_name, "success", result or {})
        return {"status": "success", "task": task_name, "result": result}
    except Exception as exc:
        logger.exception("Task '{}' raised an exception", task_name)
        _store_task_result(task_name, "failure", {
            "error": str(exc),
            "traceback": traceback.format_exc(),
        })
        raise self.retry(exc=exc)


@app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=120,
    retry_backoff=True,
    retry_backoff_max=900,
    retry_jitter=True,
)
def run_technical_audit(self):
    """Run a comprehensive technical SEO audit of the website."""
    task_name = "run_technical_audit"
    logger.info("Starting scheduled task: {}", task_name)
    try:
        from modules.technical_auditor import TechnicalAuditor
        auditor = TechnicalAuditor()
        result = auditor.run_full_audit()
        _store_task_result(task_name, "success", result or {})
        return {"status": "success", "task": task_name, "result": result}
    except Exception as exc:
        logger.exception("Task '{}' raised an exception", task_name)
        _store_task_result(task_name, "failure", {
            "error": str(exc),
            "traceback": traceback.format_exc(),
        })
        raise self.retry(exc=exc)


@app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def check_backlinks(self):
    """Check backlink profile for new, lost, and toxic links."""
    task_name = "check_backlinks"
    logger.info("Starting scheduled task: {}", task_name)
    try:
        from modules.backlink_checker import BacklinkChecker
        checker = BacklinkChecker()
        result = checker.check_all()
        _store_task_result(task_name, "success", result or {})
        return {"status": "success", "task": task_name, "result": result}
    except Exception as exc:
        logger.exception("Task '{}' raised an exception", task_name)
        _store_task_result(task_name, "failure", {
            "error": str(exc),
            "traceback": traceback.format_exc(),
        })
        raise self.retry(exc=exc)


@app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def analyze_competitors(self):
    """Analyze competitor SEO strategies and identify gaps.

    Scheduled every Monday but internally skipped on odd ISO weeks to
    achieve a bi-weekly cadence.
    """
    task_name = "analyze_competitors"
    if not _is_biweekly_run():
        logger.info("Skipping '{}' -- not a bi-weekly run week", task_name)
        return {"status": "skipped", "task": task_name, "reason": "odd ISO week"}

    logger.info("Starting scheduled task: {}", task_name)
    try:
        from modules.competitor_analyzer import CompetitorAnalyzer
        analyzer = CompetitorAnalyzer()
        result = analyzer.analyze_all()
        _store_task_result(task_name, "success", result or {})
        return {"status": "success", "task": task_name, "result": result}
    except Exception as exc:
        logger.exception("Task '{}' raised an exception", task_name)
        _store_task_result(task_name, "failure", {
            "error": str(exc),
            "traceback": traceback.format_exc(),
        })
        raise self.retry(exc=exc)


@app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def generate_content_suggestions(self):
    """Generate AI-powered content ideas and optimization suggestions."""
    task_name = "generate_content_suggestions"
    logger.info("Starting scheduled task: {}", task_name)
    try:
        from modules.content_strategist import ContentStrategist
        strategist = ContentStrategist()
        result = strategist.generate_suggestions()
        _store_task_result(task_name, "success", result or {})
        return {"status": "success", "task": task_name, "result": result}
    except Exception as exc:
        logger.exception("Task '{}' raised an exception", task_name)
        _store_task_result(task_name, "failure", {
            "error": str(exc),
            "traceback": traceback.format_exc(),
        })
        raise self.retry(exc=exc)


@app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def generate_weekly_report(self):
    """Compile and distribute the weekly SEO performance report."""
    task_name = "generate_weekly_report"
    logger.info("Starting scheduled task: {}", task_name)
    try:
        from modules.report_generator import ReportGenerator
        generator = ReportGenerator()
        result = generator.generate_weekly_report()
        _store_task_result(task_name, "success", result or {})
        return {"status": "success", "task": task_name, "result": result}
    except Exception as exc:
        logger.exception("Task '{}' raised an exception", task_name)
        _store_task_result(task_name, "failure", {
            "error": str(exc),
            "traceback": traceback.format_exc(),
        })
        raise self.retry(exc=exc)


@app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def check_local_seo(self):
    """Check local SEO health: listings, NAP consistency, reviews."""
    task_name = "check_local_seo"
    logger.info("Starting scheduled task: {}", task_name)
    try:
        from modules.local_seo_manager import LocalSEOManager
        manager = LocalSEOManager()
        result = manager.check_all()
        _store_task_result(task_name, "success", result or {})
        return {"status": "success", "task": task_name, "result": result}
    except Exception as exc:
        logger.exception("Task '{}' raised an exception", task_name)
        _store_task_result(task_name, "failure", {
            "error": str(exc),
            "traceback": traceback.format_exc(),
        })
        raise self.retry(exc=exc)


@app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def process_alerts(self):
    """Process pending alerts: evaluate thresholds and send notifications."""
    task_name = "process_alerts"
    logger.info("Starting scheduled task: {}", task_name)
    try:
        from modules.alert_processor import AlertProcessor
        processor = AlertProcessor()
        result = processor.process_pending()
        _store_task_result(task_name, "success", result or {})
        return {"status": "success", "task": task_name, "result": result}
    except Exception as exc:
        logger.exception("Task '{}' raised an exception", task_name)
        _store_task_result(task_name, "failure", {
            "error": str(exc),
            "traceback": traceback.format_exc(),
        })
        raise self.retry(exc=exc)


@app.task(
    bind=True,
    max_retries=1,
    default_retry_delay=15,
    retry_backoff=False,
)
def check_website_uptime(self):
    """Check that the company website is reachable and responsive."""
    task_name = "check_website_uptime"
    # This task runs every 5 minutes; keep logging at DEBUG to avoid noise.
    logger.debug("Starting scheduled task: {}", task_name)
    try:
        from modules.uptime_checker import UptimeChecker
        checker = UptimeChecker()
        result = checker.check()
        if result and not result.get("is_up", True):
            _store_task_result(task_name, "failure", {
                "error": "Website is DOWN",
                "status_code": result.get("status_code"),
                "response_time_ms": result.get("response_time_ms"),
            })
        return {"status": "success", "task": task_name, "result": result}
    except Exception as exc:
        logger.exception("Task '{}' raised an exception", task_name)
        _store_task_result(task_name, "failure", {
            "error": str(exc),
            "traceback": traceback.format_exc(),
        })
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Main -- convenience launcher for development
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(
        "=" * 68 + "\n"
        "  SEO & AI Monitoring Platform -- Celery Task Scheduler\n"
        "  Common Notary Apostille\n"
        "=" * 68 + "\n"
        "\n"
        "Start the Celery WORKER (consumes tasks from all priority queues):\n"
        "\n"
        "    celery -A seo_platform.scheduler.celery_app worker \\\n"
        "        --loglevel=info \\\n"
        "        -Q alerts,tracking,reporting\n"
        "\n"
        "Start the Celery BEAT scheduler (enqueues tasks on schedule):\n"
        "\n"
        "    celery -A seo_platform.scheduler.celery_app beat \\\n"
        "        --loglevel=info\n"
        "\n"
        "Start both in a single process (development only):\n"
        "\n"
        "    celery -A seo_platform.scheduler.celery_app worker \\\n"
        "        --beat --loglevel=info \\\n"
        "        -Q alerts,tracking,reporting\n"
        "\n"
        "Registered beat schedule:\n"
    )

    for name, entry in sorted(app.conf.beat_schedule.items()):
        schedule = entry["schedule"]
        if isinstance(schedule, crontab):
            timing = (
                f"crontab(hour={schedule.hour}, minute={schedule.minute}, "
                f"day_of_week={schedule.day_of_week}, "
                f"day_of_month={schedule.day_of_month})"
            )
        else:
            timing = f"every {schedule}"
        queue = entry.get("options", {}).get("queue", "default")
        print(f"  {name:<42s} | {timing:<55s} | queue={queue}")

    print()
