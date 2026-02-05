"""
Performance Analyzer Module
===========================

Detailed performance analysis including Core Web Vitals simulation,
resource optimization recommendations, and loading strategies.
"""

import asyncio
import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urljoin

import aiohttp
from rich.console import Console
from rich.table import Table

console = Console()


@dataclass
class ResourceInfo:
    """Information about a loaded resource."""
    url: str
    resource_type: str
    size: int = 0
    load_time: float = 0.0
    cached: bool = False
    compressed: bool = False


@dataclass
class PerformanceMetrics:
    """Core performance metrics."""
    time_to_first_byte: float = 0.0
    first_contentful_paint: float = 0.0
    largest_contentful_paint: float = 0.0
    total_blocking_time: float = 0.0
    cumulative_layout_shift: float = 0.0
    speed_index: float = 0.0
    total_page_size: int = 0
    total_requests: int = 0
    resources: list[ResourceInfo] = field(default_factory=list)


@dataclass
class PerformanceRecommendation:
    """Performance improvement recommendation."""
    priority: str  # high, medium, low
    title: str
    description: str
    impact: str
    resources_affected: list[str] = field(default_factory=list)


class PerformanceAnalyzer:
    """
    Analyze website performance and provide optimization recommendations.

    Analyzes:
    - Page load metrics
    - Resource loading
    - Caching effectiveness
    - Compression usage
    - Critical rendering path
    """

    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url
        self.timeout = timeout

    async def analyze(self, url: Optional[str] = None) -> PerformanceMetrics:
        """
        Analyze performance of a URL.

        Args:
            url: URL to analyze (uses base_url if not provided)

        Returns:
            PerformanceMetrics with detailed analysis
        """
        target_url = url or self.base_url
        metrics = PerformanceMetrics()

        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        ) as session:
            # Measure initial page load
            start_time = asyncio.get_event_loop().time()

            async with session.get(target_url) as response:
                ttfb = asyncio.get_event_loop().time() - start_time
                metrics.time_to_first_byte = ttfb

                content = await response.text()
                page_size = len(content.encode("utf-8"))
                metrics.total_page_size = page_size

                # Check compression
                if response.headers.get("Content-Encoding"):
                    metrics.resources.append(ResourceInfo(
                        url=target_url,
                        resource_type="document",
                        size=page_size,
                        load_time=ttfb,
                        compressed=True,
                    ))

            # Analyze resources
            await self._analyze_resources(session, content, target_url, metrics)

            # Estimate Core Web Vitals
            self._estimate_web_vitals(metrics)

        return metrics

    async def _analyze_resources(
        self,
        session: aiohttp.ClientSession,
        html: str,
        base_url: str,
        metrics: PerformanceMetrics
    ) -> None:
        """Analyze all resources loaded by the page."""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")

        resources = []

        # Scripts
        for script in soup.find_all("script", src=True):
            src = script.get("src")
            if src:
                resources.append((urljoin(base_url, src), "script"))

        # Stylesheets
        for link in soup.find_all("link", rel="stylesheet"):
            href = link.get("href")
            if href:
                resources.append((urljoin(base_url, href), "stylesheet"))

        # Images
        for img in soup.find_all("img", src=True):
            src = img.get("src")
            if src and not src.startswith("data:"):
                resources.append((urljoin(base_url, src), "image"))

        # Analyze resources in parallel
        tasks = [
            self._check_resource(session, url, res_type)
            for url, res_type in resources[:30]  # Limit to 30 resources
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, ResourceInfo):
                metrics.resources.append(result)
                metrics.total_page_size += result.size
                metrics.total_requests += 1

    async def _check_resource(
        self,
        session: aiohttp.ClientSession,
        url: str,
        resource_type: str
    ) -> Optional[ResourceInfo]:
        """Check a single resource."""
        try:
            start = asyncio.get_event_loop().time()
            async with session.head(url, allow_redirects=True) as response:
                load_time = asyncio.get_event_loop().time() - start

                size = int(response.headers.get("Content-Length", 0))
                compressed = bool(response.headers.get("Content-Encoding"))
                cached = "Cache-Control" in response.headers

                return ResourceInfo(
                    url=url,
                    resource_type=resource_type,
                    size=size,
                    load_time=load_time,
                    compressed=compressed,
                    cached=cached,
                )
        except Exception:
            return None

    def _estimate_web_vitals(self, metrics: PerformanceMetrics) -> None:
        """Estimate Core Web Vitals based on collected data."""
        # Estimate FCP (First Contentful Paint)
        # Based on TTFB + time to parse and render first content
        metrics.first_contentful_paint = metrics.time_to_first_byte * 2.5

        # Estimate LCP (Largest Contentful Paint)
        # Based on largest image load time or document load
        image_resources = [r for r in metrics.resources if r.resource_type == "image"]
        if image_resources:
            largest_image_time = max(r.load_time for r in image_resources)
            metrics.largest_contentful_paint = metrics.first_contentful_paint + largest_image_time
        else:
            metrics.largest_contentful_paint = metrics.first_contentful_paint * 1.5

        # Estimate TBT (Total Blocking Time)
        script_resources = [r for r in metrics.resources if r.resource_type == "script"]
        blocking_time = sum(
            max(0, r.load_time - 0.05)  # Tasks over 50ms
            for r in script_resources
        )
        metrics.total_blocking_time = blocking_time

        # Estimate CLS (Cumulative Layout Shift) - rough estimate
        images_without_dimensions = [
            r for r in metrics.resources
            if r.resource_type == "image" and r.size > 10000
        ]
        metrics.cumulative_layout_shift = len(images_without_dimensions) * 0.05

        # Speed Index estimate
        metrics.speed_index = (
            metrics.first_contentful_paint +
            metrics.largest_contentful_paint
        ) / 2 * 1000

    def get_recommendations(self, metrics: PerformanceMetrics) -> list[PerformanceRecommendation]:
        """Generate performance recommendations."""
        recommendations = []

        # TTFB recommendation
        if metrics.time_to_first_byte > 0.8:
            recommendations.append(PerformanceRecommendation(
                priority="high",
                title="Reduce server response time",
                description=f"TTFB is {metrics.time_to_first_byte:.2f}s (should be < 0.8s)",
                impact="Improves all loading metrics",
            ))

        # Page size recommendation
        if metrics.total_page_size > 2_000_000:
            recommendations.append(PerformanceRecommendation(
                priority="high",
                title="Reduce page size",
                description=f"Page is {metrics.total_page_size / 1_000_000:.1f}MB",
                impact="Faster loading on slow connections",
            ))

        # Image optimization
        large_images = [
            r for r in metrics.resources
            if r.resource_type == "image" and r.size > 200_000
        ]
        if large_images:
            recommendations.append(PerformanceRecommendation(
                priority="high",
                title="Optimize large images",
                description=f"{len(large_images)} images are > 200KB",
                impact="Major page size reduction",
                resources_affected=[r.url for r in large_images],
            ))

        # Compression
        uncompressed = [r for r in metrics.resources if not r.compressed]
        if uncompressed:
            recommendations.append(PerformanceRecommendation(
                priority="medium",
                title="Enable compression",
                description=f"{len(uncompressed)} resources not compressed",
                impact="30-70% size reduction",
                resources_affected=[r.url for r in uncompressed[:5]],
            ))

        # Caching
        uncached = [r for r in metrics.resources if not r.cached]
        if uncached:
            recommendations.append(PerformanceRecommendation(
                priority="medium",
                title="Add cache headers",
                description=f"{len(uncached)} resources without cache headers",
                impact="Faster repeat visits",
                resources_affected=[r.url for r in uncached[:5]],
            ))

        # Too many requests
        if metrics.total_requests > 50:
            recommendations.append(PerformanceRecommendation(
                priority="medium",
                title="Reduce HTTP requests",
                description=f"{metrics.total_requests} requests made",
                impact="Faster initial load",
            ))

        # LCP recommendation
        if metrics.largest_contentful_paint > 2.5:
            recommendations.append(PerformanceRecommendation(
                priority="high",
                title="Improve Largest Contentful Paint",
                description=f"LCP is {metrics.largest_contentful_paint:.1f}s (should be < 2.5s)",
                impact="Better user experience and SEO",
            ))

        return recommendations

    def print_report(self, metrics: PerformanceMetrics) -> None:
        """Print formatted performance report."""
        console.print("\n[bold]Performance Analysis Report[/bold]")
        console.print("=" * 60)

        # Core Web Vitals
        table = Table(title="Core Web Vitals (Estimated)")
        table.add_column("Metric", style="cyan")
        table.add_column("Value")
        table.add_column("Status")

        def get_status(value: float, good: float, poor: float) -> str:
            if value <= good:
                return "[green]Good[/green]"
            elif value <= poor:
                return "[yellow]Needs Improvement[/yellow]"
            return "[red]Poor[/red]"

        table.add_row(
            "Time to First Byte",
            f"{metrics.time_to_first_byte:.2f}s",
            get_status(metrics.time_to_first_byte, 0.8, 1.8)
        )
        table.add_row(
            "First Contentful Paint",
            f"{metrics.first_contentful_paint:.2f}s",
            get_status(metrics.first_contentful_paint, 1.8, 3.0)
        )
        table.add_row(
            "Largest Contentful Paint",
            f"{metrics.largest_contentful_paint:.2f}s",
            get_status(metrics.largest_contentful_paint, 2.5, 4.0)
        )
        table.add_row(
            "Total Blocking Time",
            f"{metrics.total_blocking_time * 1000:.0f}ms",
            get_status(metrics.total_blocking_time * 1000, 200, 600)
        )
        table.add_row(
            "Cumulative Layout Shift",
            f"{metrics.cumulative_layout_shift:.3f}",
            get_status(metrics.cumulative_layout_shift, 0.1, 0.25)
        )

        console.print(table)

        # Resource summary
        console.print(f"\n[bold]Resource Summary:[/bold]")
        console.print(f"  Total Page Size: {metrics.total_page_size / 1_000_000:.2f} MB")
        console.print(f"  Total Requests: {metrics.total_requests}")

        # Recommendations
        recommendations = self.get_recommendations(metrics)
        if recommendations:
            console.print("\n[bold]Recommendations:[/bold]")
            for rec in recommendations:
                color = {"high": "red", "medium": "yellow", "low": "blue"}[rec.priority]
                console.print(f"\n  [{color}][{rec.priority.upper()}][/{color}] {rec.title}")
                console.print(f"    {rec.description}")
                console.print(f"    Impact: {rec.impact}")
