"""RAG helpers: format retrieved documents for prompt context.

This module stays small on purpose; swap in a full LCEL chain or agent later.
"""

from __future__ import annotations

from langchain_core.documents import Document


def format_context(docs: list[Document], *, max_chars: int = 12000) -> str:
    """Join retrieved chunks into a single context block with source hints.

    Truncates to ``max_chars`` to avoid blowing the local model context window.
    """

    parts: list[str] = []
    used = 0
    for i, doc in enumerate(docs, start=1):
        src = ""
        if doc.metadata:
            u = doc.metadata.get("source") or doc.metadata.get("url")
            if u:
                src = f" (source: {u})"
        block = f"[{i}]{src}\n{doc.page_content.strip()}\n"
        if used + len(block) > max_chars:
            break
        parts.append(block)
        used += len(block)
    return "\n".join(parts).strip()
