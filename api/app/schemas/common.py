"""
Common response envelope and shared schema types for the ScholarGuard API.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Meta(BaseModel):
    """Metadata attached to every API response."""

    request_id: str = Field(..., description="Unique identifier for this request")
    processing_time_ms: Optional[float] = Field(
        None, description="Server-side processing time in milliseconds"
    )
    model_version: Optional[str] = Field(
        None, description="Version of the detection model used"
    )
    formula_version: Optional[str] = Field(
        None, description="Version of the scoring formula"
    )
    param_version: Optional[str] = Field(
        None, description="Version of the formula parameters"
    )


class APIResponse(BaseModel, Generic[T]):
    """Standard response envelope wrapping every API response."""

    code: int = Field(200, description="HTTP-style status code")
    message: str = Field("ok", description="Human-readable status message")
    data: Optional[T] = Field(None, description="Response payload")
    meta: Optional[Meta] = Field(None, description="Request metadata")


class PaginationParams(BaseModel):
    """Common pagination parameters."""

    page: int = Field(1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(20, ge=1, le=100, description="Items per page")


class PaginatedMeta(Meta):
    """Metadata with pagination information."""

    total: int = Field(0, description="Total number of items")
    page: int = Field(1, description="Current page")
    page_size: int = Field(20, description="Items per page")
    total_pages: int = Field(0, description="Total number of pages")


class TimestampMixin(BaseModel):
    """Mixin providing created/updated timestamps."""

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
