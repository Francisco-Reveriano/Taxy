"""
StreamGen — async SSE event generator.
Wraps an asyncio.Queue to decouple event emission from consumption.
"""
import asyncio
import json
from typing import AsyncGenerator

from backend.models.sse_events import SSEEvent, SSEEventType


class StreamGen:
    def __init__(self):
        self._queue: asyncio.Queue[SSEEvent | None] = asyncio.Queue()

    async def emit(self, event_type: SSEEventType, payload) -> None:
        """Enqueue an SSE event (non-blocking from producer side)."""
        event = SSEEvent(event_type=event_type, payload=payload)
        await self._queue.put(event)

    async def close(self):
        """Signal end of stream."""
        await self._queue.put(None)

    async def stream(self) -> AsyncGenerator[str, None]:
        """
        Async generator yielding SSE-formatted strings.
        Consumed by FastAPI StreamingResponse.
        Implements Last-Event-ID via event_id.
        """
        event_counter = 0
        while True:
            event = await self._queue.get()
            if event is None:
                yield "event: done\ndata: {}\n\n"
                break

            event_counter += 1
            event_id = event.event_id or str(event_counter)

            payload_str = json.dumps(event.payload)

            yield (
                f"id: {event_id}\n"
                f"event: {event.event_type.value}\n"
                f"data: {payload_str}\n\n"
            )
