"""Content generation request/response models."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.common import GenerationMode
from app.schemas.retrieval import RetrievalSource


class GenerationBlockRequest(BaseModel):
    """Generate SEO block in one of two modes."""

    mode: GenerationMode
    topic: str = Field(min_length=1, description="Primary SEO topic or product angle.")
    site_id: Optional[str] = Field(default=None, description="Scope RAG to chunks with this site_id.")
    domain: Optional[str] = Field(default=None, description="Optional domain hint for prompts.")
    use_rag: bool = Field(default=True, description="If true, retrieve context from Qdrant first.")
    language: str = Field(default="en")
    audience: str = Field(default="general business readers")


class GenerationBlockResponse(BaseModel):
    """Final text plus optional provenance."""

    text: str
    mode: GenerationMode
    word_count: int
    sources: List[RetrievalSource] = Field(default_factory=list)
    validation_passed: bool = True
    rewrite_attempts: int = 0
