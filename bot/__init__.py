"""
Common Apostille Code Review Bot
================================

A comprehensive code review and improvement bot for Common Notary Apostille.
Provides code analysis, website auditing, recommendations, and self-improvement capabilities.
"""

__version__ = "1.0.0"
__author__ = "Common Notary"

from bot.core.analyzer import CodeAnalyzer
from bot.core.reviewer import CodeReviewer
from bot.web.auditor import WebsiteAuditor
from bot.engine.recommendations import RecommendationEngine
from bot.engine.self_improve import SelfImprover

__all__ = [
    "CodeAnalyzer",
    "CodeReviewer",
    "WebsiteAuditor",
    "RecommendationEngine",
    "SelfImprover",
]
