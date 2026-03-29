"""System-level models: config, usage, audit, prompts, formulas, webhooks."""

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
from sqlalchemy.dialects.postgresql import JSON, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import Organization, User


class ModelConfig(Base):
    __tablename__ = "model_configs"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    organization_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
    )
    task_type: Mapped[str] = mapped_column(String(100), nullable=False)
    primary_model: Mapped[str] = mapped_column(String(150), nullable=False)
    fallback_model: Mapped[Optional[str]] = mapped_column(
        String(150), nullable=True
    )
    degradation_strategy: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default=text("true"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )

    # ── relationships ────────────────────────────────────────────────
    organization: Mapped[Optional["Organization"]] = relationship(
        back_populates="model_configs", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<ModelConfig id={self.id} task={self.task_type!r}>"


class UsageStat(Base):
    __tablename__ = "usage_stats"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    organization_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
    )
    task_type: Mapped[str] = mapped_column(String(100), nullable=False)
    model_used: Mapped[str] = mapped_column(String(150), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 6), nullable=False
    )
    processing_time_ms: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )

    # ── relationships ────────────────────────────────────────────────
    user: Mapped[Optional["User"]] = relationship(
        back_populates="usage_stats", lazy="selectin"
    )
    organization: Mapped[Optional["Organization"]] = relationship(
        back_populates="usage_stats", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<UsageStat id={self.id} task={self.task_type!r}>"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )

    # ── relationships ────────────────────────────────────────────────
    user: Mapped[Optional["User"]] = relationship(
        back_populates="audit_logs", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<AuditLog id={self.id} action={self.action!r}>"


class PromptVersion(Base):
    __tablename__ = "prompt_versions"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    prompt_content: Mapped[str] = mapped_column(Text, nullable=False)
    f1_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 4), nullable=True
    )
    precision_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 4), nullable=True
    )
    recall_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 4), nullable=True
    )
    eval_dataset_version: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    approved_by: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )

    # ── relationships ────────────────────────────────────────────────
    approved_by_user: Mapped[Optional["User"]] = relationship(
        back_populates="approved_prompts",
        foreign_keys=[approved_by],
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<PromptVersion id={self.id} "
            f"agent={self.agent_name!r} v={self.version!r}>"
        )


class FormulaParam(Base):
    __tablename__ = "formula_params"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    version: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False
    )
    params: Mapped[dict] = mapped_column(JSON, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<FormulaParam id={self.id} version={self.version!r}>"


class Webhook(Base):
    __tablename__ = "webhooks"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    secret: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, server_default=text("true"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )

    # ── relationships ────────────────────────────────────────────────
    organization: Mapped["Organization"] = relationship(
        back_populates="webhooks", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Webhook id={self.id} event={self.event_type!r}>"
