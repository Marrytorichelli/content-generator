"""Orchestrate crawl → text extraction → chunking → embeddings → Qdrant."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Set, Tuple
from urllib.parse import urljoin, urlparse

from langchain_core.embeddings import Embeddings
from qdrant_client import QdrantClient

from app.core.config import Settings
from app.integrations.playwright_loader import PlaywrightPageLoader
from app.schemas.crawl_ingestion import CrawlIngestionTriggerRequest, CrawlIngestionTriggerResponse
from app.services.crawl_ingestion.chunking import pages_to_chunk_documents
from app.services.crawl_ingestion.document_builder import DocumentBuilder
from app.services.crawl_ingestion.qdrant_upsert import upsert_documents
from app.services.crawl_ingestion.schema import CrawledPage, CrawlRunContext
from app.services.crawl_ingestion.text_extract import pick_best_text

logger = logging.getLogger(__name__)


def _host_from_url(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.netloc or "").split("@")[-1]
    if ":" in host:
        host = host.split(":")[0]
    return host.lower() or "unknown"


def _is_same_domain(url: str, domain: str) -> bool:
    host = _host_from_url(url)
    return host == domain


def _extract_links_from_html(html: str, base_url: str) -> List[str]:
    """Lightweight link extraction to support local crawling with minimal dependencies."""

    if not html:
        return []
    # Avoid adding a heavy parser dependency; good enough for same-domain crawl.
    import re

    hrefs = re.findall(r'(?is)href\s*=\s*["\']([^"\']+)["\']', html)
    out: List[str] = []
    for h in hrefs:
        h = h.strip()
        if not h or h.startswith("#"):
            continue
        if h.startswith("javascript:") or h.startswith("mailto:") or h.startswith("tel:"):
            continue
        abs_url = urljoin(base_url, h)
        out.append(abs_url)
    return out


class CrawlIngestionPipeline:
    """Standalone ingestion entrypoint (Playwright + Trafilatura).

    This replaces the FireCrawl crawl adapter with a minimal same-domain crawler.
    It keeps request/response schemas stable.
    """

    def __init__(
        self,
        *,
        settings: Settings,
        qdrant_client: QdrantClient,
        embeddings: Embeddings,
    ) -> None:
        self._settings = settings
        self._qdrant = qdrant_client
        self._embeddings = embeddings

    def run(self, req: CrawlIngestionTriggerRequest) -> CrawlIngestionTriggerResponse:
        """Execute full pipeline and return a summary."""

        started = datetime.now(timezone.utc)
        base = str(req.base_url)
        domain = _host_from_url(base)
        ctx = CrawlRunContext(
            source_type=req.source_type,
            language=req.language,
            domain=domain,
        )
        errors: List[str] = []
        pages, crawl_errors = self._run_playwright_crawl(base, ctx, req)
        errors.extend(crawl_errors)

        chunk_size = req.chunk_size or self._settings.chunk_size
        chunk_overlap = req.chunk_overlap if req.chunk_overlap is not None else self._settings.chunk_overlap
        docs = pages_to_chunk_documents(pages, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        try:
            n = upsert_documents(
                self._qdrant,
                collection_name=self._settings.qdrant_collection,
                embeddings=self._embeddings,
                documents=docs,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Qdrant upsert failed")
            errors.append(f"qdrant_upsert: {exc}")
            n = 0

        finished = datetime.now(timezone.utc)
        return CrawlIngestionTriggerResponse(
            chunks_upserted=n,
            pages_processed=len(pages),
            domain=domain,
            source_type=req.source_type,
            language=req.language,
            errors=errors,
            started_at=started,
            finished_at=finished,
        )

    def _run_playwright_crawl(
        self,
        base_url: str,
        ctx: CrawlRunContext,
        req: CrawlIngestionTriggerRequest,
    ) -> Tuple[List[CrawledPage], List[str]]:
        """Crawl same-domain links with Playwright rendering, then extract text."""

        max_pages = req.max_pages or 30
        max_depth = req.max_depth if req.max_depth is not None else 1

        loader = PlaywrightPageLoader(
            headless=self._settings.playwright_headless,
            nav_timeout_ms=self._settings.playwright_nav_timeout_ms,
            user_agent=self._settings.playwright_user_agent,
        )
        builder = DocumentBuilder()

        # BFS queue: (url, depth)
        queue: List[Tuple[str, int]] = [(base_url, 0)]
        seen: Set[str] = set()
        pages: List[CrawledPage] = []
        errors: List[str] = []

        while queue and len(pages) < max_pages:
            url, depth = queue.pop(0)
            if url in seen:
                continue
            seen.add(url)

            if not _is_same_domain(url, ctx.domain):
                continue

            rendered = loader.load_html(url)
            text = pick_best_text(html=rendered.html)
            if not text.strip():
                errors.append(f"Empty extracted text for {rendered.final_url}")
                continue

            doc = builder.build(
                page=rendered,
                text=text,
                source_type=ctx.source_type,
                language=ctx.language,
                domain=ctx.domain,
            )

            pages.append(
                CrawledPage(
                    url=str(doc.metadata.get("url") or rendered.final_url or rendered.url),
                    title=str(doc.metadata.get("title") or "") or None,
                    text=doc.page_content,
                    source_type=ctx.source_type,
                    language=ctx.language,
                    domain=ctx.domain,
                    raw_metadata=dict(doc.metadata),
                ),
            )

            if depth < max_depth:
                for link in _extract_links_from_html(rendered.html, rendered.final_url):
                    if link not in seen and _is_same_domain(link, ctx.domain):
                        queue.append((link, depth + 1))

        logger.info(
            "Playwright crawl complete: pages=%s seen=%s base=%s",
            len(pages),
            len(seen),
            base_url,
        )
        return pages, errors
