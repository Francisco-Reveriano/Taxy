"""File upload endpoint."""
import hashlib
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from backend.config import get_settings
from backend.models.tax_document import TaxDocument, TaxDocumentType
from backend.audit.audit_logger import AuditEvent, AuditEventType, get_audit_logger
from backend.telemetry.file_exporter import reset_traces_for_session

logger = logging.getLogger(__name__)
router = APIRouter()

UPLOAD_DIR = Path("backend/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MIME_TO_DOC_TYPE = {
    "application/pdf": None,  # detect from content
    "image/jpeg": None,
    "image/png": None,
}

FILENAME_HINTS = {
    "w-2": TaxDocumentType.W2,
    "w2": TaxDocumentType.W2,
    "1099": TaxDocumentType.FORM_1099_NEC,
    "1099-nec": TaxDocumentType.FORM_1099_NEC,
    "1099-misc": TaxDocumentType.FORM_1099_MISC,
    "1099-int": TaxDocumentType.FORM_1099_INT,
    "1099-div": TaxDocumentType.FORM_1099_DIV,
    "1040": TaxDocumentType.FORM_1040,
    "schedule-a": TaxDocumentType.SCHEDULE_A,
    "schedule-c": TaxDocumentType.SCHEDULE_C,
    "1098": TaxDocumentType.FORM_1098,
}


def detect_document_type(filename: str) -> TaxDocumentType:
    lower = filename.lower()
    for hint, doc_type in FILENAME_HINTS.items():
        if hint in lower:
            return doc_type
    return TaxDocumentType.UNKNOWN


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    session_id: str = Form(default=""),
):
    """Upload a tax document. Returns TaxDocument with file_id."""
    if not session_id:
        session_id = str(uuid.uuid4())

    # Traces must reflect only the current active user session.
    reset_traces_for_session(session_id)

    content = await file.read()

    # Enforce upload size limit
    settings = get_settings()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {settings.max_upload_size_mb}MB upload limit",
        )

    # Compute SHA-256
    sha256 = hashlib.sha256(content).hexdigest()
    file_id = str(uuid.uuid4())

    # Save to disk
    ext = Path(file.filename or "document").suffix or ".pdf"
    save_path = UPLOAD_DIR / f"{file_id}{ext}"
    save_path.write_bytes(content)

    doc_type = detect_document_type(file.filename or "")

    doc = TaxDocument(
        file_id=file_id,
        original_filename=file.filename or "unknown",
        document_type=doc_type,
        sha256_hash=sha256,
        file_path=str(save_path),
        upload_timestamp=datetime.now(timezone.utc).isoformat(),
        session_id=session_id,
    )

    # Audit
    audit = get_audit_logger()
    await audit.log(AuditEvent(
        session_id=session_id,
        event_type=AuditEventType.DOCUMENT_UPLOADED,
        agent_name="upload_api",
        input_summary=f"file={file.filename}, size={len(content)}, type={doc_type}",
        output_summary=f"file_id={file_id}, sha256={sha256[:8]}...",
        metadata={"sha256": sha256, "doc_type": doc_type.value},
    ))

    return doc


@router.delete("/upload/{file_id}")
async def remove_document(file_id: str, session_id: str = ""):
    """Remove an uploaded document."""
    matches = list(UPLOAD_DIR.glob(f"{file_id}*"))
    if not matches:
        raise HTTPException(status_code=404, detail=f"File {file_id} not found")

    for match in matches:
        match.unlink(missing_ok=True)

    audit = get_audit_logger()
    await audit.log(AuditEvent(
        session_id=session_id,
        event_type=AuditEventType.DOCUMENT_REMOVED,
        agent_name="upload_api",
        input_summary=f"file_id={file_id}",
        output_summary="document removed",
    ))

    return {"file_id": file_id, "status": "removed"}
