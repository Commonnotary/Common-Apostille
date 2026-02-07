"""
Module 8: Reporting & Alerts Dashboard
SEO & AI Monitoring Platform - Common Notary Apostille

Automated report generation (weekly SEO, monthly AI visibility),
PDF rendering via reportlab, email delivery via SendGrid, and a
full alert pipeline covering ranking drops, competitor moves,
negative reviews, website uptime, and algorithm updates.
"""

import io
import os
import datetime
from typing import Optional

import requests
from loguru import logger
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import (
    Mail, Attachment, FileContent, FileName, FileType, Disposition,
)
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, PageBreak, HRFlowable,
)
from reportlab.graphics.shapes import Drawing, Line
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.widgets.markers import makeMarker
from sqlalchemy import func, desc, and_, case
from sqlalchemy.orm import Session

from database.models import (
    Report, Alert, SEOMetric,
    Keyword, KeywordRanking, AISearchResult,
    Backlink, Review, TechnicalAudit,
    Competitor, CompetitorAnalysis, LocalCompetitor,
    SessionLocal,
)
from config.settings import (
    COMPANY, ALERTS, REPORT_CONFIG, SENDGRID_API_KEY, REPORTS_DIR,
)


# ---------------------------------------------------------------------------
# AlertManager
# ---------------------------------------------------------------------------

class AlertManager:
    """Create, query, and manage platform alerts."""

    def __init__(self, db: Optional[Session] = None):
        """Initialise with an optional database session.

        Args:
            db: SQLAlchemy session. A new session is created when *None*.
        """
        self._owns_session = db is None
        self.db: Session = db or SessionLocal()
        logger.debug("AlertManager initialised")

    # -- lifecycle -----------------------------------------------------------

    def close(self) -> None:
        """Close the database session if this instance owns it."""
        if self._owns_session:
            self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # -- core operations -----------------------------------------------------

    def create_alert(
        self,
        alert_type: str,
        severity: str,
        title: str,
        message: str,
        data: Optional[dict] = None,
    ) -> Alert:
        """Persist a new alert and return the ORM instance.

        Args:
            alert_type: Category such as ``ranking_drop``, ``competitor``,
                ``review``, ``uptime``, or ``algorithm``.
            severity: One of ``critical``, ``warning``, or ``info``.
            title: Short human-readable headline.
            message: Longer description of the event.
            data: Arbitrary JSON-serialisable payload.

        Returns:
            The newly created :class:`Alert` row.
        """
        alert = Alert(
            alert_type=alert_type,
            severity=severity,
            title=title,
            message=message,
            data=data or {},
            is_read=False,
            is_resolved=False,
        )
        self.db.add(alert)
        self.db.commit()
        self.db.refresh(alert)
        logger.info(
            "Alert created: [{}] {} - {}",
            severity.upper(),
            alert_type,
            title,
        )
        return alert

    def get_unread_alerts(self) -> list[Alert]:
        """Return every alert that has not yet been read.

        Returns:
            A list of :class:`Alert` objects ordered newest-first.
        """
        return (
            self.db.query(Alert)
            .filter(Alert.is_read == False)  # noqa: E712
            .order_by(desc(Alert.created_at))
            .all()
        )

    def mark_resolved(self, alert_id: int) -> Optional[Alert]:
        """Mark a single alert as resolved.

        Args:
            alert_id: Primary key of the alert.

        Returns:
            The updated :class:`Alert`, or *None* if not found.
        """
        alert = self.db.query(Alert).filter(Alert.id == alert_id).first()
        if alert is None:
            logger.warning("Alert id={} not found", alert_id)
            return None
        alert.is_read = True
        alert.is_resolved = True
        alert.resolved_at = datetime.datetime.utcnow()
        self.db.commit()
        self.db.refresh(alert)
        logger.info("Alert id={} marked resolved", alert_id)
        return alert

    def get_alerts_by_type(self, alert_type: str) -> list[Alert]:
        """Return all alerts that match *alert_type*.

        Args:
            alert_type: The category string to filter on.

        Returns:
            A list of matching :class:`Alert` rows, newest first.
        """
        return (
            self.db.query(Alert)
            .filter(Alert.alert_type == alert_type)
            .order_by(desc(Alert.created_at))
            .all()
        )

    def get_alert_summary(self) -> dict:
        """Aggregate unresolved alert counts by type and severity.

        Returns:
            A dict with ``by_type``, ``by_severity``, ``total_unresolved``,
            and ``total_unread`` tallies.
        """
        base = self.db.query(Alert).filter(Alert.is_resolved == False)  # noqa: E712

        by_type: dict[str, int] = {}
        for row in (
            base.with_entities(Alert.alert_type, func.count(Alert.id))
            .group_by(Alert.alert_type)
            .all()
        ):
            by_type[row[0]] = row[1]

        by_severity: dict[str, int] = {}
        for row in (
            base.with_entities(Alert.severity, func.count(Alert.id))
            .group_by(Alert.severity)
            .all()
        ):
            by_severity[row[0]] = row[1]

        total_unresolved = base.count()
        total_unread = (
            self.db.query(Alert)
            .filter(Alert.is_read == False)  # noqa: E712
            .count()
        )

        return {
            "by_type": by_type,
            "by_severity": by_severity,
            "total_unresolved": total_unresolved,
            "total_unread": total_unread,
        }


# ---------------------------------------------------------------------------
# ReportingEngine
# ---------------------------------------------------------------------------

class ReportingEngine:
    """Generate reports, run alert checks, and deliver results."""

    def __init__(self, db: Optional[Session] = None):
        """Initialise with an optional database session.

        Args:
            db: SQLAlchemy session. A new one is created when *None*.
        """
        self._owns_session = db is None
        self.db: Session = db or SessionLocal()
        self.alert_manager = AlertManager(db=self.db)
        logger.debug("ReportingEngine initialised")

    # -- lifecycle -----------------------------------------------------------

    def close(self) -> None:
        """Close resources owned by this instance."""
        if self._owns_session:
            self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # -- helpers -------------------------------------------------------------

    @staticmethod
    def _week_range() -> tuple[datetime.date, datetime.date]:
        """Return *(start, end)* for the past seven days."""
        end = datetime.date.today()
        start = end - datetime.timedelta(days=7)
        return start, end

    @staticmethod
    def _month_range() -> tuple[datetime.date, datetime.date]:
        """Return *(start, end)* for the past thirty days."""
        end = datetime.date.today()
        start = end - datetime.timedelta(days=30)
        return start, end

    # -----------------------------------------------------------------------
    # 1. Weekly SEO Report
    # -----------------------------------------------------------------------

    def generate_weekly_seo_report(self) -> dict:
        """Build and persist the weekly SEO performance report.

        Sections included:
        * Overall ranking summary (tracked keywords, positions, changes)
        * Top-10 keyword performance
        * Biggest movers -- gainers and losers
        * Traffic estimates
        * New backlinks discovered this week
        * Technical issues found
        * Recommended action items

        Returns:
            The full report payload as a structured dict.
        """
        start, end = self._week_range()
        prev_start = start - datetime.timedelta(days=7)
        logger.info(
            "Generating weekly SEO report for {} to {}", start, end,
        )

        # -- ranking summary -------------------------------------------------
        current_rankings = (
            self.db.query(KeywordRanking)
            .filter(
                KeywordRanking.tracked_date >= start,
                KeywordRanking.tracked_date <= end,
                KeywordRanking.search_engine == "google",
            )
            .all()
        )

        previous_rankings = (
            self.db.query(KeywordRanking)
            .filter(
                KeywordRanking.tracked_date >= prev_start,
                KeywordRanking.tracked_date < start,
                KeywordRanking.search_engine == "google",
            )
            .all()
        )

        prev_map: dict[int, int] = {}
        for r in previous_rankings:
            if r.keyword_id not in prev_map or (
                r.position is not None
                and (prev_map[r.keyword_id] is None or r.position < prev_map[r.keyword_id])
            ):
                prev_map[r.keyword_id] = r.position

        cur_map: dict[int, int] = {}
        for r in current_rankings:
            if r.keyword_id not in cur_map or (
                r.position is not None
                and (cur_map[r.keyword_id] is None or r.position < cur_map[r.keyword_id])
            ):
                cur_map[r.keyword_id] = r.position

        total_tracked = len(cur_map)
        in_top_3 = sum(1 for p in cur_map.values() if p is not None and p <= 3)
        in_top_10 = sum(1 for p in cur_map.values() if p is not None and p <= 10)
        in_top_20 = sum(1 for p in cur_map.values() if p is not None and p <= 20)

        avg_position = 0.0
        positioned = [p for p in cur_map.values() if p is not None]
        if positioned:
            avg_position = round(sum(positioned) / len(positioned), 1)

        ranking_summary = {
            "total_keywords_tracked": total_tracked,
            "in_top_3": in_top_3,
            "in_top_10": in_top_10,
            "in_top_20": in_top_20,
            "average_position": avg_position,
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
        }

        # -- top 10 keyword performance --------------------------------------
        keyword_performance: list[dict] = []
        for kid, pos in sorted(cur_map.items(), key=lambda x: (x[1] is None, x[1])):
            kw = self.db.query(Keyword).filter(Keyword.id == kid).first()
            if kw is None:
                continue
            prev_pos = prev_map.get(kid)
            change = None
            if pos is not None and prev_pos is not None:
                change = prev_pos - pos  # positive = improved
            keyword_performance.append({
                "keyword_id": kid,
                "keyword": kw.keyword,
                "current_position": pos,
                "previous_position": prev_pos,
                "change": change,
            })

        top_10_keywords = keyword_performance[:10]

        # -- biggest movers --------------------------------------------------
        movers = [kp for kp in keyword_performance if kp["change"] is not None]
        gainers = sorted(movers, key=lambda x: x["change"], reverse=True)[:5]
        losers = sorted(movers, key=lambda x: x["change"])[:5]

        # -- traffic estimates -----------------------------------------------
        latest_metric = (
            self.db.query(SEOMetric)
            .filter(SEOMetric.metric_date >= start, SEOMetric.metric_date <= end)
            .order_by(desc(SEOMetric.metric_date))
            .first()
        )
        prev_metric = (
            self.db.query(SEOMetric)
            .filter(SEOMetric.metric_date >= prev_start, SEOMetric.metric_date < start)
            .order_by(desc(SEOMetric.metric_date))
            .first()
        )

        traffic_estimates = {
            "organic_traffic": latest_metric.organic_traffic if latest_metric else 0,
            "organic_impressions": latest_metric.organic_impressions if latest_metric else 0,
            "organic_clicks": latest_metric.organic_clicks if latest_metric else 0,
            "traffic_change": (
                (latest_metric.organic_traffic or 0) - (prev_metric.organic_traffic or 0)
                if latest_metric and prev_metric
                else 0
            ),
        }

        # -- new backlinks ---------------------------------------------------
        new_backlinks = (
            self.db.query(Backlink)
            .filter(
                Backlink.first_seen >= start,
                Backlink.first_seen <= end,
            )
            .all()
        )
        backlink_data = [
            {
                "source_url": bl.source_url,
                "source_domain": bl.source_domain,
                "anchor_text": bl.anchor_text,
                "domain_authority": bl.domain_authority,
                "link_type": bl.link_type,
            }
            for bl in new_backlinks
        ]

        # -- technical issues ------------------------------------------------
        latest_audit = (
            self.db.query(TechnicalAudit)
            .order_by(desc(TechnicalAudit.audit_date))
            .first()
        )
        technical_issues = {
            "overall_score": latest_audit.overall_score if latest_audit else None,
            "issues_found": latest_audit.issues_found if latest_audit else 0,
            "critical_issues": latest_audit.critical_issues if latest_audit else 0,
            "warnings": latest_audit.warnings if latest_audit else 0,
        }

        # -- action items ----------------------------------------------------
        action_items: list[str] = []
        if losers:
            worst = losers[0]
            action_items.append(
                f"Investigate ranking drop for '{worst['keyword']}' "
                f"(dropped {abs(worst['change'])} positions)."
            )
        if technical_issues["critical_issues"] and technical_issues["critical_issues"] > 0:
            action_items.append(
                f"Resolve {technical_issues['critical_issues']} critical technical "
                "issues found in the latest audit."
            )
        neg_reviews = (
            self.db.query(Review)
            .filter(Review.rating <= ALERTS["negative_review_threshold"])
            .filter(Review.needs_response == True)  # noqa: E712
            .count()
        )
        if neg_reviews > 0:
            action_items.append(
                f"Respond to {neg_reviews} negative review(s) awaiting a reply."
            )
        if not backlink_data:
            action_items.append(
                "No new backlinks this week -- consider outreach to "
                "legal directories and notary associations."
            )
        if not action_items:
            action_items.append(
                "All metrics look healthy. Continue current SEO strategy."
            )

        # -- assemble report -------------------------------------------------
        report_data: dict = {
            "report_type": "weekly_seo",
            "generated_at": datetime.datetime.utcnow().isoformat(),
            "period": {"start": start.isoformat(), "end": end.isoformat()},
            "ranking_summary": ranking_summary,
            "top_10_keywords": top_10_keywords,
            "biggest_movers": {"gainers": gainers, "losers": losers},
            "traffic_estimates": traffic_estimates,
            "new_backlinks": backlink_data,
            "technical_issues": technical_issues,
            "action_items": action_items,
        }

        # persist
        report_row = Report(
            report_type="weekly_seo",
            report_date=end,
            title=f"Weekly SEO Report: {start.isoformat()} to {end.isoformat()}",
            summary=(
                f"Tracked {total_tracked} keywords. "
                f"{in_top_10} in top 10. Avg position {avg_position}. "
                f"{len(backlink_data)} new backlinks."
            ),
            data=report_data,
        )
        self.db.add(report_row)
        self.db.commit()
        self.db.refresh(report_row)
        logger.info(
            "Weekly SEO report saved (id={})", report_row.id,
        )
        return report_data

    # -----------------------------------------------------------------------
    # 2. Monthly AI Report
    # -----------------------------------------------------------------------

    def generate_monthly_ai_report(self) -> dict:
        """Build and persist the monthly AI search visibility report.

        Sections included:
        * AI engine visibility scores by platform
        * Company mentions across ChatGPT, Perplexity, Google AI,
          Bing Copilot, and Claude
        * Competitor comparison in AI results
        * AI optimisation recommendations
        * Trends over time

        Returns:
            The full report payload as a structured dict.
        """
        start, end = self._month_range()
        prev_start = start - datetime.timedelta(days=30)
        logger.info(
            "Generating monthly AI report for {} to {}", start, end,
        )

        ai_engines = ["ChatGPT", "Perplexity", "Google AI Overview", "Bing Copilot", "Claude"]

        # -- per-engine visibility -------------------------------------------
        engine_scores: dict[str, dict] = {}
        for engine in ai_engines:
            results = (
                self.db.query(AISearchResult)
                .filter(
                    AISearchResult.ai_engine == engine,
                    AISearchResult.tracked_date >= start,
                    AISearchResult.tracked_date <= end,
                )
                .all()
            )
            total = len(results)
            mentions = sum(1 for r in results if r.mentions_company)
            positive = sum(1 for r in results if r.sentiment == "positive")
            neutral = sum(1 for r in results if r.sentiment == "neutral")
            negative = sum(1 for r in results if r.sentiment == "negative")
            visibility_score = round((mentions / total) * 100, 1) if total else 0.0
            positions = [r.position_in_response for r in results if r.position_in_response is not None]
            avg_position = round(sum(positions) / len(positions), 1) if positions else None

            engine_scores[engine] = {
                "total_queries_tracked": total,
                "company_mentions": mentions,
                "visibility_score": visibility_score,
                "average_position": avg_position,
                "sentiment": {
                    "positive": positive,
                    "neutral": neutral,
                    "negative": negative,
                },
            }

        # -- aggregate mentions across all engines ---------------------------
        all_results = (
            self.db.query(AISearchResult)
            .filter(
                AISearchResult.tracked_date >= start,
                AISearchResult.tracked_date <= end,
            )
            .all()
        )
        total_queries = len(all_results)
        total_mentions = sum(1 for r in all_results if r.mentions_company)
        overall_visibility = round((total_mentions / total_queries) * 100, 1) if total_queries else 0.0

        # -- competitor comparison -------------------------------------------
        competitor_mentions: dict[str, int] = {}
        for result in all_results:
            if result.competitor_mentions:
                for comp in result.competitor_mentions:
                    competitor_mentions[comp] = competitor_mentions.get(comp, 0) + 1

        competitor_comparison = sorted(
            [{"name": name, "mentions": count} for name, count in competitor_mentions.items()],
            key=lambda x: x["mentions"],
            reverse=True,
        )

        # -- trends over time (weekly buckets) -------------------------------
        trends: list[dict] = []
        cursor = start
        while cursor < end:
            bucket_end = min(cursor + datetime.timedelta(days=7), end)
            bucket = (
                self.db.query(AISearchResult)
                .filter(
                    AISearchResult.tracked_date >= cursor,
                    AISearchResult.tracked_date < bucket_end,
                )
                .all()
            )
            bucket_total = len(bucket)
            bucket_mentions = sum(1 for r in bucket if r.mentions_company)
            trends.append({
                "week_start": cursor.isoformat(),
                "total_queries": bucket_total,
                "company_mentions": bucket_mentions,
                "visibility_pct": (
                    round((bucket_mentions / bucket_total) * 100, 1) if bucket_total else 0.0
                ),
            })
            cursor = bucket_end

        # -- previous month for comparison -----------------------------------
        prev_results = (
            self.db.query(AISearchResult)
            .filter(
                AISearchResult.tracked_date >= prev_start,
                AISearchResult.tracked_date < start,
            )
            .all()
        )
        prev_total = len(prev_results)
        prev_mentions = sum(1 for r in prev_results if r.mentions_company)
        prev_visibility = round((prev_mentions / prev_total) * 100, 1) if prev_total else 0.0
        visibility_change = round(overall_visibility - prev_visibility, 1)

        # -- recommendations -------------------------------------------------
        recommendations: list[str] = []
        for engine, stats in engine_scores.items():
            if stats["visibility_score"] == 0.0 and stats["total_queries_tracked"] > 0:
                recommendations.append(
                    f"Not appearing in {engine} results. Improve structured "
                    "data and authoritative content to gain visibility."
                )
            elif stats["visibility_score"] < 30.0 and stats["total_queries_tracked"] > 0:
                recommendations.append(
                    f"Low visibility in {engine} ({stats['visibility_score']}%). "
                    "Add FAQ schema and expand topical authority content."
                )
            if stats["sentiment"]["negative"] > stats["sentiment"]["positive"]:
                recommendations.append(
                    f"Negative sentiment dominant in {engine}. Review and "
                    "update cited content to improve brand perception."
                )
        if visibility_change < 0:
            recommendations.append(
                f"Overall AI visibility declined by {abs(visibility_change)}% "
                "compared to last month. Audit content freshness and "
                "structured data accuracy."
            )
        if not recommendations:
            recommendations.append(
                "AI visibility is strong across all platforms. "
                "Continue current optimisation strategy."
            )

        # -- assemble --------------------------------------------------------
        report_data: dict = {
            "report_type": "monthly_ai",
            "generated_at": datetime.datetime.utcnow().isoformat(),
            "period": {"start": start.isoformat(), "end": end.isoformat()},
            "overall": {
                "total_queries_tracked": total_queries,
                "total_company_mentions": total_mentions,
                "visibility_score": overall_visibility,
                "previous_visibility_score": prev_visibility,
                "visibility_change": visibility_change,
            },
            "engine_scores": engine_scores,
            "competitor_comparison": competitor_comparison,
            "trends": trends,
            "recommendations": recommendations,
        }

        report_row = Report(
            report_type="monthly_ai",
            report_date=end,
            title=f"Monthly AI Visibility Report: {start.isoformat()} to {end.isoformat()}",
            summary=(
                f"Overall AI visibility: {overall_visibility}% "
                f"({visibility_change:+.1f}% vs prior month). "
                f"{total_mentions}/{total_queries} queries mentioned company."
            ),
            data=report_data,
        )
        self.db.add(report_row)
        self.db.commit()
        self.db.refresh(report_row)
        logger.info("Monthly AI report saved (id={})", report_row.id)
        return report_data

    # -----------------------------------------------------------------------
    # 3. PDF Report Generation
    # -----------------------------------------------------------------------

    def generate_pdf_report(
        self,
        report_data: dict,
        report_type: str,
    ) -> str:
        """Render *report_data* as a branded PDF document.

        The PDF includes:
        * Common Notary Apostille header / branding
        * Executive summary
        * Trend charts and bar graphs
        * Detailed data tables
        * Recommendations section
        * Date-range and report metadata footer

        Args:
            report_data: The structured dict returned by one of the
                ``generate_*`` methods.
            report_type: A label such as ``weekly_seo`` or ``monthly_ai``.

        Returns:
            The absolute file-system path to the saved PDF.
        """
        today = datetime.date.today().isoformat()
        safe_type = report_type.replace(" ", "_")
        filename = f"{safe_type}_report_{today}.pdf"
        filepath = os.path.join(str(REPORTS_DIR), filename)

        logger.info("Generating PDF report: {}", filepath)

        doc = SimpleDocTemplate(
            filepath,
            pagesize=letter,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            rightMargin=0.75 * inch,
        )

        styles = getSampleStyleSheet()

        # -- custom styles ---------------------------------------------------
        styles.add(ParagraphStyle(
            name="BrandHeader",
            parent=styles["Title"],
            fontSize=22,
            textColor=colors.HexColor("#1a3a5c"),
            spaceAfter=4,
        ))
        styles.add(ParagraphStyle(
            name="BrandSubHeader",
            parent=styles["Heading2"],
            fontSize=12,
            textColor=colors.HexColor("#4a7ab5"),
            spaceAfter=12,
        ))
        styles.add(ParagraphStyle(
            name="SectionTitle",
            parent=styles["Heading2"],
            fontSize=14,
            textColor=colors.HexColor("#1a3a5c"),
            spaceBefore=16,
            spaceAfter=8,
        ))
        styles.add(ParagraphStyle(
            name="RecommendationItem",
            parent=styles["BodyText"],
            fontSize=10,
            leftIndent=20,
            bulletIndent=10,
            spaceAfter=4,
        ))

        elements: list = []

        # -- branding header -------------------------------------------------
        elements.append(Paragraph(COMPANY["name"], styles["BrandHeader"]))
        elements.append(Paragraph(
            f"{report_type.replace('_', ' ').title()} Report",
            styles["BrandSubHeader"],
        ))
        period = report_data.get("period", {})
        elements.append(Paragraph(
            f"Period: {period.get('start', 'N/A')} to {period.get('end', 'N/A')} "
            f"&nbsp;&nbsp;|&nbsp;&nbsp; Generated: {report_data.get('generated_at', today)}",
            styles["Normal"],
        ))
        elements.append(HRFlowable(
            width="100%", thickness=1,
            color=colors.HexColor("#1a3a5c"),
            spaceAfter=16,
        ))

        # -- executive summary -----------------------------------------------
        elements.append(Paragraph("Executive Summary", styles["SectionTitle"]))
        summary_lines = self._build_executive_summary(report_data, report_type)
        for line in summary_lines:
            elements.append(Paragraph(line, styles["BodyText"]))
        elements.append(Spacer(1, 12))

        # -- charts ----------------------------------------------------------
        chart_drawing = self._build_chart(report_data, report_type)
        if chart_drawing is not None:
            elements.append(Paragraph("Performance Trends", styles["SectionTitle"]))
            elements.append(chart_drawing)
            elements.append(Spacer(1, 12))

        # -- data tables -----------------------------------------------------
        table_obj = self._build_data_table(report_data, report_type)
        if table_obj is not None:
            elements.append(Paragraph("Detailed Data", styles["SectionTitle"]))
            elements.append(table_obj)
            elements.append(Spacer(1, 12))

        # -- recommendations -------------------------------------------------
        recs = report_data.get("recommendations") or report_data.get("action_items") or []
        if recs:
            elements.append(Paragraph("Recommendations", styles["SectionTitle"]))
            for idx, rec in enumerate(recs, 1):
                elements.append(Paragraph(
                    f"{idx}. {rec}",
                    styles["RecommendationItem"],
                ))
            elements.append(Spacer(1, 12))

        # -- metadata footer -------------------------------------------------
        elements.append(HRFlowable(
            width="100%", thickness=0.5,
            color=colors.HexColor("#cccccc"),
            spaceBefore=20,
            spaceAfter=8,
        ))
        elements.append(Paragraph(
            f"Report generated by {COMPANY['name']} SEO Monitoring Platform "
            f"&nbsp;|&nbsp; {COMPANY.get('website', '')} &nbsp;|&nbsp; {today}",
            ParagraphStyle(
                name="_footer",
                parent=styles["Normal"],
                fontSize=8,
                textColor=colors.grey,
            ),
        ))

        doc.build(elements)

        # update report row in the database if available
        report_row = (
            self.db.query(Report)
            .filter(
                Report.report_type == report_type,
                Report.report_date == datetime.date.today(),
            )
            .order_by(desc(Report.id))
            .first()
        )
        if report_row:
            report_row.file_path = filepath
            self.db.commit()

        logger.info("PDF report saved to {}", filepath)
        return filepath

    # -- PDF helper: executive summary text ----------------------------------

    @staticmethod
    def _build_executive_summary(data: dict, report_type: str) -> list[str]:
        """Return a list of summary sentences for the PDF."""
        lines: list[str] = []
        if report_type == "weekly_seo":
            rs = data.get("ranking_summary", {})
            te = data.get("traffic_estimates", {})
            bl = data.get("new_backlinks", [])
            lines.append(
                f"This week we tracked <b>{rs.get('total_keywords_tracked', 0)}</b> keywords. "
                f"<b>{rs.get('in_top_10', 0)}</b> rank in the top 10 with an average "
                f"position of <b>{rs.get('average_position', 'N/A')}</b>."
            )
            lines.append(
                f"Estimated organic traffic: <b>{te.get('organic_traffic', 0):,}</b> "
                f"(change: {te.get('traffic_change', 0):+,})."
            )
            lines.append(
                f"<b>{len(bl)}</b> new backlinks were discovered during the period."
            )
        elif report_type == "monthly_ai":
            ov = data.get("overall", {})
            lines.append(
                f"Overall AI visibility score: <b>{ov.get('visibility_score', 0)}%</b> "
                f"({ov.get('visibility_change', 0):+.1f}% vs. prior month)."
            )
            lines.append(
                f"Company was mentioned in <b>{ov.get('total_company_mentions', 0)}</b> "
                f"out of <b>{ov.get('total_queries_tracked', 0)}</b> tracked queries."
            )
        else:
            lines.append("Detailed report data follows.")
        return lines

    # -- PDF helper: chart ---------------------------------------------------

    @staticmethod
    def _build_chart(data: dict, report_type: str) -> Optional[Drawing]:
        """Create a reportlab Drawing with a trend chart if data permits."""
        if report_type == "weekly_seo":
            top_kw = data.get("top_10_keywords", [])
            if not top_kw:
                return None
            drawing = Drawing(500, 200)
            chart = VerticalBarChart()
            chart.x = 30
            chart.y = 30
            chart.width = 440
            chart.height = 140

            positions = [kw.get("current_position") or 0 for kw in top_kw]
            chart.data = [positions]
            chart.categoryAxis.categoryNames = [
                (kw.get("keyword", "")[:18] + "..") if len(kw.get("keyword", "")) > 20 else kw.get("keyword", "")
                for kw in top_kw
            ]
            chart.categoryAxis.labels.angle = 30
            chart.categoryAxis.labels.fontSize = 7
            chart.categoryAxis.labels.dy = -10
            chart.valueAxis.valueMin = 0
            chart.valueAxis.valueMax = max(positions + [10]) + 5
            chart.valueAxis.valueStep = 5
            chart.bars[0].fillColor = colors.HexColor("#4a7ab5")
            drawing.add(chart)
            return drawing

        if report_type == "monthly_ai":
            trends = data.get("trends", [])
            if not trends:
                return None
            drawing = Drawing(500, 200)
            lp = LinePlot()
            lp.x = 50
            lp.y = 30
            lp.width = 420
            lp.height = 140
            lp.data = [
                [(i, t.get("visibility_pct", 0)) for i, t in enumerate(trends)]
            ]
            lp.lines[0].strokeColor = colors.HexColor("#4a7ab5")
            lp.lines[0].strokeWidth = 2
            lp.lines[0].symbol = makeMarker("FilledCircle")
            lp.xValueAxis.valueMin = 0
            lp.xValueAxis.valueMax = max(len(trends) - 1, 1)
            lp.xValueAxis.valueStep = 1
            lp.yValueAxis.valueMin = 0
            lp.yValueAxis.valueMax = 100
            drawing.add(lp)
            return drawing

        return None

    # -- PDF helper: data table ----------------------------------------------

    @staticmethod
    def _build_data_table(data: dict, report_type: str) -> Optional[Table]:
        """Create a reportlab Table for the main data section."""
        if report_type == "weekly_seo":
            rows = data.get("top_10_keywords", [])
            if not rows:
                return None
            table_data = [["Keyword", "Position", "Previous", "Change"]]
            for kw in rows:
                change_val = kw.get("change")
                change_str = "N/A"
                if change_val is not None:
                    change_str = f"+{change_val}" if change_val > 0 else str(change_val)
                table_data.append([
                    kw.get("keyword", "")[:40],
                    str(kw.get("current_position") or "N/R"),
                    str(kw.get("previous_position") or "N/R"),
                    change_str,
                ])

        elif report_type == "monthly_ai":
            engine_scores = data.get("engine_scores", {})
            if not engine_scores:
                return None
            table_data = [["AI Engine", "Queries", "Mentions", "Visibility %", "Avg Pos"]]
            for engine, stats in engine_scores.items():
                table_data.append([
                    engine,
                    str(stats.get("total_queries_tracked", 0)),
                    str(stats.get("company_mentions", 0)),
                    f"{stats.get('visibility_score', 0)}%",
                    str(stats.get("average_position") or "N/A"),
                ])
        else:
            return None

        tbl = Table(table_data, hAlign="LEFT")
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3a5c")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("FONTSIZE", (0, 1), (-1, -1), 8),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f6fa")]),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        return tbl

    # -----------------------------------------------------------------------
    # 4. Email Delivery
    # -----------------------------------------------------------------------

    def send_email_report(
        self,
        report_path: str,
        recipients: list[str],
    ) -> bool:
        """Send *report_path* as an email attachment via SendGrid.

        Args:
            report_path: Path to the PDF file on disk.
            recipients: List of email addresses to deliver to.

        Returns:
            *True* when the email was accepted by the SendGrid API.
        """
        if not SENDGRID_API_KEY:
            logger.error("SENDGRID_API_KEY is not configured; cannot send email")
            return False

        if not os.path.isfile(report_path):
            logger.error("Report file not found: {}", report_path)
            return False

        filename = os.path.basename(report_path)
        subject = f"{COMPANY['name']} - {filename.replace('_', ' ').replace('.pdf', '').title()}"

        try:
            import base64

            with open(report_path, "rb") as fh:
                encoded_file = base64.b64encode(fh.read()).decode()

            attachment = Attachment(
                FileContent(encoded_file),
                FileName(filename),
                FileType("application/pdf"),
                Disposition("attachment"),
            )

            from_email = COMPANY.get("email") or "reports@commonnotaryapostille.com"
            message = Mail(
                from_email=from_email,
                to_emails=recipients,
                subject=subject,
                html_content=(
                    f"<p>Hello,</p>"
                    f"<p>Please find attached the latest report from "
                    f"<b>{COMPANY['name']}</b>.</p>"
                    f"<p>This is an automated message from the SEO Monitoring Platform.</p>"
                    f"<p>Best regards,<br/>{COMPANY['name']} SEO Team</p>"
                ),
            )
            message.attachment = attachment

            sg = SendGridAPIClient(SENDGRID_API_KEY)
            response = sg.send(message)

            if response.status_code in (200, 202):
                logger.info(
                    "Email sent to {} (status {})",
                    recipients,
                    response.status_code,
                )
                # flag in DB
                report_row = (
                    self.db.query(Report)
                    .filter(Report.file_path == report_path)
                    .first()
                )
                if report_row:
                    report_row.email_sent = True
                    self.db.commit()
                return True

            logger.warning(
                "SendGrid returned status {} for {}",
                response.status_code,
                recipients,
            )
            return False

        except Exception as exc:
            logger.exception("Failed to send email report: {}", exc)
            return False

    # -----------------------------------------------------------------------
    # 5. Ranking Alerts
    # -----------------------------------------------------------------------

    def check_ranking_alerts(self) -> list[Alert]:
        """Detect keywords that dropped more than the configured threshold.

        Compares the most recent ranking for each keyword against the
        previous week. Any drop exceeding
        ``ALERTS['ranking_drop_threshold']`` positions generates a
        warning-level alert.

        Returns:
            A list of newly created :class:`Alert` objects.
        """
        threshold = ALERTS.get("ranking_drop_threshold", 5)
        start, end = self._week_range()
        prev_start = start - datetime.timedelta(days=7)
        logger.info("Checking ranking alerts (threshold={})", threshold)

        current = (
            self.db.query(KeywordRanking)
            .filter(
                KeywordRanking.tracked_date >= start,
                KeywordRanking.tracked_date <= end,
                KeywordRanking.search_engine == "google",
            )
            .all()
        )
        previous = (
            self.db.query(KeywordRanking)
            .filter(
                KeywordRanking.tracked_date >= prev_start,
                KeywordRanking.tracked_date < start,
                KeywordRanking.search_engine == "google",
            )
            .all()
        )

        prev_map: dict[int, int] = {}
        for r in previous:
            if r.position is not None:
                existing = prev_map.get(r.keyword_id)
                if existing is None or r.position < existing:
                    prev_map[r.keyword_id] = r.position

        cur_map: dict[int, int] = {}
        for r in current:
            if r.position is not None:
                existing = cur_map.get(r.keyword_id)
                if existing is None or r.position < existing:
                    cur_map[r.keyword_id] = r.position

        new_alerts: list[Alert] = []
        for kid, cur_pos in cur_map.items():
            prev_pos = prev_map.get(kid)
            if prev_pos is None:
                continue
            drop = cur_pos - prev_pos  # positive means rank worsened
            if drop > threshold:
                kw = self.db.query(Keyword).filter(Keyword.id == kid).first()
                keyword_text = kw.keyword if kw else f"keyword_id={kid}"
                alert = self.alert_manager.create_alert(
                    alert_type="ranking_drop",
                    severity="warning",
                    title=f"Ranking drop for '{keyword_text}'",
                    message=(
                        f"'{keyword_text}' dropped {drop} positions "
                        f"(from #{prev_pos} to #{cur_pos})."
                    ),
                    data={
                        "keyword_id": kid,
                        "keyword": keyword_text,
                        "previous_position": prev_pos,
                        "current_position": cur_pos,
                        "drop": drop,
                    },
                )
                new_alerts.append(alert)

        logger.info("Ranking alert check complete: {} alerts", len(new_alerts))
        return new_alerts

    # -----------------------------------------------------------------------
    # 6. Competitor Alerts
    # -----------------------------------------------------------------------

    def check_competitor_alerts(self) -> list[Alert]:
        """Alert when a previously-unseen competitor enters the top results.

        Examines the most recent :class:`KeywordRanking` rows for domains
        that are not in the :class:`Competitor` or :class:`LocalCompetitor`
        tables and that rank in the top 10.

        Returns:
            Newly created :class:`Alert` objects.
        """
        logger.info("Checking competitor alerts")
        start, end = self._week_range()

        known_domains: set[str] = set()
        for comp in self.db.query(Competitor).all():
            if comp.domain:
                known_domains.add(comp.domain.lower().replace("www.", ""))
        for lc in self.db.query(LocalCompetitor).all():
            if lc.website:
                from urllib.parse import urlparse
                known_domains.add(
                    urlparse(lc.website).netloc.lower().replace("www.", "")
                )

        our_domain = COMPANY.get("website", "").replace("https://", "").replace("http://", "").replace("www.", "").rstrip("/")
        known_domains.add(our_domain)

        recent_rankings = (
            self.db.query(KeywordRanking)
            .filter(
                KeywordRanking.tracked_date >= start,
                KeywordRanking.tracked_date <= end,
                KeywordRanking.position != None,  # noqa: E711
                KeywordRanking.position <= 10,
            )
            .all()
        )

        new_domains_seen: dict[str, list[str]] = {}
        for r in recent_rankings:
            if not r.url_found:
                continue
            from urllib.parse import urlparse
            domain = urlparse(r.url_found).netloc.lower().replace("www.", "")
            if domain and domain not in known_domains:
                kw = self.db.query(Keyword).filter(Keyword.id == r.keyword_id).first()
                keyword_text = kw.keyword if kw else f"keyword_id={r.keyword_id}"
                new_domains_seen.setdefault(domain, []).append(keyword_text)

        new_alerts: list[Alert] = []
        for domain, keywords in new_domains_seen.items():
            alert = self.alert_manager.create_alert(
                alert_type="competitor",
                severity="info",
                title=f"New competitor detected: {domain}",
                message=(
                    f"{domain} appeared in the top 10 for "
                    f"{len(keywords)} keyword(s): {', '.join(keywords[:5])}."
                ),
                data={"domain": domain, "keywords": keywords},
            )
            new_alerts.append(alert)

        logger.info("Competitor alert check complete: {} alerts", len(new_alerts))
        return new_alerts

    # -----------------------------------------------------------------------
    # 7. Review Alerts
    # -----------------------------------------------------------------------

    def check_review_alerts(self) -> list[Alert]:
        """Alert on new negative reviews (rated at or below the threshold).

        Reviews that have already triggered an alert are skipped by
        checking for existing alerts with matching review data.

        Returns:
            Newly created :class:`Alert` objects.
        """
        threshold = ALERTS.get("negative_review_threshold", 3)
        logger.info("Checking review alerts (threshold={})", threshold)

        negative_reviews = (
            self.db.query(Review)
            .filter(Review.rating <= threshold, Review.rating != None)  # noqa: E711
            .order_by(desc(Review.created_at))
            .limit(50)
            .all()
        )

        existing_alert_review_ids: set[int] = set()
        for a in self.alert_manager.get_alerts_by_type("review"):
            rid = (a.data or {}).get("review_id")
            if rid is not None:
                existing_alert_review_ids.add(rid)

        new_alerts: list[Alert] = []
        for review in negative_reviews:
            if review.id in existing_alert_review_ids:
                continue
            severity = "critical" if review.rating <= 1 else "warning"
            alert = self.alert_manager.create_alert(
                alert_type="review",
                severity=severity,
                title=(
                    f"Negative review ({review.rating} stars) on "
                    f"{review.platform}"
                ),
                message=(
                    f"Reviewer '{review.reviewer_name or 'Anonymous'}' left a "
                    f"{review.rating}-star review on {review.platform}: "
                    f"\"{(review.review_text or '')[:200]}\""
                ),
                data={
                    "review_id": review.id,
                    "platform": review.platform,
                    "rating": review.rating,
                    "reviewer_name": review.reviewer_name,
                    "needs_response": review.needs_response,
                },
            )
            new_alerts.append(alert)

        logger.info("Review alert check complete: {} alerts", len(new_alerts))
        return new_alerts

    # -----------------------------------------------------------------------
    # 8. Website Uptime
    # -----------------------------------------------------------------------

    def check_website_uptime(self, url: Optional[str] = None) -> dict:
        """Perform an HTTP health check on *url* and alert on failure.

        Args:
            url: The URL to check. Defaults to the company website.

        Returns:
            A dict with ``url``, ``is_up``, ``status_code``, and
            ``response_time_ms``.
        """
        url = url or COMPANY.get("website", "https://commonnotaryapostille.com")
        logger.info("Checking uptime for {}", url)

        result: dict = {
            "url": url,
            "is_up": False,
            "status_code": None,
            "response_time_ms": None,
            "checked_at": datetime.datetime.utcnow().isoformat(),
        }

        try:
            resp = requests.get(url, timeout=30, allow_redirects=True)
            result["status_code"] = resp.status_code
            result["response_time_ms"] = round(resp.elapsed.total_seconds() * 1000)
            result["is_up"] = resp.status_code < 400
        except requests.ConnectionError:
            result["error"] = "Connection refused or DNS failure"
        except requests.Timeout:
            result["error"] = "Request timed out after 30 seconds"
        except requests.RequestException as exc:
            result["error"] = str(exc)

        if not result["is_up"]:
            self.alert_manager.create_alert(
                alert_type="uptime",
                severity="critical",
                title=f"Website DOWN: {url}",
                message=(
                    f"{url} returned status {result.get('status_code')} "
                    f"or failed to respond. Error: {result.get('error', 'N/A')}"
                ),
                data=result,
            )

        logger.info(
            "Uptime check for {}: up={}, status={}, time={}ms",
            url,
            result["is_up"],
            result["status_code"],
            result["response_time_ms"],
        )
        return result

    # -----------------------------------------------------------------------
    # 9. Algorithm Update Detection
    # -----------------------------------------------------------------------

    def check_algorithm_updates(self) -> list[Alert]:
        """Scrape public SEO news feeds for Google algorithm update announcements.

        Uses the Search Engine Roundtable RSS feed as a lightweight
        heuristic check.  Any entry whose title contains algorithm-related
        keywords will generate an informational alert.

        Returns:
            Newly created :class:`Alert` objects.
        """
        logger.info("Checking for Google algorithm updates")
        feed_url = "https://www.seroundtable.com/feed"
        algo_keywords = [
            "algorithm", "core update", "google update", "ranking update",
            "search update", "spam update", "helpful content",
        ]

        new_alerts: list[Alert] = []
        try:
            resp = requests.get(feed_url, timeout=20)
            resp.raise_for_status()

            from xml.etree import ElementTree
            root = ElementTree.fromstring(resp.content)

            existing_titles: set[str] = {
                (a.data or {}).get("title", "")
                for a in self.alert_manager.get_alerts_by_type("algorithm")
            }

            for item in root.iter("item"):
                title_el = item.find("title")
                link_el = item.find("link")
                pub_el = item.find("pubDate")
                if title_el is None:
                    continue
                title_text = title_el.text or ""
                if title_text in existing_titles:
                    continue
                if any(kw in title_text.lower() for kw in algo_keywords):
                    alert = self.alert_manager.create_alert(
                        alert_type="algorithm",
                        severity="info",
                        title=f"Algorithm news: {title_text[:120]}",
                        message=(
                            f"Potential algorithm update detected: \"{title_text}\". "
                            f"Link: {link_el.text if link_el is not None else 'N/A'}. "
                            f"Published: {pub_el.text if pub_el is not None else 'N/A'}."
                        ),
                        data={
                            "title": title_text,
                            "link": link_el.text if link_el is not None else None,
                            "pub_date": pub_el.text if pub_el is not None else None,
                        },
                    )
                    new_alerts.append(alert)

        except Exception as exc:
            logger.exception("Error checking algorithm updates: {}", exc)

        logger.info("Algorithm update check complete: {} alerts", len(new_alerts))
        return new_alerts

    # -----------------------------------------------------------------------
    # 10. Process All Alerts
    # -----------------------------------------------------------------------

    def process_all_alerts(self) -> dict:
        """Run every alert check and return a combined summary.

        Runs:
        1. Ranking drop alerts
        2. Competitor alerts
        3. Review alerts
        4. Website uptime check
        5. Algorithm update check

        Critical and warning alerts are emailed to the configured
        recipients automatically.

        Returns:
            A summary dict with counts and alert details per category.
        """
        logger.info("Running full alert pipeline")

        ranking_alerts = self.check_ranking_alerts()
        competitor_alerts = self.check_competitor_alerts()
        review_alerts = self.check_review_alerts()
        uptime_result = self.check_website_uptime()
        algorithm_alerts = self.check_algorithm_updates()

        all_new: list[Alert] = (
            ranking_alerts + competitor_alerts + review_alerts + algorithm_alerts
        )

        # email urgent alerts
        urgent = [a for a in all_new if a.severity in ("critical", "warning")]
        if urgent:
            recipients = [
                r.strip()
                for r in REPORT_CONFIG.get("email_recipients", [])
                if r.strip()
            ]
            if recipients and SENDGRID_API_KEY:
                self._send_alert_email(urgent, recipients)

        summary = {
            "processed_at": datetime.datetime.utcnow().isoformat(),
            "ranking_alerts": len(ranking_alerts),
            "competitor_alerts": len(competitor_alerts),
            "review_alerts": len(review_alerts),
            "uptime": uptime_result,
            "algorithm_alerts": len(algorithm_alerts),
            "total_new_alerts": len(all_new),
            "urgent_emailed": len(urgent),
        }

        logger.info(
            "Alert pipeline complete: {} total, {} urgent emailed",
            len(all_new),
            len(urgent),
        )
        return summary

    def _send_alert_email(self, alerts: list[Alert], recipients: list[str]) -> bool:
        """Fire a digest email for a batch of urgent alerts."""
        if not SENDGRID_API_KEY:
            return False
        try:
            rows = "".join(
                f"<tr><td style='padding:4px 8px'>{a.severity.upper()}</td>"
                f"<td style='padding:4px 8px'>{a.alert_type}</td>"
                f"<td style='padding:4px 8px'>{a.title}</td></tr>"
                for a in alerts
            )
            html = (
                f"<h2>{COMPANY['name']} - Alert Notification</h2>"
                f"<p>{len(alerts)} new alert(s) require your attention:</p>"
                f"<table border='1' cellpadding='0' cellspacing='0' "
                f"style='border-collapse:collapse'>"
                f"<tr style='background:#1a3a5c;color:#fff'>"
                f"<th style='padding:6px 8px'>Severity</th>"
                f"<th style='padding:6px 8px'>Type</th>"
                f"<th style='padding:6px 8px'>Title</th></tr>"
                f"{rows}</table>"
                f"<p>Log in to the SEO Monitoring Dashboard for details.</p>"
                f"<p>&mdash; {COMPANY['name']} SEO Team</p>"
            )

            from_email = COMPANY.get("email") or "alerts@commonnotaryapostille.com"
            message = Mail(
                from_email=from_email,
                to_emails=recipients,
                subject=f"[{COMPANY['name']}] {len(alerts)} new SEO alert(s)",
                html_content=html,
            )
            sg = SendGridAPIClient(SENDGRID_API_KEY)
            response = sg.send(message)
            logger.info(
                "Alert email sent to {} (status {})", recipients, response.status_code,
            )
            return response.status_code in (200, 202)

        except Exception as exc:
            logger.exception("Failed to send alert email: {}", exc)
            return False

    # -----------------------------------------------------------------------
    # 11. ROI Metrics
    # -----------------------------------------------------------------------

    def get_roi_metrics(self, period: str = "month") -> dict:
        """Compute ROI metrics connecting SEO efforts to leads and revenue.

        Args:
            period: One of ``week``, ``month``, or ``quarter``.

        Returns:
            A dict containing traffic, leads, conversions, revenue,
            and conversion rates for the requested window plus
            comparison to the prior window.
        """
        days = {"week": 7, "month": 30, "quarter": 90}.get(period, 30)
        end = datetime.date.today()
        start = end - datetime.timedelta(days=days)
        prev_start = start - datetime.timedelta(days=days)
        logger.info("Computing ROI metrics for period={} ({} to {})", period, start, end)

        def _agg(from_date: datetime.date, to_date: datetime.date) -> dict:
            rows = (
                self.db.query(SEOMetric)
                .filter(
                    SEOMetric.metric_date >= from_date,
                    SEOMetric.metric_date <= to_date,
                )
                .all()
            )
            if not rows:
                return {
                    "organic_traffic": 0,
                    "leads": 0,
                    "conversions": 0,
                    "revenue": 0.0,
                    "avg_position": 0.0,
                    "keywords_top_10": 0,
                    "total_backlinks": 0,
                    "domain_authority": 0,
                }
            return {
                "organic_traffic": sum(r.organic_traffic or 0 for r in rows),
                "leads": sum(r.leads_generated or 0 for r in rows),
                "conversions": sum(r.conversions or 0 for r in rows),
                "revenue": round(sum(r.revenue_attributed or 0.0 for r in rows), 2),
                "avg_position": round(
                    sum(r.average_position or 0.0 for r in rows) / len(rows), 1
                ),
                "keywords_top_10": max(
                    (r.keywords_in_top_10 or 0 for r in rows), default=0
                ),
                "total_backlinks": max(
                    (r.total_backlinks or 0 for r in rows), default=0
                ),
                "domain_authority": max(
                    (r.domain_authority or 0 for r in rows), default=0
                ),
            }

        current = _agg(start, end)
        previous = _agg(prev_start, start - datetime.timedelta(days=1))

        def _pct(cur: float, prev: float) -> Optional[float]:
            if prev == 0:
                return None
            return round(((cur - prev) / prev) * 100, 1)

        lead_conversion_rate = (
            round((current["conversions"] / current["leads"]) * 100, 1)
            if current["leads"] > 0
            else 0.0
        )
        traffic_to_lead_rate = (
            round((current["leads"] / current["organic_traffic"]) * 100, 2)
            if current["organic_traffic"] > 0
            else 0.0
        )

        return {
            "period": period,
            "date_range": {"start": start.isoformat(), "end": end.isoformat()},
            "current": current,
            "previous": previous,
            "changes": {
                "traffic_change_pct": _pct(current["organic_traffic"], previous["organic_traffic"]),
                "leads_change_pct": _pct(current["leads"], previous["leads"]),
                "conversions_change_pct": _pct(current["conversions"], previous["conversions"]),
                "revenue_change_pct": _pct(current["revenue"], previous["revenue"]),
            },
            "rates": {
                "traffic_to_lead_pct": traffic_to_lead_rate,
                "lead_to_conversion_pct": lead_conversion_rate,
            },
        }

    # -----------------------------------------------------------------------
    # 12. Dashboard Summary
    # -----------------------------------------------------------------------

    def get_dashboard_summary(self) -> dict:
        """Return a consolidated snapshot for the frontend dashboard.

        Combines ranking KPIs, AI visibility, recent alerts, traffic
        highlights, and ROI data into a single response payload.

        Returns:
            A dict ready for JSON serialisation to the frontend.
        """
        logger.info("Building dashboard summary")

        today = datetime.date.today()
        week_ago = today - datetime.timedelta(days=7)

        # -- ranking KPIs ----------------------------------------------------
        latest_metric = (
            self.db.query(SEOMetric)
            .order_by(desc(SEOMetric.metric_date))
            .first()
        )
        ranking_kpis = {
            "total_keywords_tracked": latest_metric.total_keywords_tracked if latest_metric else 0,
            "keywords_in_top_3": latest_metric.keywords_in_top_3 if latest_metric else 0,
            "keywords_in_top_10": latest_metric.keywords_in_top_10 if latest_metric else 0,
            "keywords_in_top_20": latest_metric.keywords_in_top_20 if latest_metric else 0,
            "average_position": latest_metric.average_position if latest_metric else None,
            "domain_authority": latest_metric.domain_authority if latest_metric else None,
        }

        # -- AI visibility KPIs ---------------------------------------------
        ai_results_month = (
            self.db.query(AISearchResult)
            .filter(AISearchResult.tracked_date >= today - datetime.timedelta(days=30))
            .all()
        )
        ai_total = len(ai_results_month)
        ai_mentions = sum(1 for r in ai_results_month if r.mentions_company)
        ai_kpis = {
            "total_queries": ai_total,
            "company_mentions": ai_mentions,
            "visibility_pct": round((ai_mentions / ai_total) * 100, 1) if ai_total else 0.0,
        }

        # -- traffic ---------------------------------------------------------
        traffic_kpis = {
            "organic_traffic": latest_metric.organic_traffic if latest_metric else 0,
            "organic_clicks": latest_metric.organic_clicks if latest_metric else 0,
            "organic_impressions": latest_metric.organic_impressions if latest_metric else 0,
        }

        # -- backlinks -------------------------------------------------------
        total_backlinks = self.db.query(Backlink).filter(Backlink.is_active == True).count()  # noqa: E712
        new_backlinks_week = (
            self.db.query(Backlink)
            .filter(Backlink.first_seen >= week_ago)
            .count()
        )
        backlink_kpis = {
            "total_active": total_backlinks,
            "new_this_week": new_backlinks_week,
        }

        # -- reviews ---------------------------------------------------------
        avg_rating = self.db.query(func.avg(Review.rating)).scalar()
        total_reviews = self.db.query(Review).count()
        pending_responses = (
            self.db.query(Review)
            .filter(Review.needs_response == True)  # noqa: E712
            .count()
        )
        review_kpis = {
            "average_rating": round(float(avg_rating), 2) if avg_rating else None,
            "total_reviews": total_reviews,
            "pending_responses": pending_responses,
        }

        # -- alerts ----------------------------------------------------------
        alert_summary = self.alert_manager.get_alert_summary()
        recent_alerts = [
            {
                "id": a.id,
                "type": a.alert_type,
                "severity": a.severity,
                "title": a.title,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in self.alert_manager.get_unread_alerts()[:10]
        ]

        # -- recent reports --------------------------------------------------
        recent_reports = (
            self.db.query(Report)
            .order_by(desc(Report.created_at))
            .limit(5)
            .all()
        )
        reports_list = [
            {
                "id": r.id,
                "type": r.report_type,
                "date": r.report_date.isoformat() if r.report_date else None,
                "title": r.title,
                "has_pdf": bool(r.file_path),
            }
            for r in recent_reports
        ]

        # -- ROI snapshot ----------------------------------------------------
        roi = self.get_roi_metrics(period="month")

        return {
            "generated_at": datetime.datetime.utcnow().isoformat(),
            "ranking_kpis": ranking_kpis,
            "ai_visibility": ai_kpis,
            "traffic": traffic_kpis,
            "backlinks": backlink_kpis,
            "reviews": review_kpis,
            "alerts": {
                "summary": alert_summary,
                "recent": recent_alerts,
            },
            "recent_reports": reports_list,
            "roi": roi,
        }


# ---------------------------------------------------------------------------
# __main__
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    from database.models import init_db

    logger.remove()
    logger.add(sys.stderr, level="DEBUG")
    logger.info("Initialising database")
    init_db()

    with ReportingEngine() as engine:
        logger.info("--- Weekly SEO Report ---")
        weekly = engine.generate_weekly_seo_report()
        logger.info("Weekly report keys: {}", list(weekly.keys()))

        logger.info("--- Monthly AI Report ---")
        monthly = engine.generate_monthly_ai_report()
        logger.info("Monthly report keys: {}", list(monthly.keys()))

        logger.info("--- PDF Generation (weekly) ---")
        pdf_path = engine.generate_pdf_report(weekly, "weekly_seo")
        logger.info("PDF saved to {}", pdf_path)

        logger.info("--- PDF Generation (monthly AI) ---")
        pdf_path_ai = engine.generate_pdf_report(monthly, "monthly_ai")
        logger.info("PDF saved to {}", pdf_path_ai)

        logger.info("--- Processing All Alerts ---")
        alert_summary = engine.process_all_alerts()
        logger.info("Alert summary: {}", alert_summary)

        logger.info("--- ROI Metrics ---")
        roi = engine.get_roi_metrics(period="month")
        logger.info("ROI: {}", roi)

        logger.info("--- Dashboard Summary ---")
        dashboard = engine.get_dashboard_summary()
        logger.info("Dashboard sections: {}", list(dashboard.keys()))

    logger.info("Done.")
