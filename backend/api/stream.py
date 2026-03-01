"""SSE streaming endpoint."""
import asyncio
import logging
import uuid
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.agent.n0_loop import N0AgentLoop
from backend.agent.streamgen import StreamGen
from backend.audit.audit_logger import AuditEvent, AuditEventType, get_audit_logger

logger = logging.getLogger(__name__)
router = APIRouter()

# Active loops per session
_active_loops: dict[str, N0AgentLoop] = {}
_active_streams: dict[str, StreamGen] = {}


class ChatRequest(BaseModel):
    session_id: str
    message: str


class UserAnswerRequest(BaseModel):
    session_id: str
    question_id: str
    answer: str


@router.post("/stream/chat")
async def start_chat(body: ChatRequest):
    """Start an n0 agent loop and stream results via SSE."""
    session_id = body.session_id

    # Reuse an existing StreamGen if the SSE endpoint already created one
    streamgen = _active_streams.get(session_id) or StreamGen()
    loop = N0AgentLoop()
    loop.set_streamgen(streamgen)

    _active_loops[session_id] = loop
    _active_streams[session_id] = streamgen

    # Run loop in background
    asyncio.create_task(loop.run(body.message, session_id))

    return {"session_id": session_id, "status": "started"}


@router.get("/stream")
async def stream_events(session_id: str, request: Request):
    """SSE stream endpoint for a session. Lazily creates a StreamGen so the
    frontend can connect before POST /stream/chat is called."""
    if session_id not in _active_streams:
        _active_streams[session_id] = StreamGen()

    streamgen = _active_streams[session_id]

    audit = get_audit_logger()
    await audit.log(AuditEvent(
        session_id=session_id,
        event_type=AuditEventType.SESSION_STARTED,
        agent_name="stream_api",
    ))

    async def event_generator():
        try:
            async for chunk in streamgen.stream():
                yield chunk
        finally:
            await audit.log(AuditEvent(
                session_id=session_id,
                event_type=AuditEventType.SESSION_ENDED,
                agent_name="stream_api",
            ))
            # Auto-generate audit report if analysis completed
            if session_id in _active_loops:
                try:
                    from backend.audit.report_generator import ReportGenerator
                    generator = ReportGenerator()
                    await generator.generate(session_id)
                    logger.info(f"Auto-generated audit report for session {session_id}")
                except Exception as e:
                    logger.warning(f"Auto-report generation failed: {e}")
            _active_loops.pop(session_id, None)
            _active_streams.pop(session_id, None)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.post("/stream/respond")
async def respond_to_question(body: UserAnswerRequest):
    """Inject a user answer to a pending ask_user question."""
    session_id = body.session_id
    if session_id not in _active_loops:
        raise HTTPException(status_code=404, detail="No active agent loop for session")

    loop = _active_loops[session_id]
    loop.resolve_user_answer(body.question_id, body.answer)
    return {"status": "ok"}


@router.post("/stream/message")
async def inject_message(body: ChatRequest):
    """Inject a mid-task user message to the h2A buffer."""
    if body.session_id not in _active_loops:
        raise HTTPException(status_code=404, detail="No active agent loop")

    await _active_loops[body.session_id].enqueue_user_message(body.message, session_id=body.session_id)
    return {"status": "queued"}
