"""Detection result model (Version 2 schema)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSON, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.review import AppealRecord, Feedback, ReviewRecord


class DetectionResult(Base):
    __tablename__ = "detection_results"

    # ── identity ─────────────────────────────────────────────────────
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    document_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    granularity: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="e.g. document, paragraph, sentence",
    )

    # ── scores ───────────────────────────────────────────────────────
    risk_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), nullable=False
    )
    risk_level: Mapped[str] = mapped_column(String(50), nullable=False)
    llm_confidence: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), nullable=False
    )
    stat_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), nullable=False
    )
    evidence_completeness: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    review_priority: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), nullable=False
    )

    # ── conclusion ───────────────────────────────────────────────────
    conclusion_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="preliminary | fused | human_confirmed",
    )

    # ── evidence payloads (JSON) ─────────────────────────────────────
    llm_evidence: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    stat_evidence: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    material_evidence: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )
    human_evidence: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )

    # ── analysis artefacts ───────────────────────────────────────────
    flagged_segments: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )
    report_content: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )
    recommendations: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )
    uncertainty_notes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )

    # ── heatmap (deferred generation) ──────────────────────────────
    paragraph_heatmap: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="Paragraph-level risk heatmap data"
    )
    heatmap_status: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        server_default=text("'not_requested'"),
        comment="not_requested | pending | completed",
    )

    # ── versioning ───────────────────────────────────────────────────
    formula_version: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    param_version: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    model_version: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    threshold_version: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    formula_params: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )

    # ── task status ─────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'pending'"),
        comment="pending | processing | completed | failed",
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Error details when status is failed"
    )

    # ── batch tracking ──────────────────────────────────────────────
    batch_id: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True, index=True, comment="UUID of the batch this belongs to"
    )

    # ── operational metadata ─────────────────────────────────────────
    processing_time_ms: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    cost_usd: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 6), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )

    # ── relationships ────────────────────────────────────────────────
    document: Mapped["Document"] = relationship(
        back_populates="detections", lazy="selectin"
    )
    reviews: Mapped[List["ReviewRecord"]] = relationship(
        back_populates="detection", lazy="selectin"
    )
    appeals: Mapped[List["AppealRecord"]] = relationship(
        back_populates="detection", lazy="selectin"
    )
    feedbacks: Mapped[List["Feedback"]] = relationship(
        back_populates="detection", lazy="selectin"
    )

    def __repr__(self) -> str:
        return (
            f"<DetectionResult id={self.id} "
            f"risk_score={self.risk_score} risk_level={self.risk_level!r}>"
        )
