"""
Pydantic schemas for the writing suggestion endpoints.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class SuggestionType(str, Enum):
    """Type of writing suggestion."""

    REPHRASE = "rephrase"
    RESTRUCTURE = "restructure"
    TONE = "tone"
    VOCABULARY = "vocabulary"
    GENERAL = "general"


class SuggestionItem(BaseModel):
    """A single writing suggestion."""

    suggestion_id: str = Field(..., description="Unique suggestion identifier")
    type: SuggestionType = Field(..., description="Category of the suggestion")
    original_text: str = Field(..., description="Original text segment")
    suggested_text: str = Field(..., description="Suggested replacement text")
    explanation: str = Field(..., description="Why this change was suggested")
    offset_start: int = Field(..., description="Character offset start in the original text")
    offset_end: int = Field(..., description="Character offset end in the original text")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Suggestion confidence")


# ── Requests ────────────────────────────────────────────────────────────


class SuggestRequest(BaseModel):
    """Request body for getting writing suggestions."""

    text: str = Field(
        ...,
        min_length=50,
        max_length=100_000,
        description="Text to get writing suggestions for",
    )
    detection_id: Optional[str] = Field(
        None,
        description="Link to a prior detection result for context",
    )
    focus: Optional[list[SuggestionType]] = Field(
        None,
        description="Limit suggestions to specific types",
    )
    language: Optional[str] = Field(None, description="ISO 639-1 language code")
    discipline: Optional[str] = Field(None, description="Academic discipline context")


class RewriteRequest(BaseModel):
    """Request body for confirming and applying a rewrite."""

    text: str = Field(
        ...,
        min_length=50,
        max_length=100_000,
        description="Original text to rewrite",
    )
    accepted_suggestion_ids: list[str] = Field(
        ...,
        min_length=1,
        description="IDs of accepted suggestions to apply",
    )
    detection_id: Optional[str] = Field(
        None, description="Link to original detection for audit trail"
    )


# ── Responses ───────────────────────────────────────────────────────────


class SuggestResponse(BaseModel):
    """Response containing writing suggestions."""

    suggestions: list[SuggestionItem] = Field(
        default_factory=list, description="List of writing suggestions"
    )
    original_risk_score: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Risk score of the original text"
    )
    estimated_risk_score: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Estimated risk score after applying all suggestions",
    )


class RewriteResponse(BaseModel):
    """Response containing the rewritten text."""

    rewritten_text: str = Field(..., description="Text with accepted suggestions applied")
    applied_count: int = Field(..., description="Number of suggestions applied")
    new_risk_score: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Risk score of the rewritten text"
    )
