"""Upsert chunked documents into Qdrant via LangChain vector store."""

from __future__ import annotations

import logging
from typing import List

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from qdrant_client import QdrantClient

from app.integrations.qdrant import build_vector_store

logger = logging.getLogger(__name__)


def upsert_documents(
    client: QdrantClient,
    *,
    collection_name: str,
    embeddings: Embeddings,
    documents: List[Document],
) -> int:
    """Embed and insert/update chunks. Returns number of vectors written.

    Metadata fields ``source_type``, ``domain``, and ``language`` are stored in the
    LangChain/Qdrant payload for later ``FieldCondition`` filters at query time.
    """

    if not documents:
        return 0
    store = build_vector_store(
        client,
        collection_name=collection_name,
        embeddings=embeddings,
    )
    # TODO: For very large batches, switch to batched ``add_documents`` or Qdrant async upsert.
    store.add_documents(documents)
    logger.info("Qdrant upsert complete: %s vectors → %s", len(documents), collection_name)
    return len(documents)
