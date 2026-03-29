"""
检测引擎主入口
编排预处理→LLM评议→统计分析→证据融合→报告生成完整流水线
"""

import json
from app.utils.json_extract import extract_json
import time
import logging
from typing import Optional
from uuid import UUID

from .preprocessor import TextPreprocessor, ProcessedText
from .stats import LightweightStatsCalculator
from .fusion import EvidenceFusion, FormulaParams, FusionResult
from ..llm_gateway.client import LLMClient

logger = logging.getLogger(__name__)


class DetectionEngine:
    """
    ScholarGuard 检测引擎

    流水线：
    1. 预处理 → ProcessedText
    2. E1: LLM评议 → 主评议Agent结果
    3. E2: 统计因子 → 轻量统计证据
    4. 证据融合 → RiskScore + 风险等级
    5. 解释报告 → 人类可读报告
    """

    def __init__(
        self,
        llm_client: LLMClient,
        formula_params: Optional[FormulaParams] = None,
    ):
        self.preprocessor = TextPreprocessor()
        self.stats_calculator = LightweightStatsCalculator()
        self.fusion = EvidenceFusion(params=formula_params)
        self.llm_client = llm_client

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

        # ===== 2. E1: LLM评议 =====
        llm_evidence = await self._run_llm_review(
            processed, discipline, model_override
        )

        # ===== 3. E2: 统计因子 =====
        stat_evidence = self.stats_calculator.compute(
            sentences=processed.sentences,
            paragraphs=processed.paragraphs,
            full_text=processed.full_text,
            language=processed.language,
        )

        # ===== 4. 证据融合 =====
        # 从LLM评议结果中提取风险置信度
        llm_confidence = self._extract_llm_confidence(llm_evidence)

        fusion_result = self.fusion.fuse(
            llm_confidence=llm_confidence,
            llm_risk_indicators=llm_evidence,
            stat_score=stat_evidence.stat_score,
        )

        # ===== 5. 解释报告 =====
        report = await self._generate_report(
            llm_evidence, stat_evidence, fusion_result, model_override
        )

        # ===== 6. 段落级热力图（如需要）=====
        paragraph_heatmap = None
        if granularity in ("paragraph", "document") and len(processed.paragraphs) > 1:
            paragraph_heatmap = await self._generate_heatmap(
                processed.paragraphs, model_override
            )

        # ===== 组装最终结果 =====
        processing_time_ms = int((time.time() - start_time) * 1000)

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
            # 段落热力图
            "paragraph_heatmap": paragraph_heatmap,
            # 版本冻结
            "formula_version": fusion_result.formula_version,
            "param_version": fusion_result.param_version,
            "model_version": self.llm_client.get_current_model("detection"),
            "formula_params": fusion_result.formula_params_snapshot,
            # 元数据
            "processing_time_ms": processing_time_ms,
        }

        logger.info(
            f"检测完成：risk_score={fusion_result.risk_score:.3f}, "
            f"risk_level={fusion_result.risk_level}, "
            f"耗时={processing_time_ms}ms"
        )

        return result

    async def _run_llm_review(
        self,
        processed: ProcessedText,
        discipline: str,
        model_override: Optional[str],
    ) -> dict:
        """调用LLM主评议Agent"""
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
            )
            result = extract_json(response)
            if result is None:
                logger.warning(f"LLM评议JSON提取失败，原始响应前200字: {response[:200]}")
                raise ValueError("无法从LLM响应中提取JSON")
            return result
        except Exception as e:
            logger.error(f"LLM评议解析失败: {e}")
            # 返回保守的默认结果
            return {
                "llm_confidence": 0.5,
                "risk_level": "medium",
                "dimension_scores": {
                    "vocabulary_diversity": 5,
                    "syntactic_variation": 5,
                    "argumentation_naturalness": 5,
                },
                "source_classification": {
                    "human_original": 0.5,
                    "ai_generated": 0.25,
                    "ai_human_edited": 0.15,
                    "humanizer_processed": 0.10,
                },
                "pattern_flags": {},
                "flagged_segments": [],
                "reasoning": f"LLM评议异常，使用默认保守判断: {str(e)}",
                "uncertainty_notes": "由于LLM评议过程出现异常，结果不确定性较高，强烈建议人工复核。",
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

        # 取两者的加权平均
        return 0.6 * ai_prob + 0.4 * (1 - direct_confidence) \
            if direct_confidence < 0.5 else 0.6 * ai_prob + 0.4 * direct_confidence

    async def _generate_report(
        self,
        llm_evidence: dict,
        stat_evidence,
        fusion_result: FusionResult,
        model_override: Optional[str],
    ) -> dict:
        """调用解释Agent生成报告"""
        from app.prompts.detection.primary_review_compact import (
            EXPLANATION_PROMPT_COMPACT,
        )

        # 压缩LLM证据为简要描述
        llm_brief = json.dumps({
            "risk_level": llm_evidence.get("risk_level", "medium"),
            "source": llm_evidence.get("source_classification", {}),
            "reasoning": str(llm_evidence.get("reasoning", ""))[:100],
        }, ensure_ascii=False)

        prompt = EXPLANATION_PROMPT_COMPACT.format(
            risk_score=f"{fusion_result.risk_score:.4f}",
            llm_evidence_brief=llm_brief,
            stat_evidence=json.dumps(stat_evidence.to_dict(), ensure_ascii=False),
        )

        try:
            response = await self.llm_client.chat(
                task_type="detection",
                system_prompt="你是学术风险报告撰写专家。只输出JSON。",
                user_prompt=prompt,
                model_override=model_override,
                response_format="json",
            )
            result = extract_json(response)
            if result is None:
                raise ValueError("无法从报告响应中提取JSON")
            return result
        except Exception as e:
            logger.error(f"报告生成失败: {e}")
            return {
                "risk_summary": f"风险等级：{fusion_result.risk_level}（报告生成异常，请参考数值指标）",
                "evidence_for": [],
                "evidence_against": [],
                "uncertainty_disclaimer": "报告生成过程出现异常，建议人工复核。",
                "recommended_actions": ["建议人工复核检测结果"],
                "review_suggested": True,
                "review_reason": "报告生成异常",
            }

    async def _generate_heatmap(
        self,
        paragraphs: list[str],
        model_override: Optional[str],
    ) -> list[dict]:
        """生成段落级热力图"""
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
