"""
ScholarGuard 主评议Agent Prompt - 精简版（优化推理速度）
Version: v1.0-compact
"""

PRIMARY_REVIEW_SYSTEM_COMPACT = "你是学术文本AI检测专家。只输出JSON，不要解释。"

PRIMARY_REVIEW_PROMPT_COMPACT = """分析下文是否为AI生成，输出JSON。

文本：
---
{text}
---

输出格式（严格JSON，无其他内容）：
{{"llm_confidence":<0-1>,"risk_level":"<low/medium/high/critical>","dimension_scores":{{"vocabulary_diversity":<1-10>,"syntactic_variation":<1-10>,"argumentation_naturalness":<1-10>}},"source_classification":{{"human_original":<0-1>,"ai_generated":<0-1>,"ai_human_edited":<0-1>,"humanizer_processed":<0-1>}},"pattern_flags":{{"logical_connector_density":<0-10>,"sentence_length_uniformity":<0-10>,"terminology_stacking":<0-10>}},"flagged_segments":[{{"start_char":0,"end_char":0,"text_snippet":"","issue":""}}],"reasoning":"<50字以内>","uncertainty_notes":"<30字以内>"}}

判断标准：low=自然人类写作,medium=部分AI特征,high=明显AI特征,critical=确定AI生成"""

EXPLANATION_PROMPT_COMPACT = """根据检测结果生成风险报告，输出JSON。

检测数据：风险分={risk_score}，LLM证据={llm_evidence_brief}，统计证据={stat_evidence}

输出格式：
{{"risk_summary":"<一句话>","evidence_for":["证据1"],"evidence_against":["反向证据1"],"uncertainty_disclaimer":"<结论边界>","recommended_actions":["建议1"],"review_suggested":<true/false>,"review_reason":"<原因或null>"}}"""
