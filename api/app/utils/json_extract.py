"""
从LLM响应中安全提取JSON的工具函数。
LLM经常在JSON外包裹markdown代码块标记或多余文字。
"""

import json
import re
from typing import Optional


def extract_json(text: str) -> Optional[dict]:
    """
    从LLM响应文本中尽力提取JSON对象。

    支持以下常见格式：
    1. 纯JSON字符串
    2. ```json ... ``` 代码块
    3. ``` ... ``` 代码块
    4. JSON前后有额外文字
    """
    if not text or not text.strip():
        return None

    text = text.strip()

    # 0. Strip Qwen3.5 / DeepSeek thinking tags: <think>...</think>
    think_pattern = re.compile(r'<think>.*?</think>', re.DOTALL)
    text = think_pattern.sub('', text).strip()
    if not text:
        return None

    # 1. 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. 提取 ```json ... ``` 或 ``` ... ``` 代码块
    code_block_patterns = [
        r'```json\s*\n?(.*?)\n?\s*```',
        r'```\s*\n?(.*?)\n?\s*```',
    ]
    for pattern in code_block_patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                continue

    # 3. 找到第一个 { 和最后一个 } 之间的内容（对象）
    first_brace = text.find('{')
    last_brace = text.rfind('}')
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidate = text[first_brace:last_brace + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            # 尝试修复常见问题
            # 去除注释
            candidate = re.sub(r'//.*?\n', '\n', candidate)
            # 去除尾随逗号
            candidate = re.sub(r',\s*([}\]])', r'\1', candidate)
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

    # 4. 找到第一个 [ 和最后一个 ] 之间的内容（数组）
    first_bracket = text.find('[')
    last_bracket = text.rfind(']')
    if first_bracket != -1 and last_bracket != -1 and last_bracket > first_bracket:
        candidate = text[first_bracket:last_bracket + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            candidate = re.sub(r'//.*?\n', '\n', candidate)
            candidate = re.sub(r',\s*([}\]])', r'\1', candidate)
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

    # 5. 全部失败
    return None
