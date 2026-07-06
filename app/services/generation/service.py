"""Orchestrate RAG + generation + validation + rewrite loops."""

from __future__ import annotations

import logging

from langchain_core.documents import Document
from langchain_core.language_models.chat_models import BaseChatModel

from app.agents.generation_chain import invoke_chat, render_prompt
from app.agents.rag_chain import format_context
from app.core.config import Settings
from app.schemas.generation import GenerationBlockRequest, GenerationBlockResponse
from app.schemas.retrieval import RetrievalSource
from app.services.retrieval.service import RetrievalService
from app.services.rewrite.service import RewriteService
from app.services.validation.service import ValidationService

logger = logging.getLogger(__name__)


class GenerationService:
    """Public entry for SEO block generation.

    **Ollama / Qwen:** ``llm`` is provided by ``app/integrations/ollama.py`` via deps.
    **RAG:** optional retrieval from ``RetrievalService`` (Qdrant).
    """

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
        self._llm = llm
        self._retrieval = retrieval
        self._validation = validation
        self._rewrite = rewrite

    def generate_block(self, req: GenerationBlockRequest) -> GenerationBlockResponse:
        """Generate text for ``use_cases_block`` or ``online_vs_desktop``."""

        sources: list[RetrievalSource] = []
        context = ""
        if req.use_rag:
            sources = self._retrieval.query(
                req.topic,
                site_id=req.site_id,
                top_k=self._settings.rag_top_k,
            )
            docs = [
                Document(page_content=s.text, metadata=dict(s.metadata)) for s in sources
            ]
            context = format_context(docs)

        prompt = render_prompt(
            req.mode,
            topic=req.topic,
            audience=req.audience,
            language=req.language,
            domain=req.domain,
            context=context,
        )
        logger.info("Generation mode=%s rag=%s", req.mode, req.use_rag)
        text = invoke_chat(self._llm, prompt)
        attempts = 0
        ok, issues = self._validation.validate(text, mode=req.mode)
        max_rw = self._settings.generation_max_rewrite_attempts
        while not ok and attempts < max_rw:
            attempts += 1
            text = self._rewrite.rewrite(text, mode=req.mode, issues=issues)
            ok, issues = self._validation.validate(text, mode=req.mode)

        wc = self._validation.word_count(text)
        if not ok:
            logger.warning("Generation finished with validation issues: %s", issues)

        return GenerationBlockResponse(
            text=text,
            mode=req.mode,
            word_count=wc,
            sources=sources if req.use_rag else [],
            validation_passed=ok,
            rewrite_attempts=attempts,
        )
