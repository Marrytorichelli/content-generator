"""Internal document schema for the crawl ingestion pipeline (not HTTP)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class CrawledPage:
    """One crawled URL with normalized text and metadata for RAG storage."""

    url: str
    title: Optional[str]
    text: str
    source_type: str
    language: str
    domain: str
    scraped_at: datetime = field(default_factory=_utc_now)
    raw_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_chunk_payloads(self) -> Dict[str, str]:
        """Flat string metadata for Qdrant / LangChain (filter-friendly)."""

        return {
            "url": self.url,
            "title": self.title or "",
            "source_type": self.source_type,
            "language": self.language,
            "domain": self.domain,
            "scraped_at": self.scraped_at.isoformat(),
        }


@dataclass
class CrawlRunContext:
    """Per-run context shared across pages."""

    source_type: str
    language: str
    domain: str


@dataclass
class CrawlAdapterResult:
    """Outcome of a crawl adapter (Playwright-based crawler or future loader)."""

    pages: List[CrawledPage]
    errors: List[str] = field(default_factory=list)
