import asyncio
import json
import re
import time
import uuid
from enum import Enum
from pathlib import Path
from typing import Optional, Any, Dict
from pydantic import BaseModel, Field


class AuditEventType(str, Enum):
    SESSION_STARTED = "session.started"
    SESSION_ENDED = "session.ended"
    DOCUMENT_UPLOADED = "document.uploaded"
    DOCUMENT_REMOVED = "document.removed"
    OCR_STARTED = "ocr.started"
    OCR_COMPLETED = "ocr.completed"
    OCR_FIELD_CORRECTED = "ocr.field_corrected"
    OCR_LLM_EXTRACTION = "ocr.llm_extraction"
    ANALYSIS_STARTED = "analysis.started"
    ANALYSIS_COMPLETED = "analysis.completed"
    SCORING_COMPARISON = "scoring.comparison"
    SCORING_FLAG_ASSIGNED = "scoring.flag_assigned"
    TOOL_INVOKED = "tool.invoked"
    TOOL_COMPLETED = "tool.completed"
    TOOL_FAILED = "tool.failed"
    AGENT_CYCLE_STARTED = "agent.cycle_started"
    AGENT_CYCLE_COMPLETED = "agent.cycle_completed"
    COMPRESSION_TRIGGERED = "compression.triggered"
    COMPRESSION_COMPLETED = "compression.completed"
    H2A_MESSAGE_RECEIVED = "h2a.message_received"
    H2A_CHECKPOINT_MERGED = "h2a.checkpoint_merged"
    TODO_CREATED = "todo.created"
    TODO_UPDATED = "todo.updated"
    ASK_USER_PROMPTED = "ask_user.prompted"
    ASK_USER_RESPONDED = "ask_user.responded"


class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    event_type: str
    timestamp: float = Field(default_factory=time.time)
    agent_name: Optional[str] = None
    tool_name: Optional[str] = None
    model_id: Optional[str] = None
    input_summary: Optional[str] = None
    output_summary: Optional[str] = None
    confidence_score: Optional[float] = None
    flag_status: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    pii_masked: bool = False
    metadata: Dict[str, Any] = {}
    parent_event_id: Optional[str] = None


from backend.utils.pii import mask_pii_with_flag


class AuditLogger:
    def __init__(self, audit_dir: str = "backend/audit"):
        self._audit_dir = Path(audit_dir)
        self._audit_dir.mkdir(parents=True, exist_ok=True)
        self._queue: asyncio.Queue = asyncio.Queue()
        self._task: Optional[asyncio.Task] = None

    def start(self):
        """Start the background writer task."""
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._writer())

    async def stop(self):
        """Gracefully stop the background writer."""
        if self._task and not self._task.done():
            await self._queue.join()
            self._task.cancel()

    async def log(self, event: AuditEvent):
        """Enqueue an audit event (non-blocking)."""
        # Mask PII in string fields
        masked = False
        for field in ["input_summary", "output_summary", "error_message"]:
            val = getattr(event, field)
            if val and isinstance(val, str):
                masked_val, was = mask_pii_with_flag(val)
                setattr(event, field, masked_val)
                if was:
                    masked = True
        event.pii_masked = masked
        await self._queue.put(event)

    async def _writer(self):
        """Background JSONL writer using asyncio.to_thread."""
        while True:
            event = await self._queue.get()
            try:
                log_file = self._audit_dir / f"session_{event.session_id}.jsonl"
                line = event.model_dump_json() + "\n"
                await asyncio.to_thread(self._append_line, log_file, line)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Audit write error: {e}")
            finally:
                self._queue.task_done()

    @staticmethod
    def _append_line(path: Path, line: str):
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)

    def get_session_path(self, session_id: str) -> Path:
        return self._audit_dir / f"session_{session_id}.jsonl"

    async def read_session_events(self, session_id: str) -> list[AuditEvent]:
        path = self.get_session_path(session_id)
        if not path.exists():
            return []
        lines = await asyncio.to_thread(path.read_text, encoding="utf-8")
        events = []
        for line in lines.strip().split("\n"):
            if line.strip():
                try:
                    events.append(AuditEvent.model_validate_json(line))
                except Exception:
                    pass
        return events


# Singleton
_audit_logger: AuditLogger | None = None


def get_audit_logger() -> AuditLogger:
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
