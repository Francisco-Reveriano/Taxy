"""
TaxpayerFactory — creates synthetic taxpayer profiles with ground-truth tax liability.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class TaxpayerProfile:
    profile_id: str
    name: str
    filing_status: str
    tax_year: int
    wages: float
    other_income: float
    itemized_deductions: float
    credits: List[Dict]
    ground_truth_liability: float
    description: str
    metadata: Dict = field(default_factory=dict)


# Ground truth computed using 2025 IRS brackets
PROFILE_LIBRARY = {
    "TS-01-single-simple": TaxpayerProfile(
        profile_id="TS-01",
        name="Alice Simple",
        filing_status="Single",
        tax_year=2025,
        wages=55000.0,
        other_income=0.0,
        itemized_deductions=0.0,
        credits=[],
        ground_truth_liability=4471.5,  # Standard deduction $15,750; taxable $39,250; 10%+12%
        description="Single filer, W-2 wages only, standard deduction",
    ),
    "TS-02-mfj-complex": TaxpayerProfile(
        profile_id="TS-02",
        name="Bob & Carol Complex",
        filing_status="Married Filing Jointly",
        tax_year=2025,
        wages=120000.0,
        other_income=15000.0,
        itemized_deductions=35000.0,
        credits=[{"name": "Child Tax Credit", "amount": 2000, "refundable": False}],
        ground_truth_liability=11828.0,  # Itemized $35k; taxable $100k; 10%+12%+22%
        description="MFJ, W-2 + 1099, itemized deductions, CTC",
    ),
    "TS-03-self-employed": TaxpayerProfile(
        profile_id="TS-03",
        name="Dana Freelance",
        filing_status="Single",
        tax_year=2025,
        wages=0.0,
        other_income=80000.0,
        itemized_deductions=12000.0,
        credits=[{"name": "Earned Income Credit", "amount": 500, "refundable": True}],
        ground_truth_liability=9049.0,  # Standard deduction $15,750; taxable $64,250; 10%+12%+22%
        description="Self-employed, Schedule C, SE tax, QBI deduction",
    ),
    "TS-04-high-income": TaxpayerProfile(
        profile_id="TS-04",
        name="Eve Executive",
        filing_status="Single",
        tax_year=2025,
        wages=450000.0,
        other_income=50000.0,
        itemized_deductions=80000.0,
        credits=[],
        ground_truth_liability=116547.25,  # Itemized $80k; taxable $420k; through 35% bracket
        description="High income, 37% bracket, SALT cap applies",
    ),
    "TS-05-retiree": TaxpayerProfile(
        profile_id="TS-05",
        name="Frank Retire",
        filing_status="Married Filing Jointly",
        tax_year=2025,
        wages=0.0,
        other_income=65000.0,  # Social Security + pension
        itemized_deductions=0.0,
        credits=[],
        ground_truth_liability=3543.0,  # MFJ standard $31,500; taxable $33,500; 10%+12%
        description="Retiree, Social Security + pension, standard deduction",
    ),
}


class TaxpayerFactory:
    @staticmethod
    def create(profile_id: str) -> TaxpayerProfile:
        """Return a synthetic taxpayer profile with ground truth liability."""
        for key, profile in PROFILE_LIBRARY.items():
            if profile.profile_id == profile_id or key == profile_id:
                return profile
        raise ValueError(f"Profile '{profile_id}' not found. Available: {list(PROFILE_LIBRARY.keys())}")

    @staticmethod
    def all_profiles() -> List[TaxpayerProfile]:
        return list(PROFILE_LIBRARY.values())

    @staticmethod
    def to_tax_data(profile: TaxpayerProfile) -> dict:
        """Convert profile to the tax_data dict format expected by the API."""
        total_income = profile.wages + profile.other_income
        return {
            "filing_status": profile.filing_status,
            "tax_year": profile.tax_year,
            "wages": profile.wages,
            "other_income": profile.other_income,
            "total_income": total_income,
            "itemized_deductions": profile.itemized_deductions,
            "credits": profile.credits,
            "ground_truth_liability": profile.ground_truth_liability,
        }
