from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import uuid


class WizardStep(int, Enum):
    FILING_STATUS = 1
    UPLOAD = 2
    OCR_REVIEW = 3
    INCOME = 4
    DEDUCTIONS = 5
    ANALYSIS = 6
    RESULTS = 7


class FilingStatus(str, Enum):
    SINGLE = "Single"
    MARRIED_FILING_JOINTLY = "Married Filing Jointly"
    MARRIED_FILING_SEPARATELY = "Married Filing Separately"
    HEAD_OF_HOUSEHOLD = "Head of Household"
    QUALIFYING_SURVIVING_SPOUSE = "Qualifying Surviving Spouse"


class WizardState(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    current_step: WizardStep = WizardStep.FILING_STATUS
    filing_status: Optional[FilingStatus] = None
    tax_year: int = 2025
    document_ids: List[str] = []
    income_summary: Dict[str, float] = {}
    deduction_choice: Optional[str] = None  # "standard" or "itemized"
    itemized_total: float = 0.0
    credits: List[str] = []
    analysis_triggered: bool = False
    analysis_complete: bool = False
    form_1040_ready: bool = False
    form_1040_path: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
    metadata: Dict[str, Any] = {}
