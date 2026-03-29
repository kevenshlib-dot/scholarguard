"""
轻量统计因子计算器（E2：统计与结构证据）
一期先做少量基础指标，不依赖外部模型
"""

import re
import math
from dataclasses import dataclass


@dataclass
class StatEvidence:
    """统计证据结果"""
    sentence_length_std: float       # 句长离散度（标准差）
    repetition_ratio: float          # 重复表达比例
    connector_density: float         # 连接词密度
    paragraph_uniformity: float      # 段落长度均匀性
    stat_score: float                # 综合统计分（0-1, 越高越可疑）

    def to_dict(self) -> dict:
        return {
            "sentence_length_std": round(self.sentence_length_std, 3),
            "repetition_ratio": round(self.repetition_ratio, 3),
            "connector_density": round(self.connector_density, 3),
            "paragraph_uniformity": round(self.paragraph_uniformity, 3),
            "stat_score": round(self.stat_score, 4),
        }


class LightweightStatsCalculator:
    """轻量级统计特征计算器"""

    # 中文常见AI逻辑连接词
    ZH_CONNECTORS = [
        '因此', '所以', '然而', '但是', '不过', '此外', '另外', '同时',
        '显然', '显而易见', '毫无疑问', '值得注意的是', '综上所述',
        '首先', '其次', '最后', '总之', '总的来说', '换言之',
        '具体而言', '一方面', '另一方面', '事实上', '实际上',
    ]

    # 英文常见AI连接词
    EN_CONNECTORS = [
        'therefore', 'however', 'furthermore', 'moreover', 'additionally',
        'consequently', 'nevertheless', 'in conclusion', 'specifically',
        'notably', 'importantly', 'essentially', 'fundamentally',
        'firstly', 'secondly', 'finally', 'overall', 'in summary',
    ]

    def compute(self, sentences: list[str], paragraphs: list[str],
                full_text: str, language: str = "zh") -> StatEvidence:
        """计算所有统计指标"""
        sent_std = self._sentence_length_std(sentences, language)
        rep_ratio = self._repetition_ratio(sentences)
        conn_density = self._connector_density(full_text, language)
        para_uniform = self._paragraph_uniformity(paragraphs)

        # 综合统计分：加权计算
        # 各指标都归一化到 0-1 范围，越高越可疑
        stat_score = self._compute_stat_score(
            sent_std, rep_ratio, conn_density, para_uniform, language
        )

        return StatEvidence(
            sentence_length_std=sent_std,
            repetition_ratio=rep_ratio,
            connector_density=conn_density,
            paragraph_uniformity=para_uniform,
            stat_score=stat_score,
        )

    def _sentence_length_std(self, sentences: list[str], language: str) -> float:
        """
        句长离散度（标准差）
        人类写作通常句长变化大（std较高），AI写作更均匀（std较低）
        """
        if len(sentences) < 3:
            return 0.0

        lengths = [len(s) for s in sentences]
        mean = sum(lengths) / len(lengths)
        variance = sum((l - mean) ** 2 for l in lengths) / len(lengths)
        return math.sqrt(variance)

    def _repetition_ratio(self, sentences: list[str]) -> float:
        """
        重复表达比例
        检查相邻句子是否使用了大量重复的表达模式
        """
        if len(sentences) < 2:
            return 0.0

        # 提取每句的2-gram
        def get_bigrams(text: str) -> set[str]:
            chars = re.sub(r'\s+', '', text)
            return {chars[i:i+2] for i in range(len(chars) - 1)} if len(chars) >= 2 else set()

        total_overlap = 0
        comparisons = 0

        for i in range(len(sentences) - 1):
            bg1 = get_bigrams(sentences[i])
            bg2 = get_bigrams(sentences[i + 1])
            if bg1 and bg2:
                overlap = len(bg1 & bg2) / min(len(bg1), len(bg2))
                total_overlap += overlap
                comparisons += 1

        return total_overlap / comparisons if comparisons > 0 else 0.0

    def _connector_density(self, text: str, language: str) -> float:
        """
        连接词密度
        AI文本通常使用更多逻辑连接词
        """
        connectors = self.ZH_CONNECTORS if language == "zh" else self.EN_CONNECTORS

        count = 0
        text_lower = text.lower()
        for conn in connectors:
            count += text_lower.count(conn.lower() if language == "en" else conn)

        # 按字数归一化
        char_count = len(text)
        if char_count == 0:
            return 0.0

        # 每1000字中出现的连接词数
        return (count / char_count) * 1000

    def _paragraph_uniformity(self, paragraphs: list[str]) -> float:
        """
        段落长度均匀性
        AI文本的段落长度通常更均匀（变异系数低）
        返回：变异系数（CV），越低越均匀
        """
        if len(paragraphs) < 2:
            return 0.0

        lengths = [len(p) for p in paragraphs]
        mean = sum(lengths) / len(lengths)
        if mean == 0:
            return 0.0

        variance = sum((l - mean) ** 2 for l in lengths) / len(lengths)
        std = math.sqrt(variance)
        cv = std / mean  # 变异系数

        return cv

    def _compute_stat_score(self, sent_std: float, rep_ratio: float,
                            conn_density: float, para_uniform: float,
                            language: str) -> float:
        """
        综合统计分计算
        返回 0-1，越高越可疑（越像AI）

        基于经验阈值：
        - 句长标准差低 → 更像AI
        - 重复比例高 → 可能有问题但不一定是AI
        - 连接词密度高 → 更像AI
        - 段落均匀性低（变异系数低）→ 更像AI
        """
        scores = []

        # 句长标准差：人类通常 > 15（中文字符），AI通常 < 10
        if language == "zh":
            sent_score = max(0, min(1, 1.0 - (sent_std - 5) / 20))
        else:
            sent_score = max(0, min(1, 1.0 - (sent_std - 3) / 15))
        scores.append(('sent_std', sent_score, 0.25))

        # 重复比例：> 0.5 可能有问题
        rep_score = max(0, min(1, rep_ratio / 0.6))
        scores.append(('rep_ratio', rep_score, 0.15))

        # 连接词密度（每千字）：人类通常 5-15，AI通常 15-30
        if language == "zh":
            conn_score = max(0, min(1, (conn_density - 8) / 20))
        else:
            conn_score = max(0, min(1, (conn_density - 5) / 15))
        scores.append(('conn_density', conn_score, 0.35))

        # 段落均匀性：CV < 0.2 很均匀（像AI），CV > 0.5 变化大（像人类）
        uniform_score = max(0, min(1, 1.0 - (para_uniform - 0.15) / 0.4))
        scores.append(('para_uniform', uniform_score, 0.25))

        # 加权平均
        total_weight = sum(w for _, _, w in scores)
        stat_score = sum(s * w for _, s, w in scores) / total_weight

        return stat_score
