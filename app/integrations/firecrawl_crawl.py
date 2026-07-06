"""FireCrawl **crawl** (multi-page) client with retries.

TODO: Confirm crawl request/response JSON against your FireCrawl version (cloud vs self-hosted).
TODO: Set ``FIRECRAWL_API_KEY`` (and optional ``FIRECRAWL_BASE_URL``) in environment — see ``Settings``.

Single-page scrape remains in ``app/integrations/firecrawl.py``; this module focuses on
``POST /v1/crawl`` and ``GET /v1/crawl/{id}`` style workflows.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, List, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.TransportError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (408, 429, 500, 502, 503, 504)
    return False


class FireCrawlCrawlError(RuntimeError):
    """Raised when a crawl job fails or times out."""


class FireCrawlCrawlClient:
    """Start site crawls and poll until completion."""

    def __init__(self, base_url: str, api_key: Optional[str]) -> None:
        self._base = base_url.rstrip("/")
        self._api_key = api_key

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {"Content-Type": "application/json"}
        # TODO: If your deployment uses ``x-api-key`` instead of Bearer, switch here.
        if self._api_key:
            h["Authorization"] = f"Bearer {self._api_key}"
        return h

    @retry(
        reraise=True,
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=20),
        retry=retry_if_exception(_is_retryable),
    )
    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._base}{path}"
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(url, json=payload, headers=self._headers())
            resp.raise_for_status()
            return resp.json()

    @retry(
        reraise=True,
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=20),
        retry=retry_if_exception(_is_retryable),
    )
    def _get_json(self, path: str) -> dict[str, Any]:
        url = f"{self._base}{path}"
        with httpx.Client(timeout=120.0) as client:
            resp = client.get(url, headers=self._headers())
            resp.raise_for_status()
            return resp.json()

    def start_crawl(
        self,
        entry_url: str,
        *,
        limit: Optional[int] = None,
        max_depth: Optional[int] = None,
    ) -> str:
        """Start crawl job; returns job id string.

        TODO: Adjust payload keys (``maxDepth``, ``limit``, ``crawlerOptions``) per FireCrawl docs.
        """

        payload: dict[str, Any] = {
            "url": entry_url,
            "scrapeOptions": {
                "formats": ["markdown", "html"],
            },
        }
        if limit is not None:
            payload["limit"] = limit
        if max_depth is not None:
            payload["maxDepth"] = max_depth

        logger.info("FireCrawl crawl start: %s limit=%s depth=%s", entry_url, limit, max_depth)
        body = self._post_json("/v1/crawl", payload)
        job_id = body.get("id") or body.get("jobId") or body.get("job_id")
        if not job_id:
            raise FireCrawlCrawlError(
                f"FireCrawl did not return a crawl job id. Keys: {list(body.keys())}. Raw: {body!r}",
            )
        return str(job_id)

    def get_crawl_status(self, job_id: str) -> dict[str, Any]:
        """Fetch crawl job status + partial/final data."""

        # TODO: Confirm path — some stacks use ``/v1/crawl/status/{id}``.
        return self._get_json(f"/v1/crawl/{job_id}")

    def wait_for_crawl(
        self,
        job_id: str,
        *,
        max_seconds: int = 900,
        poll_interval_seconds: float = 3.0,
        status_parser: Optional[Callable[[dict[str, Any]], Optional[str]]] = None,
    ) -> dict[str, Any]:
        """Poll until job completes, fails, or timeout."""

        deadline = time.monotonic() + max_seconds
        last_body: dict[str, Any] = {}
        while time.monotonic() < deadline:
            last_body = self.get_crawl_status(job_id)
            status: Optional[str] = None
            if status_parser:
                status = status_parser(last_body)
            if status is None:
                status = _default_extract_status(last_body)
            logger.debug("FireCrawl job %s status=%s", job_id, status)
            if status and status.lower() in ("completed", "complete", "finished", "success"):
                return last_body
            if status and status.lower() in ("failed", "error", "cancelled", "canceled"):
                raise FireCrawlCrawlError(f"FireCrawl crawl failed: status={status} body={last_body!r}")
            time.sleep(poll_interval_seconds)
        raise FireCrawlCrawlError(f"FireCrawl crawl timed out after {max_seconds}s (last={last_body!r})")


def _default_extract_status(body: dict[str, Any]) -> Optional[str]:
    """Best-effort status field across API variants."""

    if not isinstance(body, dict):
        return None
    s = body.get("status")
    if isinstance(s, str):
        return s
    data = body.get("data")
    if isinstance(data, dict):
        s2 = data.get("status")
        if isinstance(s2, str):
            return s2
    return None


def iter_crawl_documents(payload: dict[str, Any]) -> List[dict[str, Any]]:
    """Normalize list of page objects from a completed crawl response."""

    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    nested = payload.get("data", {})
    if isinstance(nested, dict):
        inner = nested.get("data") or nested.get("pages") or nested.get("results")
        if isinstance(inner, list):
            return [x for x in inner if isinstance(x, dict)]
    inner2 = payload.get("result")
    if isinstance(inner2, dict):
        lst = inner2.get("data") or inner2.get("pages")
        if isinstance(lst, list):
            return [x for x in lst if isinstance(x, dict)]
    return []
