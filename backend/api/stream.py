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
from backend.models.sse_events import SSEEventType

logger = logging.getLogger(__name__)
router = APIRouter()

# Active loops per session
_active_loops: dict[str, N0AgentLoop] = {}
_active_streams: dict[str, StreamGen] = {}
_completed_sessions: set[str] = set()


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

    # Run loop in background with error safety net
    async def _run_loop():
        try:
            await loop.run(body.message, session_id)
        except Exception as exc:
            logger.error(
                "Unhandled exception in n0 loop for session %s: %s",
                session_id, exc, exc_info=True,
            )
            try:
                await streamgen.emit(
                    SSEEventType.ERROR,
                    {"code": "LOOP_CRASHED", "message": str(exc)},
                )
                await streamgen.close()
            except Exception:
                pass  # stream may already be closed

    asyncio.create_task(_run_loop())

    return {"session_id": session_id, "status": "started"}


@router.get("/stream")
async def stream_events(session_id: str, request: Request):
    """SSE stream endpoint for a session. Lazily creates a StreamGen so the
    frontend can connect before POST /stream/chat is called."""
    if session_id not in _active_streams:
        _active_streams[session_id] = StreamGen()

    # If an active loop exists but its StreamGen doesn't match (reconnection
    # after a brief disconnect), re-attach the new stream to the loop.
    loop = _active_loops.get(session_id)
    if loop and loop._streamgen is not _active_streams[session_id]:
        loop.set_streamgen(_active_streams[session_id])

    streamgen = _active_streams[session_id]

    # If the loop already finished, return done immediately so the frontend
    # doesn't hang on an empty queue forever after a post-completion reconnect.
    loop = _active_loops.get(session_id)
    if session_id in _completed_sessions or (loop is not None and loop.is_done):
        async def finished_generator():
            yield "event: done\ndata: {}\n\n"
        return StreamingResponse(
            finished_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

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

            # Only clean up if the agent loop has finished.
            # If the loop is still running (e.g., awaiting a user answer),
            # keep it alive so /stream/respond can reach it.
            loop = _active_loops.get(session_id)
            loop_done = loop is None or loop.is_done

            if loop_done:
                _completed_sessions.add(session_id)
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
            else:
                # Loop still running — only remove the stream reference so a
                # reconnecting client gets a fresh StreamGen.  The loop itself
                # stays in _active_loops.
                _active_streams.pop(session_id, None)
                logger.info(
                    "SSE disconnected for session %s but loop still active — keeping session alive",
                    session_id,
                )

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
        logger.warning(
            "404 on /stream/respond: session_id=%s not in _active_loops (active: %s)",
            session_id,
            list(_active_loops.keys()),
        )
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
