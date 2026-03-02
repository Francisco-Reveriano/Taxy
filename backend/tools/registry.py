import asyncio
import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from backend.tools.calculator_tool import TaxCalculator
from backend.tools.mistral_ocr_tool import MistralOCRTool
from backend.tools.legal_rag_tool import LegalRAGTool
from backend.tools.ask_user_tool import AskUserTool
from backend.tools.form1040_tool import Form1040Tool

if TYPE_CHECKING:
    from backend.agent.streamgen import StreamGen

logger = logging.getLogger(__name__)

TOOL_DEFINITIONS = [
    {
        "name": "calculator_tool",
        "description": (
            "Deterministic federal tax calculator. Computes tax liability, FICA, "
            "deduction comparisons, and credit applications using 2025 IRS brackets. "
            "Use when you need precise numeric calculations."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["compute_federal_tax", "compute_fica", "compare_deductions", "apply_credits"],
                },
                "income": {"type": "number", "description": "Gross income in USD"},
                "filing_status": {
                    "type": "string",
                    "enum": [
                        "Single", "Married Filing Jointly", "Married Filing Separately",
                        "Head of Household", "Qualifying Surviving Spouse"
                    ],
                },
                "year": {"type": "integer", "default": 2025},
                "deductions": {"type": "number", "description": "Total itemized deductions"},
                "use_standard_deduction": {"type": "boolean", "default": True},
                "wages": {"type": "number", "description": "Wages for FICA calculation"},
                "standard": {"type": "number", "description": "Standard deduction amount for comparison"},
                "itemized_total": {"type": "number", "description": "Total itemized deductions for comparison"},
                "liability": {"type": "number", "description": "Tax liability before credits"},
                "credits": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "amount": {"type": "number"},
                            "refundable": {"type": "boolean"},
                        },
                    },
                },
            },
            "required": ["operation"],
        },
    },
    {
        "name": "mistral_ocr_tool",
        "description": (
            "Extracts structured fields from tax documents (W-2, 1099, 1040) using Mistral OCR. "
            "Use when a document has been uploaded and needs to be processed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Absolute path to the uploaded document"},
                "file_id": {"type": "string", "description": "Unique document identifier"},
            },
            "required": ["file_path", "file_id"],
        },
    },
    {
        "name": "legal_rag_agent_tool",
        "description": (
            "IRS publications RAG tool. Retrieves and analyzes relevant IRS guidance for the taxpayer's situation. "
            "Use for tax law questions, deduction eligibility, and regulatory compliance checks."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tax_prompt": {
                    "type": "string",
                    "description": "Detailed description of the tax situation to analyze",
                },
                "session_id": {"type": "string", "description": "Session identifier"},
            },
            "required": ["tax_prompt"],
        },
    },
    {
        "name": "form1040_tool",
        "description": (
            "Generates and validates a filled IRS Form 1040 PDF. "
            "Returns success only when required fields are present and written."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Active user session identifier"},
                "tax_data": {
                    "type": "object",
                    "description": "Normalized taxpayer and tax computation fields for 1040 generation",
                },
                "template_path": {
                    "type": "string",
                    "description": "Optional absolute path override for the 1040 PDF template",
                },
            },
            "required": ["session_id", "tax_data"],
        },
    },
    {
        "name": "ask_user_tool",
        "description": (
            "Ask the user a clarifying question. Use when critical information is missing or ambiguous "
            "and you cannot proceed without user input. Non-blocking — emits SSE event and awaits response."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "The question to ask the user"},
                "session_id": {"type": "string"},
                "options": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of choices for a multiple-choice question. When provided, the user sees radio buttons.",
                },
            },
            "required": ["question"],
        },
    },
]


class ToolRegistry:
    def __init__(self):
        self._calculator = TaxCalculator()
        self._ocr = MistralOCRTool()
        self._rag = LegalRAGTool()
        self._ask_user = AskUserTool()
        self._form1040 = Form1040Tool()

    def set_streamgen(self, streamgen: "StreamGen"):
        self._ask_user.set_streamgen(streamgen)

    async def dispatch(
        self,
        tool_name: str,
        inputs: Dict[str, Any],
        session_id: str = "",
    ) -> Dict[str, Any]:
        """Route a tool call to the appropriate implementation."""
        try:
            if tool_name == "calculator_tool":
                return self._dispatch_calculator(inputs)
            elif tool_name == "mistral_ocr_tool":
                fields = await self._ocr.process_document(
                    inputs["file_path"], inputs["file_id"]
                )
                return {"fields": [f.model_dump() for f in fields]}
            elif tool_name == "legal_rag_agent_tool":
                result = await self._rag.analyze(
                    inputs["tax_prompt"], inputs.get("session_id", session_id)
                )
                return result.model_dump()
            elif tool_name == "ask_user_tool":
                answer = await self._ask_user.ask(
                    inputs["question"],
                    inputs.get("session_id", session_id),
                    options=inputs.get("options"),
                )
                return {"answer": answer}
            elif tool_name == "form1040_tool":
                return await asyncio.to_thread(
                    self._form1040.generate_form,
                    session_id,
                    inputs.get("tax_data", {}),
                    inputs.get("template_path"),
                )
            else:
                raise ValueError(f"Unknown tool: {tool_name}")
        except Exception as e:
            logger.error(f"Tool {tool_name} error: {e}")
            raise

    def _dispatch_calculator(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        op = inputs["operation"]
        if op == "compute_federal_tax":
            return self._calculator.compute_federal_tax(
                income=inputs["income"],
                filing_status=inputs.get("filing_status", "Single"),
                year=inputs.get("year", 2025),
                deductions=inputs.get("deductions", 0.0),
                use_standard_deduction=inputs.get("use_standard_deduction", True),
            )
        elif op == "compute_fica":
            return self._calculator.compute_fica(wages=inputs["wages"])
        elif op == "compare_deductions":
            return self._calculator.compare_deductions(
                standard=inputs["standard"],
                itemized_total=inputs["itemized_total"],
            )
        elif op == "apply_credits":
            return self._calculator.apply_credits(
                liability=inputs["liability"],
                credits=inputs.get("credits", []),
            )
        else:
            raise ValueError(f"Unknown calculator operation: {op}")

    async def dispatch_parallel(
        self,
        calls: List[Dict[str, Any]],
        session_id: str = "",
    ) -> List[Dict[str, Any]]:
        """Execute multiple tool calls concurrently."""
        tasks = [
            self.dispatch(call["name"], call.get("inputs", {}), session_id)
            for call in calls
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        output = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                output.append({"error": str(result), "tool_name": calls[i]["name"]})
            else:
                output.append(result)
        return output

    def resolve_user_answer(self, question_id: str, answer: str):
        self._ask_user.resolve(question_id, answer)
