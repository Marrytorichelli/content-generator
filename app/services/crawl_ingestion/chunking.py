"""Chunk crawled pages into LangChain ``Document`` rows with rich metadata."""

from __future__ import annotations

import logging
from typing import List

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.services.crawl_ingestion.schema import CrawledPage

logger = logging.getLogger(__name__)


def build_splitter(*, chunk_size: int, chunk_overlap: int) -> RecursiveCharacterTextSplitter:
    """Create the text splitter used for RAG chunks."""

    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        is_separator_regex=False,
    )


def pages_to_chunk_documents(
    pages: List[CrawledPage],
    *,
    chunk_size: int,
    chunk_overlap: int,
) -> List[Document]:
    """Split each page's text into chunks; metadata is duplicated per chunk for Qdrant filters.

    Filter keys stored for retrieval: ``source_type``, ``domain``, ``language``, ``url``,
    ``title``, ``scraped_at``.
    """

    splitter = build_splitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    out: List[Document] = []
    for page in pages:
        text = (page.text or "").strip()
        if not text:
            logger.info("Skipping empty page text for %s", page.url)
            continue
        base_meta = page.to_chunk_payloads()
        # Optional: traceability inside chunk metadata
        base_meta["source"] = page.url
        chunks = splitter.split_text(text)
        for i, chunk in enumerate(chunks):
            meta = {**base_meta, "chunk_index": str(i), "chunk_count": str(len(chunks))}
            out.append(Document(page_content=chunk, metadata=meta))
    logger.info("Built %s chunk documents from %s pages", len(out), len(pages))
    return out
