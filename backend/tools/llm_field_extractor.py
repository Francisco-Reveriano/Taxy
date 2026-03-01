"""LLM-powered structured field extraction from OCR markdown."""
import asyncio
import json
import logging
from typing import Dict, List

import anthropic

from backend.config import get_settings
from backend.models.tax_document import OCRField

logger = logging.getLogger(__name__)

W2_EXTRACTION_PROMPT = """You are a tax document data extraction specialist. Given the raw OCR markdown output from a W-2 form, extract all standard W-2 box values into structured JSON.

Return ONLY valid JSON with this exact structure (use null for values not found):
{
  "box_1": <number or null>,
  "box_2": <number or null>,
  "box_3": <number or null>,
  "box_4": <number or null>,
  "box_5": <number or null>,
  "box_6": <number or null>,
  "box_7": <number or null>,
  "box_8": <number or null>,
  "box_10": <number or null>,
  "box_11": <number or null>,
  "box_12a": <string or null>,
  "box_12b": <string or null>,
  "box_12c": <string or null>,
  "box_12d": <string or null>,
  "box_13": <string or null>,
  "box_14": <string or null>,
  "box_15": <string or null>,
  "box_16": <number or null>,
  "box_17": <number or null>,
  "box_18": <number or null>,
  "box_19": <number or null>,
  "box_20": <string or null>,
  "employer_name": <string or null>,
  "employer_ein": <string or null>,
  "employee_name": <string or null>,
  "employee_ssn_last4": <string or null>
}

Be precise with dollar amounts. Convert text like "$55,000.00" to 55000.00.
If the OCR contains obvious errors (e.g., "O" for "0"), correct them.
If a value is illegible or missing, use null.

OCR Markdown:
"""


class LLMFieldExtractor:
    """Extract structured tax form fields from raw OCR markdown using Claude."""

    def __init__(self):
        self._settings = get_settings()
        self._client = anthropic.Anthropic(api_key=self._settings.anthropic_api_key)

    async def extract_w2_fields(
        self, raw_markdown: str, page_number: int = 1
    ) -> List[OCRField]:
        """Send aggregated OCR markdown to Claude Sonnet for structured extraction."""
        model_id = self._settings.anthropic_medium_llm_model
        prompt = W2_EXTRACTION_PROMPT + raw_markdown

        try:
            response = await asyncio.to_thread(
                self._client.messages.create,
                model=model_id,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_text = response.content[0].text

            # Parse JSON (handle markdown code blocks)
            json_text = raw_text.strip()
            if json_text.startswith("```"):
                json_text = json_text.split("\n", 1)[1]
                json_text = json_text.rsplit("```", 1)[0]

            result = json.loads(json_text)
            return self._json_to_ocr_fields(result, page_number)

        except Exception as e:
            logger.error("LLM field extraction failed: %s", e)
            return []

    def _json_to_ocr_fields(self, data: Dict, page_number: int) -> List[OCRField]:
        """Convert the LLM's JSON response to a list of OCRField objects."""
        fields = []
        for key, value in data.items():
            if value is None:
                continue
            if isinstance(value, (int, float)):
                field_value = f"{value:.2f}" if isinstance(value, float) else str(value)
            else:
                field_value = str(value)

            fields.append(OCRField(
                field_name=key,
                field_value=field_value,
                confidence=0.95,
                page_number=page_number,
            ))
        return fields
