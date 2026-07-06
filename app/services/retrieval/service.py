"""Retrieve context chunks from Qdrant for RAG."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStoreRetriever
from qdrant_client import QdrantClient

from app.core.config import Settings
from app.integrations.qdrant import build_vector_store
from app.schemas.common import SourceScope
from app.schemas.retrieval import RetrievalSource

logger = logging.getLogger(__name__)

DictFilter = Dict[str, Union[str, int, bool]]


def _scope_to_dict_filter(scope: Optional[SourceScope]) -> Optional[DictFilter]:
    """Build LangChain Qdrant dict filter (maps to ``metadata.<key>`` in payload)."""

    if scope is None:
        return None
    d: DictFilter = {}
    if scope.source_type:
        d["source_type"] = scope.source_type
    if scope.domain:
        d["domain"] = scope.domain
    if scope.language:
        d["language"] = scope.language
    if scope.site_id:
        d["site_id"] = scope.site_id
    return d if d else None


def _metadata_matches_scope(meta: Dict[str, Any], scope: SourceScope) -> bool:
    """Client-side AND filter when Qdrant returns unfiltered results."""

    def norm(s: Optional[str]) -> str:
        return (s or "").strip().lower()

    if scope.source_type and norm(meta.get("source_type")) != norm(scope.source_type):
        return False
    if scope.domain and norm(meta.get("domain")) != norm(scope.domain):
        return False
    if scope.language and norm(meta.get("language")) != norm(scope.language):
        return False
    if scope.site_id and norm(meta.get("site_id")) != norm(scope.site_id):
        return False
    return True


class RetrievalService:
    """Semantic search over ingested crawl chunks.

    **Qdrant integration:** uses LangChain ``Qdrant`` vector store from
    ``app/integrations/qdrant.py``. Metadata filtering uses LangChain's
    dict filter (payload keys ``metadata.<field>``).
    """

    def __init__(
        self,
        *,
        settings: Settings,
        qdrant_client: QdrantClient,
        embeddings: Embeddings,
    ) -> None:
        self._settings = settings
        self._client = qdrant_client
        self._embeddings = embeddings

    def _store(self):
        return build_vector_store(
            self._client,
            collection_name=self._settings.qdrant_collection,
            embeddings=self._embeddings,
        )

    def as_retriever(
        self,
        *,
        search_kwargs: Optional[Dict[str, Any]] = None,
    ) -> VectorStoreRetriever:
        """LangChain retriever with optional ``search_kwargs`` (e.g. ``k``, ``filter``)."""

        store = self._store()
        kwargs = search_kwargs or {"k": self._settings.rag_top_k}
        return store.as_retriever(search_kwargs=kwargs)

    def query(
        self,
        query: str,
        *,
        site_id: Optional[str] = None,
        top_k: Optional[int] = None,
        metadata_filter: Optional[DictFilter] = None,
        source_scope: Optional[SourceScope] = None,
    ) -> List[RetrievalSource]:
        """Return ranked sources with optional Qdrant metadata filter and post-filter."""

        k = top_k or self._settings.rag_top_k
        scope = source_scope
        if site_id and scope is None:
            scope = SourceScope(site_id=site_id)
        elif site_id and scope is not None and scope.site_id is None:
            scope = scope.model_copy(update={"site_id": site_id})

        qf = metadata_filter if metadata_filter is not None else _scope_to_dict_filter(scope)

        def _scope_from_filter(f: DictFilter) -> SourceScope:
            return SourceScope(
                source_type=str(f["source_type"]) if f.get("source_type") is not None else None,
                domain=str(f["domain"]) if f.get("domain") is not None else None,
                language=str(f["language"]) if f.get("language") is not None else None,
                site_id=str(f["site_id"]) if f.get("site_id") is not None else None,
            )

        effective_scope: Optional[SourceScope] = scope
        if effective_scope is None and qf:
            effective_scope = _scope_from_filter(qf)

        store = self._store()
        fetch_k = k if not qf else min(max(k * 3, k), 48)

        pairs: List[Tuple[Document, float]] = store.similarity_search_with_score(
            query,
            k=fetch_k,
            filter=qf,
        )

        if not pairs and qf:
            logger.warning(
                "Retrieval with metadata filter returned 0 results; retrying without server filter",
            )
            pairs = store.similarity_search_with_score(query, k=fetch_k, filter=None)
            if effective_scope:
                pairs = [
                    (d, s)
                    for d, s in pairs
                    if _metadata_matches_scope(d.metadata or {}, effective_scope)
                ]

        elif effective_scope:
            pairs = [
                (d, s)
                for d, s in pairs
                if _metadata_matches_scope(d.metadata or {}, effective_scope)
            ]

        pairs = pairs[:k]
        logger.info("Retrieval: query_chars=%s filter=%s results=%s", len(query), bool(qf), len(pairs))
        out: List[RetrievalSource] = []
        for doc, score in pairs:
            meta = {str(k2): str(v) for k2, v in (doc.metadata or {}).items() if v is not None}
            out.append(RetrievalSource(text=doc.page_content, score=float(score), metadata=meta))
        return out

    def documents_for_context(
        self,
        query: str,
        *,
        site_id: Optional[str] = None,
        source_scope: Optional[SourceScope] = None,
        top_k: Optional[int] = None,
    ) -> List[Document]:
        """Return raw LangChain documents for ``agents.rag_chain.format_context``."""

        sources = self.query(
            query,
            site_id=site_id,
            source_scope=source_scope,
            top_k=top_k,
        )
        return [Document(page_content=s.text, metadata=dict(s.metadata)) for s in sources]
