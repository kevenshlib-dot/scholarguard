"""User and Organization models."""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSON, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.dataset import EvalSample
    from app.models.detection import DetectionResult
    from app.models.document import Document
    from app.models.review import AppealRecord, Feedback, ReviewRecord
    from app.models.system import AuditLog, ModelConfig, PromptVersion, UsageStat, Webhook


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"
    ORG_ADMIN = "org_admin"
    DETECTOR = "detector"
    REVIEWER = "reviewer"
    AUDITOR = "auditor"
    API_CALLER = "api_caller"


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    budget_monthly: Mapped[float] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    api_key: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=True
    )
    review_policy: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )

    # ── relationships ────────────────────────────────────────────────
    users: Mapped[List["User"]] = relationship(
        back_populates="organization", lazy="selectin"
    )
    model_configs: Mapped[List["ModelConfig"]] = relationship(
        back_populates="organization", lazy="selectin"
    )
    usage_stats: Mapped[List["UsageStat"]] = relationship(
        back_populates="organization", lazy="selectin"
    )
    webhooks: Mapped[List["Webhook"]] = relationship(
        back_populates="organization", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Organization id={self.id} name={self.name!r}>"


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    username: Mapped[str] = mapped_column(
        String(150), unique=True, nullable=False
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        String(50), nullable=False, default=UserRole.DETECTOR
    )
    organization_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
    )
    discipline: Mapped[Optional[str]] = mapped_column(
        String(150), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default=text("true"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # ── relationships ────────────────────────────────────────────────
    organization: Mapped[Optional["Organization"]] = relationship(
        back_populates="users", lazy="selectin"
    )
    documents: Mapped[List["Document"]] = relationship(
        back_populates="user", lazy="selectin"
    )
    reviews: Mapped[List["ReviewRecord"]] = relationship(
        back_populates="reviewer",
        foreign_keys="ReviewRecord.reviewer_id",
        lazy="selectin",
    )
    appeals: Mapped[List["AppealRecord"]] = relationship(
        back_populates="user",
        foreign_keys="AppealRecord.user_id",
        lazy="selectin",
    )
    feedbacks: Mapped[List["Feedback"]] = relationship(
        back_populates="user", lazy="selectin"
    )
    audit_logs: Mapped[List["AuditLog"]] = relationship(
        back_populates="user", lazy="selectin"
    )
    usage_stats: Mapped[List["UsageStat"]] = relationship(
        back_populates="user", lazy="selectin"
    )
    approved_prompts: Mapped[List["PromptVersion"]] = relationship(
        back_populates="approved_by_user",
        foreign_keys="PromptVersion.approved_by",
        lazy="selectin",
    )
    annotations: Mapped[List["EvalSample"]] = relationship(
        back_populates="annotator", lazy="selectin"
    )
    resolved_appeals: Mapped[List["AppealRecord"]] = relationship(
        back_populates="resolver",
        foreign_keys="AppealRecord.resolved_by",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"
