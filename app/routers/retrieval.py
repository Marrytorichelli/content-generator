"""Retrieval routes: semantic search over Qdrant."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from app.core.deps import get_retrieval_service
from app.schemas.common import SourceScope
from app.schemas.retrieval import RetrievalQueryRequest, RetrievalQueryResponse
from app.services.retrieval.service import RetrievalService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/retrieval", tags=["retrieval"])


@router.post("/query", response_model=RetrievalQueryResponse)
def retrieval_query(
    body: RetrievalQueryRequest,
    svc: RetrievalService = Depends(get_retrieval_service),
) -> RetrievalQueryResponse:
    """Return top-k chunks for a query (optional metadata filter via ``source_scope`` / ``site_id``)."""

    scope = body.source_scope
    if body.site_id and scope is None:
        scope = SourceScope(site_id=body.site_id)
    elif body.site_id and scope is not None and scope.site_id is None:
        scope = scope.model_copy(update={"site_id": body.site_id})

    sources = svc.query(
        body.query,
        site_id=body.site_id,
        source_scope=scope,
        top_k=body.top_k,
    )
    logger.info("Retrieval query: %s hits", len(sources))
    return RetrievalQueryResponse(sources=sources)
