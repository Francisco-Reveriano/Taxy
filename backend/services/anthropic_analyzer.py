"""Claude-based tax analysis service."""
import asyncio
import json
import logging
import time
from typing import Optional

import anthropic

from backend.config import get_settings
from backend.models.analysis_result import LLMAnalysisResult, ConfidenceLevel
from backend.telemetry.tracer import get_tracer

logger = logging.getLogger(__name__)

ANALYSIS_PROMPT_TEMPLATE = """You are an expert tax analyst. Analyze the following taxpayer data and provide:

1. Estimated federal tax liability (dollar amount)
2. Effective tax rate
3. Applicable deductions with amounts
4. Applicable tax credits with amounts
5. Advisory notes and planning opportunities
6. Confidence level (High/Medium/Low) with rationale

Taxpayer data:
{tax_data}

Respond in valid JSON with these exact keys:
{{
  "estimated_liability": <number>,
  "effective_tax_rate": <number 0-100>,
  "applicable_deductions": [
    {{"name": "<string>", "amount": <number>, "description": "<string>"}}
  ],
  "applicable_credits": [
    {{"name": "<string>", "amount": <number>, "refundable": <bool>}}
  ],
  "advisory_notes": ["<string>", ...],
  "confidence_level": "High|Medium|Low",
  "confidence_rationale": "<string>"
}}
"""

CONFIDENCE_SCORE_MAP = {
    "High": 92.0,
    "Medium": 78.0,
    "Low": 62.0,
}


class AnthropicAnalyzer:
    def __init__(self):
        self._settings = get_settings()
        self._client = anthropic.Anthropic(api_key=self._settings.anthropic_api_key)
        self._tracer = get_tracer()

    async def analyze(
        self,
        tax_data: dict,
        session_id: str = "",
    ) -> LLMAnalysisResult:
        """Analyze tax data using Claude."""
        start = time.time()
        model_id = self._settings.anthropic_advance_llm_model

        with self._tracer.start_model_invoke_span("anthropic", model_id):
            try:
                tax_data_str = json.dumps(tax_data, indent=2)
                prompt = ANALYSIS_PROMPT_TEMPLATE.format(tax_data=tax_data_str)

                response = await asyncio.to_thread(
                    self._client.messages.create,
                    model=model_id,
                    max_tokens=4096,
                    messages=[{"role": "user", "content": prompt}],
                )

                latency = (time.time() - start) * 1000
                raw = response.content[0].text

                # Parse JSON response
                result_dict = json.loads(raw)

                confidence_str = result_dict.get("confidence_level", "Medium")
                confidence_score = CONFIDENCE_SCORE_MAP.get(confidence_str, 78.0)
                confidence_level = ConfidenceLevel(confidence_str) if confidence_str in ConfidenceLevel._value2member_map_ else ConfidenceLevel.MEDIUM

                return LLMAnalysisResult(
                    provider="anthropic",
                    model_id=model_id,
                    estimated_liability=float(result_dict.get("estimated_liability", 0.0)),
                    effective_tax_rate=float(result_dict.get("effective_tax_rate", 0.0)),
                    applicable_deductions=result_dict.get("applicable_deductions", []),
                    applicable_credits=result_dict.get("applicable_credits", []),
                    advisory_notes=result_dict.get("advisory_notes", []),
                    confidence_score=confidence_score,
                    confidence_level=confidence_level,
                    raw_response=raw,
                    latency_ms=latency,
                )

            except Exception as e:
                logger.error(f"AnthropicAnalyzer error: {e}")
                return LLMAnalysisResult(
                    provider="anthropic",
                    model_id=model_id,
                    error=str(e),
                    confidence_score=0.0,
                    latency_ms=(time.time() - start) * 1000,
                )
