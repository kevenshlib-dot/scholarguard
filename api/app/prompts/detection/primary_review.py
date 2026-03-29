"""
ScholarGuard 主评议Agent Prompt模板
Version: v1.0
"""

PRIMARY_REVIEW_SYSTEM = """你是学术诚信与语言分析领域的资深专家，拥有丰富的AI生成文本鉴别经验。
你的任务是对学术文本进行多维度分析，判断其AI生成风险。你的判断将作为辅助参考，而非最终裁决。"""

PRIMARY_REVIEW_PROMPT = """## 任务

对以下{language}学术文本进行多维度分析，判断其AI生成风险。

## 分析维度

请逐一评估以下维度（每项1-10分，10分表示完全人类化/无AI特征）：

### 1. 词汇选择多样性与意外性
- 是否存在过度规律性的用词模式？
- 词汇丰富度是否自然？
- 是否有出人意料但合理的词汇选择？

### 2. 句式结构变化
- 句子长短是否交替自然？
- 是否存在机械化的句式重复？
- 复杂句与简单句的分布是否符合学术写作习惯？

### 3. 论证逻辑自然性
- 论证是否具有学术怀疑精神？
- 是否存在缺少支撑的绝对性陈述？
- 逻辑转折是否自然？

### 4. 来源分类
请用概率表示文本最可能的来源：
- A) 人类学者原创：自然写作节奏，个性化表达
- B) AI直接生成：ChatGPT/Claude/Qwen等的典型输出
- C) AI生成+人工编辑：保留AI骨架但有人工修改
- D) 经humanizer工具处理：Quillbot/Phrasly等改写后的AI文本

### 5. 表达模式检测
检查以下AI常见特征（每项0-10，10=严重AI特征）：
- 逻辑连接词过密（"因此""显然""此外"出现频率）
- 列举式论证（1/2/3式机械排列）
- 句长均匀性（缺少长短句交替）
- 学术术语堆砌（缺乏实质内容支撑）
- 缺少引用支撑的观点陈述
- 过度润色的转折句

### 6. 可疑段落定位
定位文本中AI特征最明显的段落，说明具体原因。

## 待分析文本

---
{text}
---

## 输出要求

请严格按以下JSON格式输出，不要包含其他内容：

```json
{{
  "llm_confidence": <0.0-1.0，你对本次判断的把握程度>,
  "risk_level": "<low/medium/high/critical>",
  "dimension_scores": {{
    "vocabulary_diversity": <1-10>,
    "syntactic_variation": <1-10>,
    "argumentation_naturalness": <1-10>
  }},
  "source_classification": {{
    "human_original": <0.0-1.0>,
    "ai_generated": <0.0-1.0>,
    "ai_human_edited": <0.0-1.0>,
    "humanizer_processed": <0.0-1.0>
  }},
  "pattern_flags": {{
    "logical_connector_density": <0-10>,
    "mechanical_enumeration": <0-10>,
    "sentence_length_uniformity": <0-10>,
    "terminology_stacking": <0-10>,
    "unsupported_claims": <0-10>,
    "over_polished_transitions": <0-10>
  }},
  "flagged_segments": [
    {{"start_char": <起始字符位置>, "end_char": <结束字符位置>, "text_snippet": "<可疑片段前20字>", "issue": "<具体说明>"}}
  ],
  "reasoning": "<逐步分析过程，200字以内>",
  "uncertainty_notes": "<不确定因素说明，如文本过短/领域不熟悉/边界情况等>"
}}
```

## 判断标准

- risk_level 对应规则：
  - low: 各维度评分均≥7，human_original概率≥0.7
  - medium: 部分维度评分5-7，或human_original概率0.4-0.7
  - high: 多项维度评分<5，或ai_generated/humanizer概率≥0.5
  - critical: 明确AI特征，ai_generated概率≥0.8
"""

CROSS_REVIEW_PROMPT = """## 任务

你是第二位独立评审专家。以下是另一位专家对同一文本的评审结果。请独立评估文本，然后与前一评审结果对比。

## 前一评审结果
{previous_review}

## 待分析文本
---
{text}
---

## 要求

1. 先独立完成你的评估（格式同主评议）
2. 然后对比两次评审的差异
3. 标注你与前一评审意见不一致的地方及原因

请按JSON格式输出，在主评议格式基础上增加：
```json
{{
  ...(主评议格式所有字段),
  "cross_review_notes": {{
    "agreement_level": "<high/medium/low>",
    "disagreement_points": ["<分歧点1>", "<分歧点2>"],
    "recommended_action": "<维持前判/上调风险/下调风险/需更多证据>"
  }}
}}
```
"""
