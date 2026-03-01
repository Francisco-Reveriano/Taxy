"""
AskUserTool — non-blocking user question tool.
Emits an ask_user SSE event and returns immediately.
The answer is injected at the next h2A checkpoint.
"""
import asyncio
import uuid
from typing import Optional, TYPE_CHECKING

from backend.audit.audit_logger import AuditEvent, AuditEventType, get_audit_logger
from backend.models.sse_events import SSEEvent, SSEEventType

if TYPE_CHECKING:
    from backend.agent.streamgen import StreamGen


class AskUserTool:
    def __init__(self):
        self._pending: dict[str, asyncio.Future] = {}
        self._streamgen: Optional["StreamGen"] = None

    def set_streamgen(self, streamgen: "StreamGen"):
        self._streamgen = streamgen

    async def ask(self, question: str, session_id: str = "") -> str:
        """
        Emit an ask_user SSE event and wait for the user's response.
        Returns the user's answer as a string.
        """
        question_id = str(uuid.uuid4())
        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()
        self._pending[question_id] = future

        audit = get_audit_logger()
        await audit.log(AuditEvent(
            session_id=session_id,
            event_type=AuditEventType.ASK_USER_PROMPTED,
            agent_name="ask_user_tool",
            input_summary=question[:200],
            metadata={"question_id": question_id},
        ))

        if self._streamgen:
            await self._streamgen.emit(
                SSEEventType.ASK_USER,
                {
                    "question": question,
                    "question_id": question_id,
                    "session_id": session_id,
                },
            )

        try:
            answer = await asyncio.wait_for(future, timeout=300.0)  # 5 min timeout
            await audit.log(AuditEvent(
                session_id=session_id,
                event_type=AuditEventType.ASK_USER_RESPONDED,
                agent_name="ask_user_tool",
                output_summary=answer[:200],
                metadata={"question_id": question_id},
            ))
            return answer
        except asyncio.TimeoutError:
            del self._pending[question_id]
            return ""

    def resolve(self, question_id: str, answer: str):
        """Called when user submits their answer via HTTP."""
        if question_id in self._pending:
            future = self._pending.pop(question_id)
            if not future.done():
                future.set_result(answer)
