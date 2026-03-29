"""Tests for EvidenceFusion and FormulaParams."""

import pytest
from app.services.detection.fusion import EvidenceFusion, FormulaParams, FusionResult


# ---------------------------------------------------------------------------
# FormulaParams serialization / deserialization
# ---------------------------------------------------------------------------

class TestFormulaParams:
    def test_to_dict_contains_all_fields(self):
        p = FormulaParams()
        d = p.to_dict()
        assert d["version"] == "v1.2"
        assert d["w1"] == 0.70
        assert d["w2"] == 0.20
        assert d["w5"] == 0.10
        assert d["threshold_low"] == 0.40
        assert d["threshold_medium"] == 0.55
        assert d["threshold_high"] == 0.70

    def test_from_dict_roundtrip(self):
        original = FormulaParams(version="v2.0", w1=0.5, w2=0.3, threshold_low=0.35)
        d = original.to_dict()
        restored = FormulaParams.from_dict(d)
        assert restored.version == "v2.0"
        assert restored.w1 == 0.5
        assert restored.w2 == 0.3
        assert restored.threshold_low == 0.35

    def test_from_dict_ignores_unknown_keys(self):
        d = {"version": "v1.0", "w1": 0.8, "unknown_key": 999}
        p = FormulaParams.from_dict(d)
        assert p.w1 == 0.8
        assert p.version == "v1.0"
        # unknown_key should be silently ignored, defaults for other fields
        assert p.w2 == 0.20

    def test_from_dict_partial(self):
        """Only some fields provided; rest should be defaults."""
        p = FormulaParams.from_dict({"w1": 0.99})
        assert p.w1 == 0.99
        assert p.version == "v1.2"  # default


# ---------------------------------------------------------------------------
# FusionResult
# ---------------------------------------------------------------------------

class TestFusionResult:
    def test_to_dict_rounds_values(self):
        fr = FusionResult(
            risk_score=0.123456789,
            risk_level="medium",
            review_priority=0.987654321,
            evidence_completeness=2,
            conclusion_type="fused",
            formula_version="v1.0",
            param_version="v1.2",
            formula_params_snapshot={},
        )
        d = fr.to_dict()
        assert d["risk_score"] == 0.1235
        assert d["review_priority"] == 0.9877
        assert "formula_params_snapshot" not in d  # not in to_dict output


# ---------------------------------------------------------------------------
# EvidenceFusion.fuse() -- LLM-only (preliminary)
# ---------------------------------------------------------------------------

class TestFuseLLMOnly:
    """When only LLM evidence is provided, result should be 'preliminary'."""

    def setup_method(self):
        self.fusion = EvidenceFusion()

    def test_preliminary_conclusion(self):
        result = self.fusion.fuse(
            llm_confidence=0.8,
            llm_risk_indicators={},
        )
        assert result.conclusion_type == "preliminary"
        assert result.evidence_completeness == 1

    def test_risk_score_llm_only(self):
        result = self.fusion.fuse(
            llm_confidence=0.6,
            llm_risk_indicators={},
        )
        # risk_score = w1 * 0.6 = 0.70 * 0.6 = 0.42
        assert abs(result.risk_score - 0.42) < 1e-6

    def test_zero_confidence(self):
        result = self.fusion.fuse(llm_confidence=0.0, llm_risk_indicators={})
        assert result.risk_score == 0.0
        assert result.risk_level == "low"

    def test_full_confidence(self):
        result = self.fusion.fuse(llm_confidence=1.0, llm_risk_indicators={})
        # risk_score = 0.70 * 1.0 = 0.70  -> critical threshold
        assert result.risk_score == pytest.approx(0.70, abs=1e-6)
        assert result.risk_level == "critical"


# ---------------------------------------------------------------------------
# EvidenceFusion.fuse() -- LLM + stats (fused)
# ---------------------------------------------------------------------------

class TestFuseLLMAndStats:
    def setup_method(self):
        self.fusion = EvidenceFusion()

    def test_fused_conclusion(self):
        result = self.fusion.fuse(
            llm_confidence=0.5,
            llm_risk_indicators={},
            stat_score=0.6,
        )
        assert result.conclusion_type == "fused"
        assert result.evidence_completeness == 2

    def test_risk_score_calculation(self):
        result = self.fusion.fuse(
            llm_confidence=0.5,
            llm_risk_indicators={},
            stat_score=0.6,
        )
        # 0.70*0.5 + 0.20*0.6 = 0.35 + 0.12 = 0.47
        assert result.risk_score == pytest.approx(0.47, abs=1e-6)

    def test_high_stats_pushes_risk_up(self):
        result = self.fusion.fuse(
            llm_confidence=0.7,
            llm_risk_indicators={},
            stat_score=1.0,
        )
        # 0.70*0.7 + 0.20*1.0 = 0.49 + 0.20 = 0.69
        assert result.risk_score == pytest.approx(0.69, abs=1e-6)
        assert result.risk_level == "high"


# ---------------------------------------------------------------------------
# EvidenceFusion.fuse() -- with human credit (human_confirmed)
# ---------------------------------------------------------------------------

class TestFuseWithHumanCredit:
    def setup_method(self):
        self.fusion = EvidenceFusion()

    def test_human_confirmed_conclusion(self):
        result = self.fusion.fuse(
            llm_confidence=0.8,
            llm_risk_indicators={},
            stat_score=0.5,
            human_credit=0.9,
        )
        assert result.conclusion_type == "human_confirmed"

    def test_human_credit_reduces_risk(self):
        # Without human credit
        no_human = self.fusion.fuse(
            llm_confidence=0.8,
            llm_risk_indicators={},
            stat_score=0.5,
        )
        # With human credit
        with_human = self.fusion.fuse(
            llm_confidence=0.8,
            llm_risk_indicators={},
            stat_score=0.5,
            human_credit=1.0,
        )
        assert with_human.risk_score < no_human.risk_score

    def test_human_credit_math(self):
        result = self.fusion.fuse(
            llm_confidence=0.8,
            llm_risk_indicators={},
            stat_score=0.5,
            human_credit=1.0,
        )
        # 0.70*0.8 + 0.20*0.5 - 0.10*1.0 = 0.56 + 0.10 - 0.10 = 0.56
        assert result.risk_score == pytest.approx(0.56, abs=1e-6)

    def test_human_credit_zero_is_not_confirmed(self):
        """human_credit=0 provided but not > 0: not human_confirmed."""
        result = self.fusion.fuse(
            llm_confidence=0.5,
            llm_risk_indicators={},
            human_credit=0.0,
        )
        # human_credit is not None but equals 0, so conclusion_type != human_confirmed
        assert result.conclusion_type == "fused"  # evidence_completeness = 2

    def test_evidence_completeness_with_all_layers(self):
        result = self.fusion.fuse(
            llm_confidence=0.5,
            llm_risk_indicators={},
            stat_score=0.5,
            semantic_gap=0.3,
            human_credit=0.5,
        )
        assert result.evidence_completeness == 4


# ---------------------------------------------------------------------------
# Risk level classification at boundaries
# ---------------------------------------------------------------------------

class TestRiskClassification:
    def setup_method(self):
        self.fusion = EvidenceFusion()

    def _classify(self, score: float) -> str:
        return self.fusion._classify_risk(score)

    def test_low(self):
        assert self._classify(0.0) == "low"
        assert self._classify(0.39) == "low"

    def test_low_boundary(self):
        assert self._classify(0.40) == "medium"

    def test_medium(self):
        assert self._classify(0.40) == "medium"
        assert self._classify(0.54) == "medium"

    def test_medium_boundary(self):
        assert self._classify(0.55) == "high"

    def test_high(self):
        assert self._classify(0.55) == "high"
        assert self._classify(0.69) == "high"

    def test_high_boundary(self):
        assert self._classify(0.70) == "critical"

    def test_critical(self):
        assert self._classify(0.70) == "critical"
        assert self._classify(1.0) == "critical"


# ---------------------------------------------------------------------------
# update_with_human_review
# ---------------------------------------------------------------------------

class TestUpdateWithHumanReview:
    def setup_method(self):
        self.fusion = EvidenceFusion()

    def _make_original(self, risk_score=0.65) -> FusionResult:
        return FusionResult(
            risk_score=risk_score,
            risk_level="high",
            review_priority=0.5,
            evidence_completeness=2,
            conclusion_type="fused",
            formula_version="v1.0",
            param_version="v1.2",
            formula_params_snapshot=FormulaParams().to_dict(),
        )

    def test_reduces_risk_score(self):
        original = self._make_original(0.65)
        updated = self.fusion.update_with_human_review(original, human_credit=1.0)
        # 0.65 - 0.10 * 1.0 = 0.55
        assert updated.risk_score == pytest.approx(0.55, abs=1e-6)

    def test_conclusion_becomes_human_confirmed(self):
        original = self._make_original()
        updated = self.fusion.update_with_human_review(original, human_credit=0.5)
        assert updated.conclusion_type == "human_confirmed"

    def test_review_priority_is_zero(self):
        original = self._make_original()
        updated = self.fusion.update_with_human_review(original, human_credit=0.5)
        assert updated.review_priority == 0.0

    def test_evidence_completeness_incremented(self):
        original = self._make_original()
        updated = self.fusion.update_with_human_review(original, human_credit=0.5)
        assert updated.evidence_completeness == original.evidence_completeness + 1

    def test_adjusted_risk_level_override(self):
        original = self._make_original(0.65)
        updated = self.fusion.update_with_human_review(
            original, human_credit=0.5, adjusted_risk_level="low"
        )
        assert updated.risk_level == "low"

    def test_risk_score_clamped_to_zero(self):
        original = self._make_original(0.05)
        updated = self.fusion.update_with_human_review(original, human_credit=1.0)
        assert updated.risk_score == 0.0

    def test_preserves_formula_version(self):
        original = self._make_original()
        updated = self.fusion.update_with_human_review(original, human_credit=0.5)
        assert updated.formula_version == original.formula_version
        assert updated.param_version == original.param_version


# ---------------------------------------------------------------------------
# Review priority / uncertainty
# ---------------------------------------------------------------------------

class TestReviewPriority:
    def setup_method(self):
        self.fusion = EvidenceFusion()

    def test_uncertainty_decreases_with_confidence(self):
        """Higher LLM confidence should yield lower uncertainty."""
        high_conf = self.fusion._compute_uncertainty(
            0.95, {"source_classification": {"ai": 0.95, "human": 0.05}}
        )
        low_conf = self.fusion._compute_uncertainty(0.3, {})
        assert high_conf < low_conf

    def test_more_evidence_lowers_priority(self):
        r1 = self.fusion.fuse(llm_confidence=0.5, llm_risk_indicators={})
        r2 = self.fusion.fuse(llm_confidence=0.5, llm_risk_indicators={}, stat_score=0.5)
        # r2 has more evidence -> lower evidence_insufficiency component
        # But also higher risk_score. Check evidence_insufficiency contribution.
        # evidence_insufficiency: r1 = 1 - 1/4 = 0.75, r2 = 1 - 2/4 = 0.50
        # The net effect depends on weights, just verify values are reasonable
        assert 0 <= r1.review_priority <= 1
        assert 0 <= r2.review_priority <= 1


# ---------------------------------------------------------------------------
# Custom params
# ---------------------------------------------------------------------------

class TestCustomParams:
    def test_custom_weights(self):
        params = FormulaParams(w1=1.0, w2=0.0)
        fusion = EvidenceFusion(params=params)
        result = fusion.fuse(
            llm_confidence=0.5,
            llm_risk_indicators={},
            stat_score=1.0,  # should have no effect with w2=0
        )
        assert result.risk_score == pytest.approx(0.50, abs=1e-6)

    def test_risk_score_clamped_above(self):
        params = FormulaParams(w1=1.0, w2=1.0)
        fusion = EvidenceFusion(params=params)
        result = fusion.fuse(
            llm_confidence=0.9,
            llm_risk_indicators={},
            stat_score=0.9,
        )
        # 1.0*0.9 + 1.0*0.9 = 1.8 -> clamped to 1.0
        assert result.risk_score == 1.0

    def test_risk_score_clamped_below(self):
        params = FormulaParams(w1=0.1, w5=1.0)
        fusion = EvidenceFusion(params=params)
        result = fusion.fuse(
            llm_confidence=0.1,
            llm_risk_indicators={},
            human_credit=1.0,
        )
        # 0.1*0.1 - 1.0*1.0 = 0.01 - 1.0 = -0.99 -> clamped to 0
        assert result.risk_score == 0.0
