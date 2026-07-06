"""Ingestion API models."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl


class FireCrawlPagePayload(BaseModel):
    """Pre-scraped page from FireCrawl (pass-through if you crawl out-of-band)."""

    url: HttpUrl
    markdown: str = Field(default="", description="Primary text for RAG (from FireCrawl).")
    title: Optional[str] = None
    metadata: Optional[dict[str, str]] = None


class IngestFromFireCrawlRequest(BaseModel):
    """Either ingest already-scraped pages or ask the backend to call FireCrawl per URL."""

    site_id: Optional[str] = Field(default=None, description="Logical site key for filtering.")
    domain: Optional[str] = Field(default=None, description="Hostname for metadata (e.g. example.com).")
    pages: Optional[List[FireCrawlPagePayload]] = Field(
        default=None,
        description="If set, upsert these directly without calling FireCrawl.",
    )
    urls_to_scrape: Optional[List[HttpUrl]] = Field(
        default=None,
        description="If set, backend calls FireCrawl **Integration** per URL.",
    )


class IngestFromFireCrawlResponse(BaseModel):
    """Summary of ingestion run."""

    documents_upserted: int
    site_id: Optional[str] = None
    domain: Optional[str] = None
    message: str = "ok"
