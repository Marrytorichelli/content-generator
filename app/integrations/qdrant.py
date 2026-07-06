"""Qdrant integration: collection lifecycle and vector store construction.

**Integration point:** ``QDRANT_URL``, ``QDRANT_COLLECTION``, ``QDRANT_VECTOR_SIZE``.
LangChain's ``Qdrant`` vector store wraps ``qdrant_client.QdrantClient``.
"""

from __future__ import annotations

import logging

from langchain_community.vectorstores import Qdrant
from langchain_core.embeddings import Embeddings
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

logger = logging.getLogger(__name__)


def ensure_collection(
    client: QdrantClient,
    *,
    collection_name: str,
    vector_size: int,
) -> None:
    """Create the collection if missing (idempotent).

    Called from dependency injection so the API fails fast on misconfigured
    embedding dimensions vs existing collections (you may extend with checks).
    """

    existing = {c.name for c in client.get_collections().collections}
    if collection_name in existing:
        logger.debug("Qdrant collection exists: %s", collection_name)
        return
    logger.info("Creating Qdrant collection: %s (dim=%s)", collection_name, vector_size)
    client.create_collection(
        collection_name=collection_name,
        vectors_config=qmodels.VectorParams(size=vector_size, distance=qmodels.Distance.COSINE),
    )


def build_vector_store(
    client: QdrantClient,
    *,
    collection_name: str,
    embeddings: Embeddings,
) -> Qdrant:
    """Return a LangChain ``Qdrant`` store for retrieval and ingestion."""

    return Qdrant(
        client=client,
        collection_name=collection_name,
        embeddings=embeddings,
    )
