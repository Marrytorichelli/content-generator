"""Ollama integration: local Qwen chat + embeddings via LangChain.

Wire-up lives here so ``app/core/deps.py`` stays thin. Swap implementations
(e.g. vLLM OpenAI-compatible) behind the same LangChain ``BaseChatModel`` /
``Embeddings`` interfaces without touching routers.
"""

from langchain_community.chat_models import ChatOllama
from langchain_community.embeddings import OllamaEmbeddings
from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel

from app.core.config import Settings


def build_chat_ollama(settings: Settings, *, temperature: float = 0.4) -> BaseChatModel:
    """Construct the chat LLM pointing at Ollama (e.g. Qwen instruct).

    **Integration point:** ``OLLAMA_BASE_URL`` and ``OLLAMA_MODEL`` in :class:`Settings`.
    """

    return ChatOllama(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
        temperature=temperature,
    )


def build_ollama_embeddings(settings: Settings) -> Embeddings:
    """Construct embedding model; vector size must match ``QDRANT_VECTOR_SIZE``.

    **Integration point:** ``OLLAMA_EMBED_MODEL`` in :class:`Settings`.
    """

    return OllamaEmbeddings(
        base_url=settings.ollama_base_url,
        model=settings.ollama_embed_model,
    )
