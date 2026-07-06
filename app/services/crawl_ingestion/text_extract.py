"""Extract readable plain text from HTML (Trafilatura) and normalize it.

FireCrawl-specific behavior is removed from the ingestion path.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


def normalize_whitespace(text: str) -> str:
    """Collapse excessive blank lines and strip."""

    text = text.replace("\r\n", "\n").strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def extract_from_html(html: Optional[str]) -> str:
    """Fallback: extract main text from HTML using trafilatura.

    TODO: Swap for ``readability-lxml``, ``boilerpy3``, or enterprise HTML cleanup if needed.
    """

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
        if extracted:
            return normalize_whitespace(extracted)
    except Exception:
        logger.exception("trafilatura extraction failed; falling back to strip")
    # Last-resort: drop tags crudely (not ideal for production HTML)
    stripped = re.sub(r"(?is)<script.*?>.*?</script>", "", html)
    stripped = re.sub(r"(?is)<style.*?>.*?</style>", "", stripped)
    stripped = re.sub(r"<[^>]+>", " ", stripped)
    return normalize_whitespace(stripped)


def pick_best_text(*, html: Optional[str]) -> str:
    """Derive clean text from HTML (single source of truth)."""

    return extract_from_html(html)
