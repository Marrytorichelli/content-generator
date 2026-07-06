"""Generation: load prompt templates and invoke the chat model."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage

from app.schemas.common import GenerationMode

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _prompt_filename(mode: GenerationMode, variant: Optional[str] = None) -> str:
    """Resolve filename for a block mode and optional variant (v1/v2/v3)."""

    if variant and variant.lower() not in {"v1", "default", "base"}:
        return f"{mode}_{variant.lower()}.txt"
    return f"{mode}.txt"


def list_prompt_variants(mode: GenerationMode) -> List[str]:
    """Return available variants for a block mode (``v1``, ``v2``, …)."""

    variants: List[str] = []
    if (_PROMPTS_DIR / f"{mode}.txt").is_file():
        variants.append("v1")
    for p in sorted(_PROMPTS_DIR.glob(f"{mode}_v*.txt")):
        tag = p.stem.rsplit("_", 1)[-1]
        if tag not in variants:
            variants.append(tag)
    return variants


def load_prompt_template(
    mode: GenerationMode,
    variant: Optional[str] = None,
) -> str:
    """Load a mode-specific prompt file from ``app/prompts``.

    Resolution order:
    1. ``app/prompts/<mode>_<variant>.txt`` if variant is provided and file exists,
    2. ``app/prompts/<mode>.txt`` as the v1/default fallback.
    """

    if variant:
        variant_path = _PROMPTS_DIR / _prompt_filename(mode, variant)
        if variant_path.is_file():
            return variant_path.read_text(encoding="utf-8")
        logger.warning(
            "Prompt variant %s not found for %s, falling back to default",
            variant,
            mode,
        )

    path = _PROMPTS_DIR / _prompt_filename(mode)
    if not path.is_file():
        msg = f"Missing prompt file: {path}"
        raise FileNotFoundError(msg)
    return path.read_text(encoding="utf-8")


def render_pipeline_prompt(
    mode: GenerationMode,
    variables: dict[str, str],
    *,
    variant: Optional[str] = None,
) -> str:
    """Fill a mode template using a pre-built variable map (pipeline or legacy)."""

    template = load_prompt_template(mode, variant=variant)
    try:
        return template.format(**variables)
    except KeyError as exc:
        msg = f"Prompt template missing placeholder: {exc}"
        raise ValueError(msg) from exc


def render_prompt(
    mode: GenerationMode,
    *,
    topic: str,
    audience: str,
    language: str,
    domain: str | None,
    context: str,
) -> str:
    """Legacy shape for ``/generation/block`` — maps into unified templates."""

    from app.agents.prompt_builder import build_legacy_prompt_variables

    variables = build_legacy_prompt_variables(
        topic=topic,
        audience=audience,
        language=language,
        domain=domain,
        context=context,
        mode=mode,
    )
    return render_pipeline_prompt(mode, variables)


def invoke_chat(llm: BaseChatModel, prompt: str) -> str:
    """Single-turn generation; extend with message history / tools as needed."""

    logger.debug("Invoking chat model, prompt_chars=%s", len(prompt))
    msg = llm.invoke([HumanMessage(content=prompt)])
    content = msg.content
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return str(content).strip()
    return str(content).strip()


def render_rewrite_prompt(
    *,
    mode: GenerationMode,
    issues: list[str],
    draft: str,
) -> str:
    """Build the rewrite prompt from ``app/prompts/rewrite.txt``."""

    path = _PROMPTS_DIR / "rewrite.txt"
    template = path.read_text(encoding="utf-8")
    issues_block = "\n".join(f"- {i}" for i in issues) if issues else "- (unspecified)"
    return template.format(mode=mode, issues=issues_block, draft=draft)


def render_rewrite_pipeline_prompt(
    *,
    content_block_type: GenerationMode,
    page_type: str,
    language: str,
    product_features: str,
    lsi_keywords: str,
    keywords: str,
    competitor_brands: str,
    banned_phrases: str,
    issues: list[str],
    draft: str,
) -> str:
    """Rich rewrite prompt with product / LSI / compliance context."""

    path = _PROMPTS_DIR / "rewrite_pipeline.txt"
    template = path.read_text(encoding="utf-8")
    issues_block = "\n".join(f"- {i}" for i in issues) if issues else "- (unspecified)"
    return template.format(
        content_block_type=content_block_type,
        page_type=page_type,
        language=language,
        product_features=product_features,
        lsi_keywords=lsi_keywords,
        keywords=keywords,
        competitor_brands=competitor_brands,
        banned_phrases=banned_phrases,
        issues=issues_block,
        draft=draft,
    )
