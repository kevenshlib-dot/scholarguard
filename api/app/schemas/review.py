"""
Pydantic schemas for review, appeal, and feedback endpoints.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Enums ───────────────────────────────────────────────────────────────


class ReviewVerdict(str, Enum):
    """Possible review verdicts."""

    CONFIRMED = "confirmed"
    OVERTURNED = "overturned"
    INCONCLUSIVE = "inconclusive"


class AppealStatus(str, Enum):
    """Status of an appeal."""

    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"
    REJECTED = "rejected"


class FeedbackRating(str, Enum):
    """User feedback rating."""

    ACCURATE = "accurate"
    PARTIALLY_ACCURATE = "partially_accurate"
    INACCURATE = "inaccurate"


# ── Requests ────────────────────────────────────────────────────────────


class ReviewRequest(BaseModel):
    """Request body to submit a human review of a detection result."""

    verdict: ReviewVerdict = Field(..., description="The reviewer's verdict")
    notes: Optional[str] = Field(
        None,
        max_length=5000,
        description="Reviewer notes / justification",
    )
    reviewer_role: Optional[str] = Field(
        None, description="Role of the reviewer (e.g. instructor, admin)"
    )


class AppealRequest(BaseModel):
    """Request body to submit an appeal against a detection result."""

    reason: str = Field(
        ...,
        min_length=20,
        max_length=5000,
        description="Detailed reason for the appeal",
    )
    supporting_evidence: Optional[str] = Field(
        None,
        max_length=10_000,
        description="Additional evidence (e.g. drafts, references)",
    )


class FeedbackRequest(BaseModel):
    """Request body to submit user feedback on detection quality."""

    detection_id: str = Field(..., description="Detection this feedback relates to")
    rating: FeedbackRating = Field(..., description="Accuracy rating")
    comment: Optional[str] = Field(
        None,
        max_length=2000,
        description="Free-text comment",
    )


# ── Responses ───────────────────────────────────────────────────────────


class ReviewResponse(BaseModel):
    """Response after submitting a review."""

    review_id: str = Field(..., description="Unique review identifier")
    detection_id: str = Field(..., description="Related detection identifier")
    verdict: ReviewVerdict = Field(..., description="Applied verdict")
    reviewed_at: datetime = Field(default_factory=datetime.utcnow)


class AppealResponse(BaseModel):
    """Response for an appeal submission or status query."""

    appeal_id: str = Field(..., description="Unique appeal identifier")
    detection_id: str = Field(..., description="Related detection identifier")
    status: AppealStatus = Field(..., description="Current appeal status")
    resolution: Optional[str] = Field(None, description="Resolution details when resolved")
    submitted_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None


class FeedbackResponse(BaseModel):
    """Response after submitting feedback."""

    feedback_id: str = Field(..., description="Unique feedback identifier")
    detection_id: str = Field(..., description="Related detection identifier")
    rating: FeedbackRating = Field(..., description="Submitted rating")
    received_at: datetime = Field(default_factory=datetime.utcnow)
