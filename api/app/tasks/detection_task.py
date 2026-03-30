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
        # 从数据库读取管理面板配置的模型路由
        model_routes = await _load_model_routes_from_db(session_factory)
        # 从 Redis 读取管理面板配置的 API Key 和服务地址
        runtime_keys, runtime_urls = _load_runtime_config_from_redis(settings.redis_url)

        llm_client = LLMClient(
            ollama_url=runtime_urls.get("ollama_url", settings.ollama_url),
            vllm_url=runtime_urls.get("vllm_url", settings.vllm_url or "http://192.168.31.18:8001/v1"),
            model_routes=model_routes,
            openai_api_key=runtime_keys.get("openai") or settings.openai_api_key,
            anthropic_api_key=runtime_keys.get("anthropic") or settings.anthropic_api_key,
            google_api_key=runtime_keys.get("google") or settings.google_api_key,
        )

        # 初始化Redis客户端用于检测结果缓存
        redis_client = None
        try:
            from redis.asyncio import Redis as AsyncRedis
            redis_client = AsyncRedis.from_url(
                settings.redis_url,
                decode_responses=True,
                max_connections=5,
            )
            await redis_client.ping()
        except Exception as redis_err:
            logger.warning("Redis不可用，跳过缓存: %s", redis_err)
            redis_client = None

        detection_engine = DetectionEngine(
            llm_client=llm_client,
            redis_client=redis_client,
        )

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
                    heatmap_status=result.get("heatmap_status", "not_requested"),
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
        if redis_client is not None:
            await redis_client.aclose()
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


# ── Heatmap generation task (deferred) ───────────────────────────────


@celery_app.task(
    bind=True,
    name="app.tasks.run_heatmap",
    max_retries=1,
    default_retry_delay=15,
)
def run_heatmap(
    self,
    detection_result_id: str,
    model_override: Optional[str] = None,
) -> dict:
    """Generate paragraph-level heatmap for a completed detection.

    This runs separately from the main detection pipeline to avoid
    adding latency to the primary detection flow.
    """
    try:
        result = asyncio.run(
            _run_heatmap_async(
                detection_result_id=detection_result_id,
                model_override=model_override,
            )
        )
        return result
    except Exception as exc:
        logger.exception(
            "Heatmap task failed for detection_result_id=%s", detection_result_id
        )
        raise


async def _run_heatmap_async(
    detection_result_id: str,
    model_override: Optional[str],
) -> dict:
    """Async inner function for heatmap generation."""
    from sqlalchemy import select, update
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.config import get_settings
    from app.models.detection import DetectionResult
    from app.models.document import Document
    from app.services.detection.engine import DetectionEngine
    from app.services.detection.preprocessor import TextPreprocessor
    from app.services.llm_gateway.client import LLMClient

    settings = get_settings()
    detection_uuid = UUID(detection_result_id)

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
        # 1. Fetch the detection record and associated document text
        async with session_factory() as session:
            stmt = select(DetectionResult).where(DetectionResult.id == detection_uuid)
            row = await session.execute(stmt)
            detection = row.scalar_one_or_none()

            if detection is None:
                raise ValueError(f"Detection {detection_result_id} not found")

            # Get the document to access original text for paragraph splitting
            doc_stmt = select(Document).where(Document.id == detection.document_id)
            doc_row = await session.execute(doc_stmt)
            document = doc_row.scalar_one_or_none()

        # 2. Rebuild paragraphs from the stored llm_evidence or re-preprocess
        #    We use the preprocessor to get paragraphs from the original text
        #    For now, we can extract from the detection's stored data
        model_routes = await _load_model_routes_from_db(session_factory)
        runtime_keys, runtime_urls = _load_runtime_config_from_redis(settings.redis_url)
        llm_client = LLMClient(
            ollama_url=runtime_urls.get("ollama_url", settings.ollama_url),
            vllm_url=runtime_urls.get("vllm_url", settings.vllm_url or "http://192.168.31.18:8001/v1"),
            model_routes=model_routes,
            openai_api_key=runtime_keys.get("openai") or settings.openai_api_key,
            anthropic_api_key=runtime_keys.get("anthropic") or settings.anthropic_api_key,
            google_api_key=runtime_keys.get("google") or settings.google_api_key,
        )
        detection_engine = DetectionEngine(llm_client=llm_client)

        # Use the stat_evidence to infer paragraphs, or fall back to
        # re-reading the document content. Since Document doesn't store
        # full text (it's passed directly), we need to use flagged_segments
        # or generate placeholder paragraphs from the evidence.
        # For a proper implementation, we'd store the processed paragraphs.
        # Here we generate a basic heatmap from the LLM evidence.
        paragraphs = []
        if detection.llm_evidence and detection.llm_evidence.get("flagged_segments"):
            # Use flagged segments as paragraph proxies
            for seg in detection.llm_evidence["flagged_segments"]:
                snippet = seg.get("text_snippet", "")
                if snippet:
                    paragraphs.append(snippet)

        # If no paragraphs found, generate a simple heatmap from risk_level
        if not paragraphs:
            heatmap_data = [{"index": 0, "risk": detection.risk_level, "brief_reason": "整体评估"}]
        else:
            heatmap_data = await detection_engine.generate_heatmap(
                paragraphs=paragraphs,
                model_override=model_override,
            )

        # 3. Persist heatmap results
        async with session_factory() as session:
            stmt = (
                update(DetectionResult)
                .where(DetectionResult.id == detection_uuid)
                .values(
                    paragraph_heatmap=heatmap_data
                    if isinstance(heatmap_data, dict)
                    else {"paragraphs": heatmap_data},
                    heatmap_status="completed",
                )
            )
            await session.execute(stmt)
            await session.commit()

        logger.info(
            "Heatmap generated: id=%s paragraphs=%d",
            detection_result_id,
            len(heatmap_data),
        )
        return {"status": "completed", "detection_result_id": detection_result_id}

    finally:
        await engine.dispose()


# ── Helper: load model routes from DB ──────────────────────────────


async def _load_model_routes_from_db(session_factory) -> dict | None:
    """
    从数据库加载管理面板配置的模型路由。
    如果数据库中没有配置，返回 None（LLMClient 将使用硬编码默认值）。
    """
    from sqlalchemy import select
    from app.models.system import ModelConfig
    from app.services.llm_gateway.client import DEFAULT_MODEL_ROUTES

    try:
        async with session_factory() as session:
            stmt = select(ModelConfig).where(ModelConfig.is_active == True)
            result = await session.execute(stmt)
            db_configs = {cfg.task_type: cfg for cfg in result.scalars().all()}

        if not db_configs:
            return None  # 没有数据库配置，使用默认值

        # 将数据库配置合并到默认路由中
        routes = dict(DEFAULT_MODEL_ROUTES)  # 浅拷贝默认值
        for task_type, cfg in db_configs.items():
            default = DEFAULT_MODEL_ROUTES.get(task_type, {})
            routes[task_type] = {
                "primary": cfg.primary_model,
                "fallback": cfg.fallback_model or default.get("fallback"),
                "degradation": cfg.degradation_strategy or default.get("degradation"),
            }

        logger.info(
            "从数据库加载模型路由: %s",
            {k: v.get("primary", "?") for k, v in routes.items()},
        )
        return routes

    except Exception as e:
        logger.warning("加载数据库模型路由失败，使用默认值: %s", e)
        return None


# ── Helper: load API keys & URLs from Redis ────────────────────────


def _load_runtime_config_from_redis(redis_url: str) -> tuple[dict, dict]:
    """
    从 Redis 读取管理面板配置的 API Key 和服务地址。
    管理面板保存配置时会同步写入 Redis，这样 Celery Worker（独立进程）也能读到。

    Returns:
        (api_keys_dict, service_urls_dict)
    """
    import redis as sync_redis

    keys: dict = {}
    urls: dict = {}
    try:
        r = sync_redis.Redis.from_url(redis_url, decode_responses=True)
        for provider in ("openai", "anthropic", "google"):
            val = r.get(f"sg:api_key:{provider}")
            if val:
                keys[provider] = val
        for url_key in ("vllm_url", "ollama_url"):
            val = r.get(f"sg:service_url:{url_key}")
            if val:
                urls[url_key] = val
        if keys:
            logger.info("从 Redis 加载 API Key: %s", list(keys.keys()))
        if urls:
            logger.info("从 Redis 加载服务地址: %s", urls)
    except Exception as e:
        logger.warning("从 Redis 加载运行时配置失败: %s", e)
    return keys, urls
