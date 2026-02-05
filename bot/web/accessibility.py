"""
Accessibility Checker Module
============================

WCAG 2.1 compliance checker for ensuring website accessibility
for users with disabilities.
"""

import re
from dataclasses import dataclass, field
from typing import Optional

import aiohttp
from bs4 import BeautifulSoup
from rich.console import Console
from rich.table import Table

console = Console()


@dataclass
class AccessibilityIssue:
    """An accessibility issue found during analysis."""
    wcag_criterion: str
    level: str  # A, AA, AAA
    severity: str  # critical, high, medium, low
    title: str
    description: str
    element: str
    recommendation: str
    impact: str


@dataclass
class AccessibilityResult:
    """Complete accessibility analysis result."""
    url: str
    score: int = 100
    level_a_issues: int = 0
    level_aa_issues: int = 0
    level_aaa_issues: int = 0
    issues: list[AccessibilityIssue] = field(default_factory=list)
    passed_checks: list[str] = field(default_factory=list)


class AccessibilityChecker:
    """
    Check website accessibility against WCAG 2.1 guidelines.

    Checks:
    - Perceivable: Images, multimedia, adaptable content
    - Operable: Keyboard access, timing, navigation
    - Understandable: Readable, predictable, input assistance
    - Robust: Compatible with assistive technologies
    """

    def __init__(self):
        pass

    async def check(self, url: str) -> AccessibilityResult:
        """
        Run accessibility checks on a URL.

        Args:
            url: URL to check

        Returns:
            AccessibilityResult with all findings
        """
        result = AccessibilityResult(url=url)

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as response:
                    if response.status != 200:
                        result.issues.append(AccessibilityIssue(
                            wcag_criterion="N/A",
                            level="A",
                            severity="critical",
                            title="Page not accessible",
                            description=f"Page returned status {response.status}",
                            element="<page>",
                            recommendation="Ensure page is accessible",
                            impact="Users cannot access content",
                        ))
                        return result

                    html = await response.text()
                    soup = BeautifulSoup(html, "html.parser")

                    # Run all checks
                    self._check_language(soup, result)
                    self._check_page_title(soup, result)
                    self._check_headings(soup, result)
                    self._check_images(soup, result)
                    self._check_links(soup, result)
                    self._check_forms(soup, result)
                    self._check_tables(soup, result)
                    self._check_color_contrast(soup, result)
                    self._check_keyboard(soup, result)
                    self._check_landmarks(soup, result)
                    self._check_focus(soup, result)

                    # Count issues by level
                    for issue in result.issues:
                        if issue.level == "A":
                            result.level_a_issues += 1
                        elif issue.level == "AA":
                            result.level_aa_issues += 1
                        elif issue.level == "AAA":
                            result.level_aaa_issues += 1

                    # Calculate score
                    self._calculate_score(result)

            except Exception as e:
                result.issues.append(AccessibilityIssue(
                    wcag_criterion="N/A",
                    level="A",
                    severity="critical",
                    title="Check failed",
                    description=str(e),
                    element="<page>",
                    recommendation="Check URL and try again",
                    impact="Cannot verify accessibility",
                ))

        return result

    def _check_language(self, soup: BeautifulSoup, result: AccessibilityResult) -> None:
        """WCAG 3.1.1: Language of Page (Level A)"""
        html_tag = soup.find("html")

        if not html_tag:
            return

        lang = html_tag.get("lang", "").strip()

        if not lang:
            result.issues.append(AccessibilityIssue(
                wcag_criterion="3.1.1",
                level="A",
                severity="high",
                title="Missing page language",
                description="HTML element lacks lang attribute",
                element="<html>",
                recommendation='Add lang="en" or appropriate language code',
                impact="Screen readers may mispronounce content",
            ))
        else:
            result.passed_checks.append("3.1.1: Page language defined")

    def _check_page_title(self, soup: BeautifulSoup, result: AccessibilityResult) -> None:
        """WCAG 2.4.2: Page Titled (Level A)"""
        title = soup.find("title")

        if not title or not title.text.strip():
            result.issues.append(AccessibilityIssue(
                wcag_criterion="2.4.2",
                level="A",
                severity="high",
                title="Missing page title",
                description="Page has no <title> element",
                element="<head>",
                recommendation="Add descriptive title element",
                impact="Users cannot identify page purpose",
            ))
        else:
            result.passed_checks.append("2.4.2: Page has title")

    def _check_headings(self, soup: BeautifulSoup, result: AccessibilityResult) -> None:
        """WCAG 1.3.1: Info and Relationships (Level A)"""
        headings = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])

        if not headings:
            result.issues.append(AccessibilityIssue(
                wcag_criterion="1.3.1",
                level="A",
                severity="medium",
                title="No heading structure",
                description="Page has no heading elements",
                element="<body>",
                recommendation="Add heading hierarchy to structure content",
                impact="Difficult for screen reader users to navigate",
            ))
            return

        # Check for skipped levels
        levels = sorted(set(int(h.name[1]) for h in headings))
        for i, level in enumerate(levels[1:], 1):
            if level - levels[i - 1] > 1:
                result.issues.append(AccessibilityIssue(
                    wcag_criterion="1.3.1",
                    level="A",
                    severity="low",
                    title="Skipped heading level",
                    description=f"Heading level skipped from H{levels[i-1]} to H{level}",
                    element=f"<h{level}>",
                    recommendation="Maintain sequential heading hierarchy",
                    impact="May confuse users navigating by headings",
                ))
                break
        else:
            result.passed_checks.append("1.3.1: Heading structure is sequential")

        # Check for empty headings
        empty_headings = [h for h in headings if not h.text.strip()]
        if empty_headings:
            result.issues.append(AccessibilityIssue(
                wcag_criterion="1.3.1",
                level="A",
                severity="medium",
                title="Empty headings found",
                description=f"{len(empty_headings)} heading(s) have no text",
                element="<h*>",
                recommendation="Add text content to all headings",
                impact="Screen readers announce empty headings",
            ))

    def _check_images(self, soup: BeautifulSoup, result: AccessibilityResult) -> None:
        """WCAG 1.1.1: Non-text Content (Level A)"""
        images = soup.find_all("img")

        if not images:
            result.passed_checks.append("1.1.1: No images to check")
            return

        missing_alt = []
        empty_alt_decorative = []

        for img in images:
            alt = img.get("alt")
            src = img.get("src", "unknown")

            if alt is None:
                missing_alt.append(src)
            elif alt == "" and not img.get("role") == "presentation":
                # Empty alt without presentation role might be unintentional
                empty_alt_decorative.append(src)

        if missing_alt:
            result.issues.append(AccessibilityIssue(
                wcag_criterion="1.1.1",
                level="A",
                severity="critical",
                title="Images missing alt text",
                description=f"{len(missing_alt)} image(s) lack alt attribute",
                element="<img>",
                recommendation="Add alt text or alt=\"\" for decorative images",
                impact="Screen reader users cannot understand image content",
            ))

        if not missing_alt:
            result.passed_checks.append("1.1.1: All images have alt attribute")

    def _check_links(self, soup: BeautifulSoup, result: AccessibilityResult) -> None:
        """WCAG 2.4.4: Link Purpose (Level A)"""
        links = soup.find_all("a")

        vague_texts = ["click here", "read more", "learn more", "here", "more"]
        empty_links = []
        vague_links = []

        for link in links:
            text = link.text.strip().lower()
            aria_label = link.get("aria-label", "").strip()

            if not text and not aria_label and not link.find("img", alt=True):
                empty_links.append(link)
            elif text in vague_texts and not aria_label:
                vague_links.append(text)

        if empty_links:
            result.issues.append(AccessibilityIssue(
                wcag_criterion="2.4.4",
                level="A",
                severity="high",
                title="Empty links found",
                description=f"{len(empty_links)} link(s) have no accessible text",
                element="<a>",
                recommendation="Add link text or aria-label",
                impact="Screen reader users cannot understand link purpose",
            ))

        if vague_links:
            result.issues.append(AccessibilityIssue(
                wcag_criterion="2.4.4",
                level="A",
                severity="medium",
                title="Vague link text",
                description=f"Found links with non-descriptive text",
                element="<a>",
                recommendation="Use descriptive link text (avoid 'click here')",
                impact="Link purpose unclear out of context",
            ))

        # Check for new window without warning
        new_window_links = soup.find_all("a", target="_blank")
        for link in new_window_links:
            text = link.text.lower()
            aria = link.get("aria-label", "").lower()
            if "new window" not in text and "new tab" not in text and \
               "new window" not in aria and "new tab" not in aria:
                result.issues.append(AccessibilityIssue(
                    wcag_criterion="3.2.5",
                    level="AAA",
                    severity="low",
                    title="Links open new window without warning",
                    description="target=\"_blank\" links don't indicate new window",
                    element="<a target=\"_blank\">",
                    recommendation="Add '(opens in new tab)' or aria-label",
                    impact="May disorient users when window changes",
                ))
                break

    def _check_forms(self, soup: BeautifulSoup, result: AccessibilityResult) -> None:
        """WCAG 1.3.1, 3.3.2: Form accessibility"""
        inputs = soup.find_all(["input", "textarea", "select"])
        inputs = [i for i in inputs if i.get("type") not in ["hidden", "submit", "button", "reset"]]

        if not inputs:
            return

        unlabeled = []

        for input_elem in inputs:
            input_id = input_elem.get("id")
            has_label = (
                input_elem.get("aria-label") or
                input_elem.get("aria-labelledby") or
                input_elem.get("title") or
                (input_id and soup.find("label", {"for": input_id})) or
                input_elem.find_parent("label")
            )

            if not has_label:
                unlabeled.append(input_elem.get("name", input_elem.get("type", "input")))

        if unlabeled:
            result.issues.append(AccessibilityIssue(
                wcag_criterion="1.3.1",
                level="A",
                severity="critical",
                title="Form inputs without labels",
                description=f"{len(unlabeled)} input(s) lack proper labels",
                element="<input>",
                recommendation="Add <label for=\"id\">, aria-label, or aria-labelledby",
                impact="Screen reader users cannot identify input purpose",
            ))
        else:
            result.passed_checks.append("1.3.1: All form inputs have labels")

        # Check for required field indication
        required_inputs = soup.find_all(["input", "textarea", "select"], required=True)
        if required_inputs:
            # Check if there's visual indication
            result.passed_checks.append("3.3.2: Required fields marked")

    def _check_tables(self, soup: BeautifulSoup, result: AccessibilityResult) -> None:
        """WCAG 1.3.1: Table accessibility"""
        tables = soup.find_all("table")

        for table in tables:
            # Check for caption or aria-label
            has_caption = table.find("caption") or table.get("aria-label")
            headers = table.find_all("th")

            if not has_caption:
                result.issues.append(AccessibilityIssue(
                    wcag_criterion="1.3.1",
                    level="A",
                    severity="medium",
                    title="Table without caption",
                    description="Data table lacks caption or aria-label",
                    element="<table>",
                    recommendation="Add <caption> or aria-label to describe table",
                    impact="Screen reader users cannot understand table purpose",
                ))

            if not headers:
                result.issues.append(AccessibilityIssue(
                    wcag_criterion="1.3.1",
                    level="A",
                    severity="medium",
                    title="Table without headers",
                    description="Data table has no <th> elements",
                    element="<table>",
                    recommendation="Add <th> elements to identify column/row headers",
                    impact="Screen readers cannot associate cells with headers",
                ))

    def _check_color_contrast(self, soup: BeautifulSoup, result: AccessibilityResult) -> None:
        """WCAG 1.4.3: Contrast (Minimum) (Level AA)"""
        # Note: Full contrast checking requires computed styles
        # This is a basic check for inline styles

        elements_with_color = soup.find_all(style=re.compile(r"color:", re.I))

        if elements_with_color:
            result.issues.append(AccessibilityIssue(
                wcag_criterion="1.4.3",
                level="AA",
                severity="medium",
                title="Color contrast needs verification",
                description=f"{len(elements_with_color)} elements with inline color styles",
                element="<* style=\"color:...\">",
                recommendation="Verify 4.5:1 contrast ratio (3:1 for large text)",
                impact="Low contrast is difficult for users with visual impairments",
            ))
        else:
            result.passed_checks.append("1.4.3: No inline color styles to verify")

    def _check_keyboard(self, soup: BeautifulSoup, result: AccessibilityResult) -> None:
        """WCAG 2.1.1: Keyboard (Level A)"""
        # Check for mouse-only handlers
        mouse_handlers = soup.find_all(attrs={"onmouseover": True})
        mouse_handlers += soup.find_all(attrs={"onmousedown": True})

        for elem in mouse_handlers:
            if not elem.get("onfocus") and not elem.get("onkeydown"):
                result.issues.append(AccessibilityIssue(
                    wcag_criterion="2.1.1",
                    level="A",
                    severity="high",
                    title="Mouse-only interaction",
                    description="Element has mouse handler without keyboard equivalent",
                    element=f"<{elem.name}>",
                    recommendation="Add keyboard handlers (onfocus, onkeydown)",
                    impact="Keyboard users cannot interact with element",
                ))
                break

        # Check for positive tabindex
        positive_tabindex = soup.find_all(tabindex=re.compile(r"^[1-9]"))
        if positive_tabindex:
            result.issues.append(AccessibilityIssue(
                wcag_criterion="2.4.3",
                level="A",
                severity="medium",
                title="Positive tabindex used",
                description=f"{len(positive_tabindex)} elements have tabindex > 0",
                element="<* tabindex=\"N\">",
                recommendation="Use tabindex=\"0\" or \"-1\" only",
                impact="Tab order may be confusing",
            ))

    def _check_landmarks(self, soup: BeautifulSoup, result: AccessibilityResult) -> None:
        """WCAG 1.3.1: ARIA landmarks"""
        landmarks = ["main", "nav", "header", "footer", "aside", "section", "article"]
        found = {lm: bool(soup.find(lm)) for lm in landmarks}

        # Also check for ARIA roles
        for role in ["main", "navigation", "banner", "contentinfo"]:
            if soup.find(attrs={"role": role}):
                found[role] = True

        if not found.get("main") and not soup.find(attrs={"role": "main"}):
            result.issues.append(AccessibilityIssue(
                wcag_criterion="1.3.1",
                level="A",
                severity="medium",
                title="Missing main landmark",
                description="Page has no <main> element or role=\"main\"",
                element="<body>",
                recommendation="Add <main> element to wrap main content",
                impact="Screen reader users cannot skip to main content",
            ))
        else:
            result.passed_checks.append("1.3.1: Main landmark present")

        if not found.get("nav") and not soup.find(attrs={"role": "navigation"}):
            result.issues.append(AccessibilityIssue(
                wcag_criterion="1.3.1",
                level="A",
                severity="low",
                title="Missing navigation landmark",
                description="Page has no <nav> element",
                element="<body>",
                recommendation="Wrap navigation in <nav> element",
                impact="Screen reader users cannot find navigation easily",
            ))

    def _check_focus(self, soup: BeautifulSoup, result: AccessibilityResult) -> None:
        """WCAG 2.4.7: Focus Visible (Level AA)"""
        # Check for CSS that hides focus
        styles = soup.find_all("style")
        for style in styles:
            if style.string and "outline: none" in style.string.lower():
                result.issues.append(AccessibilityIssue(
                    wcag_criterion="2.4.7",
                    level="AA",
                    severity="high",
                    title="Focus outline may be hidden",
                    description="CSS contains 'outline: none'",
                    element="<style>",
                    recommendation="Ensure focus indicators are visible",
                    impact="Keyboard users cannot see current focus",
                ))
                break

        # Check for skip link
        skip_link = soup.find("a", href=re.compile(r"^#(main|content)"))
        if not skip_link:
            skip_link = soup.find("a", {"class": re.compile(r"skip", re.I)})

        if not skip_link:
            result.issues.append(AccessibilityIssue(
                wcag_criterion="2.4.1",
                level="A",
                severity="medium",
                title="Missing skip link",
                description="No skip navigation link found",
                element="<body>",
                recommendation="Add skip link to bypass repeated content",
                impact="Keyboard users must tab through all navigation",
            ))
        else:
            result.passed_checks.append("2.4.1: Skip link present")

    def _calculate_score(self, result: AccessibilityResult) -> None:
        """Calculate accessibility score."""
        score = 100

        for issue in result.issues:
            penalty = {
                "critical": 20,
                "high": 12,
                "medium": 6,
                "low": 2,
            }.get(issue.severity, 0)

            # Level A issues are more severe
            if issue.level == "A":
                penalty *= 1.5

            score -= penalty

        result.score = max(0, min(100, int(score)))

    def print_report(self, result: AccessibilityResult) -> None:
        """Print formatted accessibility report."""
        console.print("\n[bold]Accessibility Report (WCAG 2.1)[/bold]")
        console.print("=" * 60)
        console.print(f"URL: {result.url}")
        console.print(f"Score: {result.score}/100")

        # Summary
        table = Table(title="Issue Summary by WCAG Level")
        table.add_column("Level", style="cyan")
        table.add_column("Issues")
        table.add_column("Compliance")

        table.add_row("Level A (Required)", str(result.level_a_issues),
                     "[green]Pass[/green]" if result.level_a_issues == 0 else "[red]Fail[/red]")
        table.add_row("Level AA (Recommended)", str(result.level_aa_issues),
                     "[green]Pass[/green]" if result.level_aa_issues == 0 else "[yellow]Issues[/yellow]")
        table.add_row("Level AAA (Enhanced)", str(result.level_aaa_issues),
                     "[green]Pass[/green]" if result.level_aaa_issues == 0 else "[blue]Info[/blue]")

        console.print(table)

        # Passed checks
        if result.passed_checks:
            console.print("\n[bold green]Passed Checks:[/bold green]")
            for check in result.passed_checks[:10]:
                console.print(f"  [green]+[/green] {check}")

        # Issues
        if result.issues:
            console.print("\n[bold]Issues Found:[/bold]")

            # Group by level
            for level in ["A", "AA", "AAA"]:
                level_issues = [i for i in result.issues if i.level == level]
                if level_issues:
                    console.print(f"\n[bold]WCAG Level {level}:[/bold]")
                    for issue in level_issues:
                        color = {"critical": "red", "high": "orange1",
                                "medium": "yellow", "low": "blue"}[issue.severity]
                        console.print(f"\n  [{color}][{issue.wcag_criterion}][/{color}] {issue.title}")
                        console.print(f"    {issue.description}")
                        console.print(f"    [dim]Fix: {issue.recommendation}[/dim]")
                        console.print(f"    [dim]Impact: {issue.impact}[/dim]")
