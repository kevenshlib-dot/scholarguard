"""
ScholarGuard API - FastAPI application entry point.

Configures the ASGI application with CORS middleware, all API routers,
and lifespan hooks for initialising / tearing down shared resources
(database connections, Redis pool).
"""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import Settings, get_settings
from app.middleware.rate_limiter import close_redis, get_redis
from app.models.base import init_db, close_db
from app.routers import admin, detect, research, review, suggest

# ── Logging ─────────────────────────────────────────────────────────────

logger = logging.getLogger("scholarguard")


# ── Lifespan ────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler.

    Startup:
        - Configure logging.
        - Warm up the Redis connection pool.
        - (Future) Initialise the async database engine / session factory.

    Shutdown:
        - Close the Redis connection pool.
        - (Future) Dispose of the database engine.
    """
    settings = get_settings()

    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    logger.info(
        "ScholarGuard API starting  env=%s  formula=%s  params=%s",
        settings.environment,
        settings.formula_version,
        settings.param_version,
    )

    # Warm up Redis (fail gracefully so the app can still start without Redis)
    try:
        redis = await get_redis(settings)
        await redis.ping()
        logger.info("Redis connection established: %s", settings.redis_url)
    except Exception as exc:
        logger.warning("Redis unavailable at startup: %s", exc)

    # Initialise async SQLAlchemy engine & session factory
    await init_db()
    logger.info("Database engine initialised: %s", settings.database_url.split("@")[-1])

    yield

    # ── Shutdown ────────────────────────────────────────────────────────
    logger.info("ScholarGuard API shutting down")
    await close_db()
    await close_redis()


# ── Application factory ─────────────────────────────────────────────────


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="ScholarGuard API",
        version="0.1.0",
        description=(
            "AI-content detection, writing suggestions, and academic integrity "
            "tools for educational institutions."
        ),
        lifespan=lifespan,
    )

    # ── CORS (permissive for development) ───────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Request-ID & timing middleware ──────────────────────────────────

    @app.middleware("http")
    async def add_request_metadata(request: Request, call_next):
        """Inject a unique request ID and measure processing time."""
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        start = time.perf_counter()

        response = await call_next(request)

        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Processing-Time-Ms"] = f"{elapsed_ms:.2f}"
        return response

    # ── Routers (all under /api/v1 prefix) ──────────────────────────────
    api_prefix = "/api/v1"
    app.include_router(detect.router, prefix=api_prefix)
    app.include_router(suggest.router, prefix=api_prefix)
    app.include_router(review.router, prefix=api_prefix)
    app.include_router(research.router, prefix=api_prefix)
    app.include_router(admin.router, prefix=api_prefix)

    # ── Health check (outside versioned prefix) ─────────────────────────

    @app.get("/health", tags=["Health"], summary="Health check")
    async def health_check():
        """Return basic health status of the API.

        Used by load balancers and orchestrators to determine whether
        the service instance is ready to accept traffic.
        """
        return {
            "status": "healthy",
            "version": "0.1.0",
            "environment": settings.environment,
        }

    return app


# ── Module-level app instance (used by uvicorn) ────────────────────────

app = create_app()
