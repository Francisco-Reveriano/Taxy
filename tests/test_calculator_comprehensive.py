"""
Comprehensive unit tests for TaxCalculator.
Covers all filing statuses, FICA, deduction comparison, credits, and edge cases.
"""
import pytest

from backend.tools.calculator_tool import (
    BRACKETS_2025,
    FICA_MEDICARE_ADDITIONAL_THRESHOLD,
    FICA_SS_WAGE_BASE,
    STANDARD_DEDUCTIONS_2025,
    TaxCalculator,
)
from tests.digital_twin.factories.taxpayer_factory import TaxpayerFactory


@pytest.fixture
def calc():
    return TaxCalculator()


# ── compute_federal_tax: ground-truth per profile ─────────────────────────────

@pytest.mark.unit
class TestFederalTaxByProfile:
    """Verify the calculator matches the ground-truth liability for each profile."""

    @pytest.mark.parametrize(
        "profile_id",
        ["TS-01", "TS-02", "TS-03", "TS-04", "TS-05"],
        ids=["TS-01-single", "TS-02-mfj", "TS-03-self-emp", "TS-04-high", "TS-05-retiree"],
    )
    def test_profile_liability(self, calc, profile_id):
        profile = TaxpayerFactory.create(profile_id)
        total_income = profile.wages + profile.other_income
        standard_ded = STANDARD_DEDUCTIONS_2025.get(profile.filing_status, 15750)
        use_standard = profile.itemized_deductions <= standard_ded

        result = calc.compute_federal_tax(
            income=total_income,
            filing_status=profile.filing_status,
            year=2025,
            deductions=profile.itemized_deductions,
            use_standard_deduction=use_standard,
        )

        assert result["federal_tax"] == pytest.approx(
            profile.ground_truth_liability, rel=0.05
        ), (
            f"[{profile_id}] Expected ~${profile.ground_truth_liability:,.2f}, "
            f"got ${result['federal_tax']:,.2f}"
        )


# ── compute_federal_tax: all filing statuses ──────────────────────────────────

@pytest.mark.unit
class TestFederalTaxFilingStatuses:
    """Test that all 5 filing statuses produce distinct, correct results."""

    STATUSES = list(STANDARD_DEDUCTIONS_2025.keys())

    @pytest.mark.parametrize("status", STATUSES)
    def test_standard_deduction_applied(self, calc, status):
        result = calc.compute_federal_tax(
            income=75000.0, filing_status=status, use_standard_deduction=True
        )
        assert result["applied_deduction"] == STANDARD_DEDUCTIONS_2025[status]
        assert result["taxable_income"] == max(0.0, 75000.0 - STANDARD_DEDUCTIONS_2025[status])
        assert result["federal_tax"] > 0

    def test_mfj_lower_tax_than_single(self, calc):
        single = calc.compute_federal_tax(100000.0, "Single")
        mfj = calc.compute_federal_tax(100000.0, "Married Filing Jointly")
        assert mfj["federal_tax"] < single["federal_tax"]

    def test_hoh_lower_tax_than_single(self, calc):
        single = calc.compute_federal_tax(80000.0, "Single")
        hoh = calc.compute_federal_tax(80000.0, "Head of Household")
        assert hoh["federal_tax"] < single["federal_tax"]


# ── compute_federal_tax: edge cases ──────────────────────────────────────────

@pytest.mark.unit
class TestFederalTaxEdgeCases:

    def test_zero_income(self, calc):
        result = calc.compute_federal_tax(0.0, "Single")
        assert result["taxable_income"] == 0.0
        assert result["federal_tax"] == 0.0

    def test_income_below_standard_deduction(self, calc):
        result = calc.compute_federal_tax(10000.0, "Single")
        assert result["taxable_income"] == 0.0
        assert result["federal_tax"] == 0.0

    def test_income_exactly_at_standard_deduction(self, calc):
        std = STANDARD_DEDUCTIONS_2025["Single"]
        result = calc.compute_federal_tax(std, "Single")
        assert result["taxable_income"] == 0.0
        assert result["federal_tax"] == 0.0

    def test_income_one_dollar_above_standard_deduction(self, calc):
        std = STANDARD_DEDUCTIONS_2025["Single"]
        result = calc.compute_federal_tax(std + 1.0, "Single")
        assert result["taxable_income"] == 1.0
        assert result["federal_tax"] == pytest.approx(0.10, abs=0.01)

    def test_very_high_income_hits_37pct_bracket(self, calc):
        result = calc.compute_federal_tax(1_000_000.0, "Single")
        assert result["federal_tax"] > 0
        brackets = result["bracket_breakdown"]
        top_rate = brackets[-1]["rate"]
        assert top_rate == "37%"

    def test_bracket_breakdown_sums_to_total(self, calc):
        result = calc.compute_federal_tax(150000.0, "Single")
        bracket_sum = sum(b["tax"] for b in result["bracket_breakdown"])
        assert bracket_sum == pytest.approx(result["federal_tax"], abs=0.02)

    def test_effective_rate_between_0_and_37(self, calc):
        result = calc.compute_federal_tax(200000.0, "Single")
        assert 0 < result["effective_rate_pct"] < 37

    def test_itemized_deduction_used_when_larger(self, calc):
        result = calc.compute_federal_tax(
            income=100000.0,
            filing_status="Single",
            deductions=25000.0,
            use_standard_deduction=False,
        )
        assert result["applied_deduction"] == 25000.0

    def test_steps_list_populated(self, calc):
        result = calc.compute_federal_tax(50000.0, "Single")
        assert len(result["steps"]) >= 3
        assert result["steps"][0]["description"] == "Gross Income"


# ── compute_fica ──────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestFICA:

    def test_basic_fica(self, calc):
        result = calc.compute_fica(55000.0)
        assert result["ss_tax"] == pytest.approx(55000.0 * 0.062, abs=1.0)
        assert result["medicare_tax"] == pytest.approx(55000.0 * 0.0145, abs=1.0)
        assert result["additional_medicare_tax"] == 0.0
        assert result["total_fica"] == pytest.approx(
            result["ss_tax"] + result["medicare_tax"], abs=0.01
        )

    def test_ss_wage_base_cap(self, calc):
        wages_above_cap = FICA_SS_WAGE_BASE + 50000
        result = calc.compute_fica(wages_above_cap)
        assert result["ss_wages"] == FICA_SS_WAGE_BASE
        assert result["ss_tax"] == pytest.approx(FICA_SS_WAGE_BASE * 0.062, abs=1.0)

    def test_additional_medicare_above_threshold(self, calc):
        wages = FICA_MEDICARE_ADDITIONAL_THRESHOLD + 100000
        result = calc.compute_fica(wages)
        assert result["additional_medicare_tax"] == pytest.approx(
            100000 * 0.009, abs=1.0
        )

    def test_additional_medicare_below_threshold(self, calc):
        result = calc.compute_fica(150000.0)
        assert result["additional_medicare_tax"] == 0.0

    def test_zero_wages(self, calc):
        result = calc.compute_fica(0.0)
        assert result["total_fica"] == 0.0


# ── compare_deductions ────────────────────────────────────────────────────────

@pytest.mark.unit
class TestCompareDeductions:

    def test_standard_recommended_when_higher(self, calc):
        result = calc.compare_deductions(15750.0, 10000.0)
        assert result["recommended"] == "standard"
        assert result["tax_benefit_of_itemizing"] == 0.0

    def test_itemized_recommended_when_higher(self, calc):
        result = calc.compare_deductions(15750.0, 25000.0)
        assert result["recommended"] == "itemized"
        assert result["tax_benefit_of_itemizing"] == pytest.approx(9250.0)
        assert result["difference"] == pytest.approx(9250.0)

    def test_equal_deductions_prefers_standard(self, calc):
        result = calc.compare_deductions(15750.0, 15750.0)
        assert result["recommended"] == "standard"

    def test_zero_itemized(self, calc):
        result = calc.compare_deductions(15750.0, 0.0)
        assert result["recommended"] == "standard"


# ── apply_credits ─────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestApplyCredits:

    def test_nonrefundable_credit_reduces_liability(self, calc):
        result = calc.apply_credits(
            10000.0,
            [{"name": "CTC", "amount": 2000, "refundable": False}],
        )
        assert result["final_liability"] == pytest.approx(8000.0)
        assert result["nonrefundable_credits_applied"] == pytest.approx(2000.0)

    def test_nonrefundable_cannot_exceed_liability(self, calc):
        result = calc.apply_credits(
            500.0,
            [{"name": "CTC", "amount": 2000, "refundable": False}],
        )
        assert result["final_liability"] == 0.0
        assert result["nonrefundable_credits_applied"] == pytest.approx(500.0)

    def test_refundable_credit(self, calc):
        result = calc.apply_credits(
            3000.0,
            [{"name": "EIC", "amount": 5000, "refundable": True}],
        )
        assert result["final_liability"] == 0.0
        assert result["refund_from_credits"] == pytest.approx(2000.0)

    def test_mixed_credits(self, calc):
        result = calc.apply_credits(
            10000.0,
            [
                {"name": "CTC", "amount": 2000, "refundable": False},
                {"name": "EIC", "amount": 500, "refundable": True},
            ],
        )
        assert result["nonrefundable_credits_applied"] == pytest.approx(2000.0)
        assert result["refundable_credits_applied"] == pytest.approx(500.0)
        assert result["final_liability"] == pytest.approx(7500.0)

    def test_no_credits(self, calc):
        result = calc.apply_credits(5000.0, [])
        assert result["final_liability"] == pytest.approx(5000.0)
        assert result["credits_applied"] == []

    def test_zero_liability(self, calc):
        result = calc.apply_credits(
            0.0,
            [{"name": "CTC", "amount": 2000, "refundable": False}],
        )
        assert result["final_liability"] == 0.0
        assert result["nonrefundable_credits_applied"] == 0.0
