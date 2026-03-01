import asyncio
import logging
import time
from typing import Optional

from agents import Runner
from backend.agents.tax_analysis_agent import get_tax_analysis_agent
from backend.models.analysis_result import LLMAnalysisResult, ConfidenceLevel
from backend.config import get_settings
from backend.telemetry.tracer import get_tracer
from backend.utils.pii import mask_pii

logger = logging.getLogger(__name__)

CONFIDENCE_MAP = {
    "High": 95.0,
    "Medium": 80.0,
    "Low": 65.0,
}

MAX_RETRIES = 3


class LegalRAGTool:
    def __init__(self):
        self._settings = get_settings()

    async def analyze(self, tax_prompt: str, session_id: str = "") -> LLMAnalysisResult:
        """
        Run the Tax_Analysis_Agent with RAG against the IRS knowledge base.
        Returns LLMAnalysisResult with mapped confidence score.
        3 retries with exponential backoff.
        """
        # Mask PII before sending to OpenAI
        masked_prompt = mask_pii(tax_prompt)

        for attempt in range(MAX_RETRIES):
            try:
                start = time.time()
                tracer = get_tracer()
                with tracer.start_sub_tool_span("legal_rag", "openai_runner"):
                    result = await self._run_agent(masked_prompt)
                latency = (time.time() - start) * 1000

                confidence_str = result.Confidence or "Medium"
                confidence_score = CONFIDENCE_MAP.get(confidence_str, 80.0)
                confidence_level = ConfidenceLevel(confidence_str) if confidence_str in ConfidenceLevel._value2member_map_ else ConfidenceLevel.MEDIUM

                deductions = []
                if result.Applicable_Deductions:
                    for d in result.Applicable_Deductions:
                        deductions.append({"description": d, "amount": None})

                credits = []
                if result.Applicable_Credits:
                    for c in result.Applicable_Credits:
                        credits.append({"description": c, "amount": None})

                return LLMAnalysisResult(
                    provider="openai",
                    model_id=self._settings.openai_advance_llm_model,
                    estimated_liability=result.Estimated_Tax_Liability or 0.0,
                    applicable_deductions=deductions,
                    applicable_credits=credits,
                    advisory_notes=result.Advisory_Notes or [],
                    source_evidence=result.Source_Evidence,
                    confidence_score=confidence_score,
                    confidence_level=confidence_level,
                    raw_response=result.Business_Intepretation,
                    latency_ms=latency,
                )

            except Exception as e:
                logger.warning(f"RAG attempt {attempt + 1}/{MAX_RETRIES} failed: {e}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(1.0 * (2 ** attempt))
                else:
                    return LLMAnalysisResult(
                        provider="openai",
                        model_id=self._settings.openai_advance_llm_model,
                        error=str(e),
                        confidence_score=0.0,
                    )

    async def _run_agent(self, prompt: str):
        agent = get_tax_analysis_agent()
        result = await Runner.run(agent, input=prompt)
        return result.final_output
