"""
JWT and API-key authentication utilities for ScholarGuard.

Provides:
- create_access_token / verify_token helpers
- FastAPI dependencies: get_current_user, get_current_active_user
- Optional API-key authentication via X-API-Key header
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from app.config import Settings, get_settings

# ── Security schemes ────────────────────────────────────────────────────

bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


# ── Token payload model ─────────────────────────────────────────────────


class TokenPayload(BaseModel):
    """Decoded JWT payload."""

    sub: str
    role: str = "user"
    exp: Optional[datetime] = None


class UserContext(BaseModel):
    """Minimal user context extracted from a valid token or API key."""

    user_id: str
    role: str = "user"
    is_active: bool = True


# ── Token helpers ────────────────────────────────────────────────────────


def create_access_token(
    data: dict[str, Any],
    expires_delta: Optional[timedelta] = None,
    settings: Settings | None = None,
) -> str:
    """Create a signed JWT access token.

    Args:
        data: Claims to encode (must include ``sub``).
        expires_delta: Custom expiry duration. Falls back to settings default.
        settings: Application settings (resolved automatically if omitted).

    Returns:
        Encoded JWT string.
    """
    settings = settings or get_settings()
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.jwt_expire_minutes)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def verify_token(token: str, settings: Settings | None = None) -> TokenPayload:
    """Decode and validate a JWT token.

    Args:
        token: Raw JWT string.
        settings: Application settings.

    Returns:
        Parsed :class:`TokenPayload`.

    Raises:
        HTTPException: If the token is invalid or expired.
    """
    settings = settings or get_settings()
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        token_data = TokenPayload(
            sub=payload.get("sub", ""),
            role=payload.get("role", "user"),
            exp=payload.get("exp"),
        )
        if not token_data.sub:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing subject claim",
            )
        return token_data
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {exc}",
        ) from exc


# ── Dependencies ─────────────────────────────────────────────────────────


async def _resolve_user_from_bearer(
    credentials: Optional[HTTPAuthorizationCredentials],
    settings: Settings,
) -> Optional[UserContext]:
    """Attempt to resolve a user from a Bearer token."""
    if credentials is None:
        return None
    token_data = verify_token(credentials.credentials, settings)
    return UserContext(user_id=token_data.sub, role=token_data.role)


async def _resolve_user_from_api_key(
    api_key: Optional[str],
    settings: Settings,
) -> Optional[UserContext]:
    """Attempt to resolve a user from an API key."""
    if api_key is None:
        return None
    if api_key not in settings.allowed_api_keys:
        return None
    # API-key users are treated as service accounts with 'service' role.
    return UserContext(user_id=f"apikey:{api_key[:8]}", role="service")


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    api_key: Optional[str] = Security(api_key_header),
    settings: Settings = Depends(get_settings),
) -> UserContext:
    """FastAPI dependency that extracts an authenticated user.

    Checks Bearer token first, then falls back to X-API-Key header.

    Raises:
        HTTPException 401: If neither authentication method succeeds.
    """
    user = await _resolve_user_from_bearer(credentials, settings)
    if user is not None:
        return user

    user = await _resolve_user_from_api_key(api_key, settings)
    if user is not None:
        return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing or invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_active_user(
    user: UserContext = Depends(get_current_user),
) -> UserContext:
    """Dependency that ensures the authenticated user is active.

    Raises:
        HTTPException 403: If the user account is deactivated.
    """
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )
    return user


def require_role(*allowed_roles: str):
    """Dependency factory that restricts access to specific roles.

    Usage::

        @router.get("/admin-only", dependencies=[Depends(require_role("admin"))])
        async def admin_endpoint(): ...
    """

    async def _check_role(user: UserContext = Depends(get_current_active_user)) -> UserContext:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role}' is not permitted. Required: {allowed_roles}",
            )
        return user

    return _check_role
