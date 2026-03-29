"""
Celery task for running the AI-content detection pipeline.

Since Celery tasks are synchronous, we use asyncio.run() to drive the
async DetectionEngine and async SQLAlchemy session.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional
from uuid import UUID

from app.worker import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="app.tasks.run_detection",
    max_retries=2,
    default_retry_delay=30,
)
def run_detection(
    self,
    detection_result_id: str,
    text: str,
    granularity: str = "document",
    language: str = "auto",
    discipline: str = "通用",
    model_override: Optional[str] = None,
) -> dict:
    """Execute the full detection pipeline for a single submission.

    This task:
    1. Marks the DetectionResult status as "processing"
    2. Runs DetectionEngine.detect() (async, via asyncio.run)
    3. Persists results back to the database
    4. Marks status as "completed" (or "failed" on error)
    """
    try:
        result = asyncio.run(
            _run_detection_async(
                detection_result_id=detection_result_id,
                text=text,
                granularity=granularity,
                language=language,
                discipline=discipline,
                model_override=model_override,
            )
        )
        return result
    except Exception as exc:
        logger.exception(
            "Detection task failed for detection_result_id=%s", detection_result_id
        )
        # Persist the failure status
        asyncio.run(_mark_failed(detection_result_id, str(exc)))
        raise


async def _run_detection_async(
    detection_result_id: str,
    text: str,
    granularity: str,
    language: str,
    discipline: str,
    model_override: Optional[str],
) -> dict:
    """Async inner function that runs the detection pipeline."""
    from sqlalchemy import update
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.config import get_settings
    from app.models.detection import DetectionResult
    from app.services.detection.engine import DetectionEngine
    from app.services.llm_gateway.client import LLMClient

    settings = get_settings()
    detection_uuid = UUID(detection_result_id)

    # -- Build a standalone async engine for this task -----------------------
    engine = create_async_engine(
        settings.database_url,
        pool_size=2,
        max_overflow=0,
        pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )

    try:
        # 1. Mark status as "processing" ------------------------------------
        async with session_factory() as session:
            stmt = (
                update(DetectionResult)
                .where(DetectionResult.id == detection_uuid)
                .values(status="processing")
            )
            await session.execute(stmt)
            await session.commit()

        # 2. Build engine and run detection ----------------------------------
        llm_client = LLMClient(
            ollama_url=settings.ollama_url,
            vllm_url=settings.vllm_url or "http://192.168.31.18:8001/v1",
            openai_api_key=settings.openai_api_key,
            anthropic_api_key=settings.anthropic_api_key,
            google_api_key=settings.google_api_key,
        )
        detection_engine = DetectionEngine(llm_client=llm_client)

        result = await detection_engine.detect(
            text=text,
            granularity=granularity,
            language=language,
            discipline=discipline,
            model_override=model_override,
        )

        # 3. Persist results ------------------------------------------------
        async with session_factory() as session:
            stmt = (
                update(DetectionResult)
                .where(DetectionResult.id == detection_uuid)
                .values(
                    status="completed",
                    risk_score=result.get("risk_score", 0.0),
                    risk_level=result.get("risk_level", "low"),
                    llm_confidence=result.get("llm_confidence", 0.0),
                    stat_score=result.get("stat_score", 0.0),
                    evidence_completeness=result.get("evidence_completeness", 0),
                    review_priority=result.get("review_priority", 0.0),
                    conclusion_type=result.get("conclusion_type", "fused"),
                    llm_evidence=result.get("llm_evidence"),
                    stat_evidence=result.get("stat_evidence"),
                    material_evidence=result.get("material_evidence"),
                    flagged_segments=result.get("flagged_segments"),
                    report_content=result.get("report_content"),
                    recommendations=result.get("recommendations"),
                    uncertainty_notes=result.get("uncertainty_notes", ""),
                    formula_version=result.get("formula_version"),
                    param_version=result.get("param_version"),
                    model_version=result.get("model_version"),
                    formula_params=result.get("formula_params"),
                    processing_time_ms=result.get("processing_time_ms"),
                )
            )
            await session.execute(stmt)
            await session.commit()

        logger.info(
            "Detection completed: id=%s risk_score=%s risk_level=%s",
            detection_result_id,
            result.get("risk_score"),
            result.get("risk_level"),
        )
        return {"status": "completed", "detection_result_id": detection_result_id}

    finally:
        await engine.dispose()


async def _mark_failed(detection_result_id: str, error_message: str) -> None:
    """Mark a DetectionResult as failed with an error message."""
    from sqlalchemy import update
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.config import get_settings
    from app.models.detection import DetectionResult

    settings = get_settings()
    detection_uuid = UUID(detection_result_id)

    engine = create_async_engine(
        settings.database_url,
        pool_size=2,
        max_overflow=0,
    )
    session_factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )

    try:
        async with session_factory() as session:
            stmt = (
                update(DetectionResult)
                .where(DetectionResult.id == detection_uuid)
                .values(
                    status="failed",
                    error_message=error_message[:2000],  # truncate long errors
                )
            )
            await session.execute(stmt)
            await session.commit()
    finally:
        await engine.dispose()
