"""
Offline E2E tests for non-GREEN flag scenarios.
Exercises the full calculator → mock LLM → scoring → audit pipeline
for AMBER, RED, and YELLOW flag conditions.
"""
import json
import uuid
from pathlib import Path

import pytest

from backend.audit.audit_logger import AuditEvent, AuditEventType
from backend.models.analysis_result import (
    ConfidenceLevel,
    DualAnalysisResult,
    FlagStatus,
    LLMAnalysisResult,
)
from backend.services.scoring_engine import ScoringEngine
from backend.tools.calculator_tool import STANDARD_DEDUCTIONS_2025, TaxCalculator
from tests.digital_twin.factories.taxpayer_factory import TaxpayerFactory


@pytest.fixture
def calculator():
    return TaxCalculator()


@pytest.fixture
def scoring_engine():
    return ScoringEngine()


@pytest.fixture
def tmp_audit_dir(tmp_path):
    audit_dir = tmp_path / "audit"
    audit_dir.mkdir()
    return audit_dir


def _make_result(
    provider: str,
    model_id: str,
    liability: float,
    confidence: float,
    error: str | None = None,
) -> LLMAnalysisResult:
    return LLMAnalysisResult(
        provider=provider,
        model_id=model_id,
        estimated_liability=liability,
        effective_tax_rate=10.0,
        applicable_deductions=[],
        applicable_credits=[],
        advisory_notes=[],
        confidence_score=confidence,
        confidence_level=ConfidenceLevel.HIGH if confidence >= 90 else ConfidenceLevel.LOW,
        error=error,
        latency_ms=1200.0,
    )


def _write_audit_events(
    audit_dir: Path,
    session_id: str,
    flag_status: str,
    scenario_label: str,
) -> Path:
    jsonl_path = audit_dir / f"session_{session_id}.jsonl"
    events = [
        AuditEvent(
            session_id=session_id,
            event_type=AuditEventType.SESSION_STARTED,
            agent_name="e2e_flag_test",
            output_summary=f"Flag scenario: {scenario_label}",
        ),
        AuditEvent(
            session_id=session_id,
            event_type=AuditEventType.ANALYSIS_COMPLETED,
            agent_name="e2e_flag_test",
            flag_status=flag_status,
            output_summary=f"Flag: {flag_status}",
        ),
        AuditEvent(
            session_id=session_id,
            event_type=AuditEventType.SCORING_FLAG_ASSIGNED,
            agent_name="scoring_engine",
            flag_status=flag_status,
        ),
        AuditEvent(
            session_id=session_id,
            event_type=AuditEventType.SESSION_ENDED,
            agent_name="e2e_flag_test",
        ),
    ]
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for event in events:
            f.write(event.model_dump_json() + "\n")
    return jsonl_path


def _run_calculator_for_profile(calculator, profile_id="TS-01"):
    profile = TaxpayerFactory.create(profile_id)
    total_income = profile.wages + profile.other_income
    standard_ded = STANDARD_DEDUCTIONS_2025.get(profile.filing_status, 15750)
    use_standard = profile.itemized_deductions <= standard_ded

    calc_result = calculator.compute_federal_tax(
        income=total_income,
        filing_status=profile.filing_status,
        year=2025,
        deductions=profile.itemized_deductions,
        use_standard_deduction=use_standard,
    )
    credits_result = calculator.apply_credits(calc_result["federal_tax"], profile.credits)
    return profile, calc_result, credits_result


# ── AMBER: one LLM low confidence ───────────────────────────────────────────

@pytest.mark.e2e
class TestAmberFlagE2E:
    def test_claude_low_confidence_amber(self, calculator, scoring_engine, tmp_audit_dir):
        profile, calc_result, credits_result = _run_calculator_for_profile(calculator)
        liability = credits_result["final_liability"]
        session_id = str(uuid.uuid4())[:8]

        claude = _make_result("anthropic", "claude-opus-4-6", liability, confidence=80.0)
        openai = _make_result("openai", "gpt-4o", liability, confidence=95.0)
        dual = scoring_engine.compare(claude, openai, session_id)

        assert dual.flag_status == FlagStatus.AMBER
        assert dual.consensus_liability == pytest.approx(liability, rel=0.01)

        jsonl = _write_audit_events(tmp_audit_dir, session_id, "AMBER", "Claude low confidence")
        assert jsonl.exists()
        lines = jsonl.read_text().strip().split("\n")
        assert len(lines) >= 4
        flag_events = [l for l in lines if "AMBER" in l]
        assert len(flag_events) >= 1

    def test_openai_low_confidence_amber(self, calculator, scoring_engine, tmp_audit_dir):
        profile, calc_result, credits_result = _run_calculator_for_profile(calculator)
        liability = credits_result["final_liability"]
        session_id = str(uuid.uuid4())[:8]

        claude = _make_result("anthropic", "claude-opus-4-6", liability, confidence=94.0)
        openai = _make_result("openai", "gpt-4o", liability, confidence=78.0)
        dual = scoring_engine.compare(claude, openai, session_id)

        assert dual.flag_status == FlagStatus.AMBER


# ── RED: large liability delta ───────────────────────────────────────────────

@pytest.mark.e2e
class TestRedFlagE2E:
    def test_liability_disagreement_red(self, calculator, scoring_engine, tmp_audit_dir):
        profile, calc_result, credits_result = _run_calculator_for_profile(calculator)
        liability = credits_result["final_liability"]
        session_id = str(uuid.uuid4())[:8]

        claude = _make_result("anthropic", "claude-opus-4-6", liability, confidence=95.0)
        openai = _make_result("openai", "gpt-4o", liability * 2.5, confidence=95.0)
        dual = scoring_engine.compare(claude, openai, session_id)

        assert dual.flag_status == FlagStatus.RED
        assert dual.liability_delta > 10.0

        jsonl = _write_audit_events(tmp_audit_dir, session_id, "RED", "Liability disagreement")
        assert jsonl.exists()

    def test_hallucinated_claude_red(self, calculator, scoring_engine, tmp_audit_dir):
        profile, calc_result, credits_result = _run_calculator_for_profile(calculator)
        liability = credits_result["final_liability"]
        session_id = str(uuid.uuid4())[:8]

        claude = _make_result("anthropic", "claude-opus-4-6", 999999.0, confidence=95.0)
        openai = _make_result("openai", "gpt-4o", liability, confidence=95.0)
        dual = scoring_engine.compare(claude, openai, session_id)

        assert dual.flag_status == FlagStatus.RED

    def test_both_providers_failed_red(self, scoring_engine, tmp_audit_dir):
        session_id = str(uuid.uuid4())[:8]
        dual = scoring_engine.compare(None, None, session_id)

        assert dual.flag_status == FlagStatus.RED
        assert dual.consensus_liability is None
        assert "Both" in dual.scoring_rationale

        jsonl = _write_audit_events(tmp_audit_dir, session_id, "RED", "Both providers failed")
        assert jsonl.exists()


# ── YELLOW: single provider failure ──────────────────────────────────────────

@pytest.mark.e2e
class TestYellowFlagE2E:
    def test_claude_none_yellow(self, calculator, scoring_engine, tmp_audit_dir):
        profile, calc_result, credits_result = _run_calculator_for_profile(calculator)
        liability = credits_result["final_liability"]
        session_id = str(uuid.uuid4())[:8]

        openai = _make_result("openai", "gpt-4o", liability, confidence=95.0)
        dual = scoring_engine.compare(None, openai, session_id)

        assert dual.flag_status == FlagStatus.YELLOW
        assert dual.consensus_liability == pytest.approx(liability)
        assert "Claude" in dual.scoring_rationale

        jsonl = _write_audit_events(tmp_audit_dir, session_id, "YELLOW", "Claude failed")
        assert jsonl.exists()

    def test_openai_none_yellow(self, calculator, scoring_engine, tmp_audit_dir):
        profile, calc_result, credits_result = _run_calculator_for_profile(calculator)
        liability = credits_result["final_liability"]
        session_id = str(uuid.uuid4())[:8]

        claude = _make_result("anthropic", "claude-opus-4-6", liability, confidence=95.0)
        dual = scoring_engine.compare(claude, None, session_id)

        assert dual.flag_status == FlagStatus.YELLOW
        assert "OpenAI" in dual.scoring_rationale

    def test_claude_error_field_yellow(self, calculator, scoring_engine, tmp_audit_dir):
        profile, calc_result, credits_result = _run_calculator_for_profile(calculator)
        liability = credits_result["final_liability"]
        session_id = str(uuid.uuid4())[:8]

        claude = _make_result(
            "anthropic", "claude-opus-4-6", 0.0, confidence=0.0,
            error="503 Service Unavailable",
        )
        openai = _make_result("openai", "gpt-4o", liability, confidence=95.0)
        dual = scoring_engine.compare(claude, openai, session_id)

        assert dual.flag_status == FlagStatus.YELLOW


# ── Cross-profile flag scenarios ─────────────────────────────────────────────

@pytest.mark.e2e
class TestCrossProfileFlags:
    @pytest.mark.parametrize("profile_id", ["TS-01", "TS-02", "TS-03", "TS-04", "TS-05"])
    def test_green_flag_per_profile(self, calculator, scoring_engine, profile_id):
        """Every profile should produce GREEN when both LLMs agree."""
        profile, calc_result, credits_result = _run_calculator_for_profile(
            calculator, profile_id
        )
        liability = credits_result["final_liability"]

        claude = _make_result("anthropic", "claude-opus-4-6", liability, confidence=95.0)
        openai = _make_result("openai", "gpt-4o", liability * 1.01, confidence=93.0)
        dual = scoring_engine.compare(claude, openai, f"cross-{profile_id}")

        assert dual.flag_status == FlagStatus.GREEN, (
            f"[{profile_id}] Expected GREEN, got {dual.flag_status.value}: "
            f"{dual.scoring_rationale}"
        )

    @pytest.mark.parametrize("profile_id", ["TS-01", "TS-02", "TS-03", "TS-04", "TS-05"])
    def test_red_flag_per_profile_on_hallucination(self, calculator, scoring_engine, profile_id):
        """Every profile should produce RED when Claude hallucinates."""
        profile, calc_result, credits_result = _run_calculator_for_profile(
            calculator, profile_id
        )
        liability = credits_result["final_liability"]

        claude = _make_result("anthropic", "claude-opus-4-6", 999999.0, confidence=95.0)
        openai = _make_result("openai", "gpt-4o", liability, confidence=95.0)
        dual = scoring_engine.compare(claude, openai, f"hallu-{profile_id}")

        assert dual.flag_status == FlagStatus.RED
