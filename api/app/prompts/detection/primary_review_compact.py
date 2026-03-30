"""
ScholarGuard 主评议Agent Prompt - 精简版（优化推理速度）
Version: v2.0-compact — 合并评议+报告为单次调用
"""

PRIMARY_REVIEW_SYSTEM_COMPACT = "你是学术文本AI检测专家。只输出JSON，不要解释。"

# ── 合并后的单次调用 prompt（评议 + 报告） ──────────────────────────────
# 将原先 primary_review + explanation 两次LLM调用合并为一次
# 使用短字段名减少输出token
PRIMARY_REVIEW_PROMPT_COMPACT = """分析下文是否为AI生成，同时给出风险报告。重点识别每个片段的AI写作特征（NHPR分析）。输出JSON。

AI特征模式识别要点：
- 困惑度平滑：AI文本各句困惑度异常均匀，缺乏人类写作的自然波动
- token概率集中：AI倾向高概率词选择，缺少人类的低频词/口语化表达
- 模板化结构：固定的"首先…其次…最后"、"综上所述"等套路
- 连接词过度使用：however/furthermore/moreover等学术连接词密度异常
- 均匀性：段落长度、句式复杂度过于一致

文本：
---
{text}
---

输出格式（严格JSON，无其他内容）：
{{"conf":<0-1>,"lvl":"<low/medium/high/critical>","nhpr":<0-1 AI特征占比>,"dim":{{"vd":<1-10>,"sv":<1-10>,"an":<1-10>}},"src":{{"human":<0-1>,"ai":<0-1>,"edited":<0-1>,"humanizer":<0-1>}},"flags":{{"lcd":<0-10>,"slu":<0-10>,"ts":<0-10>}},"segs":[{{"s":<起始字符位置>,"e":<结束字符位置>,"t":"<从原文中直接复制的可疑句子或段落>","i":"<该片段的AI特征说明>","nh":"<AI特征类型: perplexity_smooth|token_concentrated|structure_templated|connector_overuse|uniformity>"}}],"reason":"<50字以内>","unc":"<30字以内>","rpt":{{"summary":"<一句话>","for":["证据1"],"against":["反向证据1"],"disclaimer":"<结论边界>","actions":["建议1"],"review":<true/false>,"review_why":"<原因或null>"}}}}

判断标准：low=自然人类写作,medium=部分AI特征,high=明显AI特征,critical=确定AI生成
nhpr=AI特征占比(0=完全人类写作,1=完全AI生成)，基于各片段AI生成特征的文本覆盖率估算
rpt.summary=风险概述,rpt.for=支撑证据,rpt.against=反向证据,rpt.actions=建议操作
segs要求：必须从原文中逐字引用2-5个最可疑的句子/段落，t字段是原文原句（不要改写或总结），i字段说明AI特征原因，nh字段标注该片段的主要AI特征类型。如果文本风险低可返回空数组。"""


# ── 旧版独立 explanation prompt（保留兼容，但主流程不再使用）────────────
EXPLANATION_PROMPT_COMPACT = """根据检测结果生成风险报告，输出JSON。

检测数据：风险分={risk_score}，LLM证据={llm_evidence_brief}，统计证据={stat_evidence}

输出格式：
{{"risk_summary":"<一句话>","evidence_for":["证据1"],"evidence_against":["反向证据1"],"uncertainty_disclaimer":"<结论边界>","recommended_actions":["建议1"],"review_suggested":<true/false>,"review_reason":"<原因或null>"}}"""
