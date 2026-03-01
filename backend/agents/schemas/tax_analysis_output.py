from pydantic import BaseModel, Field
from typing import Optional, List


class TAX_ANALYSIS_AGENT_OUTPUT(BaseModel):
    Regulation: str = Field(description="Exact IRS Publication or IRC section cited (e.g., 'IRC § 63 — Standard Deduction')")
    Business_Requirement: str = Field(description="MUST statements — filing obligations, required forms, deadlines")
    Business_Permission: str = Field(description="MAY statements — optional elections, deductions taxpayer may claim")
    Business_Prohibition: str = Field(description="MUST NOT statements — disallowed deductions, penalties for non-compliance")
    Business_Intepretation: str = Field(description="Plain-English explanation of how tax rules apply to this situation")
    Estimated_Tax_Liability: Optional[float] = Field(
        default=None,
        description="Estimated federal tax liability in USD based on retrieved IRS guidance"
    )
    Applicable_Deductions: Optional[List[str]] = Field(
        default=None,
        description="List of applicable deductions with amounts where retrievable"
    )
    Applicable_Credits: Optional[List[str]] = Field(
        default=None,
        description="List of applicable tax credits with amounts where retrievable"
    )
    Advisory_Notes: Optional[List[str]] = Field(
        default=None,
        description="Additional advisory notes, warnings, or planning opportunities"
    )
    Source_Evidence: Optional[str] = Field(
        default=None,
        description="Key supporting excerpts with document identifiers and short quotes from IRS publications"
    )
    Confidence: Optional[str] = Field(
        default=None,
        description="High/Medium/Low based on completeness of retrieved IRS sources"
    )
