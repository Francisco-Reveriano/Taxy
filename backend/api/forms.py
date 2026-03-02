"""Form output endpoints."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.tools.form1040_tool import Form1040Tool, get_form1040_status, FORM_OUTPUT_DIR

router = APIRouter()
form1040_tool = Form1040Tool()


@router.get("/forms/1040/template-fields")
async def get_form_1040_template_fields():
    """
    Introspect configured Form 1040 template fields and mapping readiness.
    """
    try:
        return form1040_tool.introspect_template_fields()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/forms/1040/{session_id}")
async def download_form_1040(session_id: str):
    """
    Download generated filled Form 1040 for a session.
    Returns 404 if no successful form output exists.
    """
    status = get_form1040_status(session_id)
    if not status:
        # Disk fallback: serve the PDF if it exists on disk (e.g., after server restart)
        candidate = FORM_OUTPUT_DIR / f"form1040_{session_id}.pdf"
        if candidate.exists():
            return FileResponse(
                path=str(candidate),
                media_type="application/pdf",
                content_disposition_type="inline",
            )
        raise HTTPException(status_code=404, detail="No Form 1040 generation record for this session")
    if not status.get("success"):
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Form 1040 generation not successful",
                "missing_required_fields": status.get("missing_required_fields", []),
                "error": status.get("error", ""),
            },
        )

    output_path = status.get("output_path")
    if not output_path:
        raise HTTPException(status_code=404, detail="Form 1040 output path not found")

    return FileResponse(
        path=output_path,
        media_type="application/pdf",
        content_disposition_type="inline",
    )


@router.get("/forms/1040/{session_id}/status")
async def get_form_1040_status(session_id: str):
    """Return structured status for Form 1040 generation."""
    status = get_form1040_status(session_id)
    if not status:
        return {
            "success": False,
            "session_id": session_id,
            "message": "No Form 1040 generation record for this session",
            "missing_required_fields": [],
        }
    return status
