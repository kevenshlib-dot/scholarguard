"""
SQLAlchemy async base configuration for ScholarGuard.

Provides the declarative base, async engine/session factory,
dependency helper, and lifecycle hooks (init_db / close_db).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator

from sqlalchemy import MetaData, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
)

from app.config import get_settings

settings = get_settings()

# ── Naming convention for Alembic autogenerate ──────────────────────────
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(AsyncAttrs, DeclarativeBase):
    """Declarative base used by every ScholarGuard model."""

    metadata = MetaData(naming_convention=convention)


# ── Engine & session factory (populated by init_db) ─────────────────────
engine = None
async_session_factory: async_sessionmaker[AsyncSession] | None = None


async def init_db() -> None:
    """Create the async engine and session factory.

    Call once at application startup (e.g. in a FastAPI lifespan).
    """
    global engine, async_session_factory

    engine = create_async_engine(
        settings.database_url,  # e.g. "postgresql+asyncpg://user:pass@host/db"
        echo=(settings.log_level.upper() == "DEBUG"),
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True,
    )

    async_session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def close_db() -> None:
    """Dispose of the engine connection pool.

    Call once at application shutdown.
    """
    global engine, async_session_factory
    if engine is not None:
        await engine.dispose()
        engine = None
        async_session_factory = None


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a per-request async session."""
    if async_session_factory is None:
        raise RuntimeError("Database not initialised. Call init_db() first.")
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
