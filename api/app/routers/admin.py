"""
Admin routes for ScholarGuard.

Endpoints for model management, usage statistics, audit logs, and
formula parameter configuration.  All endpoints require admin role.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func, update, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.middleware.auth import UserContext, require_role
from app.middleware.rate_limiter import rate_limit
from app.models.base import get_async_session
from app.models.detection import DetectionResult
from app.models.review import ReviewRecord, AppealRecord, Feedback
from app.models.system import (
    AuditLog,
    FormulaParam,
    ModelConfig,
    UsageStat,
)
from app.models.user import Organization, User
from app.schemas.common import APIResponse, Meta, PaginatedMeta, PaginationParams

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


class TaskRouteItem(BaseModel):
    """Per-task model routing configuration."""
    primary: str = Field(..., description="Primary model identifier")
    fallback: Optional[str] = Field(None, description="Fallback model")
    degradation: Optional[str] = Field(None, description="Degradation model")


class FullModelConfig(BaseModel):
    """Complete model configuration: routes + service URLs + API keys."""
    routes: dict[str, TaskRouteItem] = Field(
        ..., description="Per-task model routing"
    )
    service_urls: dict[str, str] = Field(
        default_factory=dict, description="Service URLs (vllm_url, ollama_url)"
    )
    api_keys: dict[str, str] = Field(
        default_factory=dict, description="Provider API keys (openai, anthropic, google)"
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


class UserInfo(BaseModel):
    """User information for admin user management."""

    id: str
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
    organization_name: Optional[str] = None


class UserRoleUpdate(BaseModel):
    """Request body for updating a user's role."""

    role: str = Field(..., description="New role for the user")


class UserStatusUpdate(BaseModel):
    """Request body for toggling user active status."""

    is_active: bool = Field(..., description="Whether the user is active")


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
    session: AsyncSession = Depends(get_async_session),
) -> APIResponse[list[ModelInfo]]:
    """Return a list of all registered detection / suggestion models.

    Includes model metadata, provider, version, active status, and
    supported capabilities.
    """
    request_id = str(uuid.uuid4())

    stmt = select(ModelConfig).where(ModelConfig.is_active == True)
    result = await session.execute(stmt)
    configs = result.scalars().all()

    models = [
        ModelInfo(
            model_id=str(cfg.id),
            name=cfg.primary_model,
            provider=cfg.task_type,
            version="1.0",
            is_active=cfg.is_active,
            capabilities=[cfg.task_type],
        )
        for cfg in configs
    ]

    # If no models in DB, return a sensible default
    if not models:
        models = [
            ModelInfo(
                model_id="ollama-llama3",
                name="Llama 3 (Ollama)",
                provider="ollama",
                version="3.0",
                capabilities=["detection", "suggestion"],
            ),
        ]

    return APIResponse(
        data=models,
        meta=Meta(request_id=request_id),
    )


@router.get(
    "/models/config",
    response_model=APIResponse[dict],
    dependencies=[Depends(rate_limit())],
    summary="Get full model configuration",
)
async def get_model_config(
    user: UserContext = Depends(require_role("admin")),
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_async_session),
) -> APIResponse[dict]:
    """Return the complete model configuration: routes, service URLs, API keys."""
    from app.services.llm_gateway.client import DEFAULT_MODEL_ROUTES

    request_id = str(uuid.uuid4())

    # DB overrides
    stmt = select(ModelConfig).where(ModelConfig.is_active == True)
    result = await session.execute(stmt)
    db_configs = {cfg.task_type: cfg for cfg in result.scalars().all()}

    routes = {}
    for task_type, default_route in DEFAULT_MODEL_ROUTES.items():
        if task_type in db_configs:
            cfg = db_configs[task_type]
            routes[task_type] = {
                "primary": cfg.primary_model,
                "fallback": cfg.fallback_model or default_route.get("fallback"),
                "degradation": cfg.degradation_strategy or default_route.get("degradation"),
                "source": "database",
            }
        else:
            routes[task_type] = {
                **default_route,
                "source": "default",
            }

    # Mask API keys for display (show last 4 chars)
    def mask_key(key: str | None) -> str:
        if not key:
            return ""
        if len(key) <= 8:
            return "****"
        return "*" * (len(key) - 4) + key[-4:]

    return APIResponse(
        data={
            "routes": routes,
            "service_urls": {
                "vllm_url": settings.vllm_url or "",
                "ollama_url": settings.ollama_url,
            },
            "api_keys": {
                "openai": mask_key(settings.openai_api_key),
                "anthropic": mask_key(settings.anthropic_api_key),
                "google": mask_key(settings.google_api_key),
            },
            "api_keys_set": {
                "openai": bool(settings.openai_api_key),
                "anthropic": bool(settings.anthropic_api_key),
                "google": bool(settings.google_api_key),
            },
        },
        meta=Meta(request_id=request_id),
    )


@router.put(
    "/models/config",
    response_model=APIResponse[dict],
    dependencies=[Depends(rate_limit())],
    summary="Update full model configuration",
)
async def update_model_config(
    body: FullModelConfig,
    user: UserContext = Depends(require_role("admin")),
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_async_session),
) -> APIResponse[dict]:
    """Update model routing for all task types, plus service URLs and API keys."""
    user_uuid = uuid.UUID(user.user_id) if not isinstance(user.user_id, uuid.UUID) else user.user_id

    changed_tasks = []
    for task_type, route in body.routes.items():
        stmt = select(ModelConfig).where(ModelConfig.task_type == task_type)
        result = await session.execute(stmt)
        cfg = result.scalar_one_or_none()

        if cfg:
            cfg.primary_model = route.primary
            cfg.fallback_model = route.fallback
            cfg.degradation_strategy = route.degradation
            cfg.is_active = True
            cfg.updated_at = datetime.now(timezone.utc)
        else:
            cfg = ModelConfig(
                task_type=task_type,
                primary_model=route.primary,
                fallback_model=route.fallback,
                degradation_strategy=route.degradation,
            )
            session.add(cfg)
        changed_tasks.append(task_type)

    # Update service URLs in settings (runtime + Redis for cross-process)
    if body.service_urls.get("vllm_url"):
        settings.vllm_url = body.service_urls["vllm_url"]
    if body.service_urls.get("ollama_url"):
        settings.ollama_url = body.service_urls["ollama_url"]

    # Update API keys (runtime + Redis for Celery workers)
    import redis as sync_redis
    try:
        _redis = sync_redis.Redis.from_url(settings.redis_url, decode_responses=True)
    except Exception:
        _redis = None

    for provider, key_value in body.api_keys.items():
        if not key_value or "****" in key_value:
            continue  # Skip masked or empty values
        if provider == "openai":
            settings.openai_api_key = key_value
        elif provider == "anthropic":
            settings.anthropic_api_key = key_value
        elif provider == "google":
            settings.google_api_key = key_value
        # 持久化到 Redis，让 Celery Worker 也能读到
        if _redis:
            try:
                _redis.set(f"sg:api_key:{provider}", key_value)
            except Exception:
                pass

    # 同步 service URLs 到 Redis
    if _redis:
        try:
            for url_key in ("vllm_url", "ollama_url"):
                val = body.service_urls.get(url_key)
                if val:
                    _redis.set(f"sg:service_url:{url_key}", val)
        except Exception:
            pass

    # Audit log
    audit = AuditLog(
        user_id=user_uuid,
        action="update_model_config",
        resource_type="model_config",
        resource_id="full",
        details={
            "changed_tasks": changed_tasks,
            "service_urls_updated": list(body.service_urls.keys()),
            "api_keys_updated": [k for k, v in body.api_keys.items() if v and "****" not in v],
        },
    )
    session.add(audit)

    request_id = str(uuid.uuid4())
    return APIResponse(
        data={"success": True, "updated_tasks": changed_tasks},
        meta=Meta(request_id=request_id),
    )


class ModelTestRequest(BaseModel):
    """Request to test a model connection."""
    model: str = Field(..., description="Model identifier to test")
    api_key: Optional[str] = Field(None, description="API key (for remote models)")
    service_url: Optional[str] = Field(None, description="Custom service URL (for vLLM/Ollama)")


@router.post(
    "/models/test",
    response_model=APIResponse[dict],
    dependencies=[Depends(rate_limit())],
    summary="Test model connectivity",
)
async def test_model_connection(
    body: ModelTestRequest,
    user: UserContext = Depends(require_role("admin")),
    settings: Settings = Depends(get_settings),
) -> APIResponse[dict]:
    """Send a minimal request to the model to verify connectivity."""
    import asyncio
    request_id = str(uuid.uuid4())
    model = body.model.strip()
    if not model:
        return APIResponse(
            data={"success": False, "error": "模型标识不能为空", "latency_ms": 0},
            meta=Meta(request_id=request_id),
        )

    try:
        import litellm
        start = time.time()

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": "Hello, respond with OK."}],
            "max_tokens": 16,
            "temperature": 0,
            "timeout": 15,
        }

        # Determine service URL
        if model.startswith("openai/"):
            url = body.service_url or settings.vllm_url or "http://192.168.31.18:8001/v1"
            kwargs["api_base"] = url
            kwargs["api_key"] = "not-needed"
            kwargs["extra_body"] = {"chat_template_kwargs": {"enable_thinking": False}}
        elif model.startswith("ollama/"):
            url = body.service_url or settings.ollama_url
            kwargs["api_base"] = url

        # API key handling for remote models
        if body.api_key and "****" not in body.api_key:
            api_key = body.api_key
        else:
            # Use stored keys
            api_key = None
            if model.startswith("gpt-") or (model.startswith("openai/") and not body.service_url):
                api_key = settings.openai_api_key
            elif model.startswith("claude-"):
                api_key = settings.anthropic_api_key
            elif model.startswith("gemini/"):
                api_key = settings.google_api_key

        if api_key:
            if model.startswith("gpt-"):
                kwargs["api_key"] = api_key
            elif model.startswith("claude-"):
                kwargs["api_key"] = api_key
            elif model.startswith("gemini/"):
                kwargs["api_key"] = api_key

        response = await asyncio.wait_for(
            litellm.acompletion(**kwargs),
            timeout=20,
        )

        latency_ms = int((time.time() - start) * 1000)
        content = response.choices[0].message.content or ""

        return APIResponse(
            data={
                "success": True,
                "latency_ms": latency_ms,
                "response_preview": content[:100],
                "model": model,
            },
            meta=Meta(request_id=request_id),
        )

    except asyncio.TimeoutError:
        return APIResponse(
            data={"success": False, "error": "连接超时（20秒）", "latency_ms": 20000, "model": model},
            meta=Meta(request_id=request_id),
        )
    except Exception as e:
        error_msg = str(e)
        # Simplify common errors
        if "Connection refused" in error_msg or "ConnectError" in error_msg:
            error_msg = "无法连接到服务，请检查服务地址是否正确"
        elif "RateLimitError" in error_msg or "429" in error_msg or "quota" in error_msg.lower():
            error_msg = "API 配额超限，请检查账户计费额度或稍后重试"
        elif "AuthenticationError" in error_msg or "401" in error_msg:
            if not api_key:
                error_msg = "未提供 API Key，请先在上方「远程模型 API」中填写对应的 Key"
            else:
                error_msg = "API Key 无效或已过期"
        elif "invalid_api_key" in error_msg:
            error_msg = "API Key 格式错误"
        elif "404" in error_msg:
            error_msg = f"模型 {model} 不存在或未加载"
        elif len(error_msg) > 200:
            error_msg = error_msg[:200] + "..."

        return APIResponse(
            data={"success": False, "error": error_msg, "latency_ms": 0, "model": model},
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
    session: AsyncSession = Depends(get_async_session),
) -> APIResponse[UsageStats]:
    """Return aggregated platform usage statistics.

    Includes total counts for detections, suggestions, reviews, and
    appeals, as well as today's detection count and average processing
    time.
    """
    request_id = str(uuid.uuid4())

    # Total detections
    total_det_result = await session.execute(select(func.count(DetectionResult.id)))
    total_detections = total_det_result.scalar() or 0

    # Total reviews
    total_rev_result = await session.execute(select(func.count(ReviewRecord.id)))
    total_reviews = total_rev_result.scalar() or 0

    # Total appeals
    total_app_result = await session.execute(select(func.count(AppealRecord.id)))
    total_appeals = total_app_result.scalar() or 0

    # Total suggestions (count audit log entries with action containing 'suggest')
    total_sug_result = await session.execute(
        select(func.count(AuditLog.id)).where(AuditLog.action.ilike("%suggest%"))
    )
    total_suggestions = total_sug_result.scalar() or 0

    # Detections today
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    det_today_result = await session.execute(
        select(func.count(DetectionResult.id)).where(
            DetectionResult.created_at >= today_start
        )
    )
    detections_today = det_today_result.scalar() or 0

    # Average processing time
    avg_result = await session.execute(
        select(func.avg(DetectionResult.processing_time_ms)).where(
            DetectionResult.processing_time_ms.isnot(None)
        )
    )
    avg_processing = avg_result.scalar()
    average_processing_ms = float(avg_processing) if avg_processing else 0.0

    stats = UsageStats(
        total_detections=total_detections,
        total_suggestions=total_suggestions,
        total_reviews=total_reviews,
        total_appeals=total_appeals,
        detections_today=detections_today,
        average_processing_ms=round(average_processing_ms, 2),
    )

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
    session: AsyncSession = Depends(get_async_session),
) -> APIResponse[list[AuditLogEntry]]:
    """Return paginated audit log entries.

    Audit logs record every significant action (detection, review, appeal,
    configuration change) performed on the platform.
    """
    request_id = str(uuid.uuid4())

    # Get total count
    count_result = await session.execute(select(func.count(AuditLog.id)))
    total = count_result.scalar() or 0

    # Paginated query
    offset = (page - 1) * page_size
    stmt = (
        select(AuditLog)
        .order_by(desc(AuditLog.created_at))
        .offset(offset)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    audit_logs = result.scalars().all()

    entries = [
        AuditLogEntry(
            log_id=str(log.id),
            timestamp=log.created_at,
            user_id=str(log.user_id) if log.user_id else "system",
            action=log.action,
            resource=f"{log.resource_type}:{log.resource_id}" if log.resource_id else log.resource_type,
            details=log.details,
        )
        for log in audit_logs
    ]

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    return APIResponse(
        data=entries,
        meta=PaginatedMeta(
            request_id=request_id,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        ),
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
    session: AsyncSession = Depends(get_async_session),
) -> APIResponse[FormulaParams]:
    """Return the current detection formula weights and thresholds.

    These parameters control how the individual signal scores (LLM
    confidence, statistical features, stylistic features) are combined
    into the final risk score and classification.
    """
    request_id = str(uuid.uuid4())

    # Query for the active formula params
    stmt = select(FormulaParam).where(FormulaParam.is_active == True)
    result = await session.execute(stmt)
    active_param = result.scalar_one_or_none()

    if active_param:
        params_data = active_param.params or {}
        formula = FormulaParams(
            formula_version=settings.formula_version,
            param_version=active_param.version,
            weights=params_data.get("weights", {}),
            thresholds=params_data.get("thresholds", {}),
            updated_at=active_param.created_at,
        )
    else:
        # Fallback to defaults if nothing in DB
        formula = FormulaParams(
            formula_version=settings.formula_version,
            param_version=settings.param_version,
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

    return APIResponse(
        data=formula,
        meta=Meta(
            request_id=request_id,
            formula_version=settings.formula_version,
            param_version=formula.param_version,
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
    session: AsyncSession = Depends(get_async_session),
) -> APIResponse[FormulaParams]:
    """Update the detection formula weights and / or thresholds.

    Only the fields provided in the request body are updated; existing
    values are preserved.  Changes take effect for new detection requests
    immediately.  The ``param_version`` is automatically incremented.
    """
    user_uuid = uuid.UUID(user.user_id) if not isinstance(user.user_id, uuid.UUID) else user.user_id

    # Get current active params
    stmt = select(FormulaParam).where(FormulaParam.is_active == True)
    result = await session.execute(stmt)
    current_param = result.scalar_one_or_none()

    if current_param:
        current_data = current_param.params or {}
        current_weights = current_data.get("weights", {})
        current_thresholds = current_data.get("thresholds", {})
        current_version = current_param.version
    else:
        current_weights = {
            "llm_confidence": 0.4,
            "statistical_score": 0.35,
            "stylistic_score": 0.25,
        }
        current_thresholds = {
            "low_max": 0.3,
            "medium_max": 0.6,
            "high_max": 0.85,
        }
        current_version = settings.param_version

    # Merge updates
    if body.weights:
        current_weights.update(body.weights)
    if body.thresholds:
        current_thresholds.update(body.thresholds)

    # Bump version
    parts = current_version.split(".")
    parts[-1] = str(int(parts[-1]) + 1)
    new_version = ".".join(parts)

    # Deactivate old active params
    if current_param:
        current_param.is_active = False

    # Create new version
    new_param = FormulaParam(
        version=new_version,
        params={
            "weights": current_weights,
            "thresholds": current_thresholds,
        },
        description=f"Updated by {user.user_id}",
        is_active=True,
    )
    session.add(new_param)
    await session.flush()

    # Audit log
    audit = AuditLog(
        user_id=user_uuid,
        action="update_formula_params",
        resource_type="formula_param",
        resource_id=str(new_param.id),
        details={
            "old_version": current_version,
            "new_version": new_version,
            "weights_updated": body.weights is not None,
            "thresholds_updated": body.thresholds is not None,
        },
    )
    session.add(audit)

    formula = FormulaParams(
        formula_version=settings.formula_version,
        param_version=new_version,
        weights=current_weights,
        thresholds=current_thresholds,
        updated_at=datetime.now(timezone.utc),
        updated_by=user.user_id,
    )

    request_id = str(uuid.uuid4())
    return APIResponse(
        data=formula,
        meta=Meta(
            request_id=request_id,
            formula_version=settings.formula_version,
            param_version=new_version,
        ),
    )


# ── User Management Routes ─────────────────────────────────────────────


@router.get(
    "/admin/users",
    response_model=APIResponse[list[UserInfo]],
    dependencies=[Depends(rate_limit())],
    summary="List all users (admin only)",
)
async def list_users(
    user: UserContext = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_async_session),
) -> APIResponse[list[UserInfo]]:
    """Return a list of all registered users with their details."""
    request_id = str(uuid.uuid4())

    stmt = select(User).order_by(desc(User.created_at))
    result = await session.execute(stmt)
    users = result.scalars().all()

    user_list = [
        UserInfo(
            id=str(u.id),
            username=u.username,
            email=u.email,
            role=u.role if isinstance(u.role, str) else u.role.value,
            is_active=u.is_active,
            created_at=u.created_at,
            organization_name=u.organization.name if u.organization else None,
        )
        for u in users
    ]

    return APIResponse(
        data=user_list,
        meta=Meta(request_id=request_id),
    )


@router.put(
    "/admin/users/{user_id}/role",
    response_model=APIResponse[UserInfo],
    dependencies=[Depends(rate_limit())],
    summary="Update a user's role (admin only)",
)
async def update_user_role(
    user_id: str,
    body: UserRoleUpdate,
    user: UserContext = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_async_session),
) -> APIResponse[UserInfo]:
    """Change the role of a specific user."""
    request_id = str(uuid.uuid4())

    target_uuid = uuid.UUID(user_id)
    stmt = select(User).where(User.id == target_uuid)
    result = await session.execute(stmt)
    target_user = result.scalar_one_or_none()

    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Validate the role value
    valid_roles = {"admin", "super_admin", "org_admin", "detector", "reviewer", "auditor", "api_caller"}
    if body.role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid role '{body.role}'. Must be one of: {sorted(valid_roles)}",
        )

    target_user.role = body.role
    await session.flush()

    # Audit log
    admin_uuid = uuid.UUID(user.user_id) if not isinstance(user.user_id, uuid.UUID) else user.user_id
    audit = AuditLog(
        user_id=admin_uuid,
        action="update_user_role",
        resource_type="user",
        resource_id=str(target_user.id),
        details={"new_role": body.role},
    )
    session.add(audit)

    return APIResponse(
        data=UserInfo(
            id=str(target_user.id),
            username=target_user.username,
            email=target_user.email,
            role=target_user.role if isinstance(target_user.role, str) else target_user.role.value,
            is_active=target_user.is_active,
            created_at=target_user.created_at,
            organization_name=target_user.organization.name if target_user.organization else None,
        ),
        meta=Meta(request_id=request_id),
    )


@router.put(
    "/admin/users/{user_id}/status",
    response_model=APIResponse[UserInfo],
    dependencies=[Depends(rate_limit())],
    summary="Toggle user active status (admin only)",
)
async def update_user_status(
    user_id: str,
    user: UserContext = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_async_session),
) -> APIResponse[UserInfo]:
    """Toggle the active/inactive status of a specific user."""
    request_id = str(uuid.uuid4())

    target_uuid = uuid.UUID(user_id)
    stmt = select(User).where(User.id == target_uuid)
    result = await session.execute(stmt)
    target_user = result.scalar_one_or_none()

    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    target_user.is_active = not target_user.is_active
    await session.flush()

    # Audit log
    admin_uuid = uuid.UUID(user.user_id) if not isinstance(user.user_id, uuid.UUID) else user.user_id
    audit = AuditLog(
        user_id=admin_uuid,
        action="toggle_user_status",
        resource_type="user",
        resource_id=str(target_user.id),
        details={"is_active": target_user.is_active},
    )
    session.add(audit)

    return APIResponse(
        data=UserInfo(
            id=str(target_user.id),
            username=target_user.username,
            email=target_user.email,
            role=target_user.role if isinstance(target_user.role, str) else target_user.role.value,
            is_active=target_user.is_active,
            created_at=target_user.created_at,
            organization_name=target_user.organization.name if target_user.organization else None,
        ),
        meta=Meta(request_id=request_id),
    )
