"""Rate limiter for respectful web scraping."""

import asyncio
import time
from collections import defaultdict
from typing import Optional
import logging

from ..config import get_settings

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter for web requests.

    Ensures we don't overwhelm websites with requests and respects
    reasonable rate limits.
    """

    def __init__(
        self,
        requests_per_minute: Optional[int] = None,
        delay_seconds: Optional[float] = None
    ):
        settings = get_settings()
        self.requests_per_minute = requests_per_minute or settings.max_requests_per_minute
        self.delay_seconds = delay_seconds or settings.scrape_delay_seconds

        # Track requests per domain
        self._domain_timestamps: dict[str, list[float]] = defaultdict(list)
        self._last_request_time: dict[str, float] = defaultdict(float)
        self._lock = asyncio.Lock()

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc.lower()

    def _cleanup_old_timestamps(self, domain: str, window_seconds: int = 60):
        """Remove timestamps older than the window."""
        current_time = time.time()
        cutoff = current_time - window_seconds
        self._domain_timestamps[domain] = [
            ts for ts in self._domain_timestamps[domain]
            if ts > cutoff
        ]

    async def acquire(self, url: str) -> None:
        """
        Wait until we can make a request to the given URL.

        This implements both:
        1. Per-domain rate limiting (requests per minute)
        2. Minimum delay between requests to the same domain
        """
        domain = self._get_domain(url)

        async with self._lock:
            current_time = time.time()

            # Clean up old timestamps
            self._cleanup_old_timestamps(domain)

            # Check if we've exceeded requests per minute
            if len(self._domain_timestamps[domain]) >= self.requests_per_minute:
                oldest = min(self._domain_timestamps[domain])
                wait_time = 60 - (current_time - oldest)
                if wait_time > 0:
                    logger.debug(f"Rate limit reached for {domain}, waiting {wait_time:.1f}s")
                    await asyncio.sleep(wait_time)
                    current_time = time.time()
                    self._cleanup_old_timestamps(domain)

            # Enforce minimum delay between requests
            last_request = self._last_request_time[domain]
            if last_request > 0:
                time_since_last = current_time - last_request
                if time_since_last < self.delay_seconds:
                    wait_time = self.delay_seconds - time_since_last
                    logger.debug(f"Enforcing delay for {domain}, waiting {wait_time:.1f}s")
                    await asyncio.sleep(wait_time)
                    current_time = time.time()

            # Record this request
            self._domain_timestamps[domain].append(current_time)
            self._last_request_time[domain] = current_time

    def sync_acquire(self, url: str) -> None:
        """Synchronous version of acquire for non-async code."""
        domain = self._get_domain(url)
        current_time = time.time()

        # Clean up old timestamps
        self._cleanup_old_timestamps(domain)

        # Check if we've exceeded requests per minute
        if len(self._domain_timestamps[domain]) >= self.requests_per_minute:
            oldest = min(self._domain_timestamps[domain])
            wait_time = 60 - (current_time - oldest)
            if wait_time > 0:
                logger.debug(f"Rate limit reached for {domain}, waiting {wait_time:.1f}s")
                time.sleep(wait_time)
                current_time = time.time()
                self._cleanup_old_timestamps(domain)

        # Enforce minimum delay between requests
        last_request = self._last_request_time[domain]
        if last_request > 0:
            time_since_last = current_time - last_request
            if time_since_last < self.delay_seconds:
                wait_time = self.delay_seconds - time_since_last
                logger.debug(f"Enforcing delay for {domain}, waiting {wait_time:.1f}s")
                time.sleep(wait_time)
                current_time = time.time()

        # Record this request
        self._domain_timestamps[domain].append(current_time)
        self._last_request_time[domain] = current_time

    def get_stats(self, domain: str = None) -> dict:
        """Get rate limiting statistics."""
        if domain:
            self._cleanup_old_timestamps(domain)
            return {
                "domain": domain,
                "requests_last_minute": len(self._domain_timestamps[domain]),
                "limit": self.requests_per_minute
            }

        stats = {}
        for d in self._domain_timestamps:
            self._cleanup_old_timestamps(d)
            stats[d] = {
                "requests_last_minute": len(self._domain_timestamps[d]),
                "limit": self.requests_per_minute
            }
        return stats


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter
