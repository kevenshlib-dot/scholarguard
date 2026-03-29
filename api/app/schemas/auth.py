"""Pydantic schemas for authentication endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# ── Request schemas ─────────────────────────────────────────────────────


class RegisterRequest(BaseModel):
    """Body for POST /auth/register."""

    username: str = Field(..., min_length=3, max_length=150)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    role: str = Field(default="detector", description="User role (default: detector)")
    organization_name: Optional[str] = Field(
        default=None,
        max_length=255,
        description="If provided, a new Organization is created and the user is linked to it.",
    )


class LoginRequest(BaseModel):
    """Body for POST /auth/login."""

    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    """Body for POST /auth/refresh."""

    token: str


# ── Response schemas ────────────────────────────────────────────────────


class UserResponse(BaseModel):
    """Public user representation (never includes password_hash)."""

    id: UUID
    username: str
    email: str
    role: str
    organization_id: Optional[UUID] = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """JWT token response returned on register / login / refresh."""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse
