"""Build prompt variable dicts for pipeline and legacy generation."""

from __future__ import annotations

from typing import Dict, List, Optional

from app.schemas.common import SourceScope
from app.schemas.content_pipeline import ContentPipelineRequest


def format_scope_summary(scope: SourceScope) -> str:
    """Human-readable description of Qdrant metadata filters."""

    parts: List[str] = []
    if scope.source_type:
        parts.append(f"source_type={scope.source_type}")
    if scope.domain:
        parts.append(f"domain={scope.domain}")
    if scope.language:
        parts.append(f"language={scope.language}")
    if scope.site_id:
        parts.append(f"site_id={scope.site_id}")
    return ", ".join(parts) if parts else "(no metadata filter — full collection)"


def format_bullet_lines(items: List[str]) -> str:
    """One feature / term per line for prompts."""

    return "\n".join(f"- {x.strip()}" for x in items if x and str(x).strip())


def build_retrieval_query_text(req: ContentPipelineRequest) -> str:
    """Compose a dense query string for embedding similarity search."""

    chunks: List[str] = [req.feature_description.strip()]
    if req.keywords:
        chunks.extend(x.strip() for x in req.keywords[:12] if x)
    chunks.extend(x.strip() for x in req.lsi_keywords[:10] if x)
    return "\n".join(dict.fromkeys(c for c in chunks if c))


def build_pipeline_prompt_variables(
    req: ContentPipelineRequest,
    *,
    context: str,
) -> Dict[str, str]:
    """Variables for ``use_cases_block`` / ``online_vs_desktop`` templates."""

    kw = req.keywords or []
    keywords_block = format_bullet_lines(kw) if kw else "(none — use LSI and feature description only)"
    return {
        "page_type": req.page_type,
        "content_block_type": req.content_block_type,
        "feature_description": req.feature_description.strip(),
        "product_features": format_bullet_lines(req.product_features),
        "lsi_keywords": format_bullet_lines(req.lsi_keywords),
        "keywords": keywords_block,
        "audience": req.audience,
        "language": req.language,
        "source_scope_summary": format_scope_summary(req.source_scope),
        "context": context.strip() if context else "(no RAG context)",
    }


def build_legacy_prompt_variables(
    *,
    topic: str,
    audience: str,
    language: str,
    domain: Optional[str],
    context: str,
    mode: str,
) -> Dict[str, str]:
    """Map legacy ``/generation/block`` fields into the unified prompt shape."""

    return {
        "page_type": "general",
        "content_block_type": mode,
        "feature_description": topic.strip(),
        "product_features": "- (legacy request — infer carefully from topic only)",
        "lsi_keywords": "- (legacy request — not specified)",
        "keywords": "(none)",
        "audience": audience,
        "language": language,
        "source_scope_summary": domain.strip() if domain else "(none)",
        "context": context.strip() if context else "(no RAG context)",
    }
