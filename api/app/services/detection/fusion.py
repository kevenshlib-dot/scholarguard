"""
证据融合器
将多源证据（E1:LLM, E2:统计, E3:材料, E4:人工）加权融合，计算RiskScore

公式：
RiskScore = w1×LLMConfidence + w2×StatScore + w3×SemanticConsistencyGap
          + w4×MaterialMismatch - w5×HumanEvidenceCredit

ReviewPriority = a×RiskScore + b×Uncertainty + c×EvidenceInsufficiency
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
import json


@dataclass
class FormulaParams:
    """公式参数（可配置、可版本化）"""
    version: str = "v1.3"
    # RiskScore 权重
    w1: float = 0.70   # LLM评议权重
    w2: float = 0.20   # 统计特征权重
    w3: float = 0.00   # 语义一致性差异（一期未启用）
    w4: float = 0.00   # 材料不匹配度（一期未启用）
    w5: float = 0.10   # 人工证据信用
    # ReviewPriority 权重
    a: float = 0.50
    b: float = 0.30
    c: float = 0.20
    # 风险等级阈值（v1.3：上移阈值以减少学术写作误报）
    threshold_low: float = 0.45     # <0.45 = low（人类文本典型区间0.20-0.40）
    threshold_medium: float = 0.60  # 0.45-0.60 = medium
    threshold_high: float = 0.75    # 0.60-0.75 = high, >0.75 = critical

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "w1": self.w1, "w2": self.w2, "w3": self.w3,
            "w4": self.w4, "w5": self.w5,
            "a": self.a, "b": self.b, "c": self.c,
            "threshold_low": self.threshold_low,
            "threshold_medium": self.threshold_medium,
            "threshold_high": self.threshold_high,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "FormulaParams":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class FusionResult:
    """融合计算结果"""
    risk_score: float
    risk_level: str
    review_priority: float
    evidence_completeness: int       # 已启用的证据层数 (1-4)
    conclusion_type: str             # preliminary / fused / human_confirmed
    formula_version: str
    param_version: str
    formula_params_snapshot: dict
    nhpr_score: float = 0.0
    nhpr_level: str = "low"

    def to_dict(self) -> dict:
        return {
            "risk_score": round(self.risk_score, 4),
            "risk_level": self.risk_level,
            "review_priority": round(self.review_priority, 4),
            "evidence_completeness": self.evidence_completeness,
            "conclusion_type": self.conclusion_type,
            "formula_version": self.formula_version,
            "param_version": self.param_version,
            "nhpr_score": round(self.nhpr_score, 4),
            "nhpr_level": self.nhpr_level,
        }


class EvidenceFusion:
    """证据融合器"""

    FORMULA_VERSION = "v1.1"

    def __init__(self, params: Optional[FormulaParams] = None):
        self.params = params or FormulaParams()

    def fuse(
        self,
        llm_confidence: float,
        llm_risk_indicators: dict,
        stat_score: Optional[float] = None,
        semantic_gap: Optional[float] = None,
        material_mismatch: Optional[float] = None,
        human_credit: Optional[float] = None,
    ) -> FusionResult:
        """
        执行证据融合计算

        Args:
            llm_confidence: LLM评议的风险置信度 (0-1, 越高表示越可能是AI)
            llm_risk_indicators: LLM评议的详细指标字典
            stat_score: 统计特征分 (0-1, 越高越可疑)
            semantic_gap: 语义一致性差异 (0-1, 预留)
            material_mismatch: 材料不匹配度 (0-1, 预留)
            human_credit: 人工证据信用 (0-1, 有人工确认时给予减分)
        """
        p = self.params

        # 计算已启用的证据层数
        evidence_completeness = 1  # E1 (LLM) 总是启用
        if stat_score is not None:
            evidence_completeness += 1
        if semantic_gap is not None:
            evidence_completeness += 1
        if human_credit is not None:
            evidence_completeness += 1

        # 确定结论类型
        if human_credit is not None and human_credit > 0:
            conclusion_type = "human_confirmed"
        elif evidence_completeness >= 2:
            conclusion_type = "fused"
        else:
            conclusion_type = "preliminary"

        # === RiskScore 计算 ===
        risk_score = p.w1 * llm_confidence

        if stat_score is not None:
            risk_score += p.w2 * stat_score
        # else: w2项为0（未启用）

        if semantic_gap is not None:
            risk_score += p.w3 * semantic_gap

        if material_mismatch is not None:
            risk_score += p.w4 * material_mismatch

        if human_credit is not None:
            risk_score -= p.w5 * human_credit

        # 限制在 [0, 1] 范围
        risk_score = max(0.0, min(1.0, risk_score))

        # === 风险等级 ===
        risk_level = self._classify_risk(risk_score)

        # === ReviewPriority 计算 ===
        # Uncertainty: 基于LLM置信度的反面
        uncertainty = self._compute_uncertainty(llm_confidence, llm_risk_indicators)
        # EvidenceInsufficiency: 基于缺失的证据层
        evidence_insufficiency = 1.0 - (evidence_completeness / 4.0)

        review_priority = (
            p.a * risk_score
            + p.b * uncertainty
            + p.c * evidence_insufficiency
        )
        review_priority = max(0.0, min(1.0, review_priority))

        return FusionResult(
            risk_score=risk_score,
            risk_level=risk_level,
            review_priority=review_priority,
            evidence_completeness=evidence_completeness,
            conclusion_type=conclusion_type,
            formula_version=self.FORMULA_VERSION,
            param_version=self.params.version,
            formula_params_snapshot=self.params.to_dict(),
        )

    def _classify_risk(self, risk_score: float) -> str:
        """根据阈值分类风险等级"""
        p = self.params
        if risk_score < p.threshold_low:
            return "low"
        elif risk_score < p.threshold_medium:
            return "medium"
        elif risk_score < p.threshold_high:
            return "high"
        else:
            return "critical"

    def _compute_uncertainty(self, llm_confidence: float,
                             risk_indicators: dict) -> float:
        """
        计算不确定性
        当LLM不太确定、或各维度判断不一致时，不确定性高
        """
        # 基础不确定性：LLM置信度低 → 不确定性高
        base_uncertainty = 1.0 - llm_confidence

        # 维度一致性：检查source_classification中概率的离散度
        source_probs = risk_indicators.get("source_classification", {})
        if source_probs:
            probs = list(source_probs.values())
            max_prob = max(probs) if probs else 0.5
            # 如果最高概率不突出（<0.5），说明分类不确定
            classification_uncertainty = 1.0 - max_prob
        else:
            classification_uncertainty = 0.5

        # 综合不确定性
        uncertainty = 0.6 * base_uncertainty + 0.4 * classification_uncertainty
        return max(0.0, min(1.0, uncertainty))

    def update_with_human_review(
        self,
        original_result: FusionResult,
        human_credit: float,
        adjusted_risk_level: Optional[str] = None,
    ) -> FusionResult:
        """
        人工复核后更新融合结果

        Args:
            original_result: 原始融合结果
            human_credit: 人工给予的信用分 (0-1)
            adjusted_risk_level: 人工调整后的风险等级（可选）
        """
        # 重新计算风险分（减去人工信用）
        new_risk_score = original_result.risk_score - self.params.w5 * human_credit
        new_risk_score = max(0.0, min(1.0, new_risk_score))

        risk_level = adjusted_risk_level or self._classify_risk(new_risk_score)

        return FusionResult(
            risk_score=new_risk_score,
            risk_level=risk_level,
            review_priority=0.0,  # 已复核，优先级归零
            evidence_completeness=original_result.evidence_completeness + 1,
            conclusion_type="human_confirmed",
            formula_version=original_result.formula_version,
            param_version=original_result.param_version,
            formula_params_snapshot=original_result.formula_params_snapshot,
        )
