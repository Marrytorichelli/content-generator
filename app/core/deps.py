"""FastAPI dependency providers: settings, LLM, embeddings, Qdrant, services."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Optional

from fastapi import Depends
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.embeddings import Embeddings
from qdrant_client import QdrantClient

from app.core.config import Settings, get_settings
from app.integrations.ollama import build_chat_ollama, build_ollama_embeddings
from app.integrations.qdrant import ensure_collection
from app.services.content_pipeline.service import ContentPipelineService
from app.services.crawl_ingestion.service import CrawlIngestionPipeline
from app.services.generation.service import GenerationService
from app.services.ingestion.service import IngestionService
from app.services.retrieval.service import RetrievalService
from app.services.rewrite.service import RewriteService
from app.services.validation.service import ValidationService


@lru_cache
def _qdrant_client_singleton(url: str, api_key: Optional[str]) -> QdrantClient:
    """Cached Qdrant client (per process)."""

    kwargs: dict[str, object] = {"url": url}
    if api_key:
        kwargs["api_key"] = api_key
    return QdrantClient(**kwargs)


def get_qdrant_client(settings: Annotated[Settings, Depends(get_settings)]) -> QdrantClient:
    """Return a Qdrant client and ensure the configured collection exists."""

    client = _qdrant_client_singleton(settings.qdrant_url, settings.qdrant_api_key)
    ensure_collection(
        client,
        collection_name=settings.qdrant_collection,
        vector_size=settings.qdrant_vector_size,
    )
    return client


def get_chat_model(settings: Annotated[Settings, Depends(get_settings)]) -> BaseChatModel:
    """Local Qwen (or other) chat model via Ollama."""

    return build_chat_ollama(settings)


def get_embeddings(settings: Annotated[Settings, Depends(get_settings)]) -> Embeddings:
    """Embeddings via Ollama (must match ``qdrant_vector_size``)."""

    return build_ollama_embeddings(settings)


def get_validation_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ValidationService:
    return ValidationService(settings=settings)


def get_rewrite_service(
    settings: Annotated[Settings, Depends(get_settings)],
    llm: Annotated[BaseChatModel, Depends(get_chat_model)],
) -> RewriteService:
    return RewriteService(settings=settings, llm=llm)


def get_retrieval_service(
    settings: Annotated[Settings, Depends(get_settings)],
    client: Annotated[QdrantClient, Depends(get_qdrant_client)],
    embeddings: Annotated[Embeddings, Depends(get_embeddings)],
) -> RetrievalService:
    return RetrievalService(
        settings=settings,
        qdrant_client=client,
        embeddings=embeddings,
    )


def get_ingestion_service(
    settings: Annotated[Settings, Depends(get_settings)],
    client: Annotated[QdrantClient, Depends(get_qdrant_client)],
    embeddings: Annotated[Embeddings, Depends(get_embeddings)],
) -> IngestionService:
    return IngestionService(
        settings=settings,
        qdrant_client=client,
        embeddings=embeddings,
    )


def get_crawl_ingestion_pipeline(
    settings: Annotated[Settings, Depends(get_settings)],
    client: Annotated[QdrantClient, Depends(get_qdrant_client)],
    embeddings: Annotated[Embeddings, Depends(get_embeddings)],
) -> CrawlIngestionPipeline:
    """Standalone multi-page crawl → chunk → Qdrant pipeline."""

    return CrawlIngestionPipeline(
        settings=settings,
        qdrant_client=client,
        embeddings=embeddings,
    )


def get_generation_service(
    settings: Annotated[Settings, Depends(get_settings)],
    llm: Annotated[BaseChatModel, Depends(get_chat_model)],
    retrieval: Annotated[RetrievalService, Depends(get_retrieval_service)],
    validation: Annotated[ValidationService, Depends(get_validation_service)],
    rewrite: Annotated[RewriteService, Depends(get_rewrite_service)],
) -> GenerationService:
    return GenerationService(
        settings=settings,
        llm=llm,
        retrieval=retrieval,
        validation=validation,
        rewrite=rewrite,
    )


def get_content_pipeline_service(
    settings: Annotated[Settings, Depends(get_settings)],
    llm: Annotated[BaseChatModel, Depends(get_chat_model)],
    retrieval: Annotated[RetrievalService, Depends(get_retrieval_service)],
    validation: Annotated[ValidationService, Depends(get_validation_service)],
    rewrite: Annotated[RewriteService, Depends(get_rewrite_service)],
) -> ContentPipelineService:
    """LangChain + Qdrant + Qwen pipeline with structured validation output."""

    return ContentPipelineService(
        settings=settings,
        llm=llm,
        retrieval=retrieval,
        validation=validation,
        rewrite=rewrite,
    )
