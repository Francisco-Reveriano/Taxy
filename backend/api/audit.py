"""Audit trail and report endpoints."""
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel

from backend.audit.audit_logger import AuditEvent, AuditEventType, get_audit_logger

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/audit/trail/{session_id}")
async def get_audit_trail(session_id: str):
    """Stream JSONL audit trail for a session."""
    audit = get_audit_logger()
    path = audit.get_session_path(session_id)

    if not path.exists():
        raise HTTPException(status_code=404, detail=f"No audit trail for session {session_id}")

    def iter_file():
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                yield line

    return StreamingResponse(iter_file(), media_type="application/x-ndjson")


@router.get("/audit/report/{session_id}")
async def get_audit_report_pdf(session_id: str):
    """Generate and return PDF audit report."""
    from backend.audit.report_generator import ReportGenerator
    generator = ReportGenerator()
    pdf_path, json_path = await generator.generate(session_id)

    if not pdf_path.exists():
        raise HTTPException(status_code=500, detail="PDF generation failed")

    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=f"audit_report_{session_id}.pdf",
    )


@router.get("/audit/report/{session_id}/json")
async def get_audit_report_json(session_id: str):
    """Return JSON audit report."""
    from backend.audit.report_generator import ReportGenerator
    generator = ReportGenerator()
    pdf_path, json_path = await generator.generate(session_id)

    if not json_path.exists():
        raise HTTPException(status_code=500, detail="JSON generation failed")

    return FileResponse(
        path=str(json_path),
        media_type="application/json",
        filename=f"audit_report_{session_id}.json",
    )


class AcknowledgeRequest(BaseModel):
    session_id: str


@router.post("/audit/acknowledge")
async def acknowledge_flag(body: AcknowledgeRequest):
    """Record user acknowledgment of a RED flag."""
    audit = get_audit_logger()
    await audit.log(AuditEvent(
        session_id=body.session_id,
        event_type="scoring.flag_acknowledged",
        agent_name="user",
        output_summary="User acknowledged RED flag discrepancy",
    ))
    return {"status": "acknowledged"}
