"""OpenAI Assistants RAG-based tax analysis service."""
import logging
import time

from backend.config import get_settings
from backend.models.analysis_result import LLMAnalysisResult, ConfidenceLevel
from backend.tools.legal_rag_tool import LegalRAGTool, CONFIDENCE_MAP
from backend.telemetry.tracer import get_tracer

logger = logging.getLogger(__name__)


class OpenAIAssistant:
    def __init__(self):
        self._settings = get_settings()
        self._rag_tool = LegalRAGTool()
        self._tracer = get_tracer()

    async def analyze(
        self,
        tax_data: dict,
        session_id: str = "",
    ) -> LLMAnalysisResult:
        """Analyze tax data using OpenAI RAG agent against IRS publications."""
        import json
        start = time.time()

        # Build a comprehensive tax analysis prompt
        prompt = self._build_prompt(tax_data)

        with self._tracer.start_model_invoke_span("openai", self._settings.openai_advance_llm_model):
            result = await self._rag_tool.analyze(prompt, session_id)
            result.latency_ms = (time.time() - start) * 1000
            return result

    def _build_prompt(self, tax_data: dict) -> str:
        """Build a structured prompt for the tax analysis agent."""
        import json
        return f"""Analyze the following taxpayer's tax situation using retrieved IRS publications:

## Taxpayer Financial Data
{json.dumps(tax_data, indent=2)}

## Required Analysis
1. What is the estimated federal tax liability based on IRS Publication 17 and IRC brackets?
2. What deductions is this taxpayer eligible for (standard vs itemized)?
3. What tax credits may apply?
4. Are there any special circumstances requiring additional forms or schedules?
5. What are the key filing requirements and deadlines?

Retrieve relevant IRS publications and provide a complete analysis."""
