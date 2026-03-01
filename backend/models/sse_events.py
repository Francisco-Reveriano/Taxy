from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field
import time


class SSEEventType(str, Enum):
    THOUGHT = "thought"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    ANSWER = "answer"
    ASK_USER = "ask_user"
    TODO_UPDATE = "todo_update"
    COMPRESSION = "compression"
    ERROR = "error"


class SSEEvent(BaseModel):
    event_type: SSEEventType
    payload: Any
    session_id: str = ""
    timestamp: float = Field(default_factory=time.time)
    event_id: Optional[str] = None
