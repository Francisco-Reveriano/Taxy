"""Claude-based tax analysis service."""
import asyncio
import json
import logging
import re
import time
from typing import Optional

import anthropic

from backend.config import get_settings
from backend.models.analysis_result import LLMAnalysisResult, ConfidenceLevel
from backend.telemetry.tracer import get_tracer

logger = logging.getLogger(__name__)

MAX_RETRIES = 2
RETRY_DELAY_BASE = 1.0

_RETRIABLE_ERRORS = (
    anthropic.RateLimitError,
    anthropic.InternalServerError,
    anthropic.APIConnectionError,
    TimeoutError,
    asyncio.TimeoutError,
)

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


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences wrapping a JSON payload."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[1] if "\n" in stripped else stripped[3:]
        stripped = stripped.rsplit("```", 1)[0]
    return stripped.strip()


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
        """Analyze tax data using Claude with retry for transient errors."""
        start = time.time()
        model_id = self._settings.anthropic_advance_llm_model
        last_error: Optional[Exception] = None

        with self._tracer.start_model_invoke_span("anthropic", model_id):
            for attempt in range(1 + MAX_RETRIES):
                try:
                    result = await self._call_claude(model_id, tax_data, start)
                    return result
                except _RETRIABLE_ERRORS as e:
                    last_error = e
                    if attempt < MAX_RETRIES:
                        delay = RETRY_DELAY_BASE * (2 ** attempt)
                        logger.warning(
                            "AnthropicAnalyzer transient error (attempt %d/%d), retrying in %.1fs: %s",
                            attempt + 1, 1 + MAX_RETRIES, delay, e,
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error("AnthropicAnalyzer failed after %d attempts: %s", 1 + MAX_RETRIES, e)
                except Exception as e:
                    last_error = e
                    logger.error("AnthropicAnalyzer non-retriable error: %s", e)
                    break

            return LLMAnalysisResult(
                provider="anthropic",
                model_id=model_id,
                error=str(last_error),
                confidence_score=0.0,
                latency_ms=(time.time() - start) * 1000,
            )

    async def _call_claude(
        self,
        model_id: str,
        tax_data: dict,
        start: float,
    ) -> LLMAnalysisResult:
        """Single Claude API call with robust response parsing."""
        tax_data_str = json.dumps(tax_data, indent=2)
        prompt = ANALYSIS_PROMPT_TEMPLATE.format(tax_data=tax_data_str)

        response = await asyncio.to_thread(
            self._client.messages.create,
            model=model_id,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )

        latency = (time.time() - start) * 1000

        if not response.content:
            raise ValueError("Claude returned an empty response (no content blocks)")

        raw = response.content[0].text
        if not raw or not raw.strip():
            raise ValueError("Claude returned an empty text block")

        json_text = _strip_code_fences(raw)
        result_dict = json.loads(json_text)

        confidence_str = result_dict.get("confidence_level", "Medium")
        confidence_score = CONFIDENCE_SCORE_MAP.get(confidence_str, 78.0)
        confidence_level = (
            ConfidenceLevel(confidence_str)
            if confidence_str in ConfidenceLevel._value2member_map_
            else ConfidenceLevel.MEDIUM
        )

        def _safe_num(val, default=0.0):
            try:
                return float(val)
            except (TypeError, ValueError):
                return default

        return LLMAnalysisResult(
            provider="anthropic",
            model_id=model_id,
            estimated_liability=_safe_num(result_dict.get("estimated_liability")),
            effective_tax_rate=_safe_num(result_dict.get("effective_tax_rate")),
            applicable_deductions=result_dict.get("applicable_deductions", []),
            applicable_credits=result_dict.get("applicable_credits", []),
            advisory_notes=result_dict.get("advisory_notes", []),
            confidence_score=confidence_score,
            confidence_level=confidence_level,
            raw_response=raw,
            latency_ms=latency,
        )
