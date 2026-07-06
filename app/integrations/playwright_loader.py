"""Playwright-based page loader (rendered HTML).

This replaces FireCrawl scraping in the ingestion path.
Keep this module focused on *loading* only (no extraction/chunking/Qdrant).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Optional

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RenderedPage:
    """One rendered page result."""

    url: str
    final_url: str
    title: Optional[str]
    html: str
    status: Optional[int]
    loaded_at: datetime


class PlaywrightPageLoader:
    """Render pages with Playwright and return raw HTML.

    TODO(DevOps): In containers, Playwright needs browser binaries.
    - Local dev: `python -m playwright install chromium`
    - Docker: run `python -m playwright install --with-deps chromium` during build
      (or use a Playwright base image).
    """

    def __init__(
        self,
        *,
        headless: bool = True,
        nav_timeout_ms: int = 30_000,
        user_agent: Optional[str] = None,
        extra_http_headers: Optional[dict[str, str]] = None,
    ) -> None:
        self._headless = headless
        self._nav_timeout_ms = nav_timeout_ms
        self._user_agent = user_agent
        self._extra_http_headers = extra_http_headers or {}

    def load_html(self, url: str) -> RenderedPage:
        """Load a single URL and return rendered HTML."""

        loaded_at = datetime.now(timezone.utc)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self._headless)
            context_kwargs: dict[str, object] = {}
            if self._user_agent:
                context_kwargs["user_agent"] = self._user_agent
            context = browser.new_context(**context_kwargs)
            if self._extra_http_headers:
                context.set_extra_http_headers(self._extra_http_headers)
            page = context.new_page()
            page.set_default_navigation_timeout(self._nav_timeout_ms)
            page.set_default_timeout(self._nav_timeout_ms)
            try:
                resp = page.goto(url, wait_until="networkidle")
                status = resp.status if resp else None
            except PlaywrightTimeoutError:
                logger.warning("Playwright navigation timed out: %s", url)
                status = None
            # Even if goto timed out, try to capture best-effort HTML
            final_url = page.url
            title = None
            try:
                title = page.title()
            except Exception:
                logger.debug("Failed to read title for %s", final_url, exc_info=True)
            html = ""
            try:
                html = page.content()
            except Exception:
                logger.warning("Failed to read page HTML for %s", final_url, exc_info=True)
            context.close()
            browser.close()
        return RenderedPage(
            url=url,
            final_url=final_url,
            title=title,
            html=html,
            status=status,
            loaded_at=loaded_at,
        )

    def load_many_html(self, urls: Iterable[str]) -> list[RenderedPage]:
        """Load multiple URLs reusing a single browser instance (faster for crawls)."""

        loaded_at = datetime.now(timezone.utc)
        results: list[RenderedPage] = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self._headless)
            context_kwargs: dict[str, object] = {}
            if self._user_agent:
                context_kwargs["user_agent"] = self._user_agent
            context = browser.new_context(**context_kwargs)
            if self._extra_http_headers:
                context.set_extra_http_headers(self._extra_http_headers)
            page = context.new_page()
            page.set_default_navigation_timeout(self._nav_timeout_ms)
            page.set_default_timeout(self._nav_timeout_ms)

            for url in urls:
                try:
                    resp = page.goto(url, wait_until="networkidle")
                    status = resp.status if resp else None
                except PlaywrightTimeoutError:
                    logger.warning("Playwright navigation timed out: %s", url)
                    status = None
                final_url = page.url
                title = None
                try:
                    title = page.title()
                except Exception:
                    logger.debug("Failed to read title for %s", final_url, exc_info=True)
                html = ""
                try:
                    html = page.content()
                except Exception:
                    logger.warning("Failed to read page HTML for %s", final_url, exc_info=True)
                results.append(
                    RenderedPage(
                        url=url,
                        final_url=final_url,
                        title=title,
                        html=html,
                        status=status,
                        loaded_at=loaded_at,
                    ),
                )

            context.close()
            browser.close()

        return results

