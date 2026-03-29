"""
ScholarGuard 评测指标体系
支持分场景、分版本的可复现评测
"""

from dataclasses import dataclass, field
from typing import Optional
import json
import time


@dataclass
class EvalResult:
    """单次评测运行结果"""
    # 版本信息
    eval_id: str
    dataset_version: str
    formula_version: str
    param_version: str
    model_version: str
    prompt_version: str
    timestamp: float = field(default_factory=time.time)

    # 整体指标
    total_samples: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    false_positive_rate: float = 0.0
    false_negative_rate: float = 0.0

    # 分学科指标
    discipline_metrics: dict = field(default_factory=dict)

    # 分来源类型指标
    source_type_metrics: dict = field(default_factory=dict)

    # 混淆矩阵
    confusion_matrix: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "eval_id": self.eval_id,
            "dataset_version": self.dataset_version,
            "formula_version": self.formula_version,
            "param_version": self.param_version,
            "model_version": self.model_version,
            "prompt_version": self.prompt_version,
            "timestamp": self.timestamp,
            "total_samples": self.total_samples,
            "overall": {
                "precision": round(self.precision, 4),
                "recall": round(self.recall, 4),
                "f1": round(self.f1, 4),
                "false_positive_rate": round(self.false_positive_rate, 4),
                "false_negative_rate": round(self.false_negative_rate, 4),
            },
            "by_discipline": self.discipline_metrics,
            "by_source_type": self.source_type_metrics,
            "confusion_matrix": self.confusion_matrix,
        }

    def save(self, path: str):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)


def compute_metrics(
    predictions: list[dict],
    threshold: float = 0.5,
) -> dict:
    """
    计算评测指标

    Args:
        predictions: 列表，每项包含:
            - ground_truth: "human" 或 "ai"
            - risk_score: 0-1 的风险分
            - discipline: 学科（可选）
            - source_type: 来源类型（可选）
        threshold: 判定阈值（risk_score > threshold 则判为 AI）

    Returns:
        包含各项指标的字典
    """
    tp = fp = tn = fn = 0

    discipline_stats = {}
    source_stats = {}

    for pred in predictions:
        truth = pred["ground_truth"]
        score = pred["risk_score"]
        is_ai_truth = truth == "ai"
        is_ai_pred = score > threshold

        # 混淆矩阵
        if is_ai_truth and is_ai_pred:
            tp += 1
        elif not is_ai_truth and is_ai_pred:
            fp += 1
        elif not is_ai_truth and not is_ai_pred:
            tn += 1
        else:
            fn += 1

        # 分学科统计
        disc = pred.get("discipline", "unknown")
        if disc not in discipline_stats:
            discipline_stats[disc] = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
        d = discipline_stats[disc]
        if is_ai_truth and is_ai_pred:
            d["tp"] += 1
        elif not is_ai_truth and is_ai_pred:
            d["fp"] += 1
        elif not is_ai_truth and not is_ai_pred:
            d["tn"] += 1
        else:
            d["fn"] += 1

        # 分来源类型统计
        src = pred.get("source_type", "unknown")
        if src not in source_stats:
            source_stats[src] = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
        s = source_stats[src]
        if is_ai_truth and is_ai_pred:
            s["tp"] += 1
        elif not is_ai_truth and is_ai_pred:
            s["fp"] += 1
        elif not is_ai_truth and not is_ai_pred:
            s["tn"] += 1
        else:
            s["fn"] += 1

    # 计算整体指标
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    fnr = fn / (fn + tp) if (fn + tp) > 0 else 0.0

    # 分学科指标
    disc_metrics = {}
    for disc, stats in discipline_stats.items():
        p = stats["tp"] / (stats["tp"] + stats["fp"]) if (stats["tp"] + stats["fp"]) > 0 else 0.0
        r = stats["tp"] / (stats["tp"] + stats["fn"]) if (stats["tp"] + stats["fn"]) > 0 else 0.0
        disc_metrics[disc] = {
            "precision": round(p, 4),
            "recall": round(r, 4),
            "f1": round(2 * p * r / (p + r) if (p + r) > 0 else 0.0, 4),
            "samples": sum(stats.values()),
        }

    # 分来源类型指标
    src_metrics = {}
    for src, stats in source_stats.items():
        p = stats["tp"] / (stats["tp"] + stats["fp"]) if (stats["tp"] + stats["fp"]) > 0 else 0.0
        r = stats["tp"] / (stats["tp"] + stats["fn"]) if (stats["tp"] + stats["fn"]) > 0 else 0.0
        src_metrics[src] = {
            "precision": round(p, 4),
            "recall": round(r, 4),
            "f1": round(2 * p * r / (p + r) if (p + r) > 0 else 0.0, 4),
            "samples": sum(stats.values()),
        }

    return {
        "overall": {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "false_positive_rate": fpr,
            "false_negative_rate": fnr,
        },
        "confusion_matrix": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "by_discipline": disc_metrics,
        "by_source_type": src_metrics,
        "threshold": threshold,
        "total_samples": len(predictions),
    }


def compare_versions(result_a: EvalResult, result_b: EvalResult) -> dict:
    """
    对比两个版本的评测结果，计算相对改进幅度
    """
    return {
        "version_a": {
            "model": result_a.model_version,
            "prompt": result_a.prompt_version,
            "f1": result_a.f1,
        },
        "version_b": {
            "model": result_b.model_version,
            "prompt": result_b.prompt_version,
            "f1": result_b.f1,
        },
        "improvement": {
            "f1_delta": round(result_b.f1 - result_a.f1, 4),
            "f1_relative_pct": round(
                (result_b.f1 - result_a.f1) / result_a.f1 * 100
                if result_a.f1 > 0 else 0, 2
            ),
            "precision_delta": round(result_b.precision - result_a.precision, 4),
            "recall_delta": round(result_b.recall - result_a.recall, 4),
            "fpr_delta": round(
                result_b.false_positive_rate - result_a.false_positive_rate, 4
            ),
        },
        "recommendation": (
            "新版本显著改进（F1提升>2%），建议发布"
            if (result_b.f1 - result_a.f1) > 0.02
            else "改进不显著或有退步，建议继续迭代"
        ),
    }
