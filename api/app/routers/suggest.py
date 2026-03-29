"""
Writing suggestion routes for ScholarGuard.

Endpoints for obtaining AI-powered writing suggestions and applying rewrites.
"""

from __future__ import annotations

import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.middleware.auth import UserContext, get_current_active_user
from app.middleware.rate_limiter import rate_limit
from app.models.base import get_async_session
from app.models.detection import DetectionResult
from app.models.system import AuditLog
from app.schemas.common import APIResponse, Meta
from app.schemas.suggest import (
    RewriteRequest,
    RewriteResponse,
    SuggestRequest,
    SuggestResponse,
    SuggestionItem,
    SuggestionType,
)

router = APIRouter(prefix="/suggest", tags=["Suggestions"])


@router.post(
    "",
    response_model=APIResponse[SuggestResponse],
    dependencies=[Depends(rate_limit())],
    summary="Get writing suggestions for a text",
)
async def get_suggestions(
    body: SuggestRequest,
    user: UserContext = Depends(get_current_active_user),
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_async_session),
) -> APIResponse[SuggestResponse]:
    """Analyse the submitted text and return actionable writing suggestions.

    Each suggestion includes the original segment, a proposed replacement,
    an explanation of why the change improves the text, and a confidence
    score.  If a ``detection_id`` is supplied the analysis uses prior
    detection context to provide more targeted recommendations.
    """
    start = time.perf_counter()
    request_id = str(uuid.uuid4())
    user_uuid = uuid.UUID(user.user_id) if not isinstance(user.user_id, uuid.UUID) else user.user_id

    # If a detection_id is provided, verify it exists
    original_risk_score = None
    if body.detection_id:
        try:
            detection_uuid = uuid.UUID(body.detection_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid detection_id format: {body.detection_id}",
            )
        stmt = select(DetectionResult).where(DetectionResult.id == detection_uuid)
        row = await session.execute(stmt)
        detection = row.scalar_one_or_none()
        if detection is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Detection {body.detection_id} not found",
            )
        original_risk_score = float(detection.risk_score)

    # Audit log
    audit = AuditLog(
        user_id=user_uuid,
        action="request_suggestions",
        resource_type="suggestion",
        resource_id=request_id,
        details={
            "detection_id": body.detection_id,
            "text_length": len(body.text),
        },
    )
    session.add(audit)

    # TODO: Invoke the suggestion engine (LLM + heuristic pipeline).
    # Placeholder response with no suggestions.
    result = SuggestResponse(
        suggestions=[],
        original_risk_score=original_risk_score,
        estimated_risk_score=None,
    )

    elapsed = (time.perf_counter() - start) * 1000
    return APIResponse(
        data=result,
        meta=Meta(
            request_id=request_id,
            processing_time_ms=round(elapsed, 2),
            formula_version=settings.formula_version,
            param_version=settings.param_version,
        ),
    )


@router.post(
    "/rewrite",
    response_model=APIResponse[RewriteResponse],
    dependencies=[Depends(rate_limit())],
    summary="Apply accepted suggestions and rewrite text",
)
async def apply_rewrite(
    body: RewriteRequest,
    user: UserContext = Depends(get_current_active_user),
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_async_session),
) -> APIResponse[RewriteResponse]:
    """Apply previously accepted suggestions to rewrite the original text.

    The caller provides the original text together with the IDs of the
    suggestions they wish to apply.  The response contains the rewritten
    text and an updated risk score reflecting the changes.
    """
    start = time.perf_counter()
    request_id = str(uuid.uuid4())
    user_uuid = uuid.UUID(user.user_id) if not isinstance(user.user_id, uuid.UUID) else user.user_id

    # Audit log
    audit = AuditLog(
        user_id=user_uuid,
        action="apply_rewrite",
        resource_type="rewrite",
        resource_id=request_id,
        details={
            "detection_id": body.detection_id,
            "accepted_count": len(body.accepted_suggestion_ids),
        },
    )
    session.add(audit)

    # TODO: Apply accepted suggestions via the rewrite engine.
    result = RewriteResponse(
        rewritten_text=body.text,
        applied_count=0,
        new_risk_score=None,
    )

    elapsed = (time.perf_counter() - start) * 1000
    return APIResponse(
        data=result,
        meta=Meta(
            request_id=request_id,
            processing_time_ms=round(elapsed, 2),
            formula_version=settings.formula_version,
            param_version=settings.param_version,
        ),
    )
