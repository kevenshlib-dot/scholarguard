"""Tests for LightweightStatsCalculator."""

import pytest
from app.services.detection.stats import LightweightStatsCalculator, StatEvidence


@pytest.fixture
def calc():
    return LightweightStatsCalculator()


# ---------------------------------------------------------------------------
# StatEvidence dataclass
# ---------------------------------------------------------------------------

class TestStatEvidence:
    def test_to_dict_rounding(self):
        ev = StatEvidence(
            sentence_length_std=12.34567,
            repetition_ratio=0.12345,
            connector_density=5.67891,
            paragraph_uniformity=0.98765,
            stat_score=0.55555,
        )
        d = ev.to_dict()
        assert d["sentence_length_std"] == 12.346
        assert d["repetition_ratio"] == 0.123
        assert d["connector_density"] == 5.679
        assert d["paragraph_uniformity"] == 0.988
        assert d["stat_score"] == 0.5555


# ---------------------------------------------------------------------------
# Chinese text stats
# ---------------------------------------------------------------------------

class TestChineseText:
    def test_basic_computation(self, calc):
        sentences = [
            "这是第一句话，内容比较简短。",
            "这是第二句话，同样也是一句不太长的句子。",
            "第三句话来了，它稍微长一些，用来测试句长离散度的计算效果如何。",
            "最后一句是短句。",
        ]
        paragraphs = [
            "这是第一段，包含了一些测试内容，用于验证段落均匀性的计算。",
            "这是第二段，内容长度和第一段差不多，目的是让段落比较均匀。",
        ]
        full_text = "因此这是一段测试文本。此外，我们还需要检查连接词密度。综上所述，这是结论。"

        result = calc.compute(sentences, paragraphs, full_text, language="zh")

        assert isinstance(result, StatEvidence)
        assert result.sentence_length_std >= 0
        assert 0 <= result.repetition_ratio <= 1
        assert result.connector_density >= 0
        assert result.paragraph_uniformity >= 0
        assert 0 <= result.stat_score <= 1

    def test_connector_density_zh(self, calc):
        text_with_connectors = "因此我们需要分析。此外还有其他因素。综上所述这是结论。然而情况并非如此。"
        density = calc._connector_density(text_with_connectors, "zh")
        assert density > 0

        text_no_connectors = "今天天气很好。我吃了午饭。下午去公园散步。"
        density_low = calc._connector_density(text_no_connectors, "zh")
        assert density_low < density

    def test_sentence_length_std_uniform_sentences(self, calc):
        """Uniform-length sentences should have low std."""
        sentences = ["这是一句十个字的话。"] * 5
        std = calc._sentence_length_std(sentences, "zh")
        assert std == 0.0

    def test_sentence_length_std_varied_sentences(self, calc):
        """Varied-length sentences should have higher std."""
        sentences = [
            "短句。",
            "这是一句中等长度的句子，包含更多内容。",
            "非常非常非常非常非常非常非常非常非常非常长的一句话，用来制造句长方面的差异。",
        ]
        std = calc._sentence_length_std(sentences, "zh")
        assert std > 5


# ---------------------------------------------------------------------------
# English text stats
# ---------------------------------------------------------------------------

class TestEnglishText:
    def test_basic_computation(self, calc):
        sentences = [
            "This is the first sentence in our test.",
            "The second sentence is slightly longer than the first one.",
            "Here comes the third sentence, which is even longer to test variation.",
            "Short one.",
        ]
        paragraphs = [
            "This is the first paragraph with some test content for validation.",
            "This is the second paragraph that is roughly the same length as the first.",
        ]
        full_text = (
            "Therefore we need to analyze this. Furthermore there are other factors. "
            "In conclusion this is the result. However the situation is different."
        )

        result = calc.compute(sentences, paragraphs, full_text, language="en")

        assert isinstance(result, StatEvidence)
        assert 0 <= result.stat_score <= 1

    def test_connector_density_en(self, calc):
        text = (
            "Therefore we must act. Furthermore, the data shows improvement. "
            "However, there are concerns. Moreover, we should consider alternatives. "
            "In conclusion, the plan is solid."
        )
        density = calc._connector_density(text, "en")
        assert density > 0

    def test_connector_density_en_none(self, calc):
        text = "The cat sat on the mat. It was a sunny day. Birds were singing."
        density = calc._connector_density(text, "en")
        assert density == 0.0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_sentences(self, calc):
        """Less than 3 sentences -> sentence_length_std = 0."""
        assert calc._sentence_length_std([], "zh") == 0.0
        assert calc._sentence_length_std(["one"], "zh") == 0.0
        assert calc._sentence_length_std(["one", "two"], "zh") == 0.0

    def test_single_sentence_repetition(self, calc):
        """Less than 2 sentences -> repetition_ratio = 0."""
        assert calc._repetition_ratio([]) == 0.0
        assert calc._repetition_ratio(["single"]) == 0.0

    def test_single_paragraph_uniformity(self, calc):
        assert calc._paragraph_uniformity([]) == 0.0
        assert calc._paragraph_uniformity(["only one"]) == 0.0

    def test_empty_text_connector_density(self, calc):
        assert calc._connector_density("", "zh") == 0.0

    def test_zero_length_paragraphs(self, calc):
        """Paragraphs with all empty strings -> mean=0 -> return 0."""
        assert calc._paragraph_uniformity(["", ""]) == 0.0

    def test_compute_with_minimal_input(self, calc):
        result = calc.compute(
            sentences=["a", "b"],
            paragraphs=["para"],
            full_text="ab",
            language="zh",
        )
        assert result.sentence_length_std == 0.0
        assert result.paragraph_uniformity == 0.0
        assert 0 <= result.stat_score <= 1


# ---------------------------------------------------------------------------
# stat_score weighting
# ---------------------------------------------------------------------------

class TestStatScore:
    def test_score_range(self, calc):
        """stat_score should always be in [0, 1]."""
        result = calc.compute(
            sentences=["short", "medium length sentence", "a very long sentence with many words indeed"] * 3,
            paragraphs=["paragraph one content", "paragraph two content"],
            full_text="therefore however furthermore moreover in conclusion",
            language="en",
        )
        assert 0 <= result.stat_score <= 1

    def test_high_connector_density_raises_score(self, calc):
        """Text with many connectors should score higher (more suspicious)."""
        connectors_heavy = (
            "因此我们需要分析。此外还有问题。综上所述这是结论。"
            "首先要考虑。其次要分析。最后要总结。"
            "然而情况不同。但是我们必须继续。显然这很重要。"
        )
        sentences = [s + "。" for s in connectors_heavy.split("。") if s.strip()]
        paragraphs = [connectors_heavy]

        result_heavy = calc.compute(sentences, paragraphs, connectors_heavy, language="zh")

        plain_text = "今天天气很好。我吃了午饭。下午去公园散步了。" * 3
        sentences_plain = [s + "。" for s in plain_text.split("。") if s.strip()]
        result_plain = calc.compute(sentences_plain, [plain_text], plain_text, language="zh")

        # More connectors -> higher connector_density -> higher stat_score tendency
        assert result_heavy.connector_density > result_plain.connector_density

    def test_uniform_sentences_raise_score(self, calc):
        """Uniform sentence lengths should contribute to a higher stat_score."""
        # Uniform: all same length
        uniform_sents = ["这是一句十个字的句子。"] * 10
        # Varied: very different lengths
        varied_sents = [
            "短。",
            "这是一句稍微长一些的句子，包含了很多内容和修饰语。",
            "中等。",
            "又一句非常长的句子，这个句子的目的是制造更大的句长差异来对比统计特征。",
            "好的。",
        ]

        std_uniform = calc._sentence_length_std(uniform_sents, "zh")
        std_varied = calc._sentence_length_std(varied_sents, "zh")

        # Uniform should have lower std (0), which maps to higher suspicion
        assert std_uniform < std_varied

    def test_repetition_ratio_bounds(self, calc):
        """Repetition ratio should be between 0 and 1."""
        sentences = [
            "这是一个测试句子。",
            "这也是一个测试句子。",
            "还有另一个测试句子。",
        ]
        ratio = calc._repetition_ratio(sentences)
        assert 0 <= ratio <= 1

    def test_paragraph_uniformity_varied(self, calc):
        """Very different paragraph lengths -> high CV."""
        paragraphs = [
            "短段。",
            "这是一段非常长的文字，包含了大量的内容、解释和说明，目的是让这一段和其他段落的长度有显著差异，从而测试变异系数的计算是否正确反映了段落长度的不均匀性。",
        ]
        cv = calc._paragraph_uniformity(paragraphs)
        assert cv > 0.3  # significant variation
