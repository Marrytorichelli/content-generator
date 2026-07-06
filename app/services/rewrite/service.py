"""Rewrite draft text using the LLM when validation fails."""

from __future__ import annotations

import logging

from langchain_core.language_models.chat_models import BaseChatModel

from app.agents.generation_chain import (
    invoke_chat,
    render_rewrite_pipeline_prompt,
    render_rewrite_prompt,
)
from app.agents.prompt_builder import format_bullet_lines
from app.core.config import Settings
from app.schemas.common import GenerationMode
from app.schemas.content_pipeline import ContentPipelineRequest

logger = logging.getLogger(__name__)


class RewriteService:
    """One or more LLM passes to satisfy ``ValidationService`` constraints."""

    def __init__(self, settings: Settings, llm: BaseChatModel) -> None:
        self._settings = settings
        self._llm = llm

    def rewrite(self, draft: str, *, mode: GenerationMode, issues: list[str]) -> str:
        """Produce a new draft addressing validation issues."""

        prompt = render_rewrite_prompt(mode=mode, issues=issues, draft=draft)
        logger.info("Rewrite pass for mode=%s issues=%s", mode, len(issues))
        return invoke_chat(self._llm, prompt)

    def rewrite_pipeline(
        self,
        draft: str,
        *,
        req: ContentPipelineRequest,
        issues: list[str],
    ) -> str:
        """Rewrite using rich product / LSI / compliance context."""

        kw = req.keywords or []
        keywords_block = format_bullet_lines(kw) if kw else "(none)"
        competitors = ", ".join(req.competitor_brands) if req.competitor_brands else "(none)"
        banned = ", ".join(self._settings.banned_ai_phrases_list())
        prompt = render_rewrite_pipeline_prompt(
            content_block_type=req.content_block_type,
            page_type=req.page_type,
            language=req.language,
            product_features=format_bullet_lines(req.product_features),
            lsi_keywords=format_bullet_lines(req.lsi_keywords),
            keywords=keywords_block,
            competitor_brands=competitors,
            banned_phrases=banned,
            issues=issues,
            draft=draft,
        )
        logger.info(
            "Pipeline rewrite pass block=%s issues=%s",
            req.content_block_type,
            len(issues),
        )
        return invoke_chat(self._llm, prompt)
