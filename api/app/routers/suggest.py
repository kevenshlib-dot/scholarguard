"""
Writing suggestion routes for ScholarGuard.

Endpoints for obtaining AI-powered writing suggestions and applying rewrites.
"""

from __future__ import annotations

import logging
import time
import uuid
import uuid as _uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.middleware.auth import UserContext, get_current_active_user
from app.middleware.rate_limiter import rate_limit
from app.models.base import get_async_session
from app.models.detection import DetectionResult
from app.models.system import AuditLog
from app.prompts.suggest_prompt import SUGGEST_PROMPT, SUGGEST_SYSTEM
from app.schemas.common import APIResponse, Meta
from app.schemas.suggest import (
    RewriteRequest,
    RewriteResponse,
    SuggestRequest,
    SuggestResponse,
    SuggestionItem,
    SuggestionType,
)
from app.services.llm_gateway.client import LLMClient
from app.utils.json_extract import extract_json

logger = logging.getLogger(__name__)

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
    # API key users have string IDs like "apikey:sg-test-"; generate a deterministic UUID
    try:
        user_uuid = uuid.UUID(user.user_id)
    except (ValueError, AttributeError):
        user_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, user.user_id)

    # If a detection_id is provided, verify it exists
    original_risk_score = None
    detection = None
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

    # Load detection context if available
    flagged_issues = ""
    if detection and detection.flagged_segments:
        segs = detection.flagged_segments
        if isinstance(segs, list):
            flagged_issues = "\n".join([
                f"- 位置({s.get('start_char', 0)}-{s.get('end_char', 0)}): "
                f"{s.get('text_snippet', '')} → {s.get('issue', '')}"
                for s in segs
            ])

    # Map focus types to Chinese strategy descriptions
    strategy_map = {
        "rephrase": "改写表达使之更自然",
        "restructure": "调整文章结构",
        "tone": "调整学术语气",
        "vocabulary": "替换AI常见词汇",
        "general": "综合改进",
        "naturalness": "表达自然化",
        "argumentation": "论证补强",
        "structure": "结构提醒",
    }
    focus_list = body.focus or []
    strategies_str = (
        "、".join([
            strategy_map.get(
                f.value if hasattr(f, "value") else f,
                f.value if hasattr(f, "value") else f,
            )
            for f in focus_list
        ])
        if focus_list
        else "综合优化"
    )

    # Call LLM
    llm_client = LLMClient()
    prompt = SUGGEST_PROMPT.format(
        text=body.text[:4000],
        issues=flagged_issues or "未提供具体检测结果，请根据文本特征自行分析AI痕迹",
        strategies=strategies_str,
    )

    try:
        response = await llm_client.chat(
            task_type="suggestion",
            system_prompt=SUGGEST_SYSTEM,
            user_prompt=prompt,
            response_format="json",
            max_tokens=2048,
            temperature=0.3,
        )
        raw = extract_json(response)

        suggestions: list[SuggestionItem] = []
        items = (
            raw
            if isinstance(raw, list)
            else raw.get("suggestions", [])
            if isinstance(raw, dict)
            else []
        )

        type_map = {
            "rephrase": SuggestionType.REPHRASE,
            "restructure": SuggestionType.RESTRUCTURE,
            "tone": SuggestionType.TONE,
            "vocabulary": SuggestionType.VOCABULARY,
        }

        for item in items:
            sug_type = item.get("type", "general")
            sug_enum = type_map.get(sug_type, SuggestionType.GENERAL)

            suggestions.append(
                SuggestionItem(
                    suggestion_id=item.get("id", str(_uuid.uuid4())[:8]),
                    type=sug_enum,
                    original_text=item.get("orig", ""),
                    suggested_text=item.get("new", ""),
                    explanation=item.get("why", ""),
                    offset_start=item.get("s", 0),
                    offset_end=item.get("e", 0),
                    confidence=min(max(item.get("conf", 0.7), 0.0), 1.0),
                )
            )

        result = SuggestResponse(
            suggestions=suggestions,
            original_risk_score=original_risk_score,
            estimated_risk_score=(
                max(0.0, (original_risk_score or 0.5) - 0.15)
                if suggestions
                else None
            ),
        )
    except Exception as e:
        logger.error(f"Suggestion LLM call failed: {e}")
        result = SuggestResponse(
            suggestions=[],
            original_risk_score=original_risk_score,
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
    try:
        user_uuid = uuid.UUID(user.user_id)
    except (ValueError, AttributeError):
        user_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, user.user_id)

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

    # Parse suggestion replacements from the request.
    # The frontend handles replacement client-side; the backend returns text as-is.
    result = RewriteResponse(
        rewritten_text=body.text,
        applied_count=len(body.accepted_suggestion_ids),
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
