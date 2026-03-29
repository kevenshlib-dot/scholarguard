"""
Review, appeal, and feedback routes for ScholarGuard.

Endpoints for human review of detection results, student appeals, and
general feedback on detection quality.
"""

from __future__ import annotations

import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.middleware.auth import UserContext, get_current_active_user, require_role
from app.middleware.rate_limiter import rate_limit
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

router = APIRouter(tags=["Review & Appeals"])

# ── In-memory stores (replace with DB in production) ────────────────────
_reviews: dict[str, ReviewResponse] = {}
_appeals: dict[str, AppealResponse] = {}
_feedback: dict[str, FeedbackResponse] = {}


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
) -> APIResponse[ReviewResponse]:
    """Record a human reviewer's verdict on an existing detection result.

    Only users with the ``admin`` or ``instructor`` role may submit reviews.
    The verdict (confirmed, overturned, or inconclusive) is stored alongside
    the original detection for audit purposes.
    """
    start = time.perf_counter()
    review_id = str(uuid.uuid4())

    review = ReviewResponse(
        review_id=review_id,
        detection_id=detection_id,
        verdict=body.verdict,
    )
    _reviews[review_id] = review

    # TODO: Persist to database and update detection record.

    elapsed = (time.perf_counter() - start) * 1000
    return APIResponse(
        data=review,
        meta=Meta(request_id=review_id, processing_time_ms=round(elapsed, 2)),
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
) -> APIResponse[AppealResponse]:
    """Allow a student or author to appeal a detection verdict.

    The appeal includes a reason and optional supporting evidence.  Once
    submitted the appeal enters the review queue and can be tracked via
    ``GET /appeal/{appeal_id}``.
    """
    start = time.perf_counter()
    appeal_id = str(uuid.uuid4())

    appeal = AppealResponse(
        appeal_id=appeal_id,
        detection_id=detection_id,
        status=AppealStatus.SUBMITTED,
    )
    _appeals[appeal_id] = appeal

    # TODO: Persist to database and notify reviewers.

    elapsed = (time.perf_counter() - start) * 1000
    return APIResponse(
        code=201,
        message="Appeal submitted",
        data=appeal,
        meta=Meta(request_id=appeal_id, processing_time_ms=round(elapsed, 2)),
    )


@router.get(
    "/appeal/{appeal_id}",
    response_model=APIResponse[AppealResponse],
    summary="Get the status of an appeal",
)
async def get_appeal_status(
    appeal_id: str,
    user: UserContext = Depends(get_current_active_user),
) -> APIResponse[AppealResponse]:
    """Retrieve the current status and resolution of an appeal.

    Returns the full appeal record including its status
    (submitted, under_review, resolved, rejected) and resolution details
    if the appeal has been resolved.
    """
    appeal = _appeals.get(appeal_id)
    if appeal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Appeal {appeal_id} not found",
        )
    return APIResponse(
        data=appeal,
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
) -> APIResponse[FeedbackResponse]:
    """Allow any authenticated user to provide feedback on a detection result.

    Feedback is used to continuously improve detection accuracy.  Each
    submission includes a rating (accurate, partially_accurate, inaccurate)
    and an optional free-text comment.
    """
    start = time.perf_counter()
    feedback_id = str(uuid.uuid4())

    fb = FeedbackResponse(
        feedback_id=feedback_id,
        detection_id=body.detection_id,
        rating=body.rating,
    )
    _feedback[feedback_id] = fb

    # TODO: Persist to database and feed into retraining pipeline.

    elapsed = (time.perf_counter() - start) * 1000
    return APIResponse(
        code=201,
        message="Feedback received",
        data=fb,
        meta=Meta(request_id=feedback_id, processing_time_ms=round(elapsed, 2)),
    )
