"""OCR processing endpoints."""
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List

from backend.models.tax_document import OCRField
from backend.tools.mistral_ocr_tool import MistralOCRTool, W2_BOX_MAPPING
from backend.audit.audit_logger import AuditEvent, AuditEventType, get_audit_logger

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory store for OCR results (keyed by file_id)
_ocr_results: dict[str, list[OCRField]] = {}
_file_paths: dict[str, str] = {}  # file_id -> file_path

# Human-readable display labels for OCR fields
_DISPLAY_LABELS: Dict[str, str] = {
    "employer_name": "Employer Name",
    "employer_ein": "Employer EIN",
    "employee_name": "Employee Name",
    "employee_ssn_last4": "Employee SSN (last 4)",
}

# Build W-2 display labels from W2_BOX_MAPPING
for box_id, info in W2_BOX_MAPPING.items():
    _DISPLAY_LABELS[f"w2_{box_id}"] = f"{box_id.replace('_', ' ').title()} - {info['label']}"


def _get_display_label(field_name: str) -> str:
    """Map internal field names to human-readable display labels."""
    if field_name in _DISPLAY_LABELS:
        return _DISPLAY_LABELS[field_name]
    # Passthrough fields like line_1_0 get no special label
    return ""


def _fields_with_labels(fields: List[OCRField]) -> List[dict]:
    """Serialize fields with display_label added."""
    result = []
    for f in fields:
        d = f.model_dump()
        d["display_label"] = _get_display_label(f.field_name)
        result.append(d)
    return result


class FieldCorrectionRequest(BaseModel):
    corrections: List[OCRField]
    session_id: str = ""


@router.post("/ocr/{file_id}")
async def run_ocr(file_id: str, session_id: str = ""):
    """Trigger OCR processing for an uploaded document."""
    from backend.api.upload import UPLOAD_DIR
    from pathlib import Path
    import glob

    # Find file by file_id prefix
    matches = list(UPLOAD_DIR.glob(f"{file_id}*"))
    if not matches:
        raise HTTPException(status_code=404, detail=f"File {file_id} not found")

    file_path = str(matches[0])
    ocr_tool = MistralOCRTool()

    audit = get_audit_logger()
    await audit.log(AuditEvent(
        session_id=session_id,
        event_type=AuditEventType.OCR_STARTED,
        agent_name="ocr_api",
        tool_name="mistral_ocr_tool",
        input_summary=f"file_id={file_id}",
    ))

    try:
        fields = await ocr_tool.process_document(file_path, file_id)
        _ocr_results[file_id] = fields
        _file_paths[file_id] = file_path

        await audit.log(AuditEvent(
            session_id=session_id,
            event_type=AuditEventType.OCR_COMPLETED,
            agent_name="ocr_api",
            tool_name="mistral_ocr_tool",
            input_summary=f"file_id={file_id}",
            output_summary=f"fields_extracted={len(fields)}",
            metadata={"field_count": len(fields)},
        ))

        return {"file_id": file_id, "fields": _fields_with_labels(fields)}

    except Exception as e:
        logger.error(f"OCR error for {file_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/ocr/{file_id}/fields")
async def update_ocr_fields(file_id: str, body: FieldCorrectionRequest):
    """Accept user corrections to OCR-extracted fields."""
    if file_id not in _ocr_results:
        raise HTTPException(status_code=404, detail=f"No OCR data for file_id={file_id}")

    current_fields = {f.field_name: f for f in _ocr_results[file_id]}
    audit = get_audit_logger()

    for correction in body.corrections:
        if correction.field_name in current_fields:
            original = current_fields[correction.field_name].field_value
            current_fields[correction.field_name].original_value = original
            current_fields[correction.field_name].field_value = correction.field_value
            current_fields[correction.field_name].is_corrected = True

            await audit.log(AuditEvent(
                session_id=body.session_id,
                event_type=AuditEventType.OCR_FIELD_CORRECTED,
                agent_name="ocr_api",
                input_summary=f"field={correction.field_name}, original={original}",
                output_summary=f"corrected_value={correction.field_value}",
            ))

    _ocr_results[file_id] = list(current_fields.values())
    return {"file_id": file_id, "fields": _fields_with_labels(_ocr_results[file_id])}


@router.get("/ocr/{file_id}")
async def get_ocr_results(file_id: str):
    """Get OCR results for a document."""
    if file_id not in _ocr_results:
        raise HTTPException(status_code=404, detail=f"No OCR data for file_id={file_id}")
    return {"file_id": file_id, "fields": _fields_with_labels(_ocr_results[file_id])}
