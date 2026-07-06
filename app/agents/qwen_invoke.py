"""Qwen (via Ollama) chat invocation wrapper for the content pipeline.

Centralizes LangChain ``BaseChatModel.invoke`` usage, logging, and future hooks
(temperature overrides, JSON mode, tracing).
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

logger = logging.getLogger(__name__)


class QwenChatInvoker:
    """Thin wrapper around a local Qwen model exposed through LangChain."""

    def __init__(self, llm: BaseChatModel) -> None:
        self._llm = llm

    def invoke_text(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """Run a single user turn; optional system preamble."""

        messages: List[BaseMessage] = []
        if system:
            messages.append(SystemMessage(content=system))
        messages.append(HumanMessage(content=prompt))
        logger.debug(
            "QwenChatInvoker.invoke_text chars_in=%s system=%s",
            len(prompt),
            bool(system),
        )
        msg = self._llm.invoke(messages, **kwargs)
        content = msg.content
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            return str(content).strip()
        return str(content).strip()
