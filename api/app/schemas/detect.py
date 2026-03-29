"""
Pydantic schemas for the detection endpoints.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Enums ───────────────────────────────────────────────────────────────


class Granularity(str, Enum):
    """Detection granularity level."""

    DOCUMENT = "document"
    PARAGRAPH = "paragraph"
    SENTENCE = "sentence"


class RiskLevel(str, Enum):
    """Human-readable risk classification."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TaskStatus(str, Enum):
    """Async task status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# ── Requests ────────────────────────────────────────────────────────────


class DetectRequest(BaseModel):
    """Request body for submitting text to AI-content detection."""

    text: str = Field(
        ...,
        min_length=50,
        max_length=100_000,
        description="The text to analyse for AI-generated content",
    )
    granularity: Granularity = Field(
        Granularity.DOCUMENT,
        description="Level of granularity for the analysis",
    )
    language: Optional[str] = Field(
        None,
        max_length=10,
        description="ISO 639-1 language code (auto-detected if omitted)",
    )
    discipline: Optional[str] = Field(
        None,
        max_length=100,
        description="Academic discipline for context-aware scoring",
    )


class BatchDetectRequest(BaseModel):
    """Request body for batch detection."""

    items: list[DetectRequest] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="List of texts to analyse",
    )
    callback_url: Optional[str] = Field(
        None,
        description="Webhook URL to POST results when the batch completes",
    )


# ── Segment result (paragraph / sentence) ──────────────────────────────


class SegmentResult(BaseModel):
    """Detection result for a single text segment."""

    text: str = Field(..., description="The segment text")
    offset_start: int = Field(..., description="Character offset start in the original text")
    offset_end: int = Field(..., description="Character offset end in the original text")
    risk_score: float = Field(..., ge=0.0, le=1.0, description="AI-content risk score")
    risk_level: RiskLevel = Field(..., description="Risk classification")
    llm_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="LLM perplexity-based confidence"
    )


# ── Responses ───────────────────────────────────────────────────────────


class DetectResult(BaseModel):
    """Full detection result for a single document."""

    detection_id: str = Field(..., description="Unique detection identifier")
    risk_score: float = Field(..., ge=0.0, le=1.0, description="Overall AI-content risk score")
    risk_level: RiskLevel = Field(..., description="Overall risk classification")
    llm_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="LLM perplexity-based confidence"
    )
    statistical_score: float = Field(
        ..., ge=0.0, le=1.0, description="Statistical feature score"
    )
    stylistic_score: float = Field(
        ..., ge=0.0, le=1.0, description="Stylistic analysis score"
    )
    formula_version: str = Field(..., description="Formula version used")
    param_version: str = Field(..., description="Parameter version used")
    language: str = Field(..., description="Detected or specified language")
    segments: Optional[list[SegmentResult]] = Field(
        None,
        description="Per-segment results (present when granularity != document)",
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DetectResponse(BaseModel):
    """Response returned immediately after submitting a detection request."""

    task_id: str = Field(..., description="Async task identifier to poll for results")
    status: TaskStatus = Field(TaskStatus.PENDING, description="Current task status")
    result: Optional[DetectResult] = Field(
        None, description="Detection result (present when status is completed)"
    )


class BatchDetectResponse(BaseModel):
    """Response for a batch detection submission."""

    batch_id: str = Field(..., description="Batch identifier")
    total: int = Field(..., description="Number of items in the batch")
    status: TaskStatus = Field(TaskStatus.PENDING, description="Overall batch status")
    completed: int = Field(0, description="Number of completed items")
    results: Optional[list[DetectResult]] = Field(
        None, description="Results (present when all items are completed)"
    )
