"""Tests for extract_json utility."""

import json
import pytest
from app.utils.json_extract import extract_json


# ---------------------------------------------------------------------------
# Direct JSON string
# ---------------------------------------------------------------------------

class TestDirectJSON:
    def test_simple_object(self):
        assert extract_json('{"key": "value"}') == {"key": "value"}

    def test_nested_object(self):
        data = {"outer": {"inner": [1, 2, 3]}, "flag": True}
        assert extract_json(json.dumps(data)) == data

    def test_with_whitespace(self):
        assert extract_json('  \n  {"a": 1}  \n  ') == {"a": 1}

    def test_array_top_level(self):
        result = extract_json('[1, 2, 3]')
        assert result == [1, 2, 3]

    def test_numbers_and_booleans(self):
        text = '{"count": 42, "ratio": 3.14, "active": true, "data": null}'
        result = extract_json(text)
        assert result["count"] == 42
        assert result["ratio"] == pytest.approx(3.14)
        assert result["active"] is True
        assert result["data"] is None


# ---------------------------------------------------------------------------
# JSON in markdown code blocks
# ---------------------------------------------------------------------------

class TestMarkdownCodeBlocks:
    def test_json_code_block(self):
        text = '```json\n{"key": "value"}\n```'
        assert extract_json(text) == {"key": "value"}

    def test_plain_code_block(self):
        text = '```\n{"key": "value"}\n```'
        assert extract_json(text) == {"key": "value"}

    def test_code_block_with_surrounding_text(self):
        text = 'Here is the result:\n```json\n{"score": 0.85}\n```\nDone.'
        assert extract_json(text) == {"score": 0.85}

    def test_code_block_multiline_json(self):
        text = '```json\n{\n  "name": "test",\n  "values": [1, 2, 3]\n}\n```'
        result = extract_json(text)
        assert result["name"] == "test"
        assert result["values"] == [1, 2, 3]

    def test_code_block_with_extra_whitespace(self):
        text = '```json\n  \n  {"a": 1}  \n  \n```'
        assert extract_json(text) == {"a": 1}


# ---------------------------------------------------------------------------
# JSON with extra text
# ---------------------------------------------------------------------------

class TestExtraText:
    def test_json_after_text(self):
        text = 'The analysis result is: {"risk": "high", "score": 0.9}'
        assert extract_json(text) == {"risk": "high", "score": 0.9}

    def test_json_before_text(self):
        text = '{"risk": "low"} --- end of response'
        assert extract_json(text) == {"risk": "low"}

    def test_json_surrounded_by_text(self):
        text = 'Based on analysis:\n{"result": "positive"}\nPlease review.'
        assert extract_json(text) == {"result": "positive"}

    def test_chinese_surrounding_text(self):
        text = '分析结果如下：\n{"风险等级": "高", "分数": 0.85}\n以上为最终结论。'
        result = extract_json(text)
        assert result["分数"] == 0.85


# ---------------------------------------------------------------------------
# Malformed input
# ---------------------------------------------------------------------------

class TestMalformedInput:
    def test_empty_string(self):
        assert extract_json("") is None

    def test_none_like_empty(self):
        assert extract_json("   ") is None

    def test_no_json_at_all(self):
        assert extract_json("This is just plain text without any JSON.") is None

    def test_incomplete_json(self):
        # Missing closing brace -- no valid JSON can be extracted
        assert extract_json('{"key": "value"') is None

    def test_trailing_comma_fixed(self):
        """Trailing commas should be auto-fixed."""
        text = '{"a": 1, "b": 2,}'
        result = extract_json(text)
        assert result == {"a": 1, "b": 2}

    def test_comment_lines_fixed(self):
        """Single-line comments should be stripped."""
        text = '{"a": 1, // this is a comment\n"b": 2}'
        result = extract_json(text)
        assert result == {"a": 1, "b": 2}

    def test_only_opening_brace(self):
        assert extract_json("{") is None

    def test_mismatched_braces(self):
        # First { to last } includes invalid JSON
        result = extract_json("{ broken } not json {")
        assert result is None


# ---------------------------------------------------------------------------
# Nested JSON
# ---------------------------------------------------------------------------

class TestNestedJSON:
    def test_deeply_nested(self):
        data = {
            "level1": {
                "level2": {
                    "level3": {
                        "value": 42
                    }
                }
            }
        }
        assert extract_json(json.dumps(data)) == data

    def test_nested_arrays(self):
        data = {"matrix": [[1, 2], [3, 4]], "labels": ["a", "b"]}
        assert extract_json(json.dumps(data)) == data

    def test_complex_llm_response(self):
        """Simulate a realistic LLM response with nested structure."""
        data = {
            "ai_probability": 0.85,
            "risk_level": "high",
            "source_classification": {
                "pure_ai": 0.7,
                "ai_assisted": 0.2,
                "human": 0.1,
            },
            "risk_indicators": {
                "structural_patterns": {
                    "score": 0.8,
                    "details": "Highly uniform paragraph structure",
                },
                "vocabulary_patterns": {
                    "score": 0.6,
                    "details": "Some typical AI phrases detected",
                },
            },
            "analysis_summary": "The text shows strong AI characteristics.",
        }
        wrapped = f"Here is my analysis:\n```json\n{json.dumps(data, indent=2)}\n```"
        result = extract_json(wrapped)
        assert result["ai_probability"] == 0.85
        assert result["risk_indicators"]["structural_patterns"]["score"] == 0.8

    def test_multiple_json_blocks_takes_first_code_block(self):
        """When multiple code blocks exist, the first valid one should be used."""
        text = (
            '```json\n{"first": true}\n```\n'
            'Some text\n'
            '```json\n{"second": true}\n```'
        )
        result = extract_json(text)
        assert result == {"first": True}

    def test_json_with_unicode(self):
        data = {"name": "测试", "emoji": "hello", "value": 123}
        assert extract_json(json.dumps(data, ensure_ascii=False)) == data
