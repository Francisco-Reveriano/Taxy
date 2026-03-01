"""
H2A (Human-to-Agent) Queue — dual-buffer design for mid-task interjections.
Buffer A: active (being read by agent loop)
Buffer B: staging (accumulates user messages during tool execution)
Merge only at safe checkpoints between tool calls.
"""
import asyncio
from typing import Any, List, Dict


class H2AQueue:
    def __init__(self):
        self.buffer_a: asyncio.Queue = asyncio.Queue()
        self.buffer_b: asyncio.Queue = asyncio.Queue()

    async def enqueue_user(self, message: Dict[str, Any], session_id: str = ""):
        """User sends a message — goes to staging buffer B (non-blocking)."""
        await self.buffer_b.put(message)

        from backend.audit.audit_logger import AuditEvent, AuditEventType, get_audit_logger
        audit = get_audit_logger()
        await audit.log(AuditEvent(
            session_id=session_id,
            event_type=AuditEventType.H2A_MESSAGE_RECEIVED,
            agent_name="h2a_queue",
            input_summary=str(message.get("content", ""))[:200],
        ))

    async def checkpoint_merge(
        self, messages: List[Dict[str, Any]], session_id: str = "",
    ) -> List[Dict[str, Any]]:
        """
        Atomically drain buffer B into A and append to messages list.
        Called between tool calls (safe checkpoints only).
        Returns updated messages list.
        """
        staged = []
        while not self.buffer_b.empty():
            try:
                item = self.buffer_b.get_nowait()
                staged.append(item)
                self.buffer_b.task_done()
            except asyncio.QueueEmpty:
                break

        if staged:
            from backend.audit.audit_logger import AuditEvent, AuditEventType, get_audit_logger
            audit = get_audit_logger()
            await audit.log(AuditEvent(
                session_id=session_id,
                event_type=AuditEventType.H2A_CHECKPOINT_MERGED,
                agent_name="h2a_queue",
                metadata={"merged_count": len(staged)},
            ))

        for item in staged:
            await self.buffer_a.put(item)
            # Append as user message to conversation
            if isinstance(item, dict) and "content" in item:
                messages.append({
                    "role": "user",
                    "content": f"[Mid-task update from user]: {item['content']}",
                })

        return messages

    def has_staged_messages(self) -> bool:
        return not self.buffer_b.empty()
