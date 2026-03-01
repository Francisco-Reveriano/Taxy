"""Dual-LLM analysis endpoints."""
import asyncio
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any

from backend.services.anthropic_analyzer import AnthropicAnalyzer
from backend.services.openai_assistant import OpenAIAssistant
from backend.services.scoring_engine import ScoringEngine
from backend.models.analysis_result import DualAnalysisResult
from backend.models.sse_events import SSEEventType
from backend.tools.form1040_tool import Form1040Tool
from backend.tools.calculator_tool import TaxCalculator
from backend.audit.audit_logger import AuditEvent, AuditEventType, get_audit_logger

logger = logging.getLogger(__name__)
router = APIRouter()


async def _emit_progress(session_id: str, step: str, status: str, detail: str = ""):
    """Push a progress event to the session's SSE stream if connected."""
    try:
        from backend.api.stream import _active_streams
        streamgen = _active_streams.get(session_id)
        if streamgen:
            await streamgen.emit(SSEEventType.ANALYSIS_PROGRESS, {
                "step": step,
                "status": status,
                "detail": detail,
            })
    except Exception:
        pass  # SSE not connected — that's fine


async def _emit_activity(session_id: str, event_type: SSEEventType, payload: Dict[str, Any]):
    """Push a granular activity event (tool_call, tool_result, thought, error) to the SSE stream."""
    try:
        from backend.api.stream import _active_streams
        streamgen = _active_streams.get(session_id)
        if streamgen:
            await streamgen.emit(event_type, payload)
    except Exception:
        pass

# Results cache
_analysis_cache: dict[str, DualAnalysisResult] = {}

_anthropic_analyzer = AnthropicAnalyzer()
_openai_assistant = OpenAIAssistant()
_scoring_engine = ScoringEngine()
_form1040_tool = Form1040Tool()
_tax_calculator = TaxCalculator()


def _is_valid_numeric(value: Any) -> bool:
    """Return True if value is a usable number (including 0.0)."""
    if value is None:
        return False
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Convert value to float, stripping commas and currency symbols.
    Returns *default* when conversion is impossible."""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    try:
        cleaned = str(value).replace(",", "").replace("$", "").strip()
        return float(cleaned) if cleaned else default
    except (TypeError, ValueError):
        return default


def _set_if_missing(target: Dict[str, Any], key: str, value: Any) -> None:
    """Set key only when the current value is absent or not a valid number."""
    if not _is_valid_numeric(target.get(key)):
        target[key] = value


def _merge_rag_results(tax_data: Dict[str, Any], dual_result: DualAnalysisResult) -> Dict[str, Any]:
    """
    Merge RAG-computed tax amounts from the dual-LLM analysis back into
    the user's tax_data. This closes the loop: RAG retrieves IRS guidance,
    computes liability, and the results flow into the Form 1040.
    """
    merged = dict(tax_data)

    # Use consensus liability as total_tax if available (>= 0 is valid)
    if dual_result.consensus_liability is not None and dual_result.consensus_liability >= 0:
        _set_if_missing(merged, "total_tax", dual_result.consensus_liability)
        _set_if_missing(merged, "estimated_tax_liability", dual_result.consensus_liability)

    # Pull specific fields from the OpenAI RAG result (it has IRS-grounded numbers)
    openai_result = dual_result.openai_result
    if openai_result and not openai_result.error:
        if _is_valid_numeric(openai_result.estimated_liability) and openai_result.estimated_liability >= 0:
            _set_if_missing(merged, "total_tax", openai_result.estimated_liability)

    # Pull from Claude result as fallback
    claude_result = dual_result.claude_result
    if claude_result and not claude_result.error:
        if _is_valid_numeric(claude_result.estimated_liability) and claude_result.estimated_liability >= 0:
            _set_if_missing(merged, "total_tax", claude_result.estimated_liability)

    # Compute taxable_income from total_income if not already present
    total_income = merged.get("total_income") or merged.get("wages", 0)
    _set_if_missing(merged, "taxable_income", total_income)
    _set_if_missing(merged, "adjusted_gross_income", total_income)

    # Ensure federal_tax_withheld has a default so form generation doesn't fail
    _set_if_missing(merged, "federal_tax_withheld", merged.get("federal_tax_withheld", 0.0))

    # Deterministic fallback: if total_tax is still missing after LLM merge,
    # compute it from the bracket calculator so form generation can proceed.
    if not _is_valid_numeric(merged.get("total_tax")):
        income = _safe_float(merged.get("total_income") or merged.get("wages"))
        filing = str(merged.get("filing_status", "Single"))
        deduction_type = merged.get("deduction_type", "standard")
        itemized = _safe_float(merged.get("itemized_deductions"))
        use_standard = deduction_type != "itemized"

        if income > 0:
            calc = _tax_calculator.compute_federal_tax(
                income=income,
                filing_status=filing,
                deductions=itemized,
                use_standard_deduction=use_standard,
            )
            merged["total_tax"] = calc["federal_tax"]
            _set_if_missing(merged, "taxable_income", calc["taxable_income"])
            _set_if_missing(merged, "estimated_tax_liability", calc["federal_tax"])
            logger.info(
                "Used deterministic calculator fallback: total_tax=%.2f for income=%.2f, filing=%s",
                calc["federal_tax"], income, filing,
            )
        else:
            merged["total_tax"] = 0.0

    return merged


class AnalysisRequest(BaseModel):
    session_id: str
    tax_data: Dict[str, Any]


@router.post("/analyze")
async def run_analysis(body: AnalysisRequest):
    """
    Run dual-LLM analysis concurrently (Claude + OpenAI RAG).
    Returns DualAnalysisResult with flag status.
    """
    session_id = body.session_id
    tax_data = body.tax_data

    audit = get_audit_logger()
    await audit.log(AuditEvent(
        session_id=session_id,
        event_type=AuditEventType.ANALYSIS_STARTED,
        agent_name="analyze_api",
        input_summary=f"tax_data_keys={list(tax_data.keys())}",
    ))

    try:
        # Phase 1: Dual-LLM analysis
        await _emit_progress(session_id, "dual_llm", "running", "Starting Claude + GPT-5 RAG analysis concurrently...")

        await _emit_activity(session_id, SSEEventType.TOOL_CALL, {
            "phase": "dual_llm",
            "tool": "anthropic_analyzer",
            "provider": "Claude",
            "model": _anthropic_analyzer._settings.anthropic_advance_llm_model,
            "summary": "Invoking Claude for tax liability analysis...",
        })
        await _emit_activity(session_id, SSEEventType.TOOL_CALL, {
            "phase": "dual_llm",
            "tool": "openai_rag_assistant",
            "provider": "GPT-5 RAG",
            "model": _openai_assistant._settings.openai_advance_llm_model,
            "summary": "Invoking OpenAI Assistants with IRS RAG for independent validation...",
        })

        claude_result, openai_result = await asyncio.gather(
            _anthropic_analyzer.analyze(tax_data, session_id),
            _openai_assistant.analyze(tax_data, session_id),
            return_exceptions=True,
        )

        # Handle exceptions from gather
        claude_ok = not isinstance(claude_result, Exception)
        openai_ok = not isinstance(openai_result, Exception)
        if not claude_ok:
            logger.error(f"Claude analysis failed: {claude_result}")
            await _emit_activity(session_id, SSEEventType.TOOL_RESULT, {
                "phase": "dual_llm",
                "tool": "anthropic_analyzer",
                "provider": "Claude",
                "success": False,
                "summary": f"Claude analysis failed: {claude_result}",
            })
            claude_result = None
        else:
            c_err = getattr(claude_result, "error", None)
            await _emit_activity(session_id, SSEEventType.TOOL_RESULT, {
                "phase": "dual_llm",
                "tool": "anthropic_analyzer",
                "provider": "Claude",
                "success": not c_err,
                "estimated_liability": getattr(claude_result, "estimated_liability", None),
                "confidence_score": getattr(claude_result, "confidence_score", None),
                "latency_ms": round(getattr(claude_result, "latency_ms", 0)),
                "summary": f"Claude returned liability ${getattr(claude_result, 'estimated_liability', 0):,.2f} "
                           f"(confidence {getattr(claude_result, 'confidence_score', 0):.0f}%)"
                           if not c_err else f"Claude error: {c_err}",
            })

        if not openai_ok:
            logger.error(f"OpenAI analysis failed: {openai_result}")
            await _emit_activity(session_id, SSEEventType.TOOL_RESULT, {
                "phase": "dual_llm",
                "tool": "openai_rag_assistant",
                "provider": "GPT-5 RAG",
                "success": False,
                "summary": f"OpenAI analysis failed: {openai_result}",
            })
            openai_result = None
        else:
            o_err = getattr(openai_result, "error", None)
            await _emit_activity(session_id, SSEEventType.TOOL_RESULT, {
                "phase": "dual_llm",
                "tool": "openai_rag_assistant",
                "provider": "GPT-5 RAG",
                "success": not o_err,
                "estimated_liability": getattr(openai_result, "estimated_liability", None),
                "confidence_score": getattr(openai_result, "confidence_score", None),
                "latency_ms": round(getattr(openai_result, "latency_ms", 0)),
                "summary": f"GPT-5 RAG returned liability ${getattr(openai_result, 'estimated_liability', 0):,.2f} "
                           f"(confidence {getattr(openai_result, 'confidence_score', 0):.0f}%)"
                           if not o_err else f"OpenAI error: {o_err}",
            })

        await _emit_progress(
            session_id, "dual_llm", "done",
            f"Claude: {'completed' if claude_ok else 'failed'}, GPT-5 RAG: {'completed' if openai_ok else 'failed'}",
        )

        # Phase 2: Scoring comparison
        await _emit_progress(session_id, "scoring", "running", "Comparing results and assigning confidence flag...")

        dual_result = _scoring_engine.compare(
            claude_result, openai_result, session_id,
            audit_logger=audit,
        )
        _analysis_cache[session_id] = dual_result

        await _emit_activity(session_id, SSEEventType.THOUGHT, {
            "phase": "scoring",
            "summary": f"Flag: {dual_result.flag_status.value} | Delta: {dual_result.liability_delta:.1f}% | "
                       f"{dual_result.scoring_rationale}",
        })

        await _emit_progress(
            session_id, "scoring", "done",
            f"Flag: {dual_result.flag_status.value}, Delta: {dual_result.liability_delta:.1f}%",
        )

        await audit.log(AuditEvent(
            session_id=session_id,
            event_type=AuditEventType.SCORING_FLAG_ASSIGNED,
            agent_name="scoring_engine",
            flag_status=dual_result.flag_status.value,
            output_summary=f"flag={dual_result.flag_status}, rationale={dual_result.scoring_rationale[:100]}",
        ))

        await audit.log(AuditEvent(
            session_id=session_id,
            event_type=AuditEventType.ANALYSIS_COMPLETED,
            agent_name="analyze_api",
            flag_status=dual_result.flag_status.value,
            confidence_score=dual_result.claude_result.confidence_score if dual_result.claude_result else None,
            output_summary=f"flag={dual_result.flag_status}, delta={dual_result.liability_delta:.1f}%",
        ))

        # Phase 3: Form 1040 generation
        await _emit_progress(session_id, "form1040", "running", "Merging RAG results and generating Form 1040 PDF...")

        merged_tax_data = _merge_rag_results(tax_data, dual_result)

        used_fallback = not _is_valid_numeric(tax_data.get("total_tax")) and _is_valid_numeric(merged_tax_data.get("total_tax"))
        if used_fallback and not (dual_result.consensus_liability is not None and dual_result.consensus_liability >= 0):
            await _emit_activity(session_id, SSEEventType.THOUGHT, {
                "phase": "form1040",
                "summary": f"LLM liability unavailable — used deterministic tax calculator fallback. "
                           f"Computed total_tax=${merged_tax_data.get('total_tax', 0):,.2f} from "
                           f"income=${_safe_float(merged_tax_data.get('total_income')):,.2f}, "
                           f"filing={merged_tax_data.get('filing_status', 'Single')}.",
            })

        await _emit_activity(session_id, SSEEventType.TOOL_CALL, {
            "phase": "form1040",
            "tool": "form1040_generator",
            "summary": f"Generating Form 1040 PDF with {len(merged_tax_data)} merged fields...",
        })

        form_result = await asyncio.to_thread(
            _form1040_tool.generate_form, session_id, merged_tax_data
        )
        form_ok = form_result.get("success", False)
        logger.info(
            "Form 1040 generation %s for session %s",
            "succeeded" if form_ok else "failed",
            session_id,
        )

        await _emit_activity(session_id, SSEEventType.TOOL_RESULT, {
            "phase": "form1040",
            "tool": "form1040_generator",
            "success": form_ok,
            "fields_written": form_result.get("fields_written_count", 0),
            "missing_fields": form_result.get("missing_required_fields", []),
            "summary": f"Form 1040 {'generated successfully' if form_ok else 'generation failed'} — "
                       f"{form_result.get('fields_written_count', 0)} fields written"
                       + (f", missing: {', '.join(form_result.get('missing_required_fields', []))}"
                          if form_result.get("missing_required_fields") else ""),
        })

        await _emit_progress(
            session_id, "form1040", "done",
            f"{'Generated successfully' if form_ok else 'Generation had issues'} — {form_result.get('fields_written_count', 0)} fields written",
        )

        # Phase 4: Complete
        await _emit_progress(session_id, "complete", "done", "Analysis complete — results ready")

        # Include form status in the response
        response = dual_result.model_dump()
        response["form1040_status"] = {
            "success": form_ok,
            "missing_required_fields": form_result.get("missing_required_fields", []),
            "fields_written_count": form_result.get("fields_written_count", 0),
        }

        return response

    except Exception as e:
        logger.error(f"Analysis error: {e}")
        await _emit_activity(session_id, SSEEventType.ERROR, {
            "phase": "error",
            "summary": str(e),
        })
        await _emit_progress(session_id, "error", "failed", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analyze/{session_id}/results")
async def get_analysis_results(session_id: str):
    """Get cached analysis results for a session."""
    if session_id not in _analysis_cache:
        raise HTTPException(status_code=404, detail=f"No analysis results for session {session_id}")
    return _analysis_cache[session_id]
