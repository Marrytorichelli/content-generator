"""Ingestion routes: Playwright + Trafilatura → chunk → Qdrant."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from app.core.deps import get_crawl_ingestion_pipeline, get_ingestion_service
from app.schemas.crawl_ingestion import CrawlIngestionTriggerRequest, CrawlIngestionTriggerResponse
from app.schemas.ingestion import IngestFromFireCrawlRequest, IngestFromFireCrawlResponse
from app.services.crawl_ingestion.service import CrawlIngestionPipeline
from app.services.ingestion.service import IngestionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


@router.post("/firecrawl", response_model=IngestFromFireCrawlResponse)
def ingest_firecrawl(
    body: IngestFromFireCrawlRequest,
    svc: IngestionService = Depends(get_ingestion_service),
) -> IngestFromFireCrawlResponse:
    """Upsert crawled content.

    Provide ``pages`` (already scraped text) and/or ``urls_to_scrape`` (backend renders with Playwright).
    """

    n = svc.ingest(body)
    logger.info("Ingestion complete: %s chunks", n)
    return IngestFromFireCrawlResponse(
        documents_upserted=n,
        site_id=body.site_id,
        domain=body.domain,
    )


@router.post(
    "/crawl",
    response_model=CrawlIngestionTriggerResponse,
    summary="Crawl a site (Playwright), chunk, embed, store in Qdrant",
)
def ingest_site_crawl(
    body: CrawlIngestionTriggerRequest,
    pipeline: CrawlIngestionPipeline = Depends(get_crawl_ingestion_pipeline),
) -> CrawlIngestionTriggerResponse:
    """Example trigger for the standalone ingestion pipeline.

    - **Fetch**: Playwright renders pages (Chromium).
    - **Text**: Trafilatura extracts main readable content.
    - **Metadata** on each chunk: ``url``, ``title``, ``source_type``, ``language``, ``domain``, ``scraped_at``.
    - **Qdrant**: ``upsert_documents`` in ``app/services/crawl_ingestion/qdrant_upsert.py``.
    """
    return pipeline.run(body)
