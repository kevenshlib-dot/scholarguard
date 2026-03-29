"""Evaluation dataset model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class EvalSample(Base):
    __tablename__ = "eval_samples"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    text_content: Mapped[str] = mapped_column(Text, nullable=False)
    text_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="SHA-256 hex digest"
    )
    source_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="e.g. human, gpt-4, claude-3, mixed",
    )
    discipline: Mapped[Optional[str]] = mapped_column(
        String(150), nullable=True
    )
    language: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default=text("'en'")
    )
    word_count: Mapped[int] = mapped_column(Integer, nullable=False)
    ground_truth_label: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="e.g. human, ai_generated, ai_assisted",
    )
    annotator_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    annotation_confidence: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 4), nullable=True
    )
    annotation_notes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    double_reviewed: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    dispute_flag: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    dataset_version: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )

    # ── relationships ────────────────────────────────────────────────
    annotator: Mapped[Optional["User"]] = relationship(
        back_populates="annotations", lazy="selectin"
    )

    def __repr__(self) -> str:
        return (
            f"<EvalSample id={self.id} "
            f"label={self.ground_truth_label!r}>"
        )
