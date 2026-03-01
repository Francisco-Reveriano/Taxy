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
from backend.audit.audit_logger import AuditEvent, AuditEventType, get_audit_logger

logger = logging.getLogger(__name__)
router = APIRouter()

# Results cache
_analysis_cache: dict[str, DualAnalysisResult] = {}

_anthropic_analyzer = AnthropicAnalyzer()
_openai_assistant = OpenAIAssistant()
_scoring_engine = ScoringEngine()


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
        # Run both analyses concurrently
        claude_result, openai_result = await asyncio.gather(
            _anthropic_analyzer.analyze(tax_data, session_id),
            _openai_assistant.analyze(tax_data, session_id),
            return_exceptions=True,
        )

        # Handle exceptions from gather
        if isinstance(claude_result, Exception):
            logger.error(f"Claude analysis failed: {claude_result}")
            claude_result = None
        if isinstance(openai_result, Exception):
            logger.error(f"OpenAI analysis failed: {openai_result}")
            openai_result = None

        dual_result = _scoring_engine.compare(
            claude_result, openai_result, session_id,
            audit_logger=audit,
        )
        _analysis_cache[session_id] = dual_result

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

        return dual_result

    except Exception as e:
        logger.error(f"Analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analyze/{session_id}/results")
async def get_analysis_results(session_id: str):
    """Get cached analysis results for a session."""
    if session_id not in _analysis_cache:
        raise HTTPException(status_code=404, detail=f"No analysis results for session {session_id}")
    return _analysis_cache[session_id]
