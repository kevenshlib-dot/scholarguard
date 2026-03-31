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


class UserIssueItem(BaseModel):
    """A single user-curated issue from the HITL checklist."""

    snippet: str = Field(..., description="The flagged text snippet")
    issue: str = Field(..., description="Issue description (may be user-edited)")


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
    focus: Optional[list[str]] = Field(
        None,
        description="Limit suggestions to specific strategy types",
    )
    language: Optional[str] = Field(None, description="ISO 639-1 language code")
    discipline: Optional[str] = Field(None, description="Academic discipline context")
    user_issues: Optional[list[UserIssueItem]] = Field(
        None,
        description="User-curated list of issues to address (from HITL checklist)",
    )
    custom_prompt: Optional[str] = Field(
        None,
        max_length=1000,
        description="Additional user instructions for optimization",
    )


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


# ── One-click optimize ─────────────────────────────────────────────────


class OneClickOptimizeRequest(BaseModel):
    """Request body for one-click optimization (detect → optimize → store)."""

    text: str = Field(
        ...,
        min_length=50,
        max_length=100_000,
        description="Original text to optimize",
    )
    detection_id: str = Field(
        ..., description="Detection result ID to attach optimization data to"
    )
    user_issues: Optional[list[UserIssueItem]] = Field(
        None,
        description="User-curated issues; defaults to detection flagged_segments",
    )
    focus: Optional[list[str]] = Field(
        None, description="Optimization strategy types"
    )
    custom_prompt: Optional[str] = Field(
        None, max_length=1000, description="Additional user instructions"
    )


class OneClickOptimizeResponse(BaseModel):
    """Response from one-click optimization."""

    optimized_text: str = Field(..., description="Text after applying all suggestions")
    suggestions: list[SuggestionItem] = Field(
        default_factory=list, description="Applied suggestions with explanations"
    )
    original_risk_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    estimated_risk_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    verified_risk_score: Optional[float] = Field(
        None, ge=0.0, le=1.0,
        description="Actual risk score from re-detection of optimized text",
    )
    verified_nhpr_score: Optional[float] = Field(
        None, ge=0.0, le=1.0,
        description="Actual NHPR score from re-detection of optimized text",
    )
    optimization_rounds: int = Field(
        1, description="Number of optimization rounds performed",
    )
    timestamp: str = Field(..., description="ISO timestamp of optimization")
