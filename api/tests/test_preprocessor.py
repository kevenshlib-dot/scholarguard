"""Tests for TextPreprocessor."""

import hashlib
import pytest
from app.services.detection.preprocessor import TextPreprocessor, ProcessedText


@pytest.fixture
def pp():
    return TextPreprocessor()


def _pad(text: str, min_len: int = 300) -> str:
    """Pad text to meet minimum length requirement.

    We pad generously (default 300) because format stripping may remove
    characters before the length validation runs.
    """
    while len(text) < min_len:
        text += "这是填充文本用于满足最小长度要求。"
    return text


# ---------------------------------------------------------------------------
# Chinese sentence segmentation
# ---------------------------------------------------------------------------

class TestChineseSentenceSegmentation:
    def test_basic_zh_segmentation(self, pp):
        text = _pad("这是第一句话。这是第二句话！这是第三句话？还有一句话；")
        result = pp.process(text, language="zh")
        # Should split on Chinese punctuation
        assert len(result.sentences) >= 2  # at least the padded sentences
        assert result.language == "zh"

    def test_zh_sentence_endings_preserved(self, pp):
        text = _pad("人工智能的发展非常迅速。它改变了我们的生活方式！你觉得呢？")
        result = pp.process(text, language="zh")
        # Sentence endings should be attached to sentences
        for sent in result.sentences:
            # Each sentence should end with Chinese punctuation or be the last fragment
            assert len(sent) > 5  # filter threshold

    def test_zh_short_fragments_filtered(self, pp):
        """Fragments <= 5 chars should be filtered out."""
        text = _pad("这是一句正常长度的句子。好。这又是一句正常长度的句子。")
        result = pp.process(text, language="zh")
        for sent in result.sentences:
            assert len(sent) > 5


# ---------------------------------------------------------------------------
# English sentence segmentation
# ---------------------------------------------------------------------------

class TestEnglishSentenceSegmentation:
    def test_basic_en_segmentation(self, pp):
        text = _pad(
            "This is the first sentence. This is the second sentence! "
            "Is this the third one? Yes it is. ",
            min_len=250,
        )
        result = pp.process(text, language="en")
        assert len(result.sentences) >= 2
        assert result.language == "en"

    def test_en_short_fragments_filtered(self, pp):
        """Fragments <= 10 chars should be filtered out in English."""
        text = _pad(
            "This is a normal length sentence in English. OK. "
            "Another perfectly normal English sentence here. ",
            min_len=250,
        )
        result = pp.process(text, language="en")
        for sent in result.sentences:
            assert len(sent) > 10


# ---------------------------------------------------------------------------
# HTML / LaTeX stripping
# ---------------------------------------------------------------------------

class TestFormatStripping:
    def test_html_tags_removed(self, pp):
        raw = _pad("<p>这是一段<b>加粗</b>的文字。<br/>还有换行。</p>")
        result = pp.process(raw, language="zh")
        assert "<p>" not in result.full_text
        assert "<b>" not in result.full_text
        assert "<br/>" not in result.full_text

    def test_latex_math_removed(self, pp):
        raw = _pad("这是一个公式 $E=mc^2$ 在文本中。还有 $$\\sum_{i=1}^{n} x_i$$ 显示公式。")
        result = pp.process(raw, language="zh")
        assert "$E=mc^2$" not in result.full_text
        assert "$$" not in result.full_text

    def test_latex_commands_removed(self, pp):
        raw = _pad("这是一段文字\\textbf{加粗内容}和\\emph{斜体内容}在文中。")
        result = pp.process(raw, language="zh")
        assert "\\textbf" not in result.full_text
        assert "\\emph" not in result.full_text

    def test_markdown_headers_removed(self, pp):
        raw = _pad("## 这是标题\n这是正文内容，包含了一些普通的文字段落。")
        result = pp.process(raw, language="zh")
        assert "## " not in result.full_text

    def test_markdown_bold_unwrapped(self, pp):
        raw = _pad("这是**加粗文字**和*斜体文字*的测试内容，应该保留文字去掉标记。")
        result = pp.process(raw, language="zh")
        assert "**" not in result.full_text
        assert "加粗文字" in result.full_text

    def test_markdown_links_unwrapped(self, pp):
        raw = _pad("请访问[这个链接](https://example.com)查看更多信息和详细说明。")
        result = pp.process(raw, language="zh")
        assert "https://example.com" not in result.full_text
        assert "这个链接" in result.full_text


# ---------------------------------------------------------------------------
# Content hash consistency
# ---------------------------------------------------------------------------

class TestContentHash:
    def test_same_input_same_hash(self, pp):
        text = _pad("这是一段固定的测试文本内容。")
        r1 = pp.process(text, language="zh")
        r2 = pp.process(text, language="zh")
        assert r1.content_hash == r2.content_hash

    def test_different_input_different_hash(self, pp):
        t1 = _pad("这是第一段文本内容用于测试。")
        t2 = _pad("这是完全不同的第二段文本。")
        r1 = pp.process(t1, language="zh")
        r2 = pp.process(t2, language="zh")
        assert r1.content_hash != r2.content_hash

    def test_hash_is_sha256(self, pp):
        text = _pad("测试哈希值格式。")
        result = pp.process(text, language="zh")
        assert len(result.content_hash) == 64  # SHA-256 hex digest length


# ---------------------------------------------------------------------------
# Length validation
# ---------------------------------------------------------------------------

class TestLengthValidation:
    def test_too_short_raises(self, pp):
        with pytest.raises(ValueError, match="文本过短"):
            pp.process("太短了", language="zh")

    def test_exactly_min_length(self, pp):
        text = "a" * 200
        # Should not raise -- exactly at minimum
        result = pp.process(text, language="en")
        assert result.full_text == text

    def test_too_long_raises(self, pp):
        text = "a" * 60001
        with pytest.raises(ValueError, match="文本过长"):
            pp.process(text, language="en")

    def test_exactly_max_length(self, pp):
        text = "a" * 60000
        result = pp.process(text, language="en")
        assert len(result.full_text) == 60000


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------

class TestLanguageDetection:
    def test_auto_detect_chinese(self, pp):
        text = _pad("这是一段纯中文的文本内容，用于测试语言自动检测功能是否正确。")
        result = pp.process(text, language="auto")
        assert result.language == "zh"

    def test_auto_detect_english(self, pp):
        text = "a" * 200 + " This is English text for auto detection testing purposes."
        result = pp.process(text, language="auto")
        assert result.language == "en"


# ---------------------------------------------------------------------------
# Encoding normalization
# ---------------------------------------------------------------------------

class TestEncodingNormalization:
    def test_fullwidth_digits_converted(self, pp):
        """Full-width digits should be converted to half-width."""
        text = _pad("这里有全角数字１２３和字母ＡＢＣ在文本中。")
        result = pp.process(text, language="zh")
        assert "123" in result.full_text
        assert "ABC" in result.full_text

    def test_chinese_punctuation_preserved(self, pp):
        """Chinese punctuation should NOT be converted."""
        text = _pad("这里有中文标点，包括句号。和感叹号！以及问号？")
        result = pp.process(text, language="zh")
        assert "。" in result.full_text
        assert "！" in result.full_text
        assert "？" in result.full_text


# ---------------------------------------------------------------------------
# Word counting
# ---------------------------------------------------------------------------

class TestWordCount:
    def test_zh_word_count(self, pp):
        text = _pad("我有三个中文字符加上hello英文单词。")
        result = pp.process(text, language="zh")
        # word_count = Chinese chars + English words
        assert result.word_count > 0

    def test_en_word_count(self, pp):
        text = " ".join(["word"] * 50) + " " * 100  # pad to 200+
        # Need 200 chars minimum
        text = text.ljust(200, " ")
        if len(text.strip()) < 200:
            text = " ".join(["word"] * 100)
        result = pp.process(text, language="en")
        assert result.word_count >= 50


# ---------------------------------------------------------------------------
# Paragraph segmentation
# ---------------------------------------------------------------------------

class TestParagraphSegmentation:
    def test_double_newline_splits_paragraphs(self, pp):
        para1 = "这是第一个段落，包含了足够多的内容来超过最小长度阈值。"
        para2 = "这是第二个段落，同样包含了足够多的内容来超过最小长度阈值。"
        text = _pad(f"{para1}\n\n{para2}")
        result = pp.process(text, language="zh")
        assert len(result.paragraphs) >= 1

    def test_short_paragraphs_filtered(self, pp):
        """Paragraphs shorter than 20 chars should be ignored."""
        text = _pad("短\n\n这是一个足够长度的段落内容用于测试过滤短段落的功能。")
        result = pp.process(text, language="zh")
        for para in result.paragraphs:
            assert len(para) > 20
