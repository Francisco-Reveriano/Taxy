"""Deterministic tax calculator — no LLM, pure math."""
from typing import Dict, Any, List
from dataclasses import dataclass

# 2025 Federal Tax Brackets
BRACKETS_2025 = {
    "Single": [
        (11925, 0.10),
        (48475, 0.12),
        (103350, 0.22),
        (197300, 0.24),
        (250525, 0.32),
        (626350, 0.35),
        (float("inf"), 0.37),
    ],
    "Married Filing Jointly": [
        (23850, 0.10),
        (96950, 0.12),
        (206700, 0.22),
        (394600, 0.24),
        (501050, 0.32),
        (751600, 0.35),
        (float("inf"), 0.37),
    ],
    "Married Filing Separately": [
        (11925, 0.10),
        (48475, 0.12),
        (103350, 0.22),
        (197300, 0.24),
        (250525, 0.32),
        (375800, 0.35),
        (float("inf"), 0.37),
    ],
    "Head of Household": [
        (17000, 0.10),
        (64850, 0.12),
        (103350, 0.22),
        (197300, 0.24),
        (250500, 0.32),
        (626350, 0.35),
        (float("inf"), 0.37),
    ],
    "Qualifying Surviving Spouse": [
        (23850, 0.10),
        (96950, 0.12),
        (206700, 0.22),
        (394600, 0.24),
        (501050, 0.32),
        (751600, 0.35),
        (float("inf"), 0.37),
    ],
}

STANDARD_DEDUCTIONS_2025 = {
    "Single": 15750,
    "Married Filing Jointly": 31500,
    "Married Filing Separately": 15750,
    "Head of Household": 23625,
    "Qualifying Surviving Spouse": 31500,
}

FICA_SS_RATE = 0.062
FICA_SS_WAGE_BASE = 168600
FICA_MEDICARE_RATE = 0.0145
FICA_MEDICARE_ADDITIONAL_RATE = 0.009
FICA_MEDICARE_ADDITIONAL_THRESHOLD = 200000  # Single


@dataclass
class TaxCalculationStep:
    description: str
    amount: float


class TaxCalculator:
    def compute_federal_tax(
        self,
        income: float,
        filing_status: str,
        year: int = 2025,
        deductions: float = 0.0,
        use_standard_deduction: bool = True,
    ) -> Dict[str, Any]:
        """Compute federal income tax with step-by-step breakdown."""
        steps: List[TaxCalculationStep] = []

        standard_ded = STANDARD_DEDUCTIONS_2025.get(filing_status, 15750)
        applied_deduction = standard_ded if use_standard_deduction else max(deductions, standard_ded)

        steps.append(TaxCalculationStep("Gross Income", income))
        steps.append(TaxCalculationStep("Deduction Applied", -applied_deduction))

        taxable_income = max(0.0, income - applied_deduction)
        steps.append(TaxCalculationStep("Taxable Income", taxable_income))

        brackets = BRACKETS_2025.get(filing_status, BRACKETS_2025["Single"])
        tax = 0.0
        prev_limit = 0.0
        bracket_breakdown = []

        for limit, rate in brackets:
            if taxable_income <= prev_limit:
                break
            taxable_in_bracket = min(taxable_income, limit) - prev_limit
            tax_in_bracket = taxable_in_bracket * rate
            if taxable_in_bracket > 0:
                bracket_breakdown.append({
                    "rate": f"{rate:.0%}",
                    "bracket_min": prev_limit,
                    "bracket_max": limit if limit != float("inf") else None,
                    "taxable_amount": round(taxable_in_bracket, 2),
                    "tax": round(tax_in_bracket, 2),
                })
            tax += tax_in_bracket
            prev_limit = limit

        steps.append(TaxCalculationStep("Federal Income Tax", tax))

        effective_rate = (tax / income * 100) if income > 0 else 0.0

        return {
            "gross_income": round(income, 2),
            "filing_status": filing_status,
            "year": year,
            "standard_deduction": standard_ded,
            "applied_deduction": round(applied_deduction, 2),
            "taxable_income": round(taxable_income, 2),
            "federal_tax": round(tax, 2),
            "effective_rate_pct": round(effective_rate, 2),
            "bracket_breakdown": bracket_breakdown,
            "steps": [{"description": s.description, "amount": round(s.amount, 2)} for s in steps],
        }

    def compute_fica(self, wages: float) -> Dict[str, Any]:
        """Compute Social Security and Medicare taxes."""
        ss_wages = min(wages, FICA_SS_WAGE_BASE)
        ss_tax = ss_wages * FICA_SS_RATE

        medicare_tax = wages * FICA_MEDICARE_RATE
        additional_medicare = max(0.0, wages - FICA_MEDICARE_ADDITIONAL_THRESHOLD) * FICA_MEDICARE_ADDITIONAL_RATE

        total_fica = ss_tax + medicare_tax + additional_medicare

        return {
            "wages": round(wages, 2),
            "ss_wages": round(ss_wages, 2),
            "ss_tax": round(ss_tax, 2),
            "medicare_tax": round(medicare_tax, 2),
            "additional_medicare_tax": round(additional_medicare, 2),
            "total_fica": round(total_fica, 2),
        }

    def compare_deductions(self, standard: float, itemized_total: float) -> Dict[str, Any]:
        """Compare standard vs itemized deduction."""
        recommended = "itemized" if itemized_total > standard else "standard"
        return {
            "standard_deduction": round(standard, 2),
            "itemized_total": round(itemized_total, 2),
            "difference": round(itemized_total - standard, 2),
            "recommended": recommended,
            "tax_benefit_of_itemizing": round(max(0.0, itemized_total - standard), 2),
        }

    def apply_credits(self, liability: float, credits: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Apply tax credits to reduce liability."""
        nonrefundable_credits = 0.0
        refundable_credits = 0.0
        applied = []

        for credit in credits:
            amount = credit.get("amount", 0.0)
            refundable = credit.get("refundable", False)
            name = credit.get("name", "Unknown Credit")

            if refundable:
                refundable_credits += amount
                applied.append({"name": name, "amount": amount, "type": "refundable"})
            else:
                applicable = min(amount, max(0.0, liability - nonrefundable_credits))
                nonrefundable_credits += applicable
                applied.append({"name": name, "amount": applicable, "type": "nonrefundable"})

        tax_after_nonrefundable = max(0.0, liability - nonrefundable_credits)
        final_liability = max(0.0, tax_after_nonrefundable - refundable_credits)
        refund_from_credits = max(0.0, refundable_credits - tax_after_nonrefundable)

        return {
            "original_liability": round(liability, 2),
            "nonrefundable_credits_applied": round(nonrefundable_credits, 2),
            "refundable_credits_applied": round(refundable_credits, 2),
            "final_liability": round(final_liability, 2),
            "refund_from_credits": round(refund_from_credits, 2),
            "credits_applied": applied,
        }
