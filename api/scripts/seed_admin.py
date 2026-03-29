"""
Seed the default admin user for ScholarGuard.

Creates:
- Organization: "ScholarGuard Admin"
- User: admin / admin@scholarguard.dev / admin1234 / role=admin

Run with:
    cd api && uv run python -m scripts.seed_admin
"""

from __future__ import annotations

import asyncio

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models.base import Base
from app.models.user import Organization, User


def _hash_password(plain: str) -> str:
    """Return a bcrypt hash of the plain-text password."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


async def seed_admin() -> None:
    settings = get_settings()

    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_factory() as session:
        # Check if admin user already exists
        result = await session.execute(
            select(User).where(User.email == "admin@scholarguard.dev")
        )
        existing = result.scalar_one_or_none()

        if existing is not None:
            print(f"[seed] Admin user already exists: {existing.username} ({existing.email})")
            await engine.dispose()
            return

        # Create default organization for admin
        org = Organization(name="ScholarGuard Admin", type="platform")
        session.add(org)
        await session.flush()

        # Create admin user
        admin_user = User(
            username="admin",
            email="admin@scholarguard.dev",
            password_hash=_hash_password("admin1234"),
            role="admin",
            organization_id=org.id,
        )
        session.add(admin_user)
        await session.commit()

        print(f"[seed] Created admin user: admin / admin@scholarguard.dev (role=admin)")
        print(f"[seed] Created organization: ScholarGuard Admin (id={org.id})")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_admin())
