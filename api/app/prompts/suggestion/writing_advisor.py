"""
ScholarGuard 写作建议 Prompt模板
Version: v1.0

注意：所有建议聚焦于"提升写作质量"和"表达自然化"，
而非"规避AI检测"。
"""

SUGGESTION_SYSTEM = """你是一位资深的{discipline}学术写作顾问，拥有丰富的学术论文指导经验。
你的任务是帮助作者提升学术写作质量，使其表达更加自然、论证更加严谨、结构更加合理。"""

NATURALNESS_PROMPT = """## 任务：表达自然化建议

分析以下学术文本中的表达问题，给出改善建议。

## 关注点
1. 是否存在过于模式化、公式化的表达？
2. 是否有词汇重复使用的问题？
3. 句式是否过于单一？
4. 表达是否缺乏个性化的学术风格？
5. 是否存在不自然的逻辑连接词堆砌？

## 文本
---
{text}
---

## 输出格式

```json
{{
  "overall_naturalness": <1-10, 10=非常自然>,
  "issues": [
    {{
      "type": "<repetitive_vocab/formulaic_expression/uniform_syntax/connector_overuse/other>",
      "location": "<具体位置描述>",
      "original": "<原文片段>",
      "suggestion": "<改善建议>",
      "example": "<改写示例（可选）>",
      "priority": "<high/medium/low>"
    }}
  ],
  "general_advice": "<整体写作建议，100字以内>"
}}
```

## 重要原则
- 建议应当提升写作质量，而非仅仅"让文本看起来不像AI"
- 每条建议都要说明为什么这样改会更好
- 尊重作者的学术风格和个人表达习惯
"""

ARGUMENTATION_PROMPT = """## 任务：论证补强建议

分析以下学术论述的论证质量，给出补强建议。

## 学科方向：{discipline}

## 分析维度
1. 论证的因果关系是否清晰？
2. 理论基础是否充分？
3. 是否存在隐含但未说明的假设？
4. 是否缺少实证支撑？
5. 是否遗漏了重要的反驳与回应？

## 文本
---
{text}
---

## 输出格式

```json
{{
  "argumentation_quality": <1-10>,
  "strengths": ["<论证优点1>", "<优点2>"],
  "weaknesses": [
    {{
      "type": "<weak_causality/missing_theory/hidden_assumption/lack_evidence/no_rebuttal>",
      "location": "<位置>",
      "description": "<问题描述>",
      "suggestion": "<补强建议>",
      "reference_hint": "<可参考的理论/学派/概念提示>"
    }}
  ],
  "structure_advice": "<论证结构整体建议>"
}}
```
"""

STRUCTURE_PROMPT = """## 任务：结构优化建议

分析论文的逻辑架构，对照{discipline}学术范式给出结构优化建议。

## 文本
---
{text}
---

## 输出格式

```json
{{
  "current_structure": [
    {{"section": "<章节名>", "summary": "<内容概要>", "word_count": <估计字数>}}
  ],
  "structure_issues": ["<结构问题1>", "<问题2>"],
  "suggested_structure": [
    {{"section": "<建议章节名>", "purpose": "<章节作用>", "key_content": "<应包含的核心内容>"}}
  ],
  "transition_advice": "<章节间衔接建议>"
}}
```
"""
