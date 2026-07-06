"""API models for standalone site crawl → chunk → embed → Qdrant ingestion."""

from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, HttpUrl

SourceType = Literal["platform", "competitor"]


class CrawlIngestionTriggerRequest(BaseModel):
    """Trigger a crawl of ``base_url`` and upsert chunks into Qdrant.

    TODO: Ensure ``FIRECRAWL_API_KEY`` and ``FIRECRAWL_BASE_URL`` are set in the environment
    (or swap ``CrawlLoader`` in ``app/services/crawl_ingestion/service.py`` for another adapter).
    """

    source_type: SourceType = Field(
        ...,
        description="Indexed for retrieval filters (e.g. platform vs competitor).",
    )
    base_url: HttpUrl = Field(..., description="Entry URL for the crawl (same host typically).")
    language: str = Field(
        ...,
        min_length=2,
        max_length=32,
        description="Content language tag stored on every chunk (e.g. en, de).",
    )
    max_pages: Optional[int] = Field(
        default=None,
        ge=1,
        le=10_000,
        description="Max pages to fetch (passed to FireCrawl as ``limit`` when supported).",
    )
    max_depth: Optional[int] = Field(
        default=None,
        ge=0,
        le=10,
        description="Optional crawl depth; adapter-specific (FireCrawl may ignore if unsupported).",
    )
    chunk_size: Optional[int] = Field(
        default=None,
        ge=200,
        le=8000,
        description="Override default chunk size from app settings.",
    )
    chunk_overlap: Optional[int] = Field(
        default=None,
        ge=0,
        le=2000,
        description="Override default chunk overlap from app settings.",
    )


class CrawlIngestionTriggerResponse(BaseModel):
    """Summary of a crawl ingestion run."""

    chunks_upserted: int = Field(..., ge=0)
    pages_processed: int = Field(..., ge=0)
    domain: str = Field(..., description="Host derived from ``base_url`` for filtering.")
    source_type: SourceType
    language: str
    errors: List[str] = Field(default_factory=list)
    started_at: datetime
    finished_at: datetime
