"""Convert rendered pages + extracted text into LangChain ``Document`` objects."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Optional
from urllib.parse import urlparse

from langchain_core.documents import Document

from app.integrations.playwright_loader import RenderedPage


def _host_from_url(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.netloc or "").split("@")[-1]
    if ":" in host:
        host = host.split(":")[0]
    return host.lower() or "unknown"


class DocumentBuilder:
    """Build LangChain documents with stable metadata keys for RAG compatibility."""

    def build(
        self,
        *,
        page: RenderedPage,
        text: str,
        site_id: Optional[str] = None,
        domain: Optional[str] = None,
        source_type: Optional[str] = None,
        language: Optional[str] = None,
        page_type: Optional[str] = None,
    ) -> Document:
        """Return a single Document for the page's cleaned text."""

        now = datetime.now(timezone.utc)
        url = page.final_url or page.url
        meta: Dict[str, str] = {
            "source": url,
            "url": url,
            "title": page.title or "",
            "domain": domain or _host_from_url(url),
            "indexed_at": now.isoformat(),
        }
        if site_id:
            meta["site_id"] = site_id
        if source_type:
            meta["source_type"] = source_type
        if language:
            meta["language"] = language
        if page_type:
            meta["page_type"] = page_type
        if page.status is not None:
            meta["http_status"] = str(page.status)
        if page.loaded_at:
            meta["scraped_at"] = page.loaded_at.isoformat()

        return Document(page_content=(text or "").strip(), metadata=meta)

