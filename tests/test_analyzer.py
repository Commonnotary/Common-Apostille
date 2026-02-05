"""Tests for the code analyzer module."""

import pytest
from pathlib import Path
import tempfile
import os

from bot.core.analyzer import CodeAnalyzer, Severity, IssueCategory


class TestCodeAnalyzer:
    """Tests for CodeAnalyzer class."""

    def test_analyzer_initialization(self, tmp_path):
        """Test analyzer initializes correctly."""
        analyzer = CodeAnalyzer(str(tmp_path))
        assert analyzer.project_path == tmp_path
        assert analyzer.result is not None

    def test_analyze_empty_directory(self, tmp_path):
        """Test analyzing an empty directory."""
        analyzer = CodeAnalyzer(str(tmp_path))
        result = analyzer.analyze()

        assert result.files_analyzed == 0
        assert result.total_lines == 0
        assert len(result.issues) == 0

    def test_analyze_python_syntax_error(self, tmp_path):
        """Test detecting Python syntax errors."""
        # Create a file with a syntax error
        test_file = tmp_path / "bad_syntax.py"
        test_file.write_text("def foo(\n  print('incomplete'")

        analyzer = CodeAnalyzer(str(tmp_path))
        result = analyzer.analyze()

        assert result.files_analyzed == 1
        syntax_errors = [
            i for i in result.issues
            if i.severity == Severity.CRITICAL and "Syntax" in i.message
        ]
        assert len(syntax_errors) > 0

    def test_analyze_security_issues(self, tmp_path):
        """Test detecting security issues."""
        test_file = tmp_path / "security_issues.py"
        test_file.write_text('''
password = "hardcoded_secret"
api_key = "sk-12345"
eval(user_input)
''')

        analyzer = CodeAnalyzer(str(tmp_path))
        result = analyzer.analyze()

        security_issues = [
            i for i in result.issues
            if i.category == IssueCategory.SECURITY
        ]
        assert len(security_issues) >= 2  # Should find password and api_key issues

    def test_analyze_bare_except(self, tmp_path):
        """Test detecting bare except clauses."""
        test_file = tmp_path / "bare_except.py"
        test_file.write_text('''
try:
    risky_operation()
except:
    pass
''')

        analyzer = CodeAnalyzer(str(tmp_path))
        result = analyzer.analyze()

        bare_except_issues = [
            i for i in result.issues
            if "except" in i.message.lower()
        ]
        assert len(bare_except_issues) > 0

    def test_analyze_multiple_files(self, tmp_path):
        """Test analyzing multiple files."""
        (tmp_path / "file1.py").write_text("x = 1")
        (tmp_path / "file2.py").write_text("y = 2")
        (tmp_path / "file3.py").write_text("z = 3")

        analyzer = CodeAnalyzer(str(tmp_path))
        result = analyzer.analyze()

        assert result.files_analyzed == 3

    def test_ignore_patterns(self, tmp_path):
        """Test that ignore patterns work."""
        # Create files in ignored directory
        venv = tmp_path / "venv"
        venv.mkdir()
        (venv / "ignored.py").write_text("eval('dangerous')")

        # Create file in main directory
        (tmp_path / "main.py").write_text("x = 1")

        analyzer = CodeAnalyzer(str(tmp_path))
        result = analyzer.analyze()

        # Should only analyze main.py, not venv/ignored.py
        assert result.files_analyzed == 1

    def test_calculate_score(self, tmp_path):
        """Test score calculation."""
        test_file = tmp_path / "good_code.py"
        test_file.write_text('''
def add(a, b):
    """Add two numbers."""
    return a + b
''')

        analyzer = CodeAnalyzer(str(tmp_path))
        result = analyzer.analyze()

        # Good code should have high score
        assert result.score >= 80

    def test_javascript_analysis(self, tmp_path):
        """Test JavaScript file analysis."""
        test_file = tmp_path / "test.js"
        test_file.write_text('''
var x = 1;
if (x == 1) {
    console.log("test");
}
eval("dangerous");
''')

        analyzer = CodeAnalyzer(str(tmp_path))
        result = analyzer.analyze()

        assert result.files_analyzed == 1
        # Should find var, ==, console.log, and eval issues
        assert len(result.issues) >= 2

    def test_html_analysis(self, tmp_path):
        """Test HTML file analysis."""
        test_file = tmp_path / "test.html"
        test_file.write_text('''
<html>
<body>
<img src="image.jpg">
<font color="red">Old HTML</font>
</body>
</html>
''')

        analyzer = CodeAnalyzer(str(tmp_path))
        result = analyzer.analyze()

        assert result.files_analyzed == 1
        # Should find missing alt and deprecated font issues
        assert len(result.issues) >= 1

    def test_export_report_json(self, tmp_path):
        """Test exporting report to JSON."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1")

        analyzer = CodeAnalyzer(str(tmp_path))
        analyzer.analyze()

        output_path = tmp_path / "report.json"
        analyzer.export_report(str(output_path), "json")

        assert output_path.exists()

        import json
        with open(output_path) as f:
            report = json.load(f)

        assert "summary" in report
        assert "issues" in report


class TestSeverity:
    """Tests for Severity enum."""

    def test_severity_values(self):
        """Test severity enum has correct values."""
        assert Severity.CRITICAL.value == "critical"
        assert Severity.HIGH.value == "high"
        assert Severity.MEDIUM.value == "medium"
        assert Severity.LOW.value == "low"
        assert Severity.INFO.value == "info"


class TestIssueCategory:
    """Tests for IssueCategory enum."""

    def test_category_values(self):
        """Test category enum has correct values."""
        assert IssueCategory.ERROR.value == "error"
        assert IssueCategory.SECURITY.value == "security"
        assert IssueCategory.PERFORMANCE.value == "performance"
        assert IssueCategory.STYLE.value == "style"
