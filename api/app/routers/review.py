"""
Review, appeal, and feedback routes for ScholarGuard.

Endpoints for human review of detection results, student appeals, and
general feedback on detection quality.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.auth import UserContext, get_current_active_user, require_role
from app.middleware.rate_limiter import rate_limit
from app.models.base import get_async_session
from app.models.detection import DetectionResult
from app.models.review import (
    AppealRecord,
    AppealStatus as DBAppealStatus,
    Feedback,
    FeedbackType,
    ReviewLabel,
    ReviewRecord,
)
from app.models.system import AuditLog
from app.schemas.common import APIResponse, Meta
from app.schemas.review import (
    AppealRequest,
    AppealResponse,
    AppealStatus,
    FeedbackRequest,
    FeedbackResponse,
    ReviewRequest,
    ReviewResponse,
    ReviewVerdict,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Review & Appeals"])

# ── Mapping helpers ───────────────────────────────────────────────────────

_VERDICT_TO_LABEL = {
    ReviewVerdict.CONFIRMED: ReviewLabel.MAINTAIN,
    ReviewVerdict.OVERTURNED: ReviewLabel.DISMISS,
    ReviewVerdict.INCONCLUSIVE: ReviewLabel.ADJUST,
}

_LABEL_TO_VERDICT = {v: k for k, v in _VERDICT_TO_LABEL.items()}

_RATING_TO_FEEDBACK_TYPE = {
    "accurate": FeedbackType.ACCURATE,
    "partially_accurate": FeedbackType.ACCEPTABLE_ASSIST,
    "inaccurate": FeedbackType.FALSE_POSITIVE,
}

_APPEAL_STATUS_MAP = {
    DBAppealStatus.PENDING: AppealStatus.SUBMITTED,
    DBAppealStatus.UNDER_REVIEW: AppealStatus.UNDER_REVIEW,
    DBAppealStatus.RESOLVED: AppealStatus.RESOLVED,
    DBAppealStatus.DISMISSED: AppealStatus.REJECTED,
}


# ── GET /reviews — list detections pending review ────────────────────────


@router.get(
    "/reviews",
    response_model=APIResponse,
    summary="List detection results that need human review",
)
async def list_reviews(
    status_filter: Optional[str] = Query(None, alias="status"),
    user: UserContext = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> APIResponse:
    """Return detection results that are flagged for human review.

    High-risk or critical detections, or those where the LLM suggested
    review, are included.  An optional ``status`` query parameter filters
    by review status: ``pending`` (not yet reviewed), ``reviewing``, or
    ``resolved``.
    """
    # Build base query: detections with high/critical risk, high review_priority,
    # or detections that have optimization data attached
    stmt = (
        select(DetectionResult)
        .where(DetectionResult.status == "completed")
        .where(
            or_(
                DetectionResult.risk_level.in_(["high", "critical"]),
                DetectionResult.review_priority > 0.5,
                DetectionResult.optimization_data.isnot(None),
            )
        )
        .order_by(desc(DetectionResult.created_at))
        .limit(50)
    )

    rows = await session.execute(stmt)
    detections = rows.scalars().all()

    # Gather IDs of detections that already have a review record
    det_ids = [d.id for d in detections]
    reviewed_ids: set = set()
    if det_ids:
        review_stmt = select(ReviewRecord.detection_id).where(
            ReviewRecord.detection_id.in_(det_ids)
        )
        review_rows = await session.execute(review_stmt)
        reviewed_ids = {r[0] for r in review_rows.all()}

    # Build items, filtering by status if requested
    items = []
    for det in detections:
        has_review = det.id in reviewed_ids
        if status_filter == "pending" and has_review:
            continue
        if status_filter == "resolved" and not has_review:
            continue

        # Build text preview from flagged segments or report
        text_preview = ""
        segs = det.flagged_segments
        if isinstance(segs, list) and segs:
            text_preview = segs[0].get("text_snippet", "")[:200]
        elif isinstance(segs, dict):
            seg_list = segs.get("segments", segs.get("flagged_segments", []))
            if seg_list:
                text_preview = seg_list[0].get("text_snippet", "")[:200]
        if not text_preview:
            report = det.report_content or {}
            text_preview = report.get("risk_summary", "")[:200]
        if not text_preview:
            text_preview = det.document.title if det.document else f"Detection {det.id}"

        item_status = "resolved" if has_review else "pending"
        # Use nhpr_level as primary risk indicator (consistent with DetectPage)
        display_level = det.nhpr_level or det.risk_level
        display_score = float(det.nhpr_score) if det.nhpr_score is not None else float(det.risk_score)
        items.append({
            "id": str(det.id),
            "detection_id": str(det.id),
            "submitted_at": det.created_at.isoformat() if det.created_at else "",
            "risk_level": display_level,
            "risk_score": display_score,
            "status": item_status,
            "text_preview": text_preview,
            "optimization_data": det.optimization_data,
        })

    return APIResponse(
        data={"items": items},
        meta=Meta(request_id=str(uuid.uuid4())),
    )


# ── POST /reviews/{review_id}/decide — submit review decision ───────────


@router.post(
    "/reviews/{review_id}/decide",
    response_model=APIResponse,
    summary="Submit a review decision for a detection",
)
async def decide_review(
    review_id: str,
    body: dict,
    user: UserContext = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> APIResponse:
    """Record a reviewer's decision on a detection result.

    Accepts ``decision`` (maintain/adjust/dismiss) and ``comment``.
    """
    start = time.perf_counter()

    try:
        detection_uuid = uuid.UUID(review_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid review_id format: {review_id}",
        )

    # Verify detection exists
    stmt = select(DetectionResult).where(DetectionResult.id == detection_uuid)
    row = await session.execute(stmt)
    detection = row.scalar_one_or_none()
    if detection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Detection {review_id} not found",
        )

    try:
        user_uuid = uuid.UUID(user.user_id)
    except (ValueError, AttributeError):
        user_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, user.user_id)

    decision = body.get("decision", "maintain")
    comment = body.get("comment", "")

    # Map decision to review label
    label_map = {
        "maintain": ReviewLabel.MAINTAIN,
        "adjust": ReviewLabel.ADJUST,
        "dismiss": ReviewLabel.DISMISS,
    }
    review_label = label_map.get(decision, ReviewLabel.MAINTAIN)

    # Determine adjusted risk level
    adjusted_risk_level = None
    if decision == "dismiss":
        adjusted_risk_level = "low"
    elif decision == "adjust":
        adjusted_risk_level = "medium"

    review = ReviewRecord(
        detection_id=detection_uuid,
        reviewer_id=user_uuid,
        review_label=review_label.value,
        review_comment=comment,
        adjusted_risk_level=adjusted_risk_level,
    )
    session.add(review)
    await session.flush()

    # Update detection conclusion
    detection.conclusion_type = "human_confirmed"
    if decision == "dismiss":
        detection.human_evidence = {
            "reviewer_id": str(user_uuid),
            "decision": decision,
            "comment": comment,
        }

    # Audit log
    audit = AuditLog(
        user_id=user_uuid,
        action="review_decision",
        resource_type="review",
        resource_id=str(review.id),
        details={
            "detection_id": review_id,
            "decision": decision,
        },
    )
    session.add(audit)

    elapsed = (time.perf_counter() - start) * 1000
    return APIResponse(
        data={"success": True},
        meta=Meta(request_id=str(review.id), processing_time_ms=round(elapsed, 2)),
    )


# ── POST /review/{detection_id} — original submit review ────────────────


@router.post(
    "/review/{detection_id}",
    response_model=APIResponse[ReviewResponse],
    dependencies=[Depends(rate_limit())],
    summary="Submit a human review of a detection result",
)
async def submit_review(
    detection_id: str,
    body: ReviewRequest,
    user: UserContext = Depends(require_role("admin", "instructor")),
    session: AsyncSession = Depends(get_async_session),
) -> APIResponse[ReviewResponse]:
    """Record a human reviewer's verdict on an existing detection result.

    Only users with the ``admin`` or ``instructor`` role may submit reviews.
    The verdict (confirmed, overturned, or inconclusive) is stored alongside
    the original detection for audit purposes.
    """
    start = time.perf_counter()

    # Validate detection_id
    try:
        detection_uuid = uuid.UUID(detection_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid detection_id format: {detection_id}",
        )

    # Verify detection exists
    stmt = select(DetectionResult).where(DetectionResult.id == detection_uuid)
    row = await session.execute(stmt)
    detection = row.scalar_one_or_none()
    if detection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Detection {detection_id} not found",
        )

    user_uuid = uuid.UUID(user.user_id) if not isinstance(user.user_id, uuid.UUID) else user.user_id

    # Map schema verdict to DB review label
    review_label = _VERDICT_TO_LABEL.get(body.verdict, ReviewLabel.MAINTAIN)

    # Determine adjusted risk level based on verdict
    adjusted_risk_level = None
    if body.verdict == ReviewVerdict.OVERTURNED:
        adjusted_risk_level = "low"
    elif body.verdict == ReviewVerdict.INCONCLUSIVE:
        adjusted_risk_level = "medium"

    review = ReviewRecord(
        detection_id=detection_uuid,
        reviewer_id=user_uuid,
        review_label=review_label.value,
        review_comment=body.notes,
        adjusted_risk_level=adjusted_risk_level,
    )
    session.add(review)
    await session.flush()

    # Update detection conclusion type to human_confirmed
    detection.conclusion_type = "human_confirmed"
    if body.verdict == ReviewVerdict.OVERTURNED:
        detection.human_evidence = {
            "reviewer_id": str(user_uuid),
            "verdict": body.verdict.value,
            "notes": body.notes,
        }

    # Audit log
    audit = AuditLog(
        user_id=user_uuid,
        action="submit_review",
        resource_type="review",
        resource_id=str(review.id),
        details={
            "detection_id": detection_id,
            "verdict": body.verdict.value,
        },
    )
    session.add(audit)

    response = ReviewResponse(
        review_id=str(review.id),
        detection_id=detection_id,
        verdict=body.verdict,
        reviewed_at=review.created_at,
    )

    elapsed = (time.perf_counter() - start) * 1000
    return APIResponse(
        data=response,
        meta=Meta(request_id=str(review.id), processing_time_ms=round(elapsed, 2)),
    )


@router.post(
    "/appeal/{detection_id}",
    response_model=APIResponse[AppealResponse],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit())],
    summary="Submit an appeal against a detection result",
)
async def submit_appeal(
    detection_id: str,
    body: AppealRequest,
    user: UserContext = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> APIResponse[AppealResponse]:
    """Allow a student or author to appeal a detection verdict.

    The appeal includes a reason and optional supporting evidence.  Once
    submitted the appeal enters the review queue and can be tracked via
    ``GET /appeal/{appeal_id}``.
    """
    start = time.perf_counter()

    # Validate detection_id
    try:
        detection_uuid = uuid.UUID(detection_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid detection_id format: {detection_id}",
        )

    # Verify detection exists
    stmt = select(DetectionResult).where(DetectionResult.id == detection_uuid)
    row = await session.execute(stmt)
    detection = row.scalar_one_or_none()
    if detection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Detection {detection_id} not found",
        )

    user_uuid = uuid.UUID(user.user_id) if not isinstance(user.user_id, uuid.UUID) else user.user_id

    # Build material_paths from supporting evidence if provided
    material_paths = None
    if body.supporting_evidence:
        material_paths = {"supporting_evidence": body.supporting_evidence}

    appeal = AppealRecord(
        detection_id=detection_uuid,
        user_id=user_uuid,
        appeal_reason=body.reason,
        material_paths=material_paths,
        status=DBAppealStatus.PENDING.value,
    )
    session.add(appeal)
    await session.flush()

    # Audit log
    audit = AuditLog(
        user_id=user_uuid,
        action="submit_appeal",
        resource_type="appeal",
        resource_id=str(appeal.id),
        details={"detection_id": detection_id},
    )
    session.add(audit)

    response = AppealResponse(
        appeal_id=str(appeal.id),
        detection_id=detection_id,
        status=AppealStatus.SUBMITTED,
        submitted_at=appeal.created_at,
    )

    elapsed = (time.perf_counter() - start) * 1000
    return APIResponse(
        code=201,
        message="Appeal submitted",
        data=response,
        meta=Meta(request_id=str(appeal.id), processing_time_ms=round(elapsed, 2)),
    )


@router.get(
    "/appeal/{appeal_id}",
    response_model=APIResponse[AppealResponse],
    summary="Get the status of an appeal",
)
async def get_appeal_status(
    appeal_id: str,
    user: UserContext = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> APIResponse[AppealResponse]:
    """Retrieve the current status and resolution of an appeal.

    Returns the full appeal record including its status
    (submitted, under_review, resolved, rejected) and resolution details
    if the appeal has been resolved.
    """
    try:
        appeal_uuid = uuid.UUID(appeal_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid appeal_id format: {appeal_id}",
        )

    stmt = select(AppealRecord).where(AppealRecord.id == appeal_uuid)
    row = await session.execute(stmt)
    appeal = row.scalar_one_or_none()

    if appeal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Appeal {appeal_id} not found",
        )

    # Map DB status to schema status
    db_status = DBAppealStatus(appeal.status) if isinstance(appeal.status, str) else appeal.status
    schema_status = _APPEAL_STATUS_MAP.get(db_status, AppealStatus.SUBMITTED)

    response = AppealResponse(
        appeal_id=str(appeal.id),
        detection_id=str(appeal.detection_id),
        status=schema_status,
        resolution=appeal.resolution,
        submitted_at=appeal.created_at,
        resolved_at=appeal.resolved_at,
    )

    return APIResponse(
        data=response,
        meta=Meta(request_id=appeal_id),
    )


@router.post(
    "/feedback",
    response_model=APIResponse[FeedbackResponse],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit())],
    summary="Submit feedback on detection quality",
)
async def submit_feedback(
    body: FeedbackRequest,
    user: UserContext = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> APIResponse[FeedbackResponse]:
    """Allow any authenticated user to provide feedback on a detection result.

    Feedback is used to continuously improve detection accuracy.  Each
    submission includes a rating (accurate, partially_accurate, inaccurate)
    and an optional free-text comment.
    """
    start = time.perf_counter()

    # Validate detection_id
    try:
        detection_uuid = uuid.UUID(body.detection_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid detection_id format: {body.detection_id}",
        )

    # Verify detection exists
    stmt = select(DetectionResult).where(DetectionResult.id == detection_uuid)
    row = await session.execute(stmt)
    detection = row.scalar_one_or_none()
    if detection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Detection {body.detection_id} not found",
        )

    user_uuid = uuid.UUID(user.user_id) if not isinstance(user.user_id, uuid.UUID) else user.user_id

    # Map schema rating to DB feedback type
    feedback_type = _RATING_TO_FEEDBACK_TYPE.get(body.rating.value, FeedbackType.ACCURATE)

    feedback = Feedback(
        detection_id=detection_uuid,
        user_id=user_uuid,
        feedback_type=feedback_type.value,
        user_comment=body.comment,
    )
    session.add(feedback)
    await session.flush()

    # Audit log
    audit = AuditLog(
        user_id=user_uuid,
        action="submit_feedback",
        resource_type="feedback",
        resource_id=str(feedback.id),
        details={
            "detection_id": body.detection_id,
            "rating": body.rating.value,
        },
    )
    session.add(audit)

    response = FeedbackResponse(
        feedback_id=str(feedback.id),
        detection_id=body.detection_id,
        rating=body.rating,
        received_at=feedback.created_at,
    )

    elapsed = (time.perf_counter() - start) * 1000
    return APIResponse(
        code=201,
        message="Feedback received",
        data=response,
        meta=Meta(request_id=str(feedback.id), processing_time_ms=round(elapsed, 2)),
    )
