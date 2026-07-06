"""Trafilatura-based main content extractor."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from app.services.crawl_ingestion.text_extract import normalize_whitespace

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExtractedContent:
    """Cleaned content extracted from HTML."""

    text: str


class TrafilaturaContentExtractor:
    """Extract readable main content from HTML using trafilatura."""

    def extract(self, html: str) -> ExtractedContent:
        if not html or not html.strip():
            return ExtractedContent(text="")
        try:
            import trafilatura

            extracted = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=True,
                no_fallback=False,
            )
            text = normalize_whitespace(extracted) if extracted else ""
            return ExtractedContent(text=text)
        except Exception:
            logger.exception("Trafilatura extraction failed")
            return ExtractedContent(text="")

