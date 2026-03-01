"""
Comprehensive unit tests for the ScoringEngine.
Covers all flag statuses: GREEN, AMBER, RED, YELLOW, and edge cases.
"""
import pytest

from backend.models.analysis_result import (
    ConfidenceLevel,
    DualAnalysisResult,
    FlagStatus,
    LLMAnalysisResult,
)
from backend.services.scoring_engine import ScoringEngine


@pytest.fixture
def engine():
    return ScoringEngine()


def _make_result(
    provider: str = "anthropic",
    model_id: str = "test-model",
    liability: float = 5000.0,
    confidence: float = 95.0,
    error: str | None = None,
) -> LLMAnalysisResult:
    return LLMAnalysisResult(
        provider=provider,
        model_id=model_id,
        estimated_liability=liability,
        effective_tax_rate=10.0,
        confidence_score=confidence,
        confidence_level=ConfidenceLevel.HIGH if confidence >= 90 else ConfidenceLevel.LOW,
        error=error,
    )


# ── GREEN flag ────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestGreenFlag:
    def test_both_high_confidence_small_delta(self, engine):
        claude = _make_result("anthropic", liability=5000.0, confidence=95.0)
        openai = _make_result("openai", liability=5100.0, confidence=92.0)
        result = engine.compare(claude, openai, "sess-green")

        assert result.flag_status == FlagStatus.GREEN
        assert result.consensus_liability == pytest.approx(5050.0)
        assert result.liability_delta <= 10.0

    def test_identical_results(self, engine):
        claude = _make_result("anthropic", liability=4616.0, confidence=96.0)
        openai = _make_result("openai", liability=4616.0, confidence=93.0)
        result = engine.compare(claude, openai, "sess-identical")

        assert result.flag_status == FlagStatus.GREEN
        assert result.liability_delta == 0.0
        assert result.consensus_liability == pytest.approx(4616.0)

    def test_boundary_exactly_90_confidence(self, engine):
        claude = _make_result("anthropic", liability=10000.0, confidence=90.0)
        openai = _make_result("openai", liability=10000.0, confidence=90.0)
        result = engine.compare(claude, openai, "sess-boundary")

        assert result.flag_status == FlagStatus.GREEN

    def test_boundary_exactly_10pct_delta(self, engine):
        claude = _make_result("anthropic", liability=10000.0, confidence=95.0)
        openai = _make_result("openai", liability=9000.0, confidence=95.0)
        result = engine.compare(claude, openai, "sess-delta-10")

        assert result.flag_status == FlagStatus.GREEN
        assert result.liability_delta == pytest.approx(10.0, abs=0.1)


# ── AMBER flag ────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestAmberFlag:
    def test_claude_low_confidence(self, engine):
        claude = _make_result("anthropic", liability=5000.0, confidence=85.0)
        openai = _make_result("openai", liability=5000.0, confidence=95.0)
        result = engine.compare(claude, openai, "sess-amber-claude")

        assert result.flag_status == FlagStatus.AMBER
        assert "Claude" in result.scoring_rationale or "below 90%" in result.scoring_rationale

    def test_openai_low_confidence(self, engine):
        claude = _make_result("anthropic", liability=5000.0, confidence=95.0)
        openai = _make_result("openai", liability=5000.0, confidence=78.0)
        result = engine.compare(claude, openai, "sess-amber-openai")

        assert result.flag_status == FlagStatus.AMBER

    def test_both_low_confidence_small_delta(self, engine):
        claude = _make_result("anthropic", liability=5000.0, confidence=80.0)
        openai = _make_result("openai", liability=5100.0, confidence=82.0)
        result = engine.compare(claude, openai, "sess-amber-both")

        assert result.flag_status == FlagStatus.AMBER


# ── RED flag ──────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestRedFlag:
    def test_large_liability_delta(self, engine):
        claude = _make_result("anthropic", liability=5000.0, confidence=95.0)
        openai = _make_result("openai", liability=10000.0, confidence=95.0)
        result = engine.compare(claude, openai, "sess-red-delta")

        assert result.flag_status == FlagStatus.RED
        assert result.liability_delta > 10.0
        assert "Manual review" in result.scoring_rationale or "disagreement" in result.scoring_rationale

    def test_hallucinated_liability(self, engine):
        claude = _make_result("anthropic", liability=999999.0, confidence=95.0)
        openai = _make_result("openai", liability=5000.0, confidence=95.0)
        result = engine.compare(claude, openai, "sess-red-hallucinated")

        assert result.flag_status == FlagStatus.RED
        assert result.liability_delta > 10.0

    def test_both_providers_failed(self, engine):
        result = engine.compare(None, None, "sess-red-both-fail")

        assert result.flag_status == FlagStatus.RED
        assert "Both" in result.scoring_rationale
        assert result.consensus_liability is None

    def test_both_providers_errored(self, engine):
        claude = _make_result("anthropic", liability=0.0, error="API timeout")
        openai = _make_result("openai", liability=0.0, error="Rate limited")
        result = engine.compare(claude, openai, "sess-red-both-error")

        assert result.flag_status == FlagStatus.RED


# ── YELLOW flag ───────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestYellowFlag:
    def test_claude_failed_openai_ok(self, engine):
        openai = _make_result("openai", liability=5000.0, confidence=95.0)
        result = engine.compare(None, openai, "sess-yellow-no-claude")

        assert result.flag_status == FlagStatus.YELLOW
        assert result.consensus_liability == pytest.approx(5000.0)
        assert "Claude" in result.scoring_rationale

    def test_openai_failed_claude_ok(self, engine):
        claude = _make_result("anthropic", liability=5000.0, confidence=95.0)
        result = engine.compare(claude, None, "sess-yellow-no-openai")

        assert result.flag_status == FlagStatus.YELLOW
        assert result.consensus_liability == pytest.approx(5000.0)
        assert "OpenAI" in result.scoring_rationale

    def test_claude_errored_openai_ok(self, engine):
        claude = _make_result("anthropic", liability=0.0, error="503 unavailable")
        openai = _make_result("openai", liability=5000.0, confidence=95.0)
        result = engine.compare(claude, openai, "sess-yellow-claude-err")

        assert result.flag_status == FlagStatus.YELLOW


# ── Edge cases ────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestEdgeCases:
    def test_zero_liability_both(self, engine):
        claude = _make_result("anthropic", liability=0.0, confidence=95.0)
        openai = _make_result("openai", liability=0.0, confidence=95.0)
        result = engine.compare(claude, openai, "sess-zero")

        assert result.flag_status == FlagStatus.GREEN
        assert result.consensus_liability == pytest.approx(0.0)
        assert result.liability_delta == 0.0

    def test_very_small_liability(self, engine):
        claude = _make_result("anthropic", liability=1.0, confidence=95.0)
        openai = _make_result("openai", liability=1.05, confidence=95.0)
        result = engine.compare(claude, openai, "sess-tiny")

        assert result.flag_status == FlagStatus.GREEN

    def test_consensus_is_average(self, engine):
        claude = _make_result("anthropic", liability=8000.0, confidence=95.0)
        openai = _make_result("openai", liability=8200.0, confidence=95.0)
        result = engine.compare(claude, openai, "sess-avg")

        assert result.consensus_liability == pytest.approx(8100.0)

    def test_result_has_session_id(self, engine):
        claude = _make_result("anthropic", liability=5000.0, confidence=95.0)
        openai = _make_result("openai", liability=5000.0, confidence=95.0)
        result = engine.compare(claude, openai, "my-session-42")

        assert result.session_id == "my-session-42"
        assert result.completed_at != ""

    def test_result_has_both_llm_results(self, engine):
        claude = _make_result("anthropic", liability=5000.0, confidence=95.0)
        openai = _make_result("openai", liability=5000.0, confidence=95.0)
        result = engine.compare(claude, openai, "sess-results")

        assert result.claude_result is not None
        assert result.openai_result is not None
        assert result.claude_result.provider == "anthropic"
        assert result.openai_result.provider == "openai"
