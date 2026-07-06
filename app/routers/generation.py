"""Generation routes: SEO blocks via LangChain + optional RAG."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from app.agents.generation_chain import list_prompt_variants
from app.core.deps import get_content_pipeline_service, get_generation_service
from app.schemas.common import GenerationMode
from app.schemas.content_pipeline import ContentPipelineRequest, ContentPipelineResponse
from app.schemas.generation import GenerationBlockRequest, GenerationBlockResponse
from app.services.content_pipeline.service import ContentPipelineService
from app.services.generation.service import GenerationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/generation", tags=["generation"])


@router.post("/block", response_model=GenerationBlockResponse)
def generate_block(
    body: GenerationBlockRequest,
    svc: GenerationService = Depends(get_generation_service),
) -> GenerationBlockResponse:
    """Generate ``use_cases_block`` or ``online_vs_desktop`` (200–250 words)."""

    out = svc.generate_block(body)
    logger.info(
        "Generated mode=%s words=%s valid=%s rewrites=%s",
        out.mode,
        out.word_count,
        out.validation_passed,
        out.rewrite_attempts,
    )
    return out


@router.post(
    "/content",
    response_model=ContentPipelineResponse,
    summary="Full pipeline: metadata-filtered RAG, prompts, Qwen, validation, rewrite",
)
def generate_content_pipeline(
    body: ContentPipelineRequest,
    svc: ContentPipelineService = Depends(get_content_pipeline_service),
) -> ContentPipelineResponse:
    """Generate copy with ``source_scope`` Qdrant filters and structured ``validation_report``.

    Retrieval uses ``source_scope`` (``source_type``, ``domain``, ``language``, ``site_id``)
    as LangChain/Qdrant metadata filters when possible.
    """

    out = svc.run(body)
    logger.info(
        "Pipeline block=%s valid=%s rewrites=%s sources=%s",
        out.content_block_type,
        out.validation_report.passed,
        out.rewrite_attempts,
        len(out.retrieved_sources_summary),
    )
    return out


@router.get("/prompts/{block_type}/variants")
def get_prompt_variants(block_type: GenerationMode) -> dict[str, list[str]]:
    """List available prompt variants (v1, v2, v3, ...) for a block type."""

    return {"variants": list_prompt_variants(block_type)}
