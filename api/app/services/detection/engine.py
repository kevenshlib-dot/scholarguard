"""
检测引擎主入口
编排预处理→LLM评议→统计分析→证据融合→报告生成完整流水线

v2.0 性能优化：
- 合并LLM评议+报告为单次调用（省去~20-30s）
- 热力图改为延迟生成（不在主流程中）
- Redis缓存检测结果（24h TTL）
- 优化LLM参数（低温度、缩减max_tokens）
"""

import json
from app.utils.json_extract import extract_json
import time
import logging
from typing import Optional

from .preprocessor import TextPreprocessor, ProcessedText
from .stats import LightweightStatsCalculator
from .fusion import EvidenceFusion, FormulaParams, FusionResult
from ..llm_gateway.client import LLMClient

logger = logging.getLogger(__name__)

# Redis缓存TTL（秒）= 24小时
CACHE_TTL_SECONDS = 86400


class DetectionEngine:
    """
    ScholarGuard 检测引擎 v2.0

    流水线（优化后）：
    1. 预处理 → ProcessedText
    2. 缓存检查 → 命中则直接返回
    3. E1+报告: 单次LLM调用 → 评议结果 + 报告
    4. E2: 统计因子 → 轻量统计证据
    5. 证据融合 → RiskScore + 风险等级
    6. 组装结果 + 写入缓存
    （热力图不在主流程，改为按需生成）
    """

    def __init__(
        self,
        llm_client: LLMClient,
        formula_params: Optional[FormulaParams] = None,
        redis_client=None,
    ):
        self.preprocessor = TextPreprocessor()
        self.stats_calculator = LightweightStatsCalculator()
        self.fusion = EvidenceFusion(params=formula_params)
        self.llm_client = llm_client
        self.redis = redis_client  # Optional[redis.asyncio.Redis]

    async def detect(
        self,
        text: str,
        granularity: str = "document",
        language: str = "auto",
        discipline: str = "通用",
        model_override: Optional[str] = None,
    ) -> dict:
        """
        执行完整检测流程

        Args:
            text: 待检测文本
            granularity: 检测粒度 (document/paragraph/sentence)
            language: 语言 (zh/en/auto)
            discipline: 学科 (政治学/经济学/社会学/法学/通用)
            model_override: 指定使用的模型（可选）

        Returns:
            完整检测结果字典
        """
        start_time = time.time()

        # ===== 1. 预处理 =====
        logger.info(f"开始检测，粒度={granularity}，学科={discipline}")
        processed = self.preprocessor.process(text, language)
        logger.info(
            f"预处理完成：{processed.word_count}字，"
            f"{len(processed.paragraphs)}段，{len(processed.sentences)}句"
        )

        # ===== 2. 缓存检查（缓存 key 包含模型，模型切换后不命中旧缓存）=====
        current_model = self.llm_client.get_current_model("detection")
        cache_key_suffix = f"{processed.content_hash}:{current_model}"
        cached = await self._get_cached_result(cache_key_suffix)
        if cached is not None:
            cached["processing_time_ms"] = int((time.time() - start_time) * 1000)
            cached["cache_hit"] = True
            logger.info(
                f"缓存命中：content_hash={processed.content_hash[:16]}..., "
                f"model={current_model}，耗时={cached['processing_time_ms']}ms"
            )
            return cached

        # ===== 3. E1+报告: 单次合并LLM调用 =====
        llm_result = await self._run_merged_llm_review(
            processed, discipline, model_override
        )
        llm_evidence = llm_result["evidence"]
        report = llm_result["report"]
        llm_failed = llm_result.get("llm_failed", False)

        # ===== 4. E2: 统计因子 =====
        stat_evidence = self.stats_calculator.compute(
            sentences=processed.sentences,
            paragraphs=processed.paragraphs,
            full_text=processed.full_text,
            language=processed.language,
        )

        # ===== 5. 证据融合 =====
        processing_time_ms = int((time.time() - start_time) * 1000)

        # 热力图改为延迟生成
        has_paragraphs = (
            granularity in ("paragraph", "document")
            and len(processed.paragraphs) > 1
        )

        if llm_failed:
            # LLM 不可用：所有评分归零，不做融合计算，避免误导
            logger.warning("LLM 调用失败，所有评分归零")
            result = {
                "content_hash": processed.content_hash,
                "word_count": processed.word_count,
                "language": processed.language,
                "granularity": granularity,
                # 风险评分 — 全部归零
                "risk_score": 0.0,
                "risk_level": "unknown",
                "llm_confidence": 0.0,
                "stat_score": 0.0,
                "evidence_completeness": 0,
                "review_priority": 0.0,
                "conclusion_type": "error",
                # 证据详情
                "llm_evidence": llm_evidence,
                "stat_evidence": stat_evidence.to_dict(),
                "material_evidence": None,
                "human_evidence": None,
                # 报告
                "report_content": report,
                "flagged_segments": [],
                "recommendations": report.get("recommended_actions", []),
                "uncertainty_notes": report.get("uncertainty_disclaimer", ""),
                # 段落热力图 — 不生成
                "paragraph_heatmap": None,
                "heatmap_status": "not_requested",
                # 版本冻结
                "formula_version": self.fusion.FORMULA_VERSION,
                "param_version": self.fusion.params.version,
                "model_version": self.llm_client.get_current_model("detection"),
                "formula_params": None,
                # 元数据
                "processing_time_ms": processing_time_ms,
                "cache_hit": False,
            }
        else:
            # 正常流程：融合评分
            llm_confidence = self._extract_llm_confidence(llm_evidence)

            fusion_result = self.fusion.fuse(
                llm_confidence=llm_confidence,
                llm_risk_indicators=llm_evidence,
                stat_score=stat_evidence.stat_score,
            )

            # ===== 6. 组装最终结果（无热力图） =====
            result = {
                "content_hash": processed.content_hash,
                "word_count": processed.word_count,
                "language": processed.language,
                "granularity": granularity,
                # 风险评分体系
                "risk_score": fusion_result.risk_score,
                "risk_level": fusion_result.risk_level,
                "llm_confidence": llm_confidence,
                "stat_score": stat_evidence.stat_score,
                "evidence_completeness": fusion_result.evidence_completeness,
                "review_priority": fusion_result.review_priority,
                "conclusion_type": fusion_result.conclusion_type,
                # 证据详情
                "llm_evidence": llm_evidence,
                "stat_evidence": stat_evidence.to_dict(),
                "material_evidence": None,   # 一期预留
                "human_evidence": None,      # 一期预留
                # 报告
                "report_content": report,
                "flagged_segments": llm_evidence.get("flagged_segments", []),
                "recommendations": report.get("recommended_actions", []),
                "uncertainty_notes": report.get("uncertainty_disclaimer", ""),
                # 段落热力图 — 延迟生成
                "paragraph_heatmap": None,
                "heatmap_status": "pending" if has_paragraphs else "not_requested",
                # 版本冻结
                "formula_version": fusion_result.formula_version,
                "param_version": fusion_result.param_version,
                "model_version": self.llm_client.get_current_model("detection"),
                "formula_params": fusion_result.formula_params_snapshot,
                # 元数据
                "processing_time_ms": processing_time_ms,
                "cache_hit": False,
            }

        # ===== 7. 写入缓存（key 包含模型，切换模型不命中旧缓存）=====
        await self._set_cached_result(cache_key_suffix, result)

        logger.info(
            f"检测完成：risk_score={result['risk_score']:.3f}, "
            f"risk_level={result['risk_level']}, "
            f"耗时={processing_time_ms}ms"
        )

        return result

    async def _run_merged_llm_review(
        self,
        processed: ProcessedText,
        discipline: str,
        model_override: Optional[str],
    ) -> dict:
        """
        单次合并LLM调用：评议 + 报告

        返回 {"evidence": {...}, "report": {...}}
        """
        from app.prompts.detection.primary_review_compact import (
            PRIMARY_REVIEW_SYSTEM_COMPACT as PRIMARY_REVIEW_SYSTEM,
            PRIMARY_REVIEW_PROMPT_COMPACT as PRIMARY_REVIEW_PROMPT,
        )

        prompt = PRIMARY_REVIEW_PROMPT.format(
            text=processed.full_text[:4000],  # 限制输入长度
        )

        try:
            response = await self.llm_client.chat(
                task_type="detection",
                system_prompt=PRIMARY_REVIEW_SYSTEM,
                user_prompt=prompt,
                model_override=model_override,
                response_format="json",
                max_tokens=2048,      # 从4096降低：合并后JSON约500-800 tokens
                temperature=0.1,      # 低温度：更确定性 = 更快收敛
            )
            raw = extract_json(response)
            if raw is None:
                logger.warning(
                    f"合并LLM评议JSON提取失败，响应长度={len(response)}，"
                    f"前200字: {response[:200]}，"
                    f"后100字: {response[-100:]}"
                )
                raise ValueError("无法从LLM响应中提取JSON")

            # 将短字段名映射回标准字段名
            return self._unpack_merged_response(raw)

        except Exception as e:
            logger.error(f"合并LLM评议解析失败: {e}")
            return self._default_merged_result(str(e))

    def _unpack_merged_response(self, raw: dict) -> dict:
        """
        将合并prompt的短字段名解包为标准格式

        短字段名映射：
        conf → llm_confidence, lvl → risk_level
        dim.vd/sv/an → dimension_scores
        src → source_classification
        flags → pattern_flags
        segs → flagged_segments
        rpt → report
        """
        # 兼容：如果LLM返回了完整字段名（旧格式），直接使用
        if "llm_confidence" in raw and "report_content" not in raw:
            # 旧格式但没有report — 不太可能，走标准解包
            pass

        # 解包 evidence 部分
        dim = raw.get("dim", {})
        src = raw.get("src", {})
        flags = raw.get("flags", {})
        segs = raw.get("segs", [])

        evidence = {
            "llm_confidence": raw.get("conf", raw.get("llm_confidence", 0.5)),
            "risk_level": raw.get("lvl", raw.get("risk_level", "medium")),
            "dimension_scores": {
                "vocabulary_diversity": dim.get("vd", dim.get("vocabulary_diversity", 5)),
                "syntactic_variation": dim.get("sv", dim.get("syntactic_variation", 5)),
                "argumentation_naturalness": dim.get("an", dim.get("argumentation_naturalness", 5)),
            },
            "source_classification": {
                "human_original": src.get("human", src.get("human_original", 0.5)),
                "ai_generated": src.get("ai", src.get("ai_generated", 0.25)),
                "ai_human_edited": src.get("edited", src.get("ai_human_edited", 0.15)),
                "humanizer_processed": src.get("humanizer", src.get("humanizer_processed", 0.10)),
            },
            "pattern_flags": {
                "logical_connector_density": flags.get("lcd", flags.get("logical_connector_density", 0)),
                "sentence_length_uniformity": flags.get("slu", flags.get("sentence_length_uniformity", 0)),
                "terminology_stacking": flags.get("ts", flags.get("terminology_stacking", 0)),
            },
            "flagged_segments": [
                {
                    "start_char": seg.get("s", seg.get("start_char", 0)),
                    "end_char": seg.get("e", seg.get("end_char", 0)),
                    "text_snippet": seg.get("t", seg.get("text_snippet", "")),
                    "issue": seg.get("i", seg.get("issue", "")),
                }
                for seg in segs
            ],
            "reasoning": raw.get("reason", raw.get("reasoning", "")),
            "uncertainty_notes": raw.get("unc", raw.get("uncertainty_notes", "")),
        }

        # 解包 report 部分
        rpt = raw.get("rpt", {})
        report = {
            "risk_summary": rpt.get("summary", rpt.get("risk_summary", "")),
            "evidence_for": rpt.get("for", rpt.get("evidence_for", [])),
            "evidence_against": rpt.get("against", rpt.get("evidence_against", [])),
            "uncertainty_disclaimer": rpt.get("disclaimer", rpt.get("uncertainty_disclaimer", "")),
            "recommended_actions": rpt.get("actions", rpt.get("recommended_actions", [])),
            "review_suggested": rpt.get("review", rpt.get("review_suggested", False)),
            "review_reason": rpt.get("review_why", rpt.get("review_reason", None)),
        }

        return {"evidence": evidence, "report": report}

    def _default_merged_result(self, error_msg: str) -> dict:
        """LLM调用失败时的降级结果 — 所有评分归零，明确标记异常"""
        return {
            "llm_failed": True,
            "evidence": {
                "llm_confidence": 0.0,
                "risk_level": "unknown",
                "dimension_scores": {
                    "vocabulary_diversity": 0,
                    "syntactic_variation": 0,
                    "argumentation_naturalness": 0,
                },
                "source_classification": {
                    "human_original": 0.0,
                    "ai_generated": 0.0,
                    "ai_human_edited": 0.0,
                    "humanizer_processed": 0.0,
                },
                "pattern_flags": {},
                "flagged_segments": [],
                "reasoning": f"LLM 模型调用失败，无法进行 AI 内容分析: {error_msg}",
                "uncertainty_notes": "LLM 模型不可用，检测未能完成，所有评分无效。请检查模型服务后重新检测。",
            },
            "report": {
                "risk_summary": "检测未完成：LLM 模型服务不可用，无法给出任何评估结论。",
                "evidence_for": [],
                "evidence_against": [],
                "uncertainty_disclaimer": "LLM 模型调用失败，本次检测结果无效，请排查模型服务后重新提交检测。",
                "recommended_actions": [
                    "检查 LLM 模型服务是否正常运行",
                    "确认 vLLM/Ollama 服务地址和端口可达",
                    "待模型服务恢复后重新提交检测",
                ],
                "review_suggested": False,
                "review_reason": f"LLM评议失败: {error_msg}",
            },
        }

    def _extract_llm_confidence(self, llm_evidence: dict) -> float:
        """从LLM评议结果中提取风险置信度（注意：这里的confidence表示"有多确定文本是AI的"）"""
        # 直接使用LLM返回的confidence
        direct_confidence = llm_evidence.get("llm_confidence", 0.5)

        # 补充：基于source_classification推算
        source = llm_evidence.get("source_classification", {})
        ai_prob = (
            source.get("ai_generated", 0.25)
            + source.get("ai_human_edited", 0.15) * 0.7
            + source.get("humanizer_processed", 0.1) * 0.5
        )

        # 取两者的加权平均，并限制在 [0, 1] 范围内
        raw = 0.6 * ai_prob + 0.4 * (1 - direct_confidence) \
            if direct_confidence < 0.5 else 0.6 * ai_prob + 0.4 * direct_confidence
        return max(0.0, min(1.0, raw))

    # ── 热力图：延迟生成（独立接口调用） ──────────────────────────────

    async def generate_heatmap(
        self,
        paragraphs: list[str],
        model_override: Optional[str] = None,
    ) -> list[dict]:
        """
        生成段落级热力图（从主流程移出，改为按需调用）

        调用方式：
        - 通过 /detect/{task_id}/heatmap 端点触发
        - 或在后台任务中异步执行
        """
        from app.prompts.explanation.report_generator import PARAGRAPH_HEATMAP_PROMPT

        paragraphs_json = json.dumps(
            [{"index": i, "text": p[:200]} for i, p in enumerate(paragraphs)],
            ensure_ascii=False,
        )
        prompt = PARAGRAPH_HEATMAP_PROMPT.format(paragraphs_json=paragraphs_json)

        try:
            response = await self.llm_client.chat(
                task_type="detection",
                system_prompt="你是段落风险标注专家。",
                user_prompt=prompt,
                model_override=model_override,
                response_format="json",
                max_tokens=1024,
                temperature=0.1,
            )
            result = extract_json(response)
            if result is None:
                raise ValueError("无法从热力图响应中提取JSON")
            return result.get("paragraphs", [])
        except Exception as e:
            logger.warning(f"热力图生成失败: {e}")
            return [
                {"index": i, "risk": "medium", "brief_reason": "无法评估"}
                for i in range(len(paragraphs))
            ]

    # ── Redis 缓存 ──────────────────────────────────────────────────

    async def _get_cached_result(self, content_hash: str) -> Optional[dict]:
        """从Redis获取缓存的检测结果"""
        if self.redis is None:
            return None
        try:
            cache_key = f"sg:detect:{content_hash}"
            cached = await self.redis.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Redis缓存读取失败: {e}")
        return None

    async def _set_cached_result(self, content_hash: str, result: dict) -> None:
        """将检测结果写入Redis缓存"""
        if self.redis is None:
            return
        try:
            cache_key = f"sg:detect:{content_hash}"
            # 序列化时处理不可JSON化的字段
            serializable = json.dumps(result, ensure_ascii=False, default=str)
            await self.redis.set(cache_key, serializable, ex=CACHE_TTL_SECONDS)
            logger.debug(f"检测结果已缓存: {cache_key}")
        except Exception as e:
            logger.warning(f"Redis缓存写入失败: {e}")
