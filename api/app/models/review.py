"""Review, Appeal, and Feedback models."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSON, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.detection import DetectionResult
    from app.models.user import User


# ── enumerations ─────────────────────────────────────────────────────────

class ReviewLabel(str, enum.Enum):
    MAINTAIN = "maintain"
    ADJUST = "adjust"
    DISMISS = "dismiss"


class AppealStatus(str, enum.Enum):
    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class FeedbackType(str, enum.Enum):
    ACCURATE = "accurate"
    FALSE_POSITIVE = "false_positive"
    ACCEPTABLE_ASSIST = "acceptable_assist"
    NEEDS_RERUN = "needs_rerun"


# ── models ───────────────────────────────────────────────────────────────

class ReviewRecord(Base):
    __tablename__ = "review_records"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    detection_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("detection_results.id", ondelete="CASCADE"),
        nullable=False,
    )
    reviewer_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    review_label: Mapped[ReviewLabel] = mapped_column(
        String(50), nullable=False
    )
    review_comment: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    adjusted_risk_level: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )

    # ── relationships ────────────────────────────────────────────────
    detection: Mapped["DetectionResult"] = relationship(
        back_populates="reviews", lazy="selectin"
    )
    reviewer: Mapped["User"] = relationship(
        back_populates="reviews",
        foreign_keys=[reviewer_id],
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<ReviewRecord id={self.id} label={self.review_label!r}>"


class AppealRecord(Base):
    __tablename__ = "appeal_records"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    detection_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("detection_results.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    appeal_reason: Mapped[str] = mapped_column(Text, nullable=False)
    material_paths: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )
    status: Mapped[AppealStatus] = mapped_column(
        String(50),
        nullable=False,
        server_default=text("'pending'"),
    )
    resolution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── relationships ────────────────────────────────────────────────
    detection: Mapped["DetectionResult"] = relationship(
        back_populates="appeals", lazy="selectin"
    )
    user: Mapped["User"] = relationship(
        back_populates="appeals",
        foreign_keys=[user_id],
        lazy="selectin",
    )
    resolver: Mapped[Optional["User"]] = relationship(
        back_populates="resolved_appeals",
        foreign_keys=[resolved_by],
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<AppealRecord id={self.id} status={self.status!r}>"


class Feedback(Base):
    __tablename__ = "feedbacks"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    detection_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("detection_results.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    feedback_type: Mapped[FeedbackType] = mapped_column(
        String(50), nullable=False
    )
    user_comment: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    expected_risk_level: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )
    processed: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── relationships ────────────────────────────────────────────────
    detection: Mapped["DetectionResult"] = relationship(
        back_populates="feedbacks", lazy="selectin"
    )
    user: Mapped["User"] = relationship(
        back_populates="feedbacks", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Feedback id={self.id} type={self.feedback_type!r}>"
