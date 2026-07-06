#!/usr/bin/env python
"""Local smoke test for Playwright+Trafilatura ingestion.

Usage:
  python scripts/test_playwright_ingest.py https://example.com/

Prereqs:
  - Qdrant running (local or docker)
  - Ollama embeddings configured (OLLAMA_BASE_URL + OLLAMA_EMBED_MODEL)
  - Playwright chromium installed: `python -m playwright install chromium`

This script does NOT change API contracts; it exercises the same services used by routes.
"""

from __future__ import annotations

import os
import sys

from qdrant_client import QdrantClient

from app.core.config import get_settings
from app.integrations.ollama import build_ollama_embeddings
from app.integrations.qdrant import ensure_collection
from app.schemas.ingestion import IngestFromFireCrawlRequest
from app.services.ingestion.service import IngestionService


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_playwright_ingest.py <url>")
        return 2

    url = sys.argv[1]
    settings = get_settings()

    client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    ensure_collection(
        client,
        collection_name=settings.qdrant_collection,
        vector_size=settings.qdrant_vector_size,
    )

    embeddings = build_ollama_embeddings(settings)

    svc = IngestionService(settings=settings, qdrant_client=client, embeddings=embeddings)
    req = IngestFromFireCrawlRequest(urls_to_scrape=[url], site_id="local_smoke", domain=None)
    n = svc.ingest(req)
    print(f"Upserted chunks: {n}")
    print(f"Collection: {settings.qdrant_collection} @ {settings.qdrant_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
