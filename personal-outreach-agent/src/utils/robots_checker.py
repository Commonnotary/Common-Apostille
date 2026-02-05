"""Robots.txt compliance checker."""

import asyncio
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser
from typing import Dict, Optional
import logging
import httpx

from ..config import get_settings

logger = logging.getLogger(__name__)


class RobotsChecker:
    """
    Checks robots.txt files to ensure we respect website crawling policies.

    Caches robots.txt files to avoid repeated fetches.
    """

    def __init__(self, user_agent: Optional[str] = None):
        settings = get_settings()
        self.user_agent = user_agent or settings.user_agent
        self._cache: Dict[str, RobotFileParser] = {}
        self._failed_domains: set = set()  # Domains where we couldn't fetch robots.txt

    def _get_robots_url(self, url: str) -> str:
        """Get the robots.txt URL for a given URL."""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        parsed = urlparse(url)
        return parsed.netloc.lower()

    async def _fetch_robots(self, url: str) -> Optional[RobotFileParser]:
        """Fetch and parse a robots.txt file."""
        robots_url = self._get_robots_url(url)
        domain = self._get_domain(url)

        # Check cache
        if domain in self._cache:
            return self._cache[domain]

        # Check if we've already failed for this domain
        if domain in self._failed_domains:
            return None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    robots_url,
                    timeout=10.0,
                    follow_redirects=True,
                    headers={"User-Agent": self.user_agent}
                )

                rp = RobotFileParser()
                rp.set_url(robots_url)

                if response.status_code == 200:
                    # Parse the robots.txt content
                    lines = response.text.split('\n')
                    rp.parse(lines)
                    logger.debug(f"Parsed robots.txt for {domain}")
                elif response.status_code == 404:
                    # No robots.txt means everything is allowed
                    rp.parse([])
                    logger.debug(f"No robots.txt found for {domain} (404)")
                else:
                    # Other error - be conservative and assume disallowed
                    logger.warning(f"Failed to fetch robots.txt for {domain}: {response.status_code}")
                    self._failed_domains.add(domain)
                    return None

                self._cache[domain] = rp
                return rp

        except Exception as e:
            logger.warning(f"Error fetching robots.txt for {domain}: {e}")
            self._failed_domains.add(domain)
            return None

    def _fetch_robots_sync(self, url: str) -> Optional[RobotFileParser]:
        """Synchronous version of _fetch_robots."""
        robots_url = self._get_robots_url(url)
        domain = self._get_domain(url)

        # Check cache
        if domain in self._cache:
            return self._cache[domain]

        # Check if we've already failed for this domain
        if domain in self._failed_domains:
            return None

        try:
            with httpx.Client() as client:
                response = client.get(
                    robots_url,
                    timeout=10.0,
                    follow_redirects=True,
                    headers={"User-Agent": self.user_agent}
                )

                rp = RobotFileParser()
                rp.set_url(robots_url)

                if response.status_code == 200:
                    lines = response.text.split('\n')
                    rp.parse(lines)
                    logger.debug(f"Parsed robots.txt for {domain}")
                elif response.status_code == 404:
                    rp.parse([])
                    logger.debug(f"No robots.txt found for {domain} (404)")
                else:
                    logger.warning(f"Failed to fetch robots.txt for {domain}: {response.status_code}")
                    self._failed_domains.add(domain)
                    return None

                self._cache[domain] = rp
                return rp

        except Exception as e:
            logger.warning(f"Error fetching robots.txt for {domain}: {e}")
            self._failed_domains.add(domain)
            return None

    async def can_fetch(self, url: str) -> bool:
        """
        Check if we're allowed to fetch the given URL.

        Returns True if:
        - robots.txt allows our user agent
        - robots.txt doesn't exist (404)

        Returns False if:
        - robots.txt explicitly disallows our user agent
        - We couldn't fetch robots.txt (be conservative)
        """
        rp = await self._fetch_robots(url)

        if rp is None:
            # Couldn't fetch robots.txt - be conservative
            logger.warning(f"Being conservative about {url} - couldn't verify robots.txt")
            return False

        can_fetch = rp.can_fetch(self.user_agent, url)

        if not can_fetch:
            logger.info(f"robots.txt disallows fetching: {url}")

        return can_fetch

    def can_fetch_sync(self, url: str) -> bool:
        """Synchronous version of can_fetch."""
        rp = self._fetch_robots_sync(url)

        if rp is None:
            logger.warning(f"Being conservative about {url} - couldn't verify robots.txt")
            return False

        can_fetch = rp.can_fetch(self.user_agent, url)

        if not can_fetch:
            logger.info(f"robots.txt disallows fetching: {url}")

        return can_fetch

    def get_crawl_delay(self, url: str) -> Optional[float]:
        """Get the crawl delay specified in robots.txt, if any."""
        domain = self._get_domain(url)
        rp = self._cache.get(domain)

        if rp is None:
            return None

        try:
            delay = rp.crawl_delay(self.user_agent)
            return delay
        except Exception:
            return None

    def clear_cache(self):
        """Clear the robots.txt cache."""
        self._cache.clear()
        self._failed_domains.clear()


# Global robots checker instance
_robots_checker: Optional[RobotsChecker] = None


def get_robots_checker() -> RobotsChecker:
    """Get the global robots checker instance."""
    global _robots_checker
    if _robots_checker is None:
        _robots_checker = RobotsChecker()
    return _robots_checker
