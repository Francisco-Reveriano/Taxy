"""
End-to-end tax scenario test — full pipeline through calculator, dual-LLM scoring,
audit report generation, and IRS 1040-style tax summary.

Parameterized over all 5 ground-truth profiles (TS-01 through TS-05).
No external API calls — all LLM/OCR results are mocked with realistic data.
"""
import json
import random
import uuid
from pathlib import Path

import pytest

from backend.audit.audit_logger import AuditEvent, AuditEventType, AuditLogger
from backend.models.analysis_result import (
    ConfidenceLevel,
    DualAnalysisResult,
    FlagStatus,
    LLMAnalysisResult,
)
from backend.services.scoring_engine import ScoringEngine
from backend.tools.calculator_tool import STANDARD_DEDUCTIONS_2025, TaxCalculator
from tests.digital_twin.factories.taxpayer_factory import TaxpayerFactory, TaxpayerProfile
from tests.e2e.tax_summary_report import BracketLine, CreditLine, TaxSummaryReport


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_audit_dir(tmp_path):
    """Temporary directory for JSONL audit logs and generated reports."""
    audit_dir = tmp_path / "audit"
    audit_dir.mkdir()
    return audit_dir


@pytest.fixture
def calculator():
    return TaxCalculator()


@pytest.fixture
def scoring_engine():
    return ScoringEngine()


# ---------------------------------------------------------------------------
# Parameterization: all 5 profiles
# ---------------------------------------------------------------------------
ALL_PROFILES = [
    "TS-01",
    "TS-02",
    "TS-03",
    "TS-04",
    "TS-05",
]


def _build_mock_llm_result(
    provider: str,
    model_id: str,
    base_liability: float,
    noise_pct: float,
    credits_applied: list[dict],
    effective_rate: float,
) -> LLMAnalysisResult:
    """Build a realistic LLM analysis result derived from calculator output."""
    # Add small noise to simulate LLM estimation variance
    random.seed(hash((provider, base_liability)))
    noise = base_liability * noise_pct * (random.random() * 2 - 1)
    estimated = round(base_liability + noise, 2)

    return LLMAnalysisResult(
        provider=provider,
        model_id=model_id,
        estimated_liability=max(0.0, estimated),
        effective_tax_rate=round(effective_rate + random.uniform(-0.5, 0.5), 2),
        applicable_deductions=[{"name": "Standard/Itemized", "amount": 0.0}],
        applicable_credits=credits_applied,
        advisory_notes=[f"Estimated via {model_id} analysis"],
        confidence_score=round(random.uniform(91.0, 96.0), 1),
        confidence_level=ConfidenceLevel.HIGH,
        latency_ms=round(random.uniform(800.0, 2500.0), 1),
    )


def _write_mock_audit_events(
    audit_dir: Path,
    session_id: str,
    profile: TaxpayerProfile,
    calc_result: dict,
    dual_result: DualAnalysisResult,
) -> Path:
    """Write mock audit events to a JSONL file and return its path."""
    jsonl_path = audit_dir / f"session_{session_id}.jsonl"

    events = [
        AuditEvent(
            session_id=session_id,
            event_type=AuditEventType.SESSION_STARTED,
            agent_name="e2e_test",
            output_summary=f"E2E test session for {profile.name} ({profile.profile_id})",
        ),
        AuditEvent(
            session_id=session_id,
            event_type=AuditEventType.DOCUMENT_UPLOADED,
            agent_name="e2e_test",
            input_summary=f"W-2 for {profile.name}",
            metadata={"doc_type": "W-2", "sha256": "abc123fake"},
        ),
        AuditEvent(
            session_id=session_id,
            event_type=AuditEventType.OCR_COMPLETED,
            agent_name="mistral_ocr",
            input_summary=f"W-2 for {profile.name}",
            metadata={"field_count": 8},
        ),
        AuditEvent(
            session_id=session_id,
            event_type=AuditEventType.TOOL_INVOKED,
            tool_name="calculator_tool",
            input_summary=f"income={calc_result['gross_income']}, status={profile.filing_status}",
        ),
        AuditEvent(
            session_id=session_id,
            event_type=AuditEventType.TOOL_COMPLETED,
            tool_name="calculator_tool",
            output_summary=f"federal_tax=${calc_result['federal_tax']:,.2f}",
        ),
        AuditEvent(
            session_id=session_id,
            event_type=AuditEventType.ANALYSIS_COMPLETED,
            agent_name="claude",
            model_id="claude-opus-4-6",
            confidence_score=dual_result.claude_result.confidence_score if dual_result.claude_result else 0,
            flag_status=dual_result.flag_status.value,
            output_summary=f"Estimated liability: ${dual_result.claude_result.estimated_liability:,.2f}" if dual_result.claude_result else "N/A",
        ),
        AuditEvent(
            session_id=session_id,
            event_type=AuditEventType.SCORING_COMPARISON,
            agent_name="scoring_engine",
            output_summary=f"delta={dual_result.liability_delta:.1f}%, flag={dual_result.flag_status.value}",
            metadata={
                "claude_confidence": dual_result.claude_result.confidence_score if dual_result.claude_result else 0,
                "openai_confidence": dual_result.openai_result.confidence_score if dual_result.openai_result else 0,
                "liability_delta": dual_result.liability_delta,
                "claude_liability": dual_result.claude_result.estimated_liability if dual_result.claude_result else 0,
                "openai_liability": dual_result.openai_result.estimated_liability if dual_result.openai_result else 0,
            },
        ),
        AuditEvent(
            session_id=session_id,
            event_type=AuditEventType.SESSION_ENDED,
            agent_name="e2e_test",
            output_summary="E2E test complete",
        ),
    ]

    with open(jsonl_path, "w", encoding="utf-8") as f:
        for event in events:
            f.write(event.model_dump_json() + "\n")

    return jsonl_path


@pytest.mark.parametrize("profile_id", ALL_PROFILES, ids=ALL_PROFILES)
def test_e2e_tax_scenario(
    profile_id: str,
    tmp_audit_dir: Path,
    calculator: TaxCalculator,
    scoring_engine: ScoringEngine,
):
    """
    Full E2E pipeline for one taxpayer profile:
    1. Load profile
    2. Run calculator
    3. Build mock dual-LLM results
    4. Run scoring engine
    5. Write audit JSONL
    6. Generate IRS 1040-style tax summary (text + PDF)
    7. Assert correctness
    """
    session_id = str(uuid.uuid4())[:8]

    # ── Step 1: Load profile ──────────────────────────────────────────
    profile = TaxpayerFactory.create(profile_id)
    tax_data = TaxpayerFactory.to_tax_data(profile)

    # ── Step 2: Run calculator ────────────────────────────────────────
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
    fica_result = calculator.compute_fica(profile.wages)
    deduction_cmp = calculator.compare_deductions(standard_ded, profile.itemized_deductions)
    credits_result = calculator.apply_credits(calc_result["federal_tax"], profile.credits)

    # ── Step 3: Build mock LLM results ────────────────────────────────
    # Derive from calculator output with ±2% noise to simulate LLM estimation
    final_liability_after_credits = credits_result["final_liability"]

    claude_result = _build_mock_llm_result(
        provider="anthropic",
        model_id="claude-opus-4-6",
        base_liability=final_liability_after_credits,
        noise_pct=0.02,
        credits_applied=credits_result["credits_applied"],
        effective_rate=calc_result["effective_rate_pct"],
    )
    openai_result = _build_mock_llm_result(
        provider="openai",
        model_id="gpt-5-preview",
        base_liability=final_liability_after_credits,
        noise_pct=0.02,
        credits_applied=credits_result["credits_applied"],
        effective_rate=calc_result["effective_rate_pct"],
    )

    # ── Step 4: Run scoring engine ────────────────────────────────────
    dual_result = scoring_engine.compare(
        claude=claude_result,
        openai=openai_result,
        session_id=session_id,
    )

    # ── Step 5: Write mock audit events → JSONL ──────────────────────
    jsonl_path = _write_mock_audit_events(
        audit_dir=tmp_audit_dir,
        session_id=session_id,
        profile=profile,
        calc_result=calc_result,
        dual_result=dual_result,
    )

    # ── Step 6: Build TaxSummaryReport → render text + PDF ───────────
    bracket_lines = [
        BracketLine(
            rate=b["rate"],
            bracket_min=b["bracket_min"],
            bracket_max=b["bracket_max"],
            taxable_amount=b["taxable_amount"],
            tax=b["tax"],
        )
        for b in calc_result["bracket_breakdown"]
    ]

    credit_lines = [
        CreditLine(name=c["name"], amount=c["amount"], credit_type=c["type"])
        for c in credits_result["credits_applied"]
    ]

    tax_after_credits = credits_result["final_liability"]
    total_liability = tax_after_credits + fica_result["total_fica"]

    report = TaxSummaryReport(
        taxpayer_name=profile.name,
        filing_status=profile.filing_status,
        tax_year=2025,
        profile_id=profile.profile_id,
        # Income
        wages=profile.wages,
        other_income=profile.other_income,
        total_income=total_income,
        # Adjustments (simplified)
        agi=total_income,
        # Deductions
        standard_deduction=standard_ded,
        itemized_deductions=profile.itemized_deductions,
        applied_deduction=calc_result["applied_deduction"],
        deduction_method=deduction_cmp["recommended"],
        taxable_income=calc_result["taxable_income"],
        # Tax computation
        bracket_breakdown=bracket_lines,
        federal_tax=calc_result["federal_tax"],
        effective_rate_pct=calc_result["effective_rate_pct"],
        ss_tax=fica_result["ss_tax"],
        medicare_tax=fica_result["medicare_tax"],
        additional_medicare_tax=fica_result["additional_medicare_tax"],
        total_fica=fica_result["total_fica"],
        total_tax=calc_result["federal_tax"] + fica_result["total_fica"],
        # Credits
        credits_applied=credit_lines,
        total_nonrefundable_credits=credits_result["nonrefundable_credits_applied"],
        total_refundable_credits=credits_result["refundable_credits_applied"],
        total_credits=credits_result["nonrefundable_credits_applied"] + credits_result["refundable_credits_applied"],
        # Final
        tax_after_credits=tax_after_credits,
        total_liability=total_liability,
        total_payments=0.0,
        refund_or_owed=total_liability,
        # Dual-LLM
        claude_estimate=claude_result.estimated_liability,
        openai_estimate=openai_result.estimated_liability,
        consensus_liability=dual_result.consensus_liability,
        liability_delta_pct=dual_result.liability_delta,
        flag_status=dual_result.flag_status.value,
        scoring_rationale=dual_result.scoring_rationale,
    )

    # Print text form to stdout for visibility
    text_output = report.render_text()
    print(f"\n{text_output}")

    # Render PDF
    pdf_path = tmp_audit_dir / f"tax_summary_{profile.profile_id}.pdf"
    report.render_pdf(pdf_path)

    # ── Step 7: Assertions ────────────────────────────────────────────

    # 7a. Calculator output within 5% of ground truth
    #     (ground_truth_liability is federal tax before credits for simple cases)
    computed_federal_tax = calc_result["federal_tax"]
    if profile.ground_truth_liability > 0:
        pct_diff = abs(computed_federal_tax - profile.ground_truth_liability) / profile.ground_truth_liability
        assert pct_diff <= 0.05, (
            f"[{profile.profile_id}] Federal tax ${computed_federal_tax:,.2f} differs from "
            f"ground truth ${profile.ground_truth_liability:,.2f} by {pct_diff:.1%} (>5%)"
        )

    # 7b. Dual-LLM flag status is GREEN (mocked LLMs agree within thresholds)
    assert dual_result.flag_status == FlagStatus.GREEN, (
        f"[{profile.profile_id}] Expected GREEN flag, got {dual_result.flag_status.value}. "
        f"Rationale: {dual_result.scoring_rationale}"
    )

    # 7c. Audit JSONL exists and has events
    assert jsonl_path.exists(), f"Audit JSONL not found at {jsonl_path}"
    event_count = sum(1 for line in jsonl_path.read_text().strip().split("\n") if line.strip())
    assert event_count >= 5, f"Expected ≥5 audit events, got {event_count}"

    # 7d. Tax summary PDF exists and is non-trivial
    assert pdf_path.exists(), f"Tax summary PDF not found at {pdf_path}"
    assert pdf_path.stat().st_size > 1024, (
        f"Tax summary PDF too small ({pdf_path.stat().st_size} bytes)"
    )

    # 7e. Text output contains key 1040 sections
    assert "INCOME" in text_output
    assert "DEDUCTIONS" in text_output
    assert "TAX COMPUTATION" in text_output
    assert "FICA" in text_output
    assert "CREDITS" in text_output
    assert "FINAL TAX SUMMARY" in text_output
    assert "DUAL-LLM SCORING" in text_output
    assert profile.name in text_output

    # 7f. Consensus liability is close to the calculator result
    if dual_result.consensus_liability is not None and final_liability_after_credits > 0:
        consensus_diff = abs(dual_result.consensus_liability - final_liability_after_credits) / final_liability_after_credits
        assert consensus_diff <= 0.05, (
            f"[{profile.profile_id}] Consensus ${dual_result.consensus_liability:,.2f} differs from "
            f"calculator ${final_liability_after_credits:,.2f} by {consensus_diff:.1%}"
        )

    print(f"  ✅ {profile.profile_id} ({profile.name}) — ALL ASSERTIONS PASSED")
    print(f"     Federal tax: ${computed_federal_tax:,.2f} | Ground truth: ${profile.ground_truth_liability:,.2f}")
    print(f"     Flag: {dual_result.flag_status.value} | Delta: {dual_result.liability_delta:.1f}%")
    print(f"     PDF: {pdf_path}")
