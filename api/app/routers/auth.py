"""
Authentication routes for ScholarGuard.

Endpoints for user registration, login, token refresh, and
retrieving the current authenticated user's profile.
"""

from __future__ import annotations

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.middleware.auth import (
    UserContext,
    create_access_token,
    get_current_active_user,
    verify_token,
)
from app.models.base import get_async_session
from app.models.user import Organization, User, UserRole
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ── Helpers ─────────────────────────────────────────────────────────────


def _hash_password(plain: str) -> str:
    """Return a bcrypt hash of the plain-text password."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def _verify_password(plain: str, hashed: str) -> bool:
    """Check a plain-text password against its bcrypt hash."""
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def _build_token(user: User, settings: Settings) -> str:
    """Create a JWT access token for the given user."""
    return create_access_token(
        data={
            "sub": str(user.id),
            "role": user.role if isinstance(user.role, str) else user.role.value,
            "email": user.email,
        },
        settings=settings,
    )


# ── POST /auth/register ────────────────────────────────────────────────


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(
    body: RegisterRequest,
    session: AsyncSession = Depends(get_async_session),
    settings: Settings = Depends(get_settings),
):
    """Create a new user account.

    If ``organization_name`` is provided, a new :class:`Organization` is
    created first and the user is linked to it.
    """
    # Check for duplicate email
    existing = await session.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    # Check for duplicate username
    existing = await session.execute(
        select(User).where(User.username == body.username)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this username already exists",
        )

    # Validate role
    valid_roles = {r.value for r in UserRole}
    role_value = body.role
    if role_value not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid role '{role_value}'. Must be one of: {sorted(valid_roles)}",
        )

    # Optionally create an Organization
    organization_id = None
    if body.organization_name:
        org = Organization(name=body.organization_name, type="academic")
        session.add(org)
        await session.flush()  # populate org.id
        organization_id = org.id

    # Create the User
    user = User(
        username=body.username,
        email=body.email,
        password_hash=_hash_password(body.password),
        role=role_value,
        organization_id=organization_id,
    )
    session.add(user)
    await session.flush()  # populate user.id and server defaults

    token = _build_token(user, settings)
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


# ── POST /auth/login ───────────────────────────────────────────────────


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and obtain a JWT",
)
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_async_session),
    settings: Settings = Depends(get_settings),
):
    """Verify credentials and return a JWT access token."""
    result = await session.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user is None or not _verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    token = _build_token(user, settings)
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


# ── GET /auth/me ────────────────────────────────────────────────────────


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
)
async def me(
    current_user: UserContext = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Return the profile of the currently authenticated user."""
    result = await session.execute(
        select(User).where(User.id == current_user.user_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return UserResponse.model_validate(user)


# ── POST /auth/refresh ─────────────────────────────────────────────────


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh an access token",
)
async def refresh(
    body: RefreshRequest,
    session: AsyncSession = Depends(get_async_session),
    settings: Settings = Depends(get_settings),
):
    """Accept a valid JWT and return a new token with extended expiry."""
    payload = verify_token(body.token, settings)

    # Fetch the user to confirm they still exist and are active
    result = await session.execute(
        select(User).where(User.id == payload.sub)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User no longer exists",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    token = _build_token(user, settings)
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )
