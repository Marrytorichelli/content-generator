"""FireCrawl HTTP client for crawl/scrape during ingestion.

**Integration point:** ``FIRECRAWL_BASE_URL`` and ``FIRECRAWL_API_KEY``.

The public FireCrawl API shape may evolve; adjust paths/payloads here only.
Typical flow: ``POST {base}/v1/scrape`` with ``{"url": "...", "formats": ["markdown"]}``.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional

import httpx

logger = logging.getLogger(__name__)


class FireCrawlClient:
    """Thin synchronous client; swap for async if you batch many URLs."""

    def __init__(self, base_url: str, api_key: Optional[str]) -> None:
        self._base = base_url.rstrip("/")
        self._api_key = api_key

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            h["Authorization"] = f"Bearer {self._api_key}"
        return h

    def scrape_url(self, url: str, *, formats: Optional[List[str]] = None) -> dict[str, Any]:
        """Scrape a single URL; returns parsed JSON (markdown/html/metadata).

        Extend this method if you use FireCrawl ``/v1/crawl`` jobs instead.
        """

        payload: dict[str, Any] = {"url": url, "formats": formats or ["markdown"]}
        endpoint = f"{self._base}/v1/scrape"
        logger.info("FireCrawl scrape: %s", url)
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(endpoint, json=payload, headers=self._headers())
            resp.raise_for_status()
            return resp.json()
