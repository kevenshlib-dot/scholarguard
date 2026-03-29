"""
Admin routes for ScholarGuard.

Endpoints for model management, usage statistics, audit logs, and
formula parameter configuration.  All endpoints require admin role.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.middleware.auth import UserContext, require_role
from app.middleware.rate_limiter import rate_limit
from app.schemas.common import APIResponse, Meta, PaginationParams

router = APIRouter(tags=["Admin"])


# ── Schemas (admin-specific) ────────────────────────────────────────────


class ModelInfo(BaseModel):
    """Information about an available detection model."""

    model_id: str = Field(..., description="Unique model identifier")
    name: str = Field(..., description="Human-readable model name")
    provider: str = Field(..., description="Provider (ollama, openai, anthropic, google)")
    version: str = Field(..., description="Model version string")
    is_active: bool = Field(True, description="Whether the model is currently active")
    capabilities: list[str] = Field(
        default_factory=list,
        description="Capabilities: detection, suggestion, summarisation, etc.",
    )


class ModelRouteConfig(BaseModel):
    """Configuration for routing requests to specific models."""

    detection_model: str = Field(..., description="Model ID for detection tasks")
    suggestion_model: str = Field(..., description="Model ID for suggestion tasks")
    fallback_model: Optional[str] = Field(
        None, description="Fallback model if primary is unavailable"
    )


class UsageStats(BaseModel):
    """Aggregated usage statistics."""

    total_detections: int = 0
    total_suggestions: int = 0
    total_reviews: int = 0
    total_appeals: int = 0
    detections_today: int = 0
    average_processing_ms: float = 0.0
    active_users_24h: int = 0


class AuditLogEntry(BaseModel):
    """Single audit log entry."""

    log_id: str
    timestamp: datetime
    user_id: str
    action: str
    resource: str
    details: Optional[dict[str, Any]] = None


class FormulaParams(BaseModel):
    """Detection formula parameter set."""

    formula_version: str = Field(..., description="Formula version identifier")
    param_version: str = Field(..., description="Parameter version identifier")
    weights: dict[str, float] = Field(
        default_factory=dict,
        description="Named weights used in the scoring formula",
    )
    thresholds: dict[str, float] = Field(
        default_factory=dict,
        description="Classification thresholds (e.g. low/medium/high cutoffs)",
    )
    updated_at: Optional[datetime] = None
    updated_by: Optional[str] = None


class FormulaParamsUpdate(BaseModel):
    """Request body for updating formula parameters."""

    weights: Optional[dict[str, float]] = Field(
        None, description="Updated weights (merged with existing)"
    )
    thresholds: Optional[dict[str, float]] = Field(
        None, description="Updated thresholds (merged with existing)"
    )


# ── In-memory stores (replace with DB in production) ────────────────────

_models: list[ModelInfo] = [
    ModelInfo(
        model_id="ollama-llama3",
        name="Llama 3 (Ollama)",
        provider="ollama",
        version="3.0",
        capabilities=["detection", "suggestion"],
    ),
]
_route_config = ModelRouteConfig(
    detection_model="ollama-llama3",
    suggestion_model="ollama-llama3",
)
_formula_params = FormulaParams(
    formula_version="1.0.0",
    param_version="1.0.0",
    weights={
        "llm_confidence": 0.4,
        "statistical_score": 0.35,
        "stylistic_score": 0.25,
    },
    thresholds={
        "low_max": 0.3,
        "medium_max": 0.6,
        "high_max": 0.85,
    },
)


# ── Routes ──────────────────────────────────────────────────────────────


@router.get(
    "/models",
    response_model=APIResponse[list[ModelInfo]],
    dependencies=[Depends(rate_limit())],
    summary="List available detection models",
)
async def list_models(
    user: UserContext = Depends(require_role("admin")),
    settings: Settings = Depends(get_settings),
) -> APIResponse[list[ModelInfo]]:
    """Return a list of all registered detection / suggestion models.

    Includes model metadata, provider, version, active status, and
    supported capabilities.
    """
    request_id = str(uuid.uuid4())
    return APIResponse(
        data=_models,
        meta=Meta(request_id=request_id),
    )


@router.put(
    "/models/route",
    response_model=APIResponse[ModelRouteConfig],
    dependencies=[Depends(rate_limit())],
    summary="Configure model routing",
)
async def configure_model_routing(
    body: ModelRouteConfig,
    user: UserContext = Depends(require_role("admin")),
) -> APIResponse[ModelRouteConfig]:
    """Update which models are used for detection and suggestion tasks.

    Accepts a primary detection model, a suggestion model, and an optional
    fallback model.  The configuration takes effect immediately for new
    requests.
    """
    global _route_config
    _route_config = body

    # TODO: Persist to database.

    request_id = str(uuid.uuid4())
    return APIResponse(
        data=_route_config,
        meta=Meta(request_id=request_id),
    )


@router.get(
    "/usage",
    response_model=APIResponse[UsageStats],
    dependencies=[Depends(rate_limit())],
    summary="Get aggregated usage statistics",
)
async def get_usage_stats(
    user: UserContext = Depends(require_role("admin")),
) -> APIResponse[UsageStats]:
    """Return aggregated platform usage statistics.

    Includes total counts for detections, suggestions, reviews, and
    appeals, as well as today's detection count and average processing
    time.
    """
    request_id = str(uuid.uuid4())

    # TODO: Query actual metrics from the database / metrics store.
    stats = UsageStats()

    return APIResponse(
        data=stats,
        meta=Meta(request_id=request_id),
    )


@router.get(
    "/admin/audit-logs",
    response_model=APIResponse[list[AuditLogEntry]],
    dependencies=[Depends(rate_limit())],
    summary="Retrieve audit logs",
)
async def get_audit_logs(
    page: int = 1,
    page_size: int = 20,
    user: UserContext = Depends(require_role("admin")),
) -> APIResponse[list[AuditLogEntry]]:
    """Return paginated audit log entries.

    Audit logs record every significant action (detection, review, appeal,
    configuration change) performed on the platform.
    """
    request_id = str(uuid.uuid4())

    # TODO: Query audit log table with pagination.
    logs: list[AuditLogEntry] = []

    return APIResponse(
        data=logs,
        meta=Meta(request_id=request_id),
    )


@router.get(
    "/admin/formula-params",
    response_model=APIResponse[FormulaParams],
    dependencies=[Depends(rate_limit())],
    summary="Get current formula parameters",
)
async def get_formula_params(
    user: UserContext = Depends(require_role("admin")),
    settings: Settings = Depends(get_settings),
) -> APIResponse[FormulaParams]:
    """Return the current detection formula weights and thresholds.

    These parameters control how the individual signal scores (LLM
    confidence, statistical features, stylistic features) are combined
    into the final risk score and classification.
    """
    request_id = str(uuid.uuid4())
    return APIResponse(
        data=_formula_params,
        meta=Meta(
            request_id=request_id,
            formula_version=settings.formula_version,
            param_version=settings.param_version,
        ),
    )


@router.put(
    "/admin/formula-params",
    response_model=APIResponse[FormulaParams],
    dependencies=[Depends(rate_limit())],
    summary="Update formula parameters",
)
async def update_formula_params(
    body: FormulaParamsUpdate,
    user: UserContext = Depends(require_role("admin")),
    settings: Settings = Depends(get_settings),
) -> APIResponse[FormulaParams]:
    """Update the detection formula weights and / or thresholds.

    Only the fields provided in the request body are updated; existing
    values are preserved.  Changes take effect for new detection requests
    immediately.  The ``param_version`` is automatically incremented.
    """
    global _formula_params

    if body.weights:
        _formula_params.weights.update(body.weights)
    if body.thresholds:
        _formula_params.thresholds.update(body.thresholds)

    # Bump param version.
    parts = _formula_params.param_version.split(".")
    parts[-1] = str(int(parts[-1]) + 1)
    _formula_params.param_version = ".".join(parts)
    _formula_params.updated_at = datetime.utcnow()
    _formula_params.updated_by = user.user_id

    # TODO: Persist to database.

    request_id = str(uuid.uuid4())
    return APIResponse(
        data=_formula_params,
        meta=Meta(
            request_id=request_id,
            formula_version=settings.formula_version,
            param_version=_formula_params.param_version,
        ),
    )
