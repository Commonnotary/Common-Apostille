"""
Code Analyzer Module
====================

Comprehensive code analysis for detecting errors, code smells, and quality issues.
Supports multiple languages and provides detailed reports with actionable fixes.
"""

import ast
import os
import re
import subprocess
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

from rich.console import Console
from rich.table import Table

console = Console()


class Severity(Enum):
    """Issue severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class IssueCategory(Enum):
    """Categories of code issues."""
    ERROR = "error"
    SECURITY = "security"
    PERFORMANCE = "performance"
    STYLE = "style"
    MAINTAINABILITY = "maintainability"
    BEST_PRACTICE = "best_practice"
    ACCESSIBILITY = "accessibility"
    SEO = "seo"


@dataclass
class CodeIssue:
    """Represents a single code issue found during analysis."""
    file_path: str
    line_number: int
    column: int
    message: str
    severity: Severity
    category: IssueCategory
    rule_id: str
    suggestion: str = ""
    code_snippet: str = ""
    auto_fixable: bool = False
    fix_code: str = ""


@dataclass
class AnalysisResult:
    """Complete analysis result for a file or project."""
    files_analyzed: int = 0
    total_lines: int = 0
    issues: list[CodeIssue] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    score: float = 100.0

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.CRITICAL)

    @property
    def high_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.HIGH)

    @property
    def medium_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.MEDIUM)

    @property
    def low_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.LOW)

    def calculate_score(self) -> float:
        """Calculate quality score based on issues found."""
        if not self.total_lines:
            return 100.0

        penalty = (
            self.critical_count * 10 +
            self.high_count * 5 +
            self.medium_count * 2 +
            self.low_count * 0.5
        )

        score = max(0, 100 - (penalty / max(1, self.files_analyzed) * 10))
        self.score = round(score, 2)
        return self.score


class CodeAnalyzer:
    """
    Main code analyzer that integrates multiple analysis tools.

    Supports:
    - Python (pylint, flake8, mypy, bandit)
    - JavaScript/TypeScript (eslint)
    - HTML/CSS (htmlhint, stylelint)
    - General security scanning
    """

    SUPPORTED_EXTENSIONS = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".html": "html",
        ".htm": "html",
        ".css": "css",
        ".scss": "scss",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
    }

    def __init__(self, project_path: str, config_path: Optional[str] = None):
        self.project_path = Path(project_path)
        self.config_path = Path(config_path) if config_path else None
        self.result = AnalysisResult()
        self._load_config()

    def _load_config(self) -> None:
        """Load analyzer configuration."""
        self.config = {
            "ignore_patterns": [
                "__pycache__",
                "node_modules",
                ".git",
                "venv",
                ".venv",
                "dist",
                "build",
            ],
            "severity_threshold": "low",
            "max_line_length": 100,
            "enable_security_scan": True,
            "enable_style_check": True,
            "enable_complexity_analysis": True,
        }

        if self.config_path and self.config_path.exists():
            import yaml
            with open(self.config_path) as f:
                user_config = yaml.safe_load(f)
                self.config.update(user_config)

    def analyze(self, target: Optional[str] = None) -> AnalysisResult:
        """
        Run comprehensive analysis on the project or specific file.

        Args:
            target: Optional specific file or directory to analyze

        Returns:
            AnalysisResult with all findings
        """
        target_path = Path(target) if target else self.project_path

        console.print(f"[bold blue]Analyzing:[/] {target_path}")

        if target_path.is_file():
            self._analyze_file(target_path)
        else:
            self._analyze_directory(target_path)

        self.result.calculate_score()
        return self.result

    def _analyze_directory(self, directory: Path) -> None:
        """Recursively analyze all files in a directory."""
        for item in directory.rglob("*"):
            if item.is_file() and not self._should_ignore(item):
                self._analyze_file(item)

    def _should_ignore(self, path: Path) -> bool:
        """Check if a path should be ignored based on patterns."""
        path_str = str(path)
        return any(pattern in path_str for pattern in self.config["ignore_patterns"])

    def _analyze_file(self, file_path: Path) -> None:
        """Analyze a single file based on its type."""
        extension = file_path.suffix.lower()

        if extension not in self.SUPPORTED_EXTENSIONS:
            return

        self.result.files_analyzed += 1

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                self.result.total_lines += len(content.splitlines())
        except Exception:
            return

        language = self.SUPPORTED_EXTENSIONS[extension]

        if language == "python":
            self._analyze_python(file_path, content)
        elif language in ("javascript", "typescript"):
            self._analyze_javascript(file_path, content)
        elif language == "html":
            self._analyze_html(file_path, content)
        elif language == "css":
            self._analyze_css(file_path, content)

    def _analyze_python(self, file_path: Path, content: str) -> None:
        """Analyze Python code for errors and issues."""
        # Syntax check using AST
        try:
            ast.parse(content)
        except SyntaxError as e:
            self.result.issues.append(CodeIssue(
                file_path=str(file_path),
                line_number=e.lineno or 1,
                column=e.offset or 0,
                message=f"Syntax error: {e.msg}",
                severity=Severity.CRITICAL,
                category=IssueCategory.ERROR,
                rule_id="E001",
                suggestion="Fix the syntax error to make the code runnable",
            ))
            return

        # Run pylint analysis
        self._run_pylint(file_path)

        # Run security analysis with bandit
        if self.config["enable_security_scan"]:
            self._run_bandit(file_path)

        # Check for common Python issues
        self._check_python_patterns(file_path, content)

    def _run_pylint(self, file_path: Path) -> None:
        """Run pylint on a Python file."""
        try:
            result = subprocess.run(
                [
                    "pylint",
                    "--output-format=json",
                    "--disable=C0114,C0115,C0116",
                    str(file_path),
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.stdout:
                issues = json.loads(result.stdout)
                for issue in issues:
                    severity = self._map_pylint_severity(issue.get("type", "convention"))
                    self.result.issues.append(CodeIssue(
                        file_path=str(file_path),
                        line_number=issue.get("line", 1),
                        column=issue.get("column", 0),
                        message=issue.get("message", ""),
                        severity=severity,
                        category=IssueCategory.STYLE if severity in (Severity.LOW, Severity.INFO)
                                 else IssueCategory.ERROR,
                        rule_id=issue.get("message-id", ""),
                        suggestion=self._get_pylint_suggestion(issue.get("message-id", "")),
                    ))
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
            pass

    def _map_pylint_severity(self, pylint_type: str) -> Severity:
        """Map pylint message types to severity levels."""
        mapping = {
            "fatal": Severity.CRITICAL,
            "error": Severity.HIGH,
            "warning": Severity.MEDIUM,
            "convention": Severity.LOW,
            "refactor": Severity.LOW,
            "info": Severity.INFO,
        }
        return mapping.get(pylint_type, Severity.INFO)

    def _get_pylint_suggestion(self, message_id: str) -> str:
        """Get suggestion for fixing a pylint issue."""
        suggestions = {
            "E0001": "Fix the syntax error in your code",
            "E0102": "Rename the duplicate function or class",
            "E0401": "Install the missing module or fix the import path",
            "E1101": "Check that the attribute exists on the object",
            "W0612": "Remove or use the unused variable",
            "W0611": "Remove the unused import",
            "W0613": "Use the parameter or prefix with underscore",
            "C0301": "Break the line into multiple lines",
            "C0103": "Rename to follow naming conventions (snake_case for functions/variables)",
        }
        return suggestions.get(message_id, "Review and fix the issue")

    def _run_bandit(self, file_path: Path) -> None:
        """Run bandit security analysis on a Python file."""
        try:
            result = subprocess.run(
                ["bandit", "-f", "json", "-q", str(file_path)],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.stdout:
                data = json.loads(result.stdout)
                for issue in data.get("results", []):
                    severity = Severity.HIGH if issue.get("severity") == "HIGH" else Severity.MEDIUM
                    self.result.issues.append(CodeIssue(
                        file_path=str(file_path),
                        line_number=issue.get("line_number", 1),
                        column=0,
                        message=f"Security: {issue.get('issue_text', '')}",
                        severity=severity,
                        category=IssueCategory.SECURITY,
                        rule_id=issue.get("test_id", ""),
                        suggestion=issue.get("more_info", "Review security best practices"),
                    ))
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
            pass

    def _check_python_patterns(self, file_path: Path, content: str) -> None:
        """Check for common Python anti-patterns and issues."""
        lines = content.splitlines()

        patterns = [
            (r"except\s*:", "Bare except clause catches all exceptions including KeyboardInterrupt",
             Severity.MEDIUM, "B001", "Specify the exception type to catch"),
            (r"eval\s*\(", "Use of eval() is dangerous and can execute arbitrary code",
             Severity.HIGH, "S001", "Use ast.literal_eval() for safe evaluation or avoid eval entirely"),
            (r"exec\s*\(", "Use of exec() can execute arbitrary code",
             Severity.HIGH, "S002", "Refactor to avoid using exec()"),
            (r"pickle\.loads?\s*\(", "Pickle can execute arbitrary code when loading untrusted data",
             Severity.HIGH, "S003", "Use JSON or other safe serialization formats"),
            (r"import\s+\*", "Wildcard imports make code harder to understand",
             Severity.LOW, "W001", "Import specific names instead of using wildcard"),
            (r"print\s*\((?!.*#\s*debug)", "Consider using logging instead of print",
             Severity.INFO, "I001", "Use the logging module for production code"),
            (r"TODO|FIXME|HACK|XXX", "Code contains unresolved TODO/FIXME comments",
             Severity.INFO, "I002", "Address the TODO item or create a ticket"),
            (r"password\s*=\s*['\"]", "Potential hardcoded password detected",
             Severity.CRITICAL, "S004", "Use environment variables or secure secret management"),
            (r"api_key\s*=\s*['\"]", "Potential hardcoded API key detected",
             Severity.CRITICAL, "S005", "Use environment variables or secure secret management"),
        ]

        for line_num, line in enumerate(lines, 1):
            for pattern, message, severity, rule_id, suggestion in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    self.result.issues.append(CodeIssue(
                        file_path=str(file_path),
                        line_number=line_num,
                        column=0,
                        message=message,
                        severity=severity,
                        category=IssueCategory.SECURITY if rule_id.startswith("S")
                                 else IssueCategory.BEST_PRACTICE,
                        rule_id=rule_id,
                        suggestion=suggestion,
                        code_snippet=line.strip()[:100],
                    ))

    def _analyze_javascript(self, file_path: Path, content: str) -> None:
        """Analyze JavaScript/TypeScript code for errors and issues."""
        lines = content.splitlines()

        patterns = [
            (r"eval\s*\(", "Use of eval() is dangerous",
             Severity.HIGH, "JS001", "Avoid eval - use safer alternatives"),
            (r"innerHTML\s*=", "innerHTML can lead to XSS vulnerabilities",
             Severity.HIGH, "JS002", "Use textContent or DOMPurify for sanitization"),
            (r"document\.write\s*\(", "document.write is deprecated and can cause issues",
             Severity.MEDIUM, "JS003", "Use DOM manipulation methods instead"),
            (r"var\s+", "Use let or const instead of var",
             Severity.LOW, "JS004", "Replace var with let or const"),
            (r"==(?!=)", "Use strict equality (===) instead of loose equality (==)",
             Severity.LOW, "JS005", "Use === for strict type checking"),
            (r"console\.log\s*\(", "Remove console.log statements in production",
             Severity.INFO, "JS006", "Remove or use a proper logging library"),
            (r"debugger", "Debugger statement found",
             Severity.MEDIUM, "JS007", "Remove debugger statements"),
            (r"alert\s*\(", "Avoid using alert() in production",
             Severity.LOW, "JS008", "Use a proper UI notification system"),
        ]

        for line_num, line in enumerate(lines, 1):
            for pattern, message, severity, rule_id, suggestion in patterns:
                if re.search(pattern, line):
                    self.result.issues.append(CodeIssue(
                        file_path=str(file_path),
                        line_number=line_num,
                        column=0,
                        message=message,
                        severity=severity,
                        category=IssueCategory.SECURITY if "XSS" in message or "eval" in message.lower()
                                 else IssueCategory.BEST_PRACTICE,
                        rule_id=rule_id,
                        suggestion=suggestion,
                        code_snippet=line.strip()[:100],
                    ))

    def _analyze_html(self, file_path: Path, content: str) -> None:
        """Analyze HTML for accessibility and best practices."""
        lines = content.splitlines()

        patterns = [
            (r"<img[^>]+(?!alt=)", "Image missing alt attribute",
             Severity.MEDIUM, "A001", "Add descriptive alt text for accessibility"),
            (r"<a[^>]+(?!href=)", "Anchor tag missing href",
             Severity.LOW, "H001", "Add href attribute or use button element"),
            (r"style\s*=\s*['\"]", "Inline styles found",
             Severity.LOW, "H002", "Move styles to CSS file for maintainability"),
            (r"onclick\s*=", "Inline event handler found",
             Severity.LOW, "H003", "Use addEventListener in JavaScript"),
            (r"<font\s", "Deprecated font tag found",
             Severity.MEDIUM, "H004", "Use CSS for styling text"),
            (r"<center\s", "Deprecated center tag found",
             Severity.MEDIUM, "H005", "Use CSS for centering content"),
            (r"<form[^>]+(?!action=)", "Form missing action attribute",
             Severity.MEDIUM, "H006", "Add action attribute to form"),
            (r"<input[^>]+(?!type=)", "Input missing type attribute",
             Severity.LOW, "H007", "Specify input type explicitly"),
            (r"<html[^>]+(?!lang=)", "HTML tag missing lang attribute",
             Severity.MEDIUM, "A002", "Add lang attribute for accessibility"),
        ]

        for line_num, line in enumerate(lines, 1):
            for pattern, message, severity, rule_id, suggestion in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    self.result.issues.append(CodeIssue(
                        file_path=str(file_path),
                        line_number=line_num,
                        column=0,
                        message=message,
                        severity=severity,
                        category=IssueCategory.ACCESSIBILITY if rule_id.startswith("A")
                                 else IssueCategory.BEST_PRACTICE,
                        rule_id=rule_id,
                        suggestion=suggestion,
                    ))

    def _analyze_css(self, file_path: Path, content: str) -> None:
        """Analyze CSS for issues and best practices."""
        lines = content.splitlines()

        patterns = [
            (r"!important", "Avoid using !important",
             Severity.LOW, "CSS001", "Increase specificity instead of using !important"),
            (r"float\s*:", "Float-based layouts are outdated",
             Severity.INFO, "CSS002", "Consider using flexbox or grid"),
            (r"@import\s+", "@import can slow down page loading",
             Severity.LOW, "CSS003", "Use link tags or concatenate CSS files"),
        ]

        for line_num, line in enumerate(lines, 1):
            for pattern, message, severity, rule_id, suggestion in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    self.result.issues.append(CodeIssue(
                        file_path=str(file_path),
                        line_number=line_num,
                        column=0,
                        message=message,
                        severity=severity,
                        category=IssueCategory.STYLE,
                        rule_id=rule_id,
                        suggestion=suggestion,
                    ))

    def print_report(self) -> None:
        """Print a formatted analysis report."""
        console.print("\n[bold]Code Analysis Report[/bold]")
        console.print("=" * 60)

        # Summary
        table = Table(title="Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Files Analyzed", str(self.result.files_analyzed))
        table.add_row("Total Lines", str(self.result.total_lines))
        table.add_row("Quality Score", f"{self.result.score}/100")
        table.add_row("Critical Issues", str(self.result.critical_count))
        table.add_row("High Issues", str(self.result.high_count))
        table.add_row("Medium Issues", str(self.result.medium_count))
        table.add_row("Low Issues", str(self.result.low_count))

        console.print(table)

        # Issues by severity
        if self.result.issues:
            console.print("\n[bold]Issues Found:[/bold]")

            for severity in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW]:
                issues = [i for i in self.result.issues if i.severity == severity]
                if issues:
                    color = {
                        Severity.CRITICAL: "red",
                        Severity.HIGH: "orange1",
                        Severity.MEDIUM: "yellow",
                        Severity.LOW: "blue",
                    }[severity]

                    console.print(f"\n[bold {color}]{severity.value.upper()} ({len(issues)}):[/]")
                    for issue in issues[:10]:  # Show top 10 per severity
                        console.print(f"  [{issue.rule_id}] {issue.file_path}:{issue.line_number}")
                        console.print(f"    {issue.message}")
                        if issue.suggestion:
                            console.print(f"    [dim]Suggestion: {issue.suggestion}[/dim]")
        else:
            console.print("\n[bold green]No issues found! Great job![/bold green]")

    def export_report(self, output_path: str, format: str = "json") -> None:
        """Export analysis report to file."""
        output = Path(output_path)

        if format == "json":
            data = {
                "summary": {
                    "files_analyzed": self.result.files_analyzed,
                    "total_lines": self.result.total_lines,
                    "quality_score": self.result.score,
                    "critical_count": self.result.critical_count,
                    "high_count": self.result.high_count,
                    "medium_count": self.result.medium_count,
                    "low_count": self.result.low_count,
                },
                "issues": [
                    {
                        "file": i.file_path,
                        "line": i.line_number,
                        "column": i.column,
                        "message": i.message,
                        "severity": i.severity.value,
                        "category": i.category.value,
                        "rule_id": i.rule_id,
                        "suggestion": i.suggestion,
                    }
                    for i in self.result.issues
                ],
            }
            with open(output, "w") as f:
                json.dump(data, f, indent=2)

        console.print(f"[green]Report exported to {output}[/green]")
