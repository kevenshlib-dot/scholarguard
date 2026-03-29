"""
Detection routes for ScholarGuard.

Endpoints for submitting text for AI-content detection and retrieving results.
"""

from __future__ import annotations

import time
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status

from app.config import Settings, get_settings
from app.middleware.auth import UserContext, get_current_active_user
from app.middleware.rate_limiter import rate_limit
from app.schemas.common import APIResponse, Meta
from app.schemas.detect import (
    BatchDetectRequest,
    BatchDetectResponse,
    DetectRequest,
    DetectResponse,
    DetectResult,
    RiskLevel,
    TaskStatus,
)

router = APIRouter(prefix="/detect", tags=["Detection"])

# ── In-memory task store (replace with Redis/DB in production) ──────────
_tasks: dict[str, DetectResponse] = {}
_batches: dict[str, BatchDetectResponse] = {}


@router.post(
    "",
    response_model=APIResponse[DetectResponse],
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(rate_limit())],
    summary="Submit text for AI-content detection",
)
async def submit_detection(
    body: DetectRequest,
    user: UserContext = Depends(get_current_active_user),
    settings: Settings = Depends(get_settings),
) -> APIResponse[DetectResponse]:
    """Submit a piece of text for asynchronous AI-content detection.

    Returns a ``task_id`` that can be polled via ``GET /detect/{task_id}``.
    The detection pipeline runs asynchronously; the result is available once
    the task transitions to ``completed`` status.
    """
    start = time.perf_counter()
    task_id = str(uuid.uuid4())

    # Create a pending task entry.
    task = DetectResponse(task_id=task_id, status=TaskStatus.PENDING)
    _tasks[task_id] = task

    # TODO: Dispatch to Celery / background worker here.
    # For now, produce a placeholder completed result synchronously.
    result = DetectResult(
        detection_id=str(uuid.uuid4()),
        risk_score=0.0,
        risk_level=RiskLevel.LOW,
        llm_confidence=0.0,
        statistical_score=0.0,
        stylistic_score=0.0,
        formula_version=settings.formula_version,
        param_version=settings.param_version,
        language=body.language or "en",
    )
    task.status = TaskStatus.COMPLETED
    task.result = result
    _tasks[task_id] = task

    elapsed = (time.perf_counter() - start) * 1000
    return APIResponse(
        code=202,
        message="Detection task accepted",
        data=task,
        meta=Meta(
            request_id=task_id,
            processing_time_ms=round(elapsed, 2),
            formula_version=settings.formula_version,
            param_version=settings.param_version,
        ),
    )


@router.get(
    "/{task_id}",
    response_model=APIResponse[DetectResponse],
    summary="Query detection result by task ID",
)
async def get_detection_result(
    task_id: str,
    user: UserContext = Depends(get_current_active_user),
) -> APIResponse[DetectResponse]:
    """Retrieve the status and result of a previously submitted detection task.

    Returns the current task status. When the status is ``completed``, the
    ``result`` field contains the full detection output.
    """
    task = _tasks.get(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )
    return APIResponse(
        data=task,
        meta=Meta(request_id=task_id),
    )


@router.post(
    "/batch",
    response_model=APIResponse[BatchDetectResponse],
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(rate_limit(max_tokens=5, refill_rate=0.1, key_prefix="rl:batch"))],
    summary="Submit a batch of texts for detection",
)
async def submit_batch_detection(
    body: BatchDetectRequest,
    user: UserContext = Depends(get_current_active_user),
    settings: Settings = Depends(get_settings),
) -> APIResponse[BatchDetectResponse]:
    """Submit multiple texts for AI-content detection in a single request.

    Returns a ``batch_id`` that can be polled via ``GET /detect/batch/{batch_id}``.
    An optional ``callback_url`` can be provided to receive a webhook when all
    items are processed.
    """
    start = time.perf_counter()
    batch_id = str(uuid.uuid4())

    batch = BatchDetectResponse(
        batch_id=batch_id,
        total=len(body.items),
        status=TaskStatus.PENDING,
    )
    _batches[batch_id] = batch

    # TODO: Dispatch each item to the detection pipeline.

    elapsed = (time.perf_counter() - start) * 1000
    return APIResponse(
        code=202,
        message="Batch detection accepted",
        data=batch,
        meta=Meta(
            request_id=batch_id,
            processing_time_ms=round(elapsed, 2),
            formula_version=settings.formula_version,
            param_version=settings.param_version,
        ),
    )


@router.get(
    "/batch/{batch_id}",
    response_model=APIResponse[BatchDetectResponse],
    summary="Query batch detection status",
)
async def get_batch_status(
    batch_id: str,
    user: UserContext = Depends(get_current_active_user),
) -> APIResponse[BatchDetectResponse]:
    """Retrieve the status and results of a batch detection request.

    The ``completed`` count indicates how many items have finished processing.
    When all items are done the overall status becomes ``completed`` and
    ``results`` contains the full list of detection outputs.
    """
    batch = _batches.get(batch_id)
    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch {batch_id} not found",
        )
    return APIResponse(
        data=batch,
        meta=Meta(request_id=batch_id),
    )
