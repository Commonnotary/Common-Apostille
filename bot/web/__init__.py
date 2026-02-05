"""Web analysis modules for website auditing and monitoring."""

from bot.web.auditor import WebsiteAuditor
from bot.web.performance import PerformanceAnalyzer
from bot.web.seo import SEOAnalyzer
from bot.web.accessibility import AccessibilityChecker

__all__ = ["WebsiteAuditor", "PerformanceAnalyzer", "SEOAnalyzer", "AccessibilityChecker"]
