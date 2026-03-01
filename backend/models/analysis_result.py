from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class FlagStatus(str, Enum):
    GREEN = "GREEN"
    AMBER = "AMBER"
    RED = "RED"
    YELLOW = "YELLOW"


class ConfidenceLevel(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class LLMAnalysisResult(BaseModel):
    provider: str  # "anthropic" or "openai"
    model_id: str
    estimated_liability: float = 0.0
    effective_tax_rate: float = 0.0
    applicable_deductions: List[Dict[str, Any]] = []
    applicable_credits: List[Dict[str, Any]] = []
    advisory_notes: List[str] = []
    source_evidence: Optional[str] = None
    confidence_score: float = Field(ge=0.0, le=100.0, default=0.0)
    confidence_level: ConfidenceLevel = ConfidenceLevel.LOW
    raw_response: Optional[str] = None
    error: Optional[str] = None
    latency_ms: float = 0.0


class DualAnalysisResult(BaseModel):
    session_id: str
    claude_result: Optional[LLMAnalysisResult] = None
    openai_result: Optional[LLMAnalysisResult] = None
    flag_status: FlagStatus = FlagStatus.AMBER
    consensus_liability: Optional[float] = None
    liability_delta: float = 0.0
    scoring_rationale: str = ""
    completed_at: str = ""
