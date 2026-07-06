"""Liveness and readiness endpoints."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz() -> dict[str, str]:
    """Liveness: process is up."""

    return {"status": "ok"}


@router.get("/readyz")
async def readyz(settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    """Readiness: Ollama and Qdrant reachable.

    **Integration points:** ``OLLAMA_BASE_URL`` and ``QDRANT_URL``.
    """

    checks: dict[str, Any] = {"ollama": False, "qdrant": False}
    timeout = httpx.Timeout(5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            r = await client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
            checks["ollama"] = r.is_success
        except httpx.HTTPError as e:
            logger.warning("Ollama readiness failed: %s", e)
        try:
            r2 = await client.get(f"{settings.qdrant_url.rstrip('/')}/collections")
            checks["qdrant"] = r2.is_success
        except httpx.HTTPError as e:
            logger.warning("Qdrant readiness failed: %s", e)
    ok = bool(checks["ollama"] and checks["qdrant"])
    return {"status": "ready" if ok else "not_ready", "checks": checks}
