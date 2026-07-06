"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from langchain_community.llms.ollama import OllamaEndpointNotFoundError

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.routers import generation, health, ingestion, retrieval

logger = logging.getLogger(__name__)

_WEB_DIR = Path(__file__).resolve().parent / "web"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup/shutdown hook (extend with DB pools, etc.)."""

    settings = get_settings()
    logger.info("Starting %s", settings.app_name)
    yield
    logger.info("Shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    """Application factory (use in tests and ASGI servers)."""

    settings = get_settings()
    setup_logging(settings)
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )

    app.include_router(health.router)
    app.include_router(ingestion.router)
    app.include_router(retrieval.router)
    app.include_router(generation.router)

    if _WEB_DIR.is_dir():
        app.mount("/ui", StaticFiles(directory=str(_WEB_DIR), html=True), name="ui")

        @app.get("/", include_in_schema=False)
        def _root() -> RedirectResponse:
            return RedirectResponse(url="/ui/")

    @app.exception_handler(OllamaEndpointNotFoundError)
    async def ollama_model_missing(_: Request, exc: OllamaEndpointNotFoundError) -> JSONResponse:
        # Provide a concrete remediation instead of a generic 500.
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(Exception)
    async def unhandled(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error: %s", exc)
        return JSONResponse(status_code=500, content={"detail": "internal_error"})

    return app


app = create_app()
