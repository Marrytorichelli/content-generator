"""Schemas for the LangChain + Qdrant content generation pipeline."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.common import GenerationMode, SourceScope


class ContentPipelineRequest(BaseModel):
    """Input for RAG content generation with validation and rewrite."""

    page_type: str = Field(
        ...,
        min_length=1,
        description="e.g. landing, blog, comparison, feature_page",
    )
    content_block_type: GenerationMode = Field(
        ...,
        description="Selects prompt template: use_cases_block | online_vs_desktop",
    )
    feature_description: str = Field(
        ...,
        min_length=1,
        description="What the copy should communicate about the product/feature.",
    )
    product_features: List[str] = Field(
        ...,
        min_length=1,
        description="Authoritative list of features the copy may reference (grounding).",
    )
    lsi_keywords: List[str] = Field(
        ...,
        min_length=1,
        description="LSI terms that should appear in the final text (coverage validated).",
    )
    keywords: Optional[List[str]] = Field(
        default=None,
        description="Optional primary SEO keywords to weave in naturally.",
    )
    language: str = Field(default="en", min_length=2, max_length=32)
    source_scope: SourceScope = Field(
        default_factory=SourceScope,
        description="Qdrant metadata filter for retrieval.",
    )
    competitor_brands: List[str] = Field(
        default_factory=list,
        description="Brand names/substrings that must not appear in output.",
    )
    use_rag: bool = Field(default=True)
    top_k: Optional[int] = Field(default=None, ge=1, le=32)
    audience: str = Field(default="prospective customers comparing options")
    prompt_variant: Optional[str] = Field(
        default=None,
        description=(
            "Which prompt variant to use: v1 (default), v2, v3, etc. "
            "Resolves to app/prompts/<block>_<variant>.txt with fallback to <block>.txt."
        ),
    )


class ValidationCheckResult(BaseModel):
    """Single validation rule outcome."""

    name: str
    passed: bool
    detail: Optional[str] = None


class ValidationReport(BaseModel):
    """Structured validation outcome for API consumers."""

    passed: bool
    word_count: int
    lsi_required: int
    lsi_matched: int
    missing_lsi_keywords: List[str] = Field(default_factory=list)
    banned_phrases_found: List[str] = Field(default_factory=list)
    competitor_mentions_found: List[str] = Field(default_factory=list)
    unsupported_feature_notes: List[str] = Field(default_factory=list)
    structure_issues: List[str] = Field(default_factory=list)
    checks: List[ValidationCheckResult] = Field(default_factory=list)


class RetrievedSourceSummary(BaseModel):
    """One retrieved chunk summary for the response payload."""

    text_preview: str = Field(..., description="Truncated chunk text.")
    score: Optional[float] = None
    url: Optional[str] = None
    title: Optional[str] = None
    source_type: Optional[str] = None
    domain: Optional[str] = None
    language: Optional[str] = None


class ContentPipelineResponse(BaseModel):
    """Final structured output from the orchestration service."""

    final_text: str
    content_block_type: GenerationMode
    page_type: str
    language: str
    validation_report: ValidationReport
    retrieved_sources_summary: List[RetrievedSourceSummary]
    rewrite_attempts: int = 0
