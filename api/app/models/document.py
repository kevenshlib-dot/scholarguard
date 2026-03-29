"""Document model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.detection import DetectionResult
    from app.models.user import User


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="SHA-256 hex digest"
    )
    word_count: Mapped[int] = mapped_column(Integer, nullable=False)
    language: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default=text("'en'")
    )
    discipline: Mapped[Optional[str]] = mapped_column(
        String(150), nullable=True
    )
    file_path: Mapped[Optional[str]] = mapped_column(
        String(1024), nullable=True
    )
    file_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )

    # ── relationships ────────────────────────────────────────────────
    user: Mapped["User"] = relationship(
        back_populates="documents", lazy="selectin"
    )
    detections: Mapped[List["DetectionResult"]] = relationship(
        back_populates="document", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Document id={self.id} title={self.title!r}>"
