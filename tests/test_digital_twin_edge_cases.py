"""
Digital twin edge-case tests — offline fault injection.
No running backend needed. Exercises the ScoringEngine and Evaluator
with mock LLMAnalysisResult data matching scenarios TS-06 through TS-12.
"""
import pytest

from backend.models.analysis_result import (
    ConfidenceLevel,
    FlagStatus,
    LLMAnalysisResult,
)
from backend.services.scoring_engine import ScoringEngine
from tests.digital_twin.evaluation import Evaluator, EvaluationResult


@pytest.fixture
def engine():
    return ScoringEngine()


@pytest.fixture
def evaluator():
    return Evaluator()


def _make_result(
    provider: str,
    liability: float,
    confidence: float,
    error: str | None = None,
) -> LLMAnalysisResult:
    return LLMAnalysisResult(
        provider=provider,
        model_id=f"mock-{provider}",
        estimated_liability=liability,
        effective_tax_rate=10.0,
        confidence_score=confidence,
        confidence_level=ConfidenceLevel.HIGH if confidence >= 90 else ConfidenceLevel.LOW,
        error=error,
    )


TS01_GROUND_TRUTH = 4616.0


# ── TS-07: Low confidence → AMBER ────────────────────────────────────────────

@pytest.mark.unit
class TestTS07LowConfidence:
    def test_scoring_produces_amber(self, engine):
        claude = _make_result("anthropic", TS01_GROUND_TRUTH, confidence=75.0)
        openai = _make_result("openai", TS01_GROUND_TRUTH, confidence=95.0)
        result = engine.compare(claude, openai, "ts07")

        assert result.flag_status == FlagStatus.AMBER

    def test_evaluator_flags_mismatch(self, evaluator):
        result = evaluator.evaluate(
            scenario_id="TS-07",
            ground_truth_liability=TS01_GROUND_TRUTH,
            estimated_liability=TS01_GROUND_TRUTH,
            flag_status="AMBER",
            expected_flag="AMBER",
            latencies_ms=[1500.0],
        )
        assert result.passed
        assert result.liability_accurate


# ── TS-08: Hallucination → RED ────────────────────────────────────────────────

@pytest.mark.unit
class TestTS08Hallucination:
    def test_scoring_produces_red(self, engine):
        claude = _make_result("anthropic", 999999.0, confidence=95.0)
        openai = _make_result("openai", TS01_GROUND_TRUTH, confidence=95.0)
        result = engine.compare(claude, openai, "ts08")

        assert result.flag_status == FlagStatus.RED
        assert result.liability_delta > 10.0

    def test_evaluator_detects_liability_mismatch(self, evaluator):
        result = evaluator.evaluate(
            scenario_id="TS-08",
            ground_truth_liability=TS01_GROUND_TRUTH,
            estimated_liability=502307.5,  # average of hallucinated + real
            flag_status="RED",
            expected_flag="RED",
            latencies_ms=[2000.0],
        )
        assert not result.liability_accurate
        assert result.flag_precision == 1.0


# ── TS-09: Claude failure → YELLOW ───────────────────────────────────────────

@pytest.mark.unit
class TestTS09ClaudeFailure:
    def test_scoring_produces_yellow(self, engine):
        openai = _make_result("openai", TS01_GROUND_TRUTH, confidence=95.0)
        result = engine.compare(None, openai, "ts09")

        assert result.flag_status == FlagStatus.YELLOW
        assert result.consensus_liability == pytest.approx(TS01_GROUND_TRUTH)

    def test_evaluator_flag_correct(self, evaluator):
        result = evaluator.evaluate(
            scenario_id="TS-09",
            ground_truth_liability=TS01_GROUND_TRUTH,
            estimated_liability=TS01_GROUND_TRUTH,
            flag_status="YELLOW",
            expected_flag="YELLOW",
            latencies_ms=[1000.0],
        )
        assert result.passed


# ── TS-10: OpenAI failure → YELLOW ───────────────────────────────────────────

@pytest.mark.unit
class TestTS10OpenAIFailure:
    def test_scoring_produces_yellow(self, engine):
        claude = _make_result("anthropic", TS01_GROUND_TRUTH, confidence=95.0)
        result = engine.compare(claude, None, "ts10")

        assert result.flag_status == FlagStatus.YELLOW
        assert result.consensus_liability == pytest.approx(TS01_GROUND_TRUTH)

    def test_evaluator_flag_correct(self, evaluator):
        result = evaluator.evaluate(
            scenario_id="TS-10",
            ground_truth_liability=TS01_GROUND_TRUTH,
            estimated_liability=TS01_GROUND_TRUTH,
            flag_status="YELLOW",
            expected_flag="YELLOW",
            latencies_ms=[800.0],
        )
        assert result.passed


# ── TS-11: Both fail → RED ───────────────────────────────────────────────────

@pytest.mark.unit
class TestTS11BothFail:
    def test_scoring_produces_red(self, engine):
        result = engine.compare(None, None, "ts11")

        assert result.flag_status == FlagStatus.RED
        assert result.consensus_liability is None

    def test_evaluator_detects_failure(self, evaluator):
        result = evaluator.evaluate(
            scenario_id="TS-11",
            ground_truth_liability=TS01_GROUND_TRUTH,
            estimated_liability=0.0,
            flag_status="RED",
            expected_flag="RED",
            latencies_ms=[500.0],
        )
        assert not result.liability_accurate
        assert result.flag_precision == 1.0


# ── TS-12: Slow response → GREEN (latency check) ────────────────────────────

@pytest.mark.unit
class TestTS12SlowResponse:
    def test_scoring_still_green_when_accurate(self, engine):
        claude = _make_result("anthropic", TS01_GROUND_TRUTH, confidence=95.0)
        openai = _make_result("openai", TS01_GROUND_TRUTH, confidence=93.0)
        result = engine.compare(claude, openai, "ts12")

        assert result.flag_status == FlagStatus.GREEN

    def test_evaluator_passes_if_under_threshold(self, evaluator):
        result = evaluator.evaluate(
            scenario_id="TS-12",
            ground_truth_liability=TS01_GROUND_TRUTH,
            estimated_liability=TS01_GROUND_TRUTH,
            flag_status="GREEN",
            expected_flag="GREEN",
            latencies_ms=[5000.0, 5200.0, 5100.0],
        )
        assert result.passed
        assert result.latency_p95_ms < 30000

    def test_evaluator_fails_if_over_threshold(self, evaluator):
        result = evaluator.evaluate(
            scenario_id="TS-12-over",
            ground_truth_liability=TS01_GROUND_TRUTH,
            estimated_liability=TS01_GROUND_TRUTH,
            flag_status="GREEN",
            expected_flag="GREEN",
            latencies_ms=[35000.0, 36000.0],
        )
        assert not result.passed
        assert any("latency" in f.lower() for f in result.failures)


# ── Evaluator unit tests ─────────────────────────────────────────────────────

@pytest.mark.unit
class TestEvaluator:
    def test_liability_tolerance(self, evaluator):
        result = evaluator.evaluate(
            scenario_id="tol-pass",
            ground_truth_liability=5000.0,
            estimated_liability=5040.0,
            flag_status="GREEN",
            expected_flag="GREEN",
            latencies_ms=[1000.0],
        )
        assert result.liability_accurate
        assert result.liability_delta_usd == pytest.approx(40.0)

    def test_liability_tolerance_exceeded(self, evaluator):
        result = evaluator.evaluate(
            scenario_id="tol-fail",
            ground_truth_liability=5000.0,
            estimated_liability=5100.0,
            flag_status="GREEN",
            expected_flag="GREEN",
            latencies_ms=[1000.0],
        )
        assert not result.liability_accurate

    def test_flag_mismatch_fails(self, evaluator):
        result = evaluator.evaluate(
            scenario_id="flag-fail",
            ground_truth_liability=5000.0,
            estimated_liability=5000.0,
            flag_status="GREEN",
            expected_flag="AMBER",
            latencies_ms=[1000.0],
        )
        assert not result.passed
        assert result.flag_precision == 0.0

    def test_empty_latencies(self, evaluator):
        result = evaluator.evaluate(
            scenario_id="no-lat",
            ground_truth_liability=5000.0,
            estimated_liability=5000.0,
            flag_status="GREEN",
            expected_flag="GREEN",
            latencies_ms=[],
        )
        assert result.latency_p95_ms == 0.0
        assert result.passed

    def test_p95_calculation(self, evaluator):
        latencies = [100.0 * i for i in range(1, 21)]  # 100..2000
        result = evaluator.evaluate(
            scenario_id="p95-calc",
            ground_truth_liability=0.0,
            estimated_liability=0.0,
            flag_status="GREEN",
            expected_flag="GREEN",
            latencies_ms=latencies,
        )
        assert result.latency_p95_ms == pytest.approx(1900.0, abs=200.0)
