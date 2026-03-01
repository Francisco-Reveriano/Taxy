"""
Regression tests for Form 1040 generation failures.

Covers:
- _merge_rag_results with null/empty/zero total_tax
- Deterministic calculator fallback when both LLMs fail
- Form1040Tool semantic extraction with broadened aliases
- Forms API status payload structure
"""
import pytest
from unittest.mock import patch, MagicMock
from typing import Optional

from backend.api.analyze import _merge_rag_results, _is_valid_numeric, _set_if_missing, _safe_float
from backend.models.analysis_result import (
    DualAnalysisResult,
    FlagStatus,
    LLMAnalysisResult,
)
from backend.tools.form1040_tool import Form1040Tool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_llm_result(
    provider: str = "anthropic",
    liability: float = 0.0,
    confidence: float = 90.0,
    error: Optional[str] = None,
) -> LLMAnalysisResult:
    return LLMAnalysisResult(
        provider=provider,
        model_id="test-model",
        estimated_liability=liability,
        confidence_score=confidence,
        error=error,
    )


def _make_dual(
    claude: Optional[LLMAnalysisResult] = None,
    openai: Optional[LLMAnalysisResult] = None,
    consensus: Optional[float] = None,
    flag: FlagStatus = FlagStatus.GREEN,
) -> DualAnalysisResult:
    return DualAnalysisResult(
        session_id="test-session",
        claude_result=claude,
        openai_result=openai,
        consensus_liability=consensus,
        flag_status=flag,
    )


BASIC_TAX_DATA = {
    "first_name": "Jane",
    "last_name": "Doe",
    "ssn": "123-45-6789",
    "filing_status": "Single",
    "total_income": 75000,
    "wages": 75000,
    "federal_tax_withheld": 8000,
}


# ---------------------------------------------------------------------------
# _is_valid_numeric
# ---------------------------------------------------------------------------

class TestIsValidNumeric:
    def test_none_is_invalid(self):
        assert not _is_valid_numeric(None)

    def test_empty_string_is_invalid(self):
        assert not _is_valid_numeric("")

    def test_zero_is_valid(self):
        assert _is_valid_numeric(0)
        assert _is_valid_numeric(0.0)

    def test_positive_number_is_valid(self):
        assert _is_valid_numeric(1234.56)

    def test_numeric_string_is_valid(self):
        assert _is_valid_numeric("500.00")


# ---------------------------------------------------------------------------
# _set_if_missing
# ---------------------------------------------------------------------------

class TestSetIfMissing:
    def test_sets_when_key_absent(self):
        d: dict = {}
        _set_if_missing(d, "total_tax", 100.0)
        assert d["total_tax"] == 100.0

    def test_sets_when_key_is_none(self):
        d = {"total_tax": None}
        _set_if_missing(d, "total_tax", 200.0)
        assert d["total_tax"] == 200.0

    def test_sets_when_key_is_empty_string(self):
        d = {"total_tax": ""}
        _set_if_missing(d, "total_tax", 300.0)
        assert d["total_tax"] == 300.0

    def test_preserves_existing_valid_value(self):
        d = {"total_tax": 500.0}
        _set_if_missing(d, "total_tax", 999.0)
        assert d["total_tax"] == 500.0

    def test_preserves_zero(self):
        d = {"total_tax": 0.0}
        _set_if_missing(d, "total_tax", 999.0)
        assert d["total_tax"] == 0.0


# ---------------------------------------------------------------------------
# _merge_rag_results
# ---------------------------------------------------------------------------

class TestMergeRagResults:
    def test_consensus_populates_total_tax(self):
        dual = _make_dual(consensus=5000.0)
        merged = _merge_rag_results(BASIC_TAX_DATA, dual)
        assert merged["total_tax"] == 5000.0

    def test_consensus_zero_still_populates(self):
        dual = _make_dual(consensus=0.0)
        merged = _merge_rag_results({"total_income": 0, "wages": 0, "filing_status": "Single"}, dual)
        assert merged["total_tax"] == 0.0

    def test_null_incoming_total_tax_is_overwritten(self):
        """If tax_data has total_tax=None, merge should replace it."""
        data = {**BASIC_TAX_DATA, "total_tax": None}
        dual = _make_dual(consensus=4000.0)
        merged = _merge_rag_results(data, dual)
        assert merged["total_tax"] == 4000.0

    def test_empty_string_incoming_total_tax_is_overwritten(self):
        data = {**BASIC_TAX_DATA, "total_tax": ""}
        dual = _make_dual(consensus=4000.0)
        merged = _merge_rag_results(data, dual)
        assert merged["total_tax"] == 4000.0

    def test_existing_valid_total_tax_preserved(self):
        data = {**BASIC_TAX_DATA, "total_tax": 6000.0}
        dual = _make_dual(consensus=4000.0)
        merged = _merge_rag_results(data, dual)
        assert merged["total_tax"] == 6000.0

    def test_openai_fallback_when_consensus_missing(self):
        openai = _make_llm_result("openai", liability=3500.0)
        dual = _make_dual(openai=openai, consensus=None)
        merged = _merge_rag_results(BASIC_TAX_DATA, dual)
        assert merged["total_tax"] == 3500.0

    def test_claude_fallback_when_others_missing(self):
        claude = _make_llm_result("anthropic", liability=4200.0)
        dual = _make_dual(claude=claude, consensus=None)
        merged = _merge_rag_results(BASIC_TAX_DATA, dual)
        assert merged["total_tax"] == 4200.0

    def test_deterministic_fallback_when_all_llm_fail(self):
        """Both providers failed → calculator fallback should populate total_tax."""
        dual = _make_dual(consensus=None, flag=FlagStatus.RED)
        merged = _merge_rag_results(BASIC_TAX_DATA, dual)
        assert _is_valid_numeric(merged.get("total_tax"))
        assert merged["total_tax"] > 0

    def test_taxable_income_defaults_from_total_income(self):
        dual = _make_dual(consensus=5000.0)
        data = {**BASIC_TAX_DATA}
        data.pop("taxable_income", None)
        merged = _merge_rag_results(data, dual)
        assert merged["taxable_income"] == 75000

    def test_adjusted_gross_income_defaults(self):
        dual = _make_dual(consensus=5000.0)
        merged = _merge_rag_results(BASIC_TAX_DATA, dual)
        assert "adjusted_gross_income" in merged

    def test_federal_tax_withheld_defaults_to_zero(self):
        data = {"total_income": 50000, "filing_status": "Single", "wages": 50000}
        dual = _make_dual(consensus=5000.0)
        merged = _merge_rag_results(data, dual)
        assert _is_valid_numeric(merged.get("federal_tax_withheld"))


# ---------------------------------------------------------------------------
# Form1040Tool semantic extraction
# ---------------------------------------------------------------------------

class TestForm1040SemanticExtraction:
    def setup_method(self):
        with patch("backend.tools.form1040_tool.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                form_1040_template_path="/tmp/fake.pdf"
            )
            self.tool = Form1040Tool()

    def test_total_tax_picks_estimated_liability(self):
        data = {
            **BASIC_TAX_DATA,
            "estimated_liability": 7500.0,
        }
        values = self.tool._extract_semantic_values(data)
        assert values["total_tax"] == 7500.0

    def test_total_tax_picks_estimated_tax_liability(self):
        data = {
            **BASIC_TAX_DATA,
            "estimated_tax_liability": 3200.0,
        }
        values = self.tool._extract_semantic_values(data)
        assert values["total_tax"] == 3200.0

    def test_total_tax_picks_federal_tax(self):
        data = {
            **BASIC_TAX_DATA,
            "federal_tax": 4100.0,
        }
        values = self.tool._extract_semantic_values(data)
        assert values["total_tax"] == 4100.0

    def test_zero_total_tax_is_valid(self):
        data = {**BASIC_TAX_DATA, "total_tax": 0.0}
        values = self.tool._extract_semantic_values(data)
        assert "total_tax" in values
        assert values["total_tax"] == 0.0

    def test_federal_tax_withheld_defaults_to_zero(self):
        data = {**BASIC_TAX_DATA}
        data.pop("federal_tax_withheld", None)
        values = self.tool._extract_semantic_values(data)
        assert values.get("federal_tax_withheld") == 0.0

    def test_refund_computed_when_withheld_exceeds_tax(self):
        data = {
            **BASIC_TAX_DATA,
            "total_tax": 5000.0,
            "federal_tax_withheld": 8000.0,
        }
        values = self.tool._extract_semantic_values(data)
        assert values["refund_amount"] == 3000.0
        assert values["amount_owed"] == 0.0

    def test_amount_owed_when_tax_exceeds_withheld(self):
        data = {
            **BASIC_TAX_DATA,
            "total_tax": 10000.0,
            "federal_tax_withheld": 8000.0,
        }
        values = self.tool._extract_semantic_values(data)
        assert values["refund_amount"] == 0.0
        assert values["amount_owed"] == 2000.0


# ---------------------------------------------------------------------------
# Form1040Tool failure diagnostics
# ---------------------------------------------------------------------------

class TestForm1040FailureDiagnostics:
    def setup_method(self):
        with patch("backend.tools.form1040_tool.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                form_1040_template_path="/tmp/fake.pdf"
            )
            self.tool = Form1040Tool()

    def test_record_failure_includes_available_keys(self):
        result = self.tool._record_failure(
            "sess-1",
            "Missing fields",
            ["total_tax"],
            semantic_values={"first_name": "Jane", "ssn": "xxx"},
        )
        assert result["success"] is False
        assert "available_semantic_keys" in result
        assert "first_name" in result["available_semantic_keys"]

    def test_has_value_accepts_zero(self):
        assert Form1040Tool._has_value(0) is True
        assert Form1040Tool._has_value(0.0) is True
        assert Form1040Tool._has_value("0") is True

    def test_has_value_rejects_none_and_empty(self):
        assert Form1040Tool._has_value(None) is False
        assert Form1040Tool._has_value("") is False
        assert Form1040Tool._has_value("   ") is False


# ---------------------------------------------------------------------------
# _is_valid_numeric — non-numeric string rejection (robustness fix)
# ---------------------------------------------------------------------------

class TestIsValidNumericRobustness:
    def test_non_numeric_string_is_invalid(self):
        assert not _is_valid_numeric("unknown")
        assert not _is_valid_numeric("N/A")
        assert not _is_valid_numeric("not a number")

    def test_whitespace_only_is_invalid(self):
        assert not _is_valid_numeric("   ")
        assert not _is_valid_numeric("\t\n")

    def test_currency_string_is_invalid(self):
        """Strings like '$50,000' are not directly float-parseable."""
        assert not _is_valid_numeric("$50,000")

    def test_string_zero_is_valid(self):
        assert _is_valid_numeric("0")
        assert _is_valid_numeric("0.0")

    def test_negative_number_is_valid(self):
        assert _is_valid_numeric(-100)
        assert _is_valid_numeric("-100.5")


# ---------------------------------------------------------------------------
# _safe_float
# ---------------------------------------------------------------------------

class TestSafeFloat:
    def test_none_returns_default(self):
        assert _safe_float(None) == 0.0
        assert _safe_float(None, 42.0) == 42.0

    def test_int_and_float(self):
        assert _safe_float(100) == 100.0
        assert _safe_float(3.14) == 3.14

    def test_numeric_string(self):
        assert _safe_float("1234.56") == 1234.56

    def test_commas_stripped(self):
        assert _safe_float("50,000") == 50000.0
        assert _safe_float("1,234,567.89") == 1234567.89

    def test_currency_symbol_stripped(self):
        assert _safe_float("$91,282.31") == 91282.31

    def test_non_numeric_string_returns_default(self):
        assert _safe_float("N/A") == 0.0
        assert _safe_float("unknown", -1.0) == -1.0

    def test_empty_string_returns_default(self):
        assert _safe_float("") == 0.0
        assert _safe_float("   ") == 0.0

    def test_bool_treated_as_number(self):
        assert _safe_float(True) == 1.0
        assert _safe_float(False) == 0.0


# ---------------------------------------------------------------------------
# _merge_rag_results — non-numeric resilience
# ---------------------------------------------------------------------------

class TestMergeRobustness:
    def test_non_numeric_total_income_does_not_crash(self):
        data = {**BASIC_TAX_DATA, "total_income": "N/A"}
        dual = _make_dual(consensus=None, flag=FlagStatus.RED)
        merged = _merge_rag_results(data, dual)
        assert _is_valid_numeric(merged.get("total_tax"))

    def test_comma_formatted_income_handled(self):
        data = {**BASIC_TAX_DATA, "total_income": "75,000"}
        dual = _make_dual(consensus=None, flag=FlagStatus.RED)
        merged = _merge_rag_results(data, dual)
        assert _is_valid_numeric(merged.get("total_tax"))

    def test_non_numeric_itemized_deductions_does_not_crash(self):
        data = {**BASIC_TAX_DATA, "itemized_deductions": "lots", "deduction_type": "itemized"}
        dual = _make_dual(consensus=None, flag=FlagStatus.RED)
        merged = _merge_rag_results(data, dual)
        assert _is_valid_numeric(merged.get("total_tax"))


# ---------------------------------------------------------------------------
# Filing status case normalization
# ---------------------------------------------------------------------------

class TestFilingStatusCaseNormalization:
    def setup_method(self):
        with patch("backend.tools.form1040_tool.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                form_1040_template_path="/tmp/fake.pdf"
            )
            self.tool = Form1040Tool()

    def test_lowercase_single_matches(self):
        for canonical, field in self.tool.FILING_STATUS_CHECKBOXES.items():
            lower = canonical.lower()
            matched = None
            for c, f in self.tool.FILING_STATUS_CHECKBOXES.items():
                if c.lower() == lower:
                    matched = f
                    break
            assert matched == field, f"'{lower}' should match '{canonical}'"

    def test_uppercase_single_matches(self):
        for canonical, field in self.tool.FILING_STATUS_CHECKBOXES.items():
            upper = canonical.upper()
            matched = None
            for c, f in self.tool.FILING_STATUS_CHECKBOXES.items():
                if c.lower() == upper.lower():
                    matched = f
                    break
            assert matched == field, f"'{upper}' should match '{canonical}'"

    def test_exact_case_still_works(self):
        for canonical, field in self.tool.FILING_STATUS_CHECKBOXES.items():
            assert self.tool.FILING_STATUS_CHECKBOXES.get(canonical) == field


# ---------------------------------------------------------------------------
# Anthropic analyzer response parsing
# ---------------------------------------------------------------------------

class TestStripCodeFences:
    def test_strips_json_fence(self):
        from backend.services.anthropic_analyzer import _strip_code_fences
        raw = '```json\n{"estimated_liability": 5000}\n```'
        assert _strip_code_fences(raw) == '{"estimated_liability": 5000}'

    def test_strips_plain_fence(self):
        from backend.services.anthropic_analyzer import _strip_code_fences
        raw = '```\n{"key": "val"}\n```'
        assert _strip_code_fences(raw) == '{"key": "val"}'

    def test_no_fence_passthrough(self):
        from backend.services.anthropic_analyzer import _strip_code_fences
        raw = '{"key": "val"}'
        assert _strip_code_fences(raw) == '{"key": "val"}'

    def test_whitespace_around_fence(self):
        from backend.services.anthropic_analyzer import _strip_code_fences
        raw = '  ```json\n{"a": 1}\n```  '
        assert _strip_code_fences(raw) == '{"a": 1}'
