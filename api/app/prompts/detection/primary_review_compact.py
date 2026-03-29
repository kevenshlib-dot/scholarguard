"""
ScholarGuard 主评议Agent Prompt - 精简版（优化推理速度）
Version: v2.0-compact — 合并评议+报告为单次调用
"""

PRIMARY_REVIEW_SYSTEM_COMPACT = "你是学术文本AI检测专家。只输出JSON，不要解释。"

# ── 合并后的单次调用 prompt（评议 + 报告） ──────────────────────────────
# 将原先 primary_review + explanation 两次LLM调用合并为一次
# 使用短字段名减少输出token
PRIMARY_REVIEW_PROMPT_COMPACT = """分析下文是否为AI生成，同时给出风险报告。输出JSON。

文本：
---
{text}
---

输出格式（严格JSON，无其他内容）：
{{"conf":<0-1>,"lvl":"<low/medium/high/critical>","dim":{{"vd":<1-10>,"sv":<1-10>,"an":<1-10>}},"src":{{"human":<0-1>,"ai":<0-1>,"edited":<0-1>,"humanizer":<0-1>}},"flags":{{"lcd":<0-10>,"slu":<0-10>,"ts":<0-10>}},"segs":[{{"s":0,"e":0,"t":"","i":""}}],"reason":"<50字以内>","unc":"<30字以内>","rpt":{{"summary":"<一句话>","for":["证据1"],"against":["反向证据1"],"disclaimer":"<结论边界>","actions":["建议1"],"review":<true/false>,"review_why":"<原因或null>"}}}}

判断标准：low=自然人类写作,medium=部分AI特征,high=明显AI特征,critical=确定AI生成
rpt.summary=风险概述,rpt.for=支撑证据,rpt.against=反向证据,rpt.actions=建议操作"""


# ── 旧版独立 explanation prompt（保留兼容，但主流程不再使用）────────────
EXPLANATION_PROMPT_COMPACT = """根据检测结果生成风险报告，输出JSON。

检测数据：风险分={risk_score}，LLM证据={llm_evidence_brief}，统计证据={stat_evidence}

输出格式：
{{"risk_summary":"<一句话>","evidence_for":["证据1"],"evidence_against":["反向证据1"],"uncertainty_disclaimer":"<结论边界>","recommended_actions":["建议1"],"review_suggested":<true/false>,"review_reason":"<原因或null>"}}"""
