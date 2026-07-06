"""Retrieval / RAG query models."""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from app.schemas.common import SourceScope


class RetrievalSource(BaseModel):
    """One retrieved chunk with optional score."""

    text: str
    score: Optional[float] = None
    metadata: Dict[str, str] = Field(default_factory=dict)


class RetrievalQueryRequest(BaseModel):
    """Semantic search over the Qdrant collection."""

    query: str = Field(min_length=1)
    site_id: Optional[str] = Field(
        default=None,
        description="Filter by indexed site_id if set (shortcut for source_scope).",
    )
    source_scope: Optional[SourceScope] = Field(
        default=None,
        description="Metadata filter (merged with site_id when both provided).",
    )
    top_k: Optional[int] = Field(default=None, ge=1, le=32)


class RetrievalQueryResponse(BaseModel):
    """Ranked sources for RAG."""

    sources: List[RetrievalSource]
