"""
Code Fixer Module
=================

Automatically fix common code issues and apply best practices.
Supports safe auto-fixing with preview and rollback capabilities.
"""

import ast
import re
import shutil
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Callable

from rich.console import Console
from rich.syntax import Syntax
from rich.panel import Panel

console = Console()


@dataclass
class Fix:
    """Represents a single code fix."""
    file_path: str
    line_number: int
    original: str
    fixed: str
    description: str
    rule_id: str
    auto_applied: bool = False


@dataclass
class FixResult:
    """Result of applying fixes."""
    total_fixes: int = 0
    applied_fixes: int = 0
    skipped_fixes: int = 0
    errors: list[str] = field(default_factory=list)
    fixes: list[Fix] = field(default_factory=list)


class CodeFixer:
    """
    Automatically fix code issues with safety measures.

    Features:
    - Safe auto-fixing with backup
    - Preview mode
    - Rollback capability
    - Support for Python, JavaScript, HTML, CSS
    """

    def __init__(self, project_path: str, backup_dir: Optional[str] = None):
        self.project_path = Path(project_path)
        self.backup_dir = Path(backup_dir) if backup_dir else self.project_path / ".fix_backups"
        self.fix_history: list[tuple[str, str]] = []  # (original_path, backup_path)

    def fix_file(
        self,
        file_path: str,
        preview: bool = True,
        auto_apply: bool = False
    ) -> FixResult:
        """
        Fix issues in a single file.

        Args:
            file_path: Path to file to fix
            preview: Show preview before applying
            auto_apply: Automatically apply all fixes

        Returns:
            FixResult with details of fixes made
        """
        path = Path(file_path)
        result = FixResult()

        try:
            with open(path, "r", encoding="utf-8") as f:
                original_content = f.read()
        except Exception as e:
            result.errors.append(f"Could not read file: {e}")
            return result

        # Determine file type and apply appropriate fixes
        extension = path.suffix.lower()
        fixed_content = original_content
        fixes = []

        if extension == ".py":
            fixed_content, fixes = self._fix_python(path, original_content)
        elif extension in (".js", ".jsx", ".ts", ".tsx"):
            fixed_content, fixes = self._fix_javascript(path, original_content)
        elif extension in (".html", ".htm"):
            fixed_content, fixes = self._fix_html(path, original_content)
        elif extension == ".css":
            fixed_content, fixes = self._fix_css(path, original_content)

        result.fixes = fixes
        result.total_fixes = len(fixes)

        if not fixes:
            console.print(f"[green]No fixes needed for {file_path}[/green]")
            return result

        # Preview changes
        if preview and not auto_apply:
            self._show_preview(file_path, original_content, fixed_content, fixes)

            if not self._confirm_apply():
                result.skipped_fixes = len(fixes)
                return result

        # Create backup and apply fixes
        if fixed_content != original_content:
            self._create_backup(path)

            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(fixed_content)
                result.applied_fixes = len(fixes)
                console.print(f"[green]Applied {len(fixes)} fix(es) to {file_path}[/green]")
            except Exception as e:
                result.errors.append(f"Could not write file: {e}")
                self._restore_backup(path)

        return result

    def fix_project(self, preview: bool = True) -> FixResult:
        """Fix all files in the project."""
        total_result = FixResult()

        for file_path in self.project_path.rglob("*"):
            if self._should_fix(file_path):
                result = self.fix_file(str(file_path), preview=preview)
                total_result.total_fixes += result.total_fixes
                total_result.applied_fixes += result.applied_fixes
                total_result.skipped_fixes += result.skipped_fixes
                total_result.errors.extend(result.errors)
                total_result.fixes.extend(result.fixes)

        return total_result

    def _should_fix(self, path: Path) -> bool:
        """Check if file should be fixed."""
        if not path.is_file():
            return False

        ignore = ["__pycache__", "node_modules", ".git", "venv", ".venv", ".fix_backups"]
        if any(p in str(path) for p in ignore):
            return False

        return path.suffix in [".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".htm", ".css"]

    def _fix_python(self, path: Path, content: str) -> tuple[str, list[Fix]]:
        """Apply Python-specific fixes."""
        fixes = []
        lines = content.splitlines(keepends=True)
        fixed_lines = []

        for i, line in enumerate(lines, 1):
            original_line = line
            fixed_line = line

            # Fix trailing whitespace
            if line.rstrip() != line.rstrip('\n'):
                fixed_line = line.rstrip() + '\n' if line.endswith('\n') else line.rstrip()
                fixes.append(Fix(
                    file_path=str(path),
                    line_number=i,
                    original=original_line.rstrip('\n'),
                    fixed=fixed_line.rstrip('\n'),
                    description="Remove trailing whitespace",
                    rule_id="W291",
                ))

            # Fix comparison to None
            none_compare = re.search(r'(\w+)\s*==\s*None', fixed_line)
            if none_compare:
                fixed_line = re.sub(r'(\w+)\s*==\s*None', r'\1 is None', fixed_line)
                fixes.append(Fix(
                    file_path=str(path),
                    line_number=i,
                    original=original_line.rstrip('\n'),
                    fixed=fixed_line.rstrip('\n'),
                    description="Use 'is None' instead of '== None'",
                    rule_id="E711",
                ))

            # Fix comparison to True/False
            bool_compare = re.search(r'(\w+)\s*==\s*(True|False)', fixed_line)
            if bool_compare:
                var_name = bool_compare.group(1)
                bool_val = bool_compare.group(2)
                replacement = var_name if bool_val == "True" else f"not {var_name}"
                fixed_line = re.sub(r'\w+\s*==\s*(True|False)', replacement, fixed_line)
                fixes.append(Fix(
                    file_path=str(path),
                    line_number=i,
                    original=original_line.rstrip('\n'),
                    fixed=fixed_line.rstrip('\n'),
                    description=f"Simplify boolean comparison",
                    rule_id="E712",
                ))

            # Fix multiple imports on one line
            if re.match(r'^import\s+\w+,\s*\w+', fixed_line.strip()):
                imports = re.findall(r'import\s+([\w,\s]+)', fixed_line.strip())
                if imports:
                    modules = [m.strip() for m in imports[0].split(',')]
                    indent = len(fixed_line) - len(fixed_line.lstrip())
                    fixed_line = '\n'.join([' ' * indent + f'import {m}' for m in modules]) + '\n'
                    fixes.append(Fix(
                        file_path=str(path),
                        line_number=i,
                        original=original_line.rstrip('\n'),
                        fixed=fixed_line.rstrip('\n'),
                        description="Split multiple imports to separate lines",
                        rule_id="E401",
                    ))

            fixed_lines.append(fixed_line)

        fixed_content = ''.join(fixed_lines)

        # Ensure file ends with newline
        if fixed_content and not fixed_content.endswith('\n'):
            fixed_content += '\n'
            fixes.append(Fix(
                file_path=str(path),
                line_number=len(lines),
                original="(end of file)",
                fixed="(newline added)",
                description="Add newline at end of file",
                rule_id="W292",
            ))

        return fixed_content, fixes

    def _fix_javascript(self, path: Path, content: str) -> tuple[str, list[Fix]]:
        """Apply JavaScript-specific fixes."""
        fixes = []
        lines = content.splitlines(keepends=True)
        fixed_lines = []

        for i, line in enumerate(lines, 1):
            original_line = line
            fixed_line = line

            # Fix var to let/const
            var_match = re.match(r'^(\s*)var\s+(\w+)\s*=', line)
            if var_match:
                indent = var_match.group(1)
                var_name = var_match.group(2)
                # Use const for simple assignments
                fixed_line = re.sub(r'^(\s*)var\s+', r'\1const ', line)
                fixes.append(Fix(
                    file_path=str(path),
                    line_number=i,
                    original=original_line.rstrip('\n'),
                    fixed=fixed_line.rstrip('\n'),
                    description="Replace var with const",
                    rule_id="JS004",
                ))

            # Fix == to ===
            if '==' in fixed_line and '===' not in fixed_line and '!==' not in fixed_line:
                # Be careful not to change !== or ===
                fixed_line = re.sub(r'([^!=])={2}([^=])', r'\1===\2', fixed_line)
                if fixed_line != original_line:
                    fixes.append(Fix(
                        file_path=str(path),
                        line_number=i,
                        original=original_line.rstrip('\n'),
                        fixed=fixed_line.rstrip('\n'),
                        description="Use strict equality (===)",
                        rule_id="JS005",
                    ))

            # Fix != to !==
            if '!=' in fixed_line and '!==' not in fixed_line:
                fixed_line = re.sub(r'!=([^=])', r'!==\1', fixed_line)
                if fixed_line != original_line:
                    fixes.append(Fix(
                        file_path=str(path),
                        line_number=i,
                        original=original_line.rstrip('\n'),
                        fixed=fixed_line.rstrip('\n'),
                        description="Use strict inequality (!==)",
                        rule_id="JS005",
                    ))

            fixed_lines.append(fixed_line)

        return ''.join(fixed_lines), fixes

    def _fix_html(self, path: Path, content: str) -> tuple[str, list[Fix]]:
        """Apply HTML-specific fixes."""
        fixes = []
        fixed_content = content

        # Add alt to images without it
        img_pattern = r'<img([^>]*)(?<!alt=")(/?>)'
        matches = list(re.finditer(img_pattern, fixed_content, re.IGNORECASE))

        for match in reversed(matches):
            if 'alt=' not in match.group(1).lower():
                line_num = content[:match.start()].count('\n') + 1
                # Add empty alt attribute
                replacement = f'<img{match.group(1)} alt=""{match.group(2)}'
                fixed_content = fixed_content[:match.start()] + replacement + fixed_content[match.end():]
                fixes.append(Fix(
                    file_path=str(path),
                    line_number=line_num,
                    original=match.group(0),
                    fixed=replacement,
                    description="Add alt attribute to image",
                    rule_id="A001",
                ))

        return fixed_content, fixes

    def _fix_css(self, path: Path, content: str) -> tuple[str, list[Fix]]:
        """Apply CSS-specific fixes."""
        fixes = []
        lines = content.splitlines(keepends=True)
        fixed_lines = []

        for i, line in enumerate(lines, 1):
            original_line = line
            fixed_line = line

            # Remove trailing whitespace
            if line.rstrip() != line.rstrip('\n'):
                fixed_line = line.rstrip() + '\n' if line.endswith('\n') else line.rstrip()
                fixes.append(Fix(
                    file_path=str(path),
                    line_number=i,
                    original=original_line.rstrip('\n'),
                    fixed=fixed_line.rstrip('\n'),
                    description="Remove trailing whitespace",
                    rule_id="CSS100",
                ))

            fixed_lines.append(fixed_line)

        return ''.join(fixed_lines), fixes

    def _show_preview(
        self,
        file_path: str,
        original: str,
        fixed: str,
        fixes: list[Fix]
    ) -> None:
        """Show preview of changes."""
        console.print(f"\n[bold]Preview of changes for {file_path}:[/bold]")

        for fix in fixes[:20]:  # Show first 20 fixes
            console.print(f"\n[yellow]Line {fix.line_number}:[/yellow] {fix.description}")
            console.print(f"  [red]- {fix.original}[/red]")
            console.print(f"  [green]+ {fix.fixed}[/green]")

        if len(fixes) > 20:
            console.print(f"\n... and {len(fixes) - 20} more fixes")

    def _confirm_apply(self) -> bool:
        """Ask user to confirm applying fixes."""
        try:
            response = input("\nApply these fixes? [y/N]: ")
            return response.lower() in ('y', 'yes')
        except EOFError:
            return False

    def _create_backup(self, file_path: Path) -> None:
        """Create backup of file before modifying."""
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.name}.{timestamp}.bak"
        backup_path = self.backup_dir / backup_name

        shutil.copy2(file_path, backup_path)
        self.fix_history.append((str(file_path), str(backup_path)))

    def _restore_backup(self, file_path: Path) -> bool:
        """Restore file from backup."""
        for original, backup in reversed(self.fix_history):
            if original == str(file_path):
                shutil.copy2(backup, file_path)
                console.print(f"[green]Restored {file_path} from backup[/green]")
                return True
        return False

    def rollback_all(self) -> int:
        """Rollback all changes made in this session."""
        restored = 0
        for original, backup in reversed(self.fix_history):
            try:
                shutil.copy2(backup, original)
                restored += 1
            except Exception as e:
                console.print(f"[red]Could not restore {original}: {e}[/red]")

        console.print(f"[green]Restored {restored} file(s)[/green]")
        return restored
