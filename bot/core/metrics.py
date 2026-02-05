"""
Code Metrics Module
===================

Calculate and track code quality metrics including complexity,
maintainability, test coverage, and technical debt.
"""

import ast
import os
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

from rich.console import Console
from rich.table import Table

console = Console()


@dataclass
class FunctionMetrics:
    """Metrics for a single function."""
    name: str
    file_path: str
    line_start: int
    line_end: int
    lines_of_code: int
    cyclomatic_complexity: int
    parameters: int
    cognitive_complexity: int = 0
    has_docstring: bool = False
    has_type_hints: bool = False


@dataclass
class FileMetrics:
    """Metrics for a single file."""
    path: str
    lines_of_code: int
    lines_of_comments: int
    blank_lines: int
    functions: list[FunctionMetrics] = field(default_factory=list)
    classes: int = 0
    imports: int = 0
    average_complexity: float = 0.0
    maintainability_index: float = 100.0


@dataclass
class ProjectMetrics:
    """Metrics for the entire project."""
    total_files: int = 0
    total_lines: int = 0
    code_lines: int = 0
    comment_lines: int = 0
    blank_lines: int = 0
    total_functions: int = 0
    total_classes: int = 0
    average_complexity: float = 0.0
    average_maintainability: float = 100.0
    test_coverage: float = 0.0
    documentation_coverage: float = 0.0
    technical_debt_hours: float = 0.0
    files: list[FileMetrics] = field(default_factory=list)
    calculated_at: datetime = field(default_factory=datetime.now)


class CodeMetrics:
    """
    Calculate comprehensive code metrics for quality assessment.

    Metrics calculated:
    - Lines of Code (LOC)
    - Cyclomatic Complexity
    - Cognitive Complexity
    - Maintainability Index
    - Technical Debt Estimate
    - Documentation Coverage
    """

    def __init__(self, project_path: str):
        self.project_path = Path(project_path)

    def calculate(self, target: Optional[str] = None) -> ProjectMetrics:
        """Calculate metrics for project or specific file."""
        target_path = Path(target) if target else self.project_path
        metrics = ProjectMetrics()

        if target_path.is_file():
            file_metrics = self._calculate_file_metrics(target_path)
            if file_metrics:
                metrics.files.append(file_metrics)
        else:
            for file_path in target_path.rglob("*"):
                if self._should_analyze(file_path):
                    file_metrics = self._calculate_file_metrics(file_path)
                    if file_metrics:
                        metrics.files.append(file_metrics)

        self._aggregate_metrics(metrics)
        return metrics

    def _should_analyze(self, path: Path) -> bool:
        """Check if file should be analyzed."""
        if not path.is_file():
            return False

        ignore = ["__pycache__", "node_modules", ".git", "venv", ".venv"]
        if any(p in str(path) for p in ignore):
            return False

        return path.suffix in [".py", ".js", ".ts", ".jsx", ".tsx"]

    def _calculate_file_metrics(self, file_path: Path) -> Optional[FileMetrics]:
        """Calculate metrics for a single file."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                lines = content.splitlines()
        except Exception:
            return None

        code_lines = 0
        comment_lines = 0
        blank_lines = 0
        in_multiline_comment = False

        for line in lines:
            stripped = line.strip()

            if not stripped:
                blank_lines += 1
            elif stripped.startswith("#") or stripped.startswith("//"):
                comment_lines += 1
            elif '"""' in stripped or "'''" in stripped:
                if stripped.count('"""') == 2 or stripped.count("'''") == 2:
                    comment_lines += 1
                else:
                    in_multiline_comment = not in_multiline_comment
                    comment_lines += 1
            elif in_multiline_comment:
                comment_lines += 1
            elif stripped.startswith("/*"):
                in_multiline_comment = True
                comment_lines += 1
            elif stripped.endswith("*/"):
                in_multiline_comment = False
                comment_lines += 1
            else:
                code_lines += 1

        metrics = FileMetrics(
            path=str(file_path),
            lines_of_code=code_lines,
            lines_of_comments=comment_lines,
            blank_lines=blank_lines,
        )

        # Count imports
        metrics.imports = len(re.findall(r"^(?:import|from)\s+", content, re.MULTILINE))

        # Python-specific analysis
        if file_path.suffix == ".py":
            self._analyze_python_file(content, metrics)

        # Calculate maintainability
        metrics.maintainability_index = self._calculate_maintainability(metrics)

        return metrics

    def _analyze_python_file(self, content: str, metrics: FileMetrics) -> None:
        """Analyze Python-specific metrics."""
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                metrics.classes += 1

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_metrics = self._analyze_function(node, content, metrics.path)
                metrics.functions.append(func_metrics)

        # Calculate average complexity
        if metrics.functions:
            metrics.average_complexity = sum(
                f.cyclomatic_complexity for f in metrics.functions
            ) / len(metrics.functions)

    def _analyze_function(self, node: ast.FunctionDef, content: str, file_path: str) -> FunctionMetrics:
        """Analyze a single function."""
        complexity = self._calculate_cyclomatic_complexity(node)

        # Check for docstring
        has_docstring = (
            node.body and
            isinstance(node.body[0], ast.Expr) and
            isinstance(node.body[0].value, ast.Constant) and
            isinstance(node.body[0].value.value, str)
        )

        # Check for type hints
        has_type_hints = (
            node.returns is not None or
            any(arg.annotation is not None for arg in node.args.args)
        )

        return FunctionMetrics(
            name=node.name,
            file_path=file_path,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            lines_of_code=(node.end_lineno or node.lineno) - node.lineno + 1,
            cyclomatic_complexity=complexity,
            parameters=len(node.args.args),
            cognitive_complexity=self._calculate_cognitive_complexity(node),
            has_docstring=has_docstring,
            has_type_hints=has_type_hints,
        )

    def _calculate_cyclomatic_complexity(self, node: ast.AST) -> int:
        """Calculate cyclomatic complexity of a function."""
        complexity = 1  # Base complexity

        for child in ast.walk(node):
            # Decision points
            if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
            elif isinstance(child, ast.comprehension):
                complexity += 1
                if child.ifs:
                    complexity += len(child.ifs)
            elif isinstance(child, ast.Assert):
                complexity += 1
            elif isinstance(child, ast.Match):  # Python 3.10+
                complexity += len(child.cases)

        return complexity

    def _calculate_cognitive_complexity(self, node: ast.AST, nesting: int = 0) -> int:
        """Calculate cognitive complexity (how hard code is to understand)."""
        complexity = 0

        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.If, ast.While, ast.For)):
                complexity += 1 + nesting
                complexity += self._calculate_cognitive_complexity(child, nesting + 1)
            elif isinstance(child, ast.BoolOp):
                complexity += 1
            elif isinstance(child, (ast.Break, ast.Continue)):
                complexity += 1
            elif isinstance(child, ast.ExceptHandler):
                complexity += 1 + nesting
                complexity += self._calculate_cognitive_complexity(child, nesting + 1)
            elif isinstance(child, ast.Lambda):
                complexity += 1
            else:
                complexity += self._calculate_cognitive_complexity(child, nesting)

        return complexity

    def _calculate_maintainability(self, metrics: FileMetrics) -> float:
        """
        Calculate Maintainability Index (0-100).

        Based on: MI = 171 - 5.2 * ln(V) - 0.23 * G - 16.2 * ln(LOC)
        Simplified version for practical use.
        """
        import math

        if metrics.lines_of_code == 0:
            return 100.0

        loc = max(1, metrics.lines_of_code)
        complexity = max(1, metrics.average_complexity)
        comment_ratio = metrics.lines_of_comments / max(1, loc)

        # Simplified MI calculation
        mi = 171 - 5.2 * math.log(loc) - 0.23 * complexity

        # Bonus for comments
        mi += comment_ratio * 20

        # Normalize to 0-100
        mi = max(0, min(100, mi))

        return round(mi, 2)

    def _aggregate_metrics(self, metrics: ProjectMetrics) -> None:
        """Aggregate file metrics into project metrics."""
        metrics.total_files = len(metrics.files)

        for file in metrics.files:
            metrics.total_lines += file.lines_of_code + file.lines_of_comments + file.blank_lines
            metrics.code_lines += file.lines_of_code
            metrics.comment_lines += file.lines_of_comments
            metrics.blank_lines += file.blank_lines
            metrics.total_functions += len(file.functions)
            metrics.total_classes += file.classes

        if metrics.files:
            metrics.average_complexity = sum(f.average_complexity for f in metrics.files) / len(metrics.files)
            metrics.average_maintainability = sum(f.maintainability_index for f in metrics.files) / len(metrics.files)

        # Calculate documentation coverage
        total_funcs = sum(len(f.functions) for f in metrics.files)
        documented_funcs = sum(
            sum(1 for func in f.functions if func.has_docstring)
            for f in metrics.files
        )
        if total_funcs > 0:
            metrics.documentation_coverage = (documented_funcs / total_funcs) * 100

        # Estimate technical debt (rough estimate)
        metrics.technical_debt_hours = self._estimate_technical_debt(metrics)

    def _estimate_technical_debt(self, metrics: ProjectMetrics) -> float:
        """Estimate technical debt in hours."""
        debt = 0.0

        # Complex functions need refactoring
        for file in metrics.files:
            for func in file.functions:
                if func.cyclomatic_complexity > 10:
                    debt += 2.0  # 2 hours to refactor
                elif func.cyclomatic_complexity > 7:
                    debt += 1.0

                if func.lines_of_code > 50:
                    debt += 1.5

                if not func.has_docstring:
                    debt += 0.25

                if not func.has_type_hints:
                    debt += 0.25

        # Low maintainability files
        for file in metrics.files:
            if file.maintainability_index < 50:
                debt += 4.0
            elif file.maintainability_index < 70:
                debt += 2.0

        return round(debt, 1)

    def print_report(self, metrics: ProjectMetrics) -> None:
        """Print formatted metrics report."""
        console.print("\n[bold]Code Metrics Report[/bold]")
        console.print("=" * 60)

        # Summary table
        table = Table(title="Project Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Total Files", str(metrics.total_files))
        table.add_row("Total Lines", str(metrics.total_lines))
        table.add_row("Code Lines", str(metrics.code_lines))
        table.add_row("Comment Lines", str(metrics.comment_lines))
        table.add_row("Blank Lines", str(metrics.blank_lines))
        table.add_row("Functions", str(metrics.total_functions))
        table.add_row("Classes", str(metrics.total_classes))
        table.add_row("Avg Complexity", f"{metrics.average_complexity:.2f}")
        table.add_row("Maintainability", f"{metrics.average_maintainability:.1f}/100")
        table.add_row("Doc Coverage", f"{metrics.documentation_coverage:.1f}%")
        table.add_row("Technical Debt", f"{metrics.technical_debt_hours:.1f} hours")

        console.print(table)

        # Complex functions
        complex_funcs = []
        for file in metrics.files:
            for func in file.functions:
                if func.cyclomatic_complexity > 7:
                    complex_funcs.append(func)

        if complex_funcs:
            console.print("\n[bold yellow]Complex Functions (need refactoring):[/bold yellow]")
            complex_funcs.sort(key=lambda f: f.cyclomatic_complexity, reverse=True)
            for func in complex_funcs[:10]:
                console.print(f"  {func.name} ({func.file_path}:{func.line_start})")
                console.print(f"    Complexity: {func.cyclomatic_complexity}, Lines: {func.lines_of_code}")

        # Low maintainability files
        low_maint = [f for f in metrics.files if f.maintainability_index < 70]
        if low_maint:
            console.print("\n[bold red]Low Maintainability Files:[/bold red]")
            low_maint.sort(key=lambda f: f.maintainability_index)
            for file in low_maint[:5]:
                console.print(f"  {file.path}: {file.maintainability_index:.1f}/100")

    def get_quality_grade(self, metrics: ProjectMetrics) -> str:
        """Get letter grade for code quality."""
        score = (
            metrics.average_maintainability * 0.4 +
            min(100, (10 - min(10, metrics.average_complexity)) * 10) * 0.3 +
            metrics.documentation_coverage * 0.2 +
            (100 if metrics.technical_debt_hours < 10 else max(0, 100 - metrics.technical_debt_hours)) * 0.1
        )

        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"
