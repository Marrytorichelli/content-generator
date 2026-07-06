"""Application settings loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for the SEO RAG API.

    Qwen runs locally via **Ollama**; set ``OLLAMA_MODEL`` to your pulled Qwen tag.
    Qdrant URL should point at the REST API (e.g. ``http://127.0.0.1:6333``).
    FireCrawl is used during ingestion to fetch normalized page content.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="seo-rag-backend", description="Service name for logs and OpenAPI.")
    log_level: str = Field(default="INFO", description="Root logging level.")

    ollama_base_url: str = Field(
        default="http://127.0.0.1:11434",
        alias="OLLAMA_BASE_URL",
        description="Ollama HTTP API base (local Qwen + embeddings).",
    )
    ollama_model: str = Field(
        default="qwen2.5:7b-instruct",
        alias="OLLAMA_MODEL",
        description="Chat model tag in Ollama (e.g. Qwen instruct).",
    )
    ollama_embed_model: str = Field(
        default="nomic-embed-text",
        alias="OLLAMA_EMBED_MODEL",
        description="Embedding model tag in Ollama.",
    )

    qdrant_url: str = Field(
        default="http://127.0.0.1:6333",
        alias="QDRANT_URL",
        description="Qdrant REST URL.",
    )
    qdrant_api_key: Optional[str] = Field(default=None, alias="QDRANT_API_KEY")
    qdrant_collection: str = Field(
        default="seo_crawl",
        alias="QDRANT_COLLECTION",
        description="Vector collection for crawled pages.",
    )
    qdrant_vector_size: int = Field(
        default=768,
        alias="QDRANT_VECTOR_SIZE",
        description="Embedding dimension (must match Ollama embed model).",
    )

    firecrawl_base_url: str = Field(
        default="https://api.firecrawl.dev",
        alias="FIRECRAWL_BASE_URL",
        description="FireCrawl API base (or self-hosted instance).",
    )
    firecrawl_api_key: Optional[str] = Field(default=None, alias="FIRECRAWL_API_KEY")

    # --- Playwright ingestion (replaces FireCrawl in ingestion path) ---
    playwright_headless: bool = Field(default=True, alias="PLAYWRIGHT_HEADLESS")
    playwright_nav_timeout_ms: int = Field(default=30_000, alias="PLAYWRIGHT_NAV_TIMEOUT_MS")
    playwright_user_agent: Optional[str] = Field(default=None, alias="PLAYWRIGHT_USER_AGENT")

    generation_min_words: int = Field(default=200, ge=1)
    generation_max_words: int = Field(default=250, ge=1)
    generation_max_rewrite_attempts: int = Field(default=2, ge=0, le=5)

    rag_top_k: int = Field(default=6, ge=1, le=32)
    chunk_size: int = Field(default=1200, ge=100)
    chunk_overlap: int = Field(default=200, ge=0)

    banned_ai_phrases: str = Field(
        default=(
            "as an ai language model|as an ai|i cannot|delve into|"
            "game-changer|leverage synergies|unlock the power|"
            "in today's digital landscape|revolutionize your workflow|"
            "best of the best|ultimate|fantastic|incredible|"
            "state-of-the-art|cutting-edge|next-level|seamlessly|"
            "effortlessly|one-stop|world-class"
        ),
        alias="BANNED_AI_PHRASES",
        description="Pipe-separated substrings flagged as AI-style fluff (case-insensitive).",
    )

    prompt_variant: str = Field(
        default="v1",
        alias="PROMPT_VARIANT",
        description=(
            "Selects which prompt variant file to use. "
            "Resolves to app/prompts/<block>_<variant>.txt with fallback to <block>.txt."
        ),
    )

    def banned_ai_phrases_list(self) -> list[str]:
        """Split configured banned phrase string into a list."""

        return [p.strip() for p in self.banned_ai_phrases.split("|") if p.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return cached settings singleton."""

    return Settings()
