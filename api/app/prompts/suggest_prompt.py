"""
ScholarGuard 写作建议 Prompt
"""

SUGGEST_SYSTEM = "你是学术写作优化专家。根据AI检测结果，为用户提供具体的文本改写建议，使文本更自然、更具学术深度。只输出JSON，不要解释。"

SUGGEST_PROMPT = """根据以下文本和检测到的AI特征问题，提供具体的改写建议。

原文：
---
{text}
---

检测到的问题：
{issues}

优化策略：{strategies}

输出格式（严格JSON数组，无其他内容）：
[{{"id":"s1","type":"<rephrase/restructure/tone/vocabulary/general>","orig":"<原文片段，从原文逐字复制>","new":"<改写后的文本>","why":"<改写原因，20字以内>","s":<起始字符位置>,"e":<结束字符位置>,"conf":<0-1置信度>}}]

要求：
1. 每条建议的orig必须是从原文中逐字复制的片段
2. new是改写后的替代文本，需保持学术性但更自然
3. 提供3-8条最有价值的建议，按重要性排序
4. rephrase=改写表达使之自然,restructure=调整结构,tone=调整语气,vocabulary=替换AI常见词汇,general=综合改进
5. s和e是orig在原文中的字符位置
6. 改写应降低AI检测风险，同时保持学术水平"""
