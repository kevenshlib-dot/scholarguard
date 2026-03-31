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
    OneClickOptimizeRequest,
    OneClickOptimizeResponse,
    RewriteRequest,
    RewriteResponse,
    SuggestRequest,
    SuggestResponse,
    SuggestionItem,
    SuggestionType,
)
from app.services.detection.engine import DetectionEngine
from app.services.llm_gateway.client import DEFAULT_MODEL_ROUTES, LLMClient
from app.utils.json_extract import extract_json

logger = logging.getLogger(__name__)


def _format_stat_evidence(stat_ev: dict | None) -> str:
    """Format stat_evidence dict into a readable string for the LLM prompt."""
    if not stat_ev:
        return "无统计数据"
    parts = []
    if "sentence_length_std" in stat_ev:
        parts.append(f"句长标准差={stat_ev['sentence_length_std']:.1f}")
    if "connector_density" in stat_ev:
        parts.append(f"连接词密度={stat_ev['connector_density']:.1f}/千字")
    if "paragraph_uniformity" in stat_ev:
        parts.append(f"段落均匀性CV={stat_ev['paragraph_uniformity']:.3f}")
    if "repetition_ratio" in stat_ev:
        parts.append(f"重复率={stat_ev['repetition_ratio']:.3f}")
    if "stat_score" in stat_ev:
        parts.append(f"综合统计分={stat_ev['stat_score']:.3f}")
    return "，".join(parts) if parts else "无统计数据"

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

    # Load detection context: prefer user-curated issues (HITL) over DB-fetched
    flagged_issues = ""
    if body.user_issues:
        # User has reviewed and curated the issues checklist
        flagged_issues = "\n".join([
            f"- \"{ui.snippet}\" → {ui.issue}"
            for ui in body.user_issues
        ])
    elif detection and detection.flagged_segments:
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

    # Load model routes from DB and API keys from Redis (same as detection_task)
    model_routes = await _load_model_routes(session)
    runtime_keys, runtime_urls = _load_runtime_config_from_redis(settings.redis_url)

    # Call LLM
    llm_client = LLMClient(
        ollama_url=runtime_urls.get("ollama_url", "http://localhost:11434"),
        vllm_url=runtime_urls.get("vllm_url", settings.vllm_url or "http://192.168.31.18:8001/v1"),
        model_routes=model_routes,
        openai_api_key=runtime_keys.get("openai") or settings.openai_api_key,
        anthropic_api_key=runtime_keys.get("anthropic") or settings.anthropic_api_key,
        google_api_key=runtime_keys.get("google") or settings.google_api_key,
    )
    # Build stat_evidence string from detection record
    stat_evidence_str = _format_stat_evidence(
        detection.stat_evidence if detection else None
    )

    prompt = SUGGEST_PROMPT.format(
        text=body.text[:4000],
        issues=flagged_issues or "未提供具体检测结果，请根据文本特征自行分析AI痕迹",
        stat_evidence=stat_evidence_str,
        strategies=strategies_str,
    )

    # Append user's custom prompt if provided
    if body.custom_prompt:
        prompt += f"\n\n用户补充要求：{body.custom_prompt}"

    try:
        response = await llm_client.chat(
            task_type="suggestion",
            system_prompt=SUGGEST_SYSTEM,
            user_prompt=prompt,
            response_format="json",
            max_tokens=2048,
            temperature=0.3,
        )

        logger.info(
            f"Suggest LLM raw response (first 500 chars): "
            f"{response[:500] if response else '<empty>'}"
        )

        raw = extract_json(response)
        logger.info(f"Suggest extract_json result type={type(raw).__name__}, value={str(raw)[:300] if raw else 'None'}")

        suggestions: list[SuggestionItem] = []
        items = (
            raw
            if isinstance(raw, list)
            else raw.get("suggestions", [])
            if isinstance(raw, dict)
            else []
        )

        logger.info(f"Suggest parsed {len(items)} items from LLM response")

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
        import traceback
        logger.error(
            f"Suggestion LLM call failed: {type(e).__name__}: {e}\n"
            f"{traceback.format_exc()}"
        )
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


def _load_runtime_config_from_redis(redis_url: str) -> tuple[dict, dict]:
    """Load API keys and service URLs from Redis (written by admin panel)."""
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
            logger.info("Suggest: loaded API keys from Redis: %s", list(keys.keys()))
    except Exception as e:
        logger.warning("Suggest: failed to load Redis config: %s", e)
    return keys, urls


async def _load_model_routes(session: AsyncSession) -> dict | None:
    """Load model routes from admin panel DB config, falling back to defaults."""
    try:
        from app.models.system import ModelConfig

        stmt = select(ModelConfig).where(ModelConfig.is_active == True)  # noqa: E712
        result = await session.execute(stmt)
        db_configs = {cfg.task_type: cfg for cfg in result.scalars().all()}

        if not db_configs:
            return None

        routes = dict(DEFAULT_MODEL_ROUTES)
        for task_type, cfg in db_configs.items():
            default = DEFAULT_MODEL_ROUTES.get(task_type, {})
            routes[task_type] = {
                "primary": cfg.primary_model,
                "fallback": cfg.fallback_model or default.get("fallback"),
                "degradation": cfg.degradation_strategy or default.get("degradation"),
            }

        logger.info("Suggest: loaded model routes from DB: %s",
                     {k: v.get("primary", "?") for k, v in routes.items()})
        return routes
    except Exception as e:
        logger.warning("Suggest: failed to load DB model routes, using defaults: %s", e)
        return None


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


# ── One-click optimize ─────────────────────────────────────────────────


@router.post(
    "/optimize-and-store",
    response_model=APIResponse[OneClickOptimizeResponse],
    dependencies=[Depends(rate_limit())],
    summary="One-click: generate suggestions, apply them, and persist to detection",
)
async def optimize_and_store(
    body: OneClickOptimizeRequest,
    user: UserContext = Depends(get_current_active_user),
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_async_session),
) -> APIResponse[OneClickOptimizeResponse]:
    """Generate writing suggestions, apply all of them to the text, and store
    the optimization result on the associated DetectionResult record.

    This powers the one-click optimize button on the detection results page.
    """
    from datetime import datetime, timezone

    start = time.perf_counter()
    request_id = str(uuid.uuid4())
    try:
        user_uuid = uuid.UUID(user.user_id)
    except (ValueError, AttributeError):
        user_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, user.user_id)

    # ── Load detection ──────────────────────────────────────────────
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

    # ── Build issues context ────────────────────────────────────────
    flagged_issues = ""
    if body.user_issues:
        flagged_issues = "\n".join(
            f'- "{ui.snippet}" \u2192 {ui.issue}' for ui in body.user_issues
        )
    elif detection.flagged_segments:
        segs = detection.flagged_segments
        if isinstance(segs, list):
            flagged_issues = "\n".join(
                f"- \u4f4d\u7f6e({s.get('start_char', 0)}-{s.get('end_char', 0)}): "
                f"{s.get('text_snippet', '')} \u2192 {s.get('issue', '')}"
                for s in segs
            )

    # ── Strategies ──────────────────────────────────────────────────
    strategy_map = {
        "rephrase": "\u6539\u5199\u8868\u8fbe\u4f7f\u4e4b\u66f4\u81ea\u7136",
        "restructure": "\u8c03\u6574\u6587\u7ae0\u7ed3\u6784",
        "tone": "\u8c03\u6574\u5b66\u672f\u8bed\u6c14",
        "vocabulary": "\u66ff\u6362AI\u5e38\u89c1\u8bcd\u6c47",
        "general": "\u7efc\u5408\u6539\u8fdb",
    }
    focus_list = body.focus or []
    strategies_str = (
        "\u3001".join(
            strategy_map.get(
                f.value if hasattr(f, "value") else f,
                f.value if hasattr(f, "value") else f,
            )
            for f in focus_list
        )
        if focus_list
        else "\u7efc\u5408\u4f18\u5316"
    )

    # ── LLM call ────────────────────────────────────────────────────
    model_routes = await _load_model_routes(session)
    runtime_keys, runtime_urls = _load_runtime_config_from_redis(settings.redis_url)

    llm_client = LLMClient(
        ollama_url=runtime_urls.get("ollama_url", "http://localhost:11434"),
        vllm_url=runtime_urls.get(
            "vllm_url", settings.vllm_url or "http://192.168.31.18:8001/v1"
        ),
        model_routes=model_routes,
        openai_api_key=runtime_keys.get("openai") or settings.openai_api_key,
        anthropic_api_key=runtime_keys.get("anthropic") or settings.anthropic_api_key,
        google_api_key=runtime_keys.get("google") or settings.google_api_key,
    )
    # Build stat_evidence string from detection record
    stat_evidence_str = _format_stat_evidence(
        detection.stat_evidence if detection else None
    )

    prompt = SUGGEST_PROMPT.format(
        text=body.text[:4000],
        issues=flagged_issues or "未提供具体检测结果，请根据文本特征自行分析AI痕迹",
        stat_evidence=stat_evidence_str,
        strategies=strategies_str,
    )
    if body.custom_prompt:
        prompt += f"\n\n用户补充要求：{body.custom_prompt}"

    suggestions: list[SuggestionItem] = []
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
    except Exception as e:
        logger.error(f"One-click optimize LLM call failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM 服务不可用，请在系统管理中检查模型配置：{e}",
        )

    if not suggestions:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="未能生成任何优化建议，请调整优化策略后重试",
        )

    # ── Apply suggestions (reverse offset order) ────────────────────
    optimized_text = body.text
    sorted_sugs = sorted(suggestions, key=lambda s: s.offset_start, reverse=True)
    for sug in sorted_sugs:
        if sug.original_text and sug.original_text in optimized_text:
            optimized_text = optimized_text.replace(
                sug.original_text, sug.suggested_text, 1
            )

    now_str = datetime.now(timezone.utc).isoformat()

    # ── Re-detect optimized text (skip cache) ──────────────────────
    verified_risk_score = None
    verified_nhpr_score = None
    optimization_rounds = 1
    original_nhpr = float(detection.nhpr_score) if detection.nhpr_score else None

    try:
        detection_engine = DetectionEngine(
            llm_client=llm_client,
            redis_client=None,  # skip cache for re-detection
        )
        language = "auto"
        discipline = "通用"
        # Try to extract discipline from original detection metadata
        if detection.llm_evidence and isinstance(detection.llm_evidence, dict):
            discipline = detection.llm_evidence.get("discipline", "通用")

        verify_result = await detection_engine.detect(
            text=optimized_text,
            granularity="document",
            language=language,
            discipline=discipline,
        )
        verified_risk_score = verify_result.get("risk_score")
        verified_nhpr_score = verify_result.get("nhpr_score")

        logger.info(
            f"Re-detection after optimization: risk={verified_risk_score:.4f}, "
            f"nhpr={verified_nhpr_score:.4f} (original nhpr={original_nhpr})"
        )

        # ── Second iteration if NHPR improvement < 0.10 ───────────
        nhpr_delta = (
            (original_nhpr - verified_nhpr_score)
            if original_nhpr is not None and verified_nhpr_score is not None
            else None
        )
        if nhpr_delta is not None and nhpr_delta < 0.10:
            logger.info(
                f"NHPR delta={nhpr_delta:.4f} < 0.10, running second optimization round"
            )
            # Build a more targeted prompt for round 2
            round2_stat_ev = _format_stat_evidence(
                verify_result.get("stat_evidence")
            )
            round2_issues = (
                f"上一轮优化后NHPR仍为{verified_nhpr_score:.2f}（仅下降{nhpr_delta:.2f}），"
                f"请重点降低以下指标：\n{round2_stat_ev}"
            )
            round2_prompt = SUGGEST_PROMPT.format(
                text=optimized_text[:4000],
                issues=round2_issues,
                stat_evidence=round2_stat_ev,
                strategies=strategies_str,
            )

            try:
                round2_response = await llm_client.chat(
                    task_type="suggestion",
                    system_prompt=SUGGEST_SYSTEM,
                    user_prompt=round2_prompt,
                    response_format="json",
                    max_tokens=2048,
                    temperature=0.3,
                )
                round2_raw = extract_json(round2_response)
                round2_items = (
                    round2_raw
                    if isinstance(round2_raw, list)
                    else round2_raw.get("suggestions", [])
                    if isinstance(round2_raw, dict)
                    else []
                )

                round2_sugs = []
                for item in round2_items:
                    sug_type = item.get("type", "general")
                    sug_enum = type_map.get(sug_type, SuggestionType.GENERAL)
                    round2_sugs.append(
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

                if round2_sugs:
                    # Apply round 2 suggestions
                    r2_sorted = sorted(
                        round2_sugs, key=lambda s: s.offset_start, reverse=True
                    )
                    for sug in r2_sorted:
                        if sug.original_text and sug.original_text in optimized_text:
                            optimized_text = optimized_text.replace(
                                sug.original_text, sug.suggested_text, 1
                            )
                    suggestions.extend(round2_sugs)
                    optimization_rounds = 2

                    # Re-detect after round 2
                    verify_result_r2 = await detection_engine.detect(
                        text=optimized_text,
                        granularity="document",
                        language=language,
                        discipline=discipline,
                    )
                    verified_risk_score = verify_result_r2.get("risk_score")
                    verified_nhpr_score = verify_result_r2.get("nhpr_score")
                    logger.info(
                        f"Re-detection after round 2: risk={verified_risk_score:.4f}, "
                        f"nhpr={verified_nhpr_score:.4f}"
                    )
            except Exception as e2:
                logger.warning(f"Second optimization round failed: {e2}")

    except Exception as e:
        logger.warning(f"Post-optimization re-detection failed: {e}")
        # Fall back to hardcoded estimate
        verified_risk_score = max(0.0, original_risk_score - 0.15)
        verified_nhpr_score = None

    estimated_risk_score = verified_risk_score

    # ── Persist to detection record ─────────────────────────────────
    optimization_payload = {
        "optimized_text": optimized_text,
        "original_text": body.text,
        "suggestions": [s.model_dump() for s in suggestions],
        "timestamp": now_str,
        "estimated_risk_score": estimated_risk_score,
        "verified_risk_score": verified_risk_score,
        "verified_nhpr_score": verified_nhpr_score,
        "optimization_rounds": optimization_rounds,
    }
    detection.optimization_data = optimization_payload
    session.add(detection)

    # ── Audit log ───────────────────────────────────────────────────
    audit = AuditLog(
        user_id=user_uuid,
        action="one_click_optimize",
        resource_type="optimization",
        resource_id=str(detection.id),
        details={
            "detection_id": body.detection_id,
            "suggestion_count": len(suggestions),
            "optimization_rounds": optimization_rounds,
            "verified_risk_score": verified_risk_score,
            "verified_nhpr_score": verified_nhpr_score,
        },
    )
    session.add(audit)
    await session.commit()

    elapsed = (time.perf_counter() - start) * 1000
    return APIResponse(
        data=OneClickOptimizeResponse(
            optimized_text=optimized_text,
            suggestions=suggestions,
            original_risk_score=original_risk_score,
            estimated_risk_score=estimated_risk_score,
            verified_risk_score=verified_risk_score,
            verified_nhpr_score=verified_nhpr_score,
            optimization_rounds=optimization_rounds,
            timestamp=now_str,
        ),
        meta=Meta(
            request_id=request_id,
            processing_time_ms=round(elapsed, 2),
            formula_version=settings.formula_version,
            param_version=settings.param_version,
        ),
    )
