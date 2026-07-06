"""Shared schema types."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

GenerationMode = Literal["use_cases_block", "online_vs_desktop"]


class SourceScope(BaseModel):
    """Metadata filters for Qdrant retrieval (AND semantics on chunk payload)."""

    source_type: Optional[str] = Field(
        default=None,
        description="e.g. platform | competitor (indexed at ingest time).",
    )
    domain: Optional[str] = Field(default=None, description="Hostname filter, e.g. www.example.com")
    language: Optional[str] = Field(default=None, description="Chunk language tag, e.g. en")
    site_id: Optional[str] = Field(default=None, description="Legacy site scope if present in chunks.")
