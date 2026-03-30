"""
Detection routes for ScholarGuard.

Endpoints for submitting text for AI-content detection and retrieving results.
Detection work is dispatched to Celery workers; the API returns immediately
with a task_id that clients can poll.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.middleware.auth import UserContext, get_current_active_user
from app.middleware.rate_limiter import rate_limit
from app.models.base import get_async_session
from app.models.document import Document
from app.models.detection import DetectionResult
from app.models.system import AuditLog
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
    session: AsyncSession = Depends(get_async_session),
) -> APIResponse[DetectResponse]:
    """Submit a piece of text for asynchronous AI-content detection.

    Returns a ``task_id`` that can be polled via ``GET /detect/{task_id}``.
    The detection pipeline runs asynchronously in a Celery worker; the result
    is available once the task transitions to ``completed`` status.
    """
    from app.tasks.detection_task import run_detection

    start = time.perf_counter()
    # API key users have string IDs like "apikey:sg-test-"; generate a deterministic UUID
    try:
        user_uuid = uuid.UUID(user.user_id)
    except (ValueError, AttributeError):
        user_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, user.user_id)

    # ── Create document record ────────────────────────────────────────
    content_hash = hashlib.sha256(body.text.encode("utf-8")).hexdigest()
    word_count = len(body.text.split())

    document = Document(
        user_id=user_uuid,
        title=f"Detection submission ({word_count} words)",
        content_hash=content_hash,
        word_count=word_count,
        language=body.language or "en",
        discipline=body.discipline,
    )
    session.add(document)
    await session.flush()  # get document.id populated

    # ── Create detection result (status=pending) ─────────────────────
    detection = DetectionResult(
        document_id=document.id,
        granularity=body.granularity.value,
        status="pending",
        risk_score=0.0,
        risk_level=RiskLevel.LOW.value,
        llm_confidence=0.0,
        stat_score=0.0,
        evidence_completeness=0,
        review_priority=0.0,
        conclusion_type="preliminary",
        formula_version=settings.formula_version,
        param_version=settings.param_version,
    )
    session.add(detection)
    await session.flush()  # get detection.id populated

    # ── Write audit log ───────────────────────────────────────────────
    audit = AuditLog(
        user_id=user_uuid,
        action="submit_detection",
        resource_type="detection",
        resource_id=str(detection.id),
        details={
            "word_count": word_count,
            "language": body.language or "en",
            "granularity": body.granularity.value,
        },
    )
    session.add(audit)

    # Commit so the Celery worker can see the records
    await session.commit()

    # ── Dispatch Celery task ──────────────────────────────────────────
    run_detection.delay(
        detection_result_id=str(detection.id),
        text=body.text,
        granularity=body.granularity.value,
        language=body.language or "auto",
        discipline=body.discipline or "通用",
        model_override=None,
    )

    # ── Build response ────────────────────────────────────────────────
    task = DetectResponse(
        task_id=str(detection.id),
        status=TaskStatus.PENDING,
        result=None,
    )

    elapsed = (time.perf_counter() - start) * 1000
    return APIResponse(
        code=202,
        message="Detection task accepted",
        data=task,
        meta=Meta(
            request_id=str(detection.id),
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
    session: AsyncSession = Depends(get_async_session),
) -> APIResponse[BatchDetectResponse]:
    """Retrieve the status and results of a batch detection request.

    The ``completed`` count indicates how many items have finished processing.
    When all items are done the overall status becomes ``completed`` and
    ``results`` contains the full list of detection outputs.
    """
    # Fetch all detection results belonging to this batch
    stmt = select(DetectionResult).where(DetectionResult.batch_id == batch_id)
    rows = await session.execute(stmt)
    detections = rows.scalars().all()

    if not detections:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch {batch_id} not found",
        )

    results: list[DetectResult] = []
    completed_count = 0
    has_failed = False

    for det in detections:
        if det.status == "completed":
            completed_count += 1
        elif det.status == "failed":
            has_failed = True

        results.append(
            DetectResult(
                detection_id=str(det.id),
                risk_score=float(det.risk_score),
                risk_level=RiskLevel(det.risk_level),
                llm_confidence=float(det.llm_confidence),
                statistical_score=float(det.stat_score),
                stylistic_score=0.0,
                formula_version=det.formula_version or "",
                param_version=det.param_version or "",
                language=det.document.language if det.document else "en",
                created_at=det.created_at,
            )
        )

    # Determine overall batch status
    total = len(detections)
    if completed_count == total:
        overall_status = TaskStatus.COMPLETED
    elif has_failed and completed_count + sum(1 for d in detections if d.status == "failed") == total:
        overall_status = TaskStatus.FAILED
    else:
        overall_status = TaskStatus.PROCESSING

    batch_resp = BatchDetectResponse(
        batch_id=batch_id,
        total=total,
        status=overall_status,
        completed=completed_count,
        results=results,
    )

    return APIResponse(
        data=batch_resp,
        meta=Meta(request_id=batch_id),
    )


@router.get(
    "/{task_id}",
    response_model=APIResponse[DetectResponse],
    summary="Query detection result by task ID",
)
async def get_detection_result(
    task_id: str,
    user: UserContext = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> APIResponse[DetectResponse]:
    """Retrieve the status and result of a previously submitted detection task.

    Returns the current task status. When the status is ``completed``, the
    ``result`` field contains the full detection output.
    """
    try:
        detection_uuid = uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid task_id format: {task_id}",
        )

    stmt = select(DetectionResult).where(DetectionResult.id == detection_uuid)
    row = await session.execute(stmt)
    detection = row.scalar_one_or_none()

    if detection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )

    # Map DB status to schema enum
    try:
        task_status = TaskStatus(detection.status)
    except ValueError:
        task_status = TaskStatus.PENDING

    # Only include result when completed
    result = None
    if task_status == TaskStatus.COMPLETED:
        from app.schemas.detect import FlaggedSegment

        # Extract flagged_segments from DB JSON
        raw_segs = detection.flagged_segments or []
        if isinstance(raw_segs, dict):
            raw_segs = raw_segs.get("segments", raw_segs.get("flagged_segments", []))
        flagged = [
            FlaggedSegment(
                start_char=s.get("start_char", 0),
                end_char=s.get("end_char", 0),
                text_snippet=s.get("text_snippet", ""),
                issue=s.get("issue", ""),
            )
            for s in (raw_segs if isinstance(raw_segs, list) else [])
        ]

        # Extract report fields
        report = detection.report_content or {}
        evidence_summary = report.get("risk_summary", "")
        recs_raw = detection.recommendations or report.get("recommended_actions", [])
        recommendations = recs_raw if isinstance(recs_raw, list) else []

        result = DetectResult(
            detection_id=str(detection.id),
            risk_score=float(detection.risk_score),
            risk_level=RiskLevel(detection.risk_level),
            llm_confidence=float(detection.llm_confidence),
            statistical_score=float(detection.stat_score),
            stylistic_score=0.0,
            formula_version=detection.formula_version or "",
            param_version=detection.param_version or "",
            model_version=detection.model_version or None,
            language=detection.document.language if detection.document else "en",
            flagged_segments=flagged if flagged else None,
            evidence_summary=evidence_summary or None,
            recommendations=recommendations if recommendations else None,
            uncertainty_notes=detection.uncertainty_notes or None,
            created_at=detection.created_at,
        )

    task = DetectResponse(
        task_id=str(detection.id),
        status=task_status,
        result=result,
    )

    return APIResponse(
        data=task,
        meta=Meta(request_id=task_id),
    )


@router.post(
    "/{task_id}/heatmap",
    response_model=APIResponse,
    summary="Generate paragraph-level heatmap for a completed detection",
)
async def generate_heatmap(
    task_id: str,
    user: UserContext = Depends(get_current_active_user),
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_async_session),
) -> APIResponse:
    """Trigger paragraph-level heatmap generation for a completed detection.

    The heatmap is generated asynchronously. The ``heatmap_status`` field on
    the detection result transitions from ``pending`` to ``completed`` once
    the heatmap data is available. Poll ``GET /detect/{task_id}`` to check.
    """
    from app.tasks.detection_task import run_heatmap

    try:
        detection_uuid = uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid task_id format: {task_id}",
        )

    stmt = select(DetectionResult).where(DetectionResult.id == detection_uuid)
    row = await session.execute(stmt)
    detection = row.scalar_one_or_none()

    if detection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )

    if detection.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Detection must be completed before generating heatmap",
        )

    # If already completed, return existing data
    if detection.heatmap_status == "completed" and detection.paragraph_heatmap:
        return APIResponse(
            data={"heatmap_status": "completed", "paragraph_heatmap": detection.paragraph_heatmap},
            meta=Meta(request_id=task_id),
        )

    # Dispatch heatmap generation task
    run_heatmap.delay(
        detection_result_id=task_id,
    )

    return APIResponse(
        code=202,
        message="Heatmap generation started",
        data={"heatmap_status": "pending"},
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
    session: AsyncSession = Depends(get_async_session),
) -> APIResponse[BatchDetectResponse]:
    """Submit multiple texts for AI-content detection in a single request.

    Returns a ``batch_id`` that can be polled via ``GET /detect/batch/{batch_id}``.
    Each item is dispatched as a separate Celery task.
    """
    from app.tasks.detection_task import run_detection

    start = time.perf_counter()
    batch_id = str(uuid.uuid4())
    try:
        user_uuid = uuid.UUID(user.user_id)
    except (ValueError, AttributeError):
        user_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, user.user_id)

    task_ids: list[str] = []

    for item in body.items:
        content_hash = hashlib.sha256(item.text.encode("utf-8")).hexdigest()
        word_count = len(item.text.split())

        document = Document(
            user_id=user_uuid,
            title=f"Batch detection ({word_count} words)",
            content_hash=content_hash,
            word_count=word_count,
            language=item.language or "en",
            discipline=item.discipline,
        )
        session.add(document)
        await session.flush()

        detection = DetectionResult(
            document_id=document.id,
            batch_id=batch_id,
            granularity=item.granularity.value,
            status="pending",
            risk_score=0.0,
            risk_level=RiskLevel.LOW.value,
            llm_confidence=0.0,
            stat_score=0.0,
            evidence_completeness=0,
            review_priority=0.0,
            conclusion_type="preliminary",
            formula_version=settings.formula_version,
            param_version=settings.param_version,
        )
        session.add(detection)
        await session.flush()

        task_ids.append(str(detection.id))

    # Audit log for the batch
    audit = AuditLog(
        user_id=user_uuid,
        action="submit_batch_detection",
        resource_type="batch",
        resource_id=batch_id,
        details={"item_count": len(body.items), "task_ids": task_ids},
    )
    session.add(audit)

    # Commit so Celery workers can see the records
    await session.commit()

    # Dispatch all Celery tasks after commit
    for i, item in enumerate(body.items):
        run_detection.delay(
            detection_result_id=task_ids[i],
            text=item.text,
            granularity=item.granularity.value,
            language=item.language or "auto",
            discipline=item.discipline or "通用",
            model_override=None,
        )

    batch_resp = BatchDetectResponse(
        batch_id=batch_id,
        total=len(body.items),
        status=TaskStatus.PENDING,
        completed=0,
    )

    elapsed = (time.perf_counter() - start) * 1000
    return APIResponse(
        code=202,
        message="Batch detection accepted",
        data=batch_resp,
        meta=Meta(
            request_id=batch_id,
            processing_time_ms=round(elapsed, 2),
            formula_version=settings.formula_version,
            param_version=settings.param_version,
        ),
    )
