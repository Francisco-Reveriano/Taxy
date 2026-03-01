"""
TodoManager — tracks the agent's current plan as a structured TODO list.
Emits todo_update SSE events when state changes.
"""
import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from backend.agent.streamgen import StreamGen
from backend.models.sse_events import SSEEventType


class TodoStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TodoItem:
    id: str
    description: str
    status: TodoStatus = TodoStatus.PENDING
    priority: int = 0
    tool_required: Optional[str] = None


class TodoManager:
    MAX_FAILURES = 3

    def __init__(self, streamgen: Optional["StreamGen"] = None):
        self._items: List[TodoItem] = []
        self._streamgen = streamgen
        self._failure_count = 0

    def set_streamgen(self, streamgen: "StreamGen"):
        self._streamgen = streamgen

    def write(self, items: List[TodoItem], session_id: str = ""):
        """Replace the full TODO list."""
        self._items = items
        # Emit todo.created for new items
        from backend.audit.audit_logger import AuditEvent, AuditEventType, get_audit_logger
        import asyncio
        audit = get_audit_logger()
        for item in items:
            try:
                asyncio.get_event_loop().create_task(audit.log(AuditEvent(
                    session_id=session_id,
                    event_type=AuditEventType.TODO_CREATED,
                    agent_name="todo_manager",
                    metadata={"todo_id": item.id, "description": item.description},
                )))
            except RuntimeError:
                pass  # No event loop running

    def inject_context(self) -> dict:
        """Returns a system message dict with current plan state."""
        total = len(self._items)
        completed = sum(1 for i in self._items if i.status == TodoStatus.COMPLETED)
        next_item = next(
            (i for i in self._items if i.status == TodoStatus.PENDING),
            None
        )
        content = f"Current plan: [{completed}]/[{total}] complete."
        if next_item:
            content += f" Next: {next_item.description}"
        return {"role": "user", "content": f"[Plan Status] {content}"}

    def has_pending(self) -> bool:
        return any(i.status == TodoStatus.PENDING for i in self._items)

    def is_done(self) -> bool:
        if not self._items:
            return True
        all_complete = all(
            i.status in (TodoStatus.COMPLETED, TodoStatus.FAILED)
            for i in self._items
        )
        return all_complete or self._failure_count >= self.MAX_FAILURES

    async def evaluate(self, results: List[dict], session_id: str = ""):
        """Mark items completed/failed based on tool results."""
        for result in results:
            if "error" in result:
                self._failure_count += 1
                # Mark in-progress item as failed
                for item in self._items:
                    if item.status == TodoStatus.IN_PROGRESS:
                        item.status = TodoStatus.FAILED
                        break
            else:
                for item in self._items:
                    if item.status == TodoStatus.IN_PROGRESS:
                        item.status = TodoStatus.COMPLETED
                        break

        await self._emit_update()

        # Emit todo.updated audit events
        from backend.audit.audit_logger import AuditEvent, AuditEventType, get_audit_logger
        audit = get_audit_logger()
        for item in self._items:
            if item.status in (TodoStatus.COMPLETED, TodoStatus.FAILED):
                await audit.log(AuditEvent(
                    session_id=session_id,
                    event_type=AuditEventType.TODO_UPDATED,
                    agent_name="todo_manager",
                    metadata={"todo_id": item.id, "status": item.status.value},
                ))

    def mark_in_progress(self, item_id: str):
        for item in self._items:
            if item.id == item_id:
                item.status = TodoStatus.IN_PROGRESS
                break

    async def _emit_update(self):
        if self._streamgen:
            await self._streamgen.emit(
                SSEEventType.TODO_UPDATE,
                [
                    {
                        "id": i.id,
                        "description": i.description,
                        "status": i.status.value,
                        "priority": i.priority,
                    }
                    for i in self._items
                ],
            )

    def to_dict(self) -> List[dict]:
        return [
            {
                "id": i.id,
                "description": i.description,
                "status": i.status.value,
                "priority": i.priority,
            }
            for i in self._items
        ]
