"""Ingest crawled content: chunk, embed via Ollama, upsert into Qdrant."""

from __future__ import annotations

import logging

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.embeddings import Embeddings
from qdrant_client import QdrantClient

from app.core.config import Settings
from app.integrations.playwright_loader import PlaywrightPageLoader
from app.integrations.qdrant import build_vector_store
from app.schemas.ingestion import FireCrawlPagePayload, IngestFromFireCrawlRequest

logger = logging.getLogger(__name__)


class IngestionService:
    """Upsert page text into Qdrant.

    **Ingestion migration:** FireCrawl scraping is replaced with Playwright + Trafilatura.
    **Qdrant integration:** vector store from ``app/integrations/qdrant.py``.
    """

    def __init__(
        self,
        *,
        settings: Settings,
        qdrant_client: QdrantClient,
        embeddings: Embeddings,
    ) -> None:
        self._settings = settings
        self._client = qdrant_client
        self._embeddings = embeddings

    def ingest(self, req: IngestFromFireCrawlRequest) -> int:
        """Return number of LangChain documents upserted."""

        pages: list[FireCrawlPagePayload] = list(req.pages or [])
        if req.urls_to_scrape:
            # Backward-compatible request schema: we still accept `urls_to_scrape`,
            # but fetching/rendering is now done locally with Playwright.
            loader = PlaywrightPageLoader(
                headless=self._settings.playwright_headless,
                nav_timeout_ms=self._settings.playwright_nav_timeout_ms,
                user_agent=self._settings.playwright_user_agent,
            )
            for u in req.urls_to_scrape:
                rendered = loader.load_html(str(u))
                text = self._extract_clean_text(rendered.html)
                pages.append(
                    FireCrawlPagePayload(
                        url=u,
                        # Keep field name for compatibility; content is now clean text.
                        markdown=text,
                        title=rendered.title,
                        metadata=None,
                    )
                )

        if not pages:
            logger.warning("Ingestion called with no pages and no urls_to_scrape")
            return 0

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self._settings.chunk_size,
            chunk_overlap=self._settings.chunk_overlap,
        )
        docs: list[Document] = []
        for p in pages:
            text = (p.markdown or "").strip()
            if not text:
                logger.info("Skip empty markdown for %s", p.url)
                continue
            meta: dict[str, str] = {
                "source": str(p.url),
                "url": str(p.url),
            }
            if req.site_id:
                meta["site_id"] = req.site_id
            if req.domain:
                meta["domain"] = req.domain
            if p.title:
                meta["title"] = p.title
            if p.metadata:
                for k, v in p.metadata.items():
                    meta[f"page_{k}"] = v
            for chunk in splitter.split_text(text):
                docs.append(Document(page_content=chunk, metadata=meta.copy()))

        if not docs:
            return 0

        store = build_vector_store(
            self._client,
            collection_name=self._settings.qdrant_collection,
            embeddings=self._embeddings,
        )
        logger.info("Upserting %s chunks into Qdrant", len(docs))
        store.add_documents(docs)
        return len(docs)

    def _extract_clean_text(self, html: str) -> str:
        """Extract readable text from HTML using trafilatura."""

        if not html or not html.strip():
            return ""
        try:
            import trafilatura

            extracted = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=True,
                no_fallback=False,
            )
            text = (extracted or "").strip()
            if not text:
                return ""
            # Normalize whitespace lightly to improve chunking stability
            return " ".join(text.split())
        except Exception:
            logger.exception("Trafilatura extraction failed in ingestion service")
            return ""
