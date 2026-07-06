"""Orchestrate retrieval → prompt → Qwen → validation → rewrite for structured SEO output."""

from __future__ import annotations

import logging
from typing import List

from langchain_core.documents import Document
from langchain_core.language_models.chat_models import BaseChatModel

from app.agents.generation_chain import render_pipeline_prompt
from app.agents.prompt_builder import build_pipeline_prompt_variables, build_retrieval_query_text
from app.agents.qwen_invoke import QwenChatInvoker
from app.agents.rag_chain import format_context
from app.core.config import Settings
from app.schemas.content_pipeline import (
    ContentPipelineRequest,
    ContentPipelineResponse,
    RetrievedSourceSummary,
)
from app.schemas.retrieval import RetrievalSource
from app.services.retrieval.service import RetrievalService
from app.services.rewrite.service import RewriteService
from app.services.validation.service import ValidationService, flatten_validation_issues

logger = logging.getLogger(__name__)


def _sources_to_summary(sources: List[RetrievalSource]) -> List[RetrievedSourceSummary]:
    out: List[RetrievedSourceSummary] = []
    for s in sources:
        preview = s.text.strip().replace("\n", " ")
        if len(preview) > 420:
            preview = preview[:417] + "..."
        meta = s.metadata or {}
        out.append(
            RetrievedSourceSummary(
                text_preview=preview,
                score=s.score,
                url=meta.get("url") or meta.get("source"),
                title=meta.get("title"),
                source_type=meta.get("source_type"),
                domain=meta.get("domain"),
                language=meta.get("language"),
            ),
        )
    return out


class ContentPipelineService:
    """LangChain + Qdrant + local Qwen pipeline with compliance validation."""

    def __init__(
        self,
        *,
        settings: Settings,
        llm: BaseChatModel,
        retrieval: RetrievalService,
        validation: ValidationService,
        rewrite: RewriteService,
    ) -> None:
        self._settings = settings
        self._retrieval = retrieval
        self._validation = validation
        self._rewrite = rewrite
        self._qwen = QwenChatInvoker(llm)

    def run(self, req: ContentPipelineRequest) -> ContentPipelineResponse:
        """Execute RAG retrieval, generation, validation, and optional rewrites."""

        sources: List[RetrievalSource] = []
        context = ""
        if req.use_rag:
            q = build_retrieval_query_text(req)
            sources = self._retrieval.query(
                q,
                top_k=req.top_k or self._settings.rag_top_k,
                source_scope=req.source_scope,
            )
            docs = [Document(page_content=s.text, metadata=dict(s.metadata)) for s in sources]
            context = format_context(docs)

        variables = build_pipeline_prompt_variables(req, context=context)
        variant = req.prompt_variant or self._settings.prompt_variant
        prompt = render_pipeline_prompt(
            req.content_block_type,
            variables,
            variant=variant,
        )
        logger.info(
            "Content pipeline: block=%s rag=%s variant=%s",
            req.content_block_type,
            req.use_rag,
            variant,
        )
        text = self._qwen.invoke_text(prompt)

        report = self._validation.validate_pipeline(
            text,
            mode=req.content_block_type,
            req=req,
        )
        attempts = 0
        max_rw = self._settings.generation_max_rewrite_attempts
        while not report.passed and attempts < max_rw:
            attempts += 1
            issues = flatten_validation_issues(report)
            text = self._rewrite.rewrite_pipeline(text, req=req, issues=issues)
            report = self._validation.validate_pipeline(
                text,
                mode=req.content_block_type,
                req=req,
            )

        if not report.passed:
            logger.warning(
                "Pipeline finished with validation failures after %s rewrites",
                attempts,
            )

        return ContentPipelineResponse(
            final_text=text,
            content_block_type=req.content_block_type,
            page_type=req.page_type,
            language=req.language,
            validation_report=report,
            retrieved_sources_summary=_sources_to_summary(sources) if req.use_rag else [],
            rewrite_attempts=attempts,
        )
