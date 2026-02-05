"""
Self-Improvement Module
=======================

Machine learning and feedback-based system for continuous improvement
of the code review bot. Learns from past reviews and user feedback.
"""

import json
import hashlib
from pathlib import Path
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional
from collections import defaultdict

from rich.console import Console
from rich.table import Table

console = Console()


@dataclass
class Feedback:
    """User feedback on a review or recommendation."""
    id: str
    timestamp: datetime
    feedback_type: str  # positive, negative, suggestion
    target_type: str  # issue, recommendation, review
    target_id: str
    comment: str = ""
    was_helpful: bool = True
    was_accurate: bool = True
    suggested_improvement: str = ""


@dataclass
class Pattern:
    """A learned pattern from code reviews."""
    id: str
    pattern_type: str
    pattern: str
    severity: str
    occurrences: int = 0
    true_positives: int = 0
    false_positives: int = 0
    confidence: float = 1.0
    last_seen: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def accuracy(self) -> float:
        """Calculate pattern accuracy."""
        total = self.true_positives + self.false_positives
        if total == 0:
            return 1.0
        return self.true_positives / total


@dataclass
class LearningMetrics:
    """Metrics tracking the bot's learning progress."""
    total_reviews: int = 0
    total_feedback: int = 0
    positive_feedback: int = 0
    negative_feedback: int = 0
    patterns_learned: int = 0
    accuracy_improvement: float = 0.0
    last_training: Optional[datetime] = None


class SelfImprover:
    """
    Self-improvement system for the code review bot.

    Features:
    - Learns from user feedback
    - Tracks pattern accuracy
    - Adjusts severity levels based on feedback
    - Discovers new patterns from code
    - Improves recommendations over time
    - Generates improvement reports
    """

    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.feedback_file = self.data_dir / "feedback.json"
        self.patterns_file = self.data_dir / "patterns.json"
        self.metrics_file = self.data_dir / "metrics.json"
        self.config_file = self.data_dir / "config.json"

        self.feedback: list[Feedback] = []
        self.patterns: dict[str, Pattern] = {}
        self.metrics = LearningMetrics()
        self.config = {
            "min_confidence_threshold": 0.6,
            "feedback_weight": 0.1,
            "pattern_decay_days": 90,
            "auto_adjust_severity": True,
            "learn_new_patterns": True,
        }

        self._load_data()

    def _load_data(self) -> None:
        """Load saved data from files."""
        # Load feedback
        if self.feedback_file.exists():
            try:
                with open(self.feedback_file) as f:
                    data = json.load(f)
                    self.feedback = [
                        Feedback(
                            id=fb["id"],
                            timestamp=datetime.fromisoformat(fb["timestamp"]),
                            feedback_type=fb["feedback_type"],
                            target_type=fb["target_type"],
                            target_id=fb["target_id"],
                            comment=fb.get("comment", ""),
                            was_helpful=fb.get("was_helpful", True),
                            was_accurate=fb.get("was_accurate", True),
                            suggested_improvement=fb.get("suggested_improvement", ""),
                        )
                        for fb in data
                    ]
            except Exception:
                self.feedback = []

        # Load patterns
        if self.patterns_file.exists():
            try:
                with open(self.patterns_file) as f:
                    data = json.load(f)
                    self.patterns = {
                        pid: Pattern(
                            id=p["id"],
                            pattern_type=p["pattern_type"],
                            pattern=p["pattern"],
                            severity=p["severity"],
                            occurrences=p.get("occurrences", 0),
                            true_positives=p.get("true_positives", 0),
                            false_positives=p.get("false_positives", 0),
                            confidence=p.get("confidence", 1.0),
                            last_seen=datetime.fromisoformat(p.get("last_seen", datetime.now().isoformat())),
                            created_at=datetime.fromisoformat(p.get("created_at", datetime.now().isoformat())),
                        )
                        for pid, p in data.items()
                    }
            except Exception:
                self.patterns = {}

        # Load metrics
        if self.metrics_file.exists():
            try:
                with open(self.metrics_file) as f:
                    data = json.load(f)
                    self.metrics = LearningMetrics(
                        total_reviews=data.get("total_reviews", 0),
                        total_feedback=data.get("total_feedback", 0),
                        positive_feedback=data.get("positive_feedback", 0),
                        negative_feedback=data.get("negative_feedback", 0),
                        patterns_learned=data.get("patterns_learned", 0),
                        accuracy_improvement=data.get("accuracy_improvement", 0.0),
                        last_training=datetime.fromisoformat(data["last_training"]) if data.get("last_training") else None,
                    )
            except Exception:
                self.metrics = LearningMetrics()

        # Load config
        if self.config_file.exists():
            try:
                with open(self.config_file) as f:
                    self.config.update(json.load(f))
            except Exception:
                pass

    def _save_data(self) -> None:
        """Save data to files."""
        # Save feedback
        with open(self.feedback_file, "w") as f:
            json.dump([
                {
                    "id": fb.id,
                    "timestamp": fb.timestamp.isoformat(),
                    "feedback_type": fb.feedback_type,
                    "target_type": fb.target_type,
                    "target_id": fb.target_id,
                    "comment": fb.comment,
                    "was_helpful": fb.was_helpful,
                    "was_accurate": fb.was_accurate,
                    "suggested_improvement": fb.suggested_improvement,
                }
                for fb in self.feedback
            ], f, indent=2)

        # Save patterns
        with open(self.patterns_file, "w") as f:
            json.dump({
                pid: {
                    "id": p.id,
                    "pattern_type": p.pattern_type,
                    "pattern": p.pattern,
                    "severity": p.severity,
                    "occurrences": p.occurrences,
                    "true_positives": p.true_positives,
                    "false_positives": p.false_positives,
                    "confidence": p.confidence,
                    "last_seen": p.last_seen.isoformat(),
                    "created_at": p.created_at.isoformat(),
                }
                for pid, p in self.patterns.items()
            }, f, indent=2)

        # Save metrics
        with open(self.metrics_file, "w") as f:
            json.dump({
                "total_reviews": self.metrics.total_reviews,
                "total_feedback": self.metrics.total_feedback,
                "positive_feedback": self.metrics.positive_feedback,
                "negative_feedback": self.metrics.negative_feedback,
                "patterns_learned": self.metrics.patterns_learned,
                "accuracy_improvement": self.metrics.accuracy_improvement,
                "last_training": self.metrics.last_training.isoformat() if self.metrics.last_training else None,
            }, f, indent=2)

        # Save config
        with open(self.config_file, "w") as f:
            json.dump(self.config, f, indent=2)

    def record_feedback(
        self,
        target_type: str,
        target_id: str,
        feedback_type: str,
        was_helpful: bool = True,
        was_accurate: bool = True,
        comment: str = "",
        suggested_improvement: str = ""
    ) -> Feedback:
        """
        Record user feedback.

        Args:
            target_type: Type of item (issue, recommendation, review)
            target_id: ID of the target item
            feedback_type: positive, negative, or suggestion
            was_helpful: Whether the item was helpful
            was_accurate: Whether the item was accurate
            comment: User comment
            suggested_improvement: Suggested improvement

        Returns:
            Created Feedback object
        """
        feedback = Feedback(
            id=hashlib.md5(f"{target_id}{datetime.now().isoformat()}".encode()).hexdigest()[:12],
            timestamp=datetime.now(),
            feedback_type=feedback_type,
            target_type=target_type,
            target_id=target_id,
            comment=comment,
            was_helpful=was_helpful,
            was_accurate=was_accurate,
            suggested_improvement=suggested_improvement,
        )

        self.feedback.append(feedback)

        # Update metrics
        self.metrics.total_feedback += 1
        if feedback_type == "positive":
            self.metrics.positive_feedback += 1
        elif feedback_type == "negative":
            self.metrics.negative_feedback += 1

        # Learn from feedback
        self._learn_from_feedback(feedback)

        self._save_data()

        console.print(f"[green]Feedback recorded. Thank you for helping improve the bot![/green]")

        return feedback

    def _learn_from_feedback(self, feedback: Feedback) -> None:
        """Learn from a single feedback item."""
        if feedback.target_type == "issue":
            # Update pattern accuracy
            pattern_id = feedback.target_id.split(":")[0] if ":" in feedback.target_id else feedback.target_id

            if pattern_id in self.patterns:
                pattern = self.patterns[pattern_id]

                if feedback.was_accurate:
                    pattern.true_positives += 1
                else:
                    pattern.false_positives += 1

                # Recalculate confidence
                pattern.confidence = self._calculate_confidence(pattern)

                # Auto-adjust severity if enabled
                if self.config["auto_adjust_severity"] and pattern.accuracy < 0.7:
                    self._adjust_severity(pattern)

    def _calculate_confidence(self, pattern: Pattern) -> float:
        """Calculate confidence score for a pattern."""
        base_accuracy = pattern.accuracy
        occurrence_factor = min(1.0, pattern.occurrences / 100)  # More occurrences = more reliable
        age_factor = self._calculate_age_factor(pattern)

        confidence = (base_accuracy * 0.6 + occurrence_factor * 0.3 + age_factor * 0.1)
        return round(confidence, 3)

    def _calculate_age_factor(self, pattern: Pattern) -> float:
        """Calculate age factor for pattern relevance."""
        days_old = (datetime.now() - pattern.created_at).days
        decay_days = self.config["pattern_decay_days"]

        if days_old >= decay_days:
            return 0.5
        return 1.0 - (days_old / decay_days * 0.5)

    def _adjust_severity(self, pattern: Pattern) -> None:
        """Adjust pattern severity based on accuracy."""
        severity_levels = ["info", "low", "medium", "high", "critical"]

        current_idx = severity_levels.index(pattern.severity) if pattern.severity in severity_levels else 2

        if pattern.accuracy < 0.5:
            # Demote severity
            new_idx = max(0, current_idx - 1)
            pattern.severity = severity_levels[new_idx]
            console.print(f"[yellow]Pattern {pattern.id} severity reduced to {pattern.severity}[/yellow]")

    def learn_pattern(
        self,
        pattern_type: str,
        pattern: str,
        severity: str,
        description: str = ""
    ) -> Pattern:
        """
        Learn a new pattern from code analysis.

        Args:
            pattern_type: Type of pattern (error, security, style, etc.)
            pattern: The pattern string or regex
            severity: Severity level
            description: Description of what the pattern detects

        Returns:
            Created Pattern object
        """
        pattern_id = hashlib.md5(f"{pattern_type}{pattern}".encode()).hexdigest()[:12]

        if pattern_id in self.patterns:
            # Update existing pattern
            existing = self.patterns[pattern_id]
            existing.occurrences += 1
            existing.last_seen = datetime.now()
            self._save_data()
            return existing

        new_pattern = Pattern(
            id=pattern_id,
            pattern_type=pattern_type,
            pattern=pattern,
            severity=severity,
        )

        self.patterns[pattern_id] = new_pattern
        self.metrics.patterns_learned += 1

        self._save_data()

        return new_pattern

    def get_active_patterns(self) -> list[Pattern]:
        """Get patterns that meet confidence threshold."""
        threshold = self.config["min_confidence_threshold"]
        return [p for p in self.patterns.values() if p.confidence >= threshold]

    def record_review(self, review_result: dict) -> None:
        """
        Record a completed review for learning.

        Args:
            review_result: Dictionary with review results
        """
        self.metrics.total_reviews += 1

        # Learn from issues found
        for issue in review_result.get("issues", []):
            rule_id = issue.get("rule_id", "")
            if rule_id:
                self.learn_pattern(
                    pattern_type=issue.get("category", "unknown"),
                    pattern=rule_id,
                    severity=issue.get("severity", "medium"),
                )

        self._save_data()

    def analyze_improvement(self) -> dict:
        """
        Analyze the bot's improvement over time.

        Returns:
            Dictionary with improvement metrics
        """
        if not self.feedback:
            return {"message": "No feedback data available yet"}

        # Calculate feedback trends
        recent_feedback = [
            f for f in self.feedback
            if (datetime.now() - f.timestamp).days <= 30
        ]

        older_feedback = [
            f for f in self.feedback
            if 30 < (datetime.now() - f.timestamp).days <= 60
        ]

        recent_positive_rate = (
            sum(1 for f in recent_feedback if f.feedback_type == "positive") /
            max(1, len(recent_feedback))
        )

        older_positive_rate = (
            sum(1 for f in older_feedback if f.feedback_type == "positive") /
            max(1, len(older_feedback))
        ) if older_feedback else recent_positive_rate

        # Calculate pattern accuracy improvement
        active_patterns = self.get_active_patterns()
        avg_accuracy = (
            sum(p.accuracy for p in active_patterns) / len(active_patterns)
            if active_patterns else 0
        )

        improvement = {
            "total_reviews": self.metrics.total_reviews,
            "total_feedback": self.metrics.total_feedback,
            "positive_feedback_rate": round(recent_positive_rate * 100, 1),
            "feedback_rate_change": round((recent_positive_rate - older_positive_rate) * 100, 1),
            "patterns_learned": self.metrics.patterns_learned,
            "active_patterns": len(active_patterns),
            "average_pattern_accuracy": round(avg_accuracy * 100, 1),
            "improvement_trend": "improving" if recent_positive_rate > older_positive_rate else "stable",
        }

        return improvement

    def get_improvement_suggestions(self) -> list[str]:
        """Get suggestions for improving the bot itself."""
        suggestions = []

        # Analyze feedback for common issues
        negative_feedback = [f for f in self.feedback if f.feedback_type == "negative"]

        if negative_feedback:
            # Group by target type
            by_type = defaultdict(list)
            for f in negative_feedback:
                by_type[f.target_type].append(f)

            for target_type, feedbacks in by_type.items():
                if len(feedbacks) > 3:
                    suggestions.append(
                        f"Review {target_type} detection - {len(feedbacks)} negative feedbacks received"
                    )

        # Check for low-confidence patterns
        low_confidence = [p for p in self.patterns.values() if p.confidence < 0.7]
        if low_confidence:
            suggestions.append(
                f"Consider reviewing {len(low_confidence)} low-confidence patterns"
            )

        # Check for unused patterns
        unused = [
            p for p in self.patterns.values()
            if (datetime.now() - p.last_seen).days > 60
        ]
        if unused:
            suggestions.append(
                f"Consider removing {len(unused)} patterns not seen in 60+ days"
            )

        # Analyze suggestions from feedback
        improvement_suggestions = [
            f.suggested_improvement
            for f in self.feedback
            if f.suggested_improvement
        ]
        if improvement_suggestions:
            suggestions.append("User suggestions to review:")
            for sugg in improvement_suggestions[-5:]:
                suggestions.append(f"  - {sugg[:100]}")

        return suggestions

    def train(self) -> dict:
        """
        Perform a training cycle to improve the bot.

        Returns:
            Dictionary with training results
        """
        console.print("[bold blue]Starting training cycle...[/bold blue]")

        results = {
            "patterns_updated": 0,
            "patterns_removed": 0,
            "severity_adjustments": 0,
        }

        # Update pattern confidences
        for pattern in list(self.patterns.values()):
            old_confidence = pattern.confidence
            pattern.confidence = self._calculate_confidence(pattern)

            if pattern.confidence != old_confidence:
                results["patterns_updated"] += 1

            # Remove very low confidence patterns
            if pattern.confidence < 0.3 and pattern.occurrences < 5:
                del self.patterns[pattern.id]
                results["patterns_removed"] += 1
                continue

            # Auto-adjust severity
            if self.config["auto_adjust_severity"] and pattern.accuracy < 0.6:
                self._adjust_severity(pattern)
                results["severity_adjustments"] += 1

        self.metrics.last_training = datetime.now()
        self._save_data()

        console.print(f"[green]Training complete![/green]")
        console.print(f"  Patterns updated: {results['patterns_updated']}")
        console.print(f"  Patterns removed: {results['patterns_removed']}")
        console.print(f"  Severity adjustments: {results['severity_adjustments']}")

        return results

    def print_status(self) -> None:
        """Print current learning status."""
        console.print("\n[bold]Self-Improvement Status[/bold]")
        console.print("=" * 60)

        # Metrics table
        table = Table(title="Learning Metrics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Total Reviews", str(self.metrics.total_reviews))
        table.add_row("Total Feedback", str(self.metrics.total_feedback))
        table.add_row("Positive Feedback", str(self.metrics.positive_feedback))
        table.add_row("Negative Feedback", str(self.metrics.negative_feedback))
        table.add_row("Patterns Learned", str(self.metrics.patterns_learned))
        table.add_row("Active Patterns", str(len(self.get_active_patterns())))

        if self.metrics.last_training:
            table.add_row("Last Training", self.metrics.last_training.strftime("%Y-%m-%d %H:%M"))

        console.print(table)

        # Improvement analysis
        improvement = self.analyze_improvement()
        if "positive_feedback_rate" in improvement:
            console.print(f"\n[bold]Improvement Trend: {improvement['improvement_trend']}[/bold]")
            console.print(f"Positive Feedback Rate: {improvement['positive_feedback_rate']}%")
            console.print(f"Pattern Accuracy: {improvement['average_pattern_accuracy']}%")

        # Suggestions
        suggestions = self.get_improvement_suggestions()
        if suggestions:
            console.print("\n[bold yellow]Improvement Suggestions:[/bold yellow]")
            for sugg in suggestions:
                console.print(f"  - {sugg}")

    def export_learning_data(self, output_path: str) -> None:
        """Export all learning data for backup or analysis."""
        data = {
            "exported_at": datetime.now().isoformat(),
            "metrics": asdict(self.metrics) if hasattr(self.metrics, '__dataclass_fields__') else {
                "total_reviews": self.metrics.total_reviews,
                "total_feedback": self.metrics.total_feedback,
                "positive_feedback": self.metrics.positive_feedback,
                "negative_feedback": self.metrics.negative_feedback,
                "patterns_learned": self.metrics.patterns_learned,
            },
            "patterns_count": len(self.patterns),
            "feedback_count": len(self.feedback),
            "config": self.config,
        }

        with open(output_path, "w") as f:
            json.dump(data, f, indent=2, default=str)

        console.print(f"[green]Learning data exported to {output_path}[/green]")
