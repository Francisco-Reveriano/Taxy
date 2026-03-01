"""
Compressor — context window manager using Haiku for summarization.
Preserves critical state: TODO list, extracted tax data, user corrections,
filing status, and confidence scores.
"""
import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

COMPRESSION_THRESHOLD = 0.92  # Trigger at 92% context utilization
CLAUDE_MD_PATH = Path("backend/memory/CLAUDE.md")

# Token estimates per model (context window sizes)
MODEL_CONTEXT_WINDOWS = {
    "claude-opus-4-6": 200000,
    "claude-sonnet-4-6": 200000,
    "claude-haiku-4-5": 200000,
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
}


class Compressor:
    def __init__(self, threshold: float = COMPRESSION_THRESHOLD):
        self._threshold = threshold
        self._client = None

    def _get_client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic()
        return self._client

    def _estimate_tokens(self, messages: List[Dict[str, Any]]) -> int:
        """Rough token estimate: 4 chars per token."""
        total_chars = sum(
            len(str(m.get("content", ""))) for m in messages
        )
        return total_chars // 4

    def check_threshold(self, messages: List[Dict[str, Any]], model: str) -> bool:
        """Returns True if context utilization exceeds threshold."""
        token_count = self._estimate_tokens(messages)
        context_window = MODEL_CONTEXT_WINDOWS.get(model, 100000)
        utilization = token_count / context_window
        logger.debug(f"Context utilization: {utilization:.1%} ({token_count} tokens)")
        return utilization >= self._threshold

    async def compress(
        self,
        messages: List[Dict[str, Any]],
        session_state: Optional[Dict[str, Any]] = None,
        session_id: str = "",
    ) -> List[Dict[str, Any]]:
        """
        Compress conversation using Claude Haiku summarization.
        Writes summary to CLAUDE.md (atomic write).
        Returns condensed message list.
        """
        from backend.config import get_settings
        settings = get_settings()

        # Build summarization prompt
        conversation_text = "\n".join(
            f"[{m.get('role', 'unknown').upper()}]: {m.get('content', '')}"
            for m in messages
            if isinstance(m.get("content"), str)
        )

        state_context = ""
        if session_state:
            state_context = f"\n\nSession state: {json.dumps(session_state, indent=2)}"

        prompt = f"""Summarize this tax assistant conversation. Preserve ALL of:
1. Current TODO list and completion status
2. Extracted tax data (income, deductions, credits, filing status)
3. User corrections to OCR fields
4. Confidence scores from both LLM analyses
5. Any pending questions or unresolved issues
6. Key agent decisions and their rationale

Conversation:
{conversation_text}
{state_context}

Return a concise summary that allows the agent to continue seamlessly."""

        from backend.audit.audit_logger import AuditEvent, AuditEventType, get_audit_logger
        audit = get_audit_logger()

        before_tokens = self._estimate_tokens(messages)

        await audit.log(AuditEvent(
            session_id=session_id,
            event_type=AuditEventType.COMPRESSION_TRIGGERED,
            agent_name="compressor",
            metadata={"before_tokens": before_tokens},
        ))

        try:
            result = await asyncio.to_thread(self._summarize_sync, prompt, settings)
            summary = result

            # Write to CLAUDE.md (atomic)
            self._atomic_write(CLAUDE_MD_PATH, summary)

            # Return condensed messages preserving system context
            system_messages = [m for m in messages if m.get("role") == "system"]
            condensed = system_messages + [
                {
                    "role": "assistant",
                    "content": f"[Context compressed. Summary:\n{summary}]",
                }
            ]

            after_tokens = self._estimate_tokens(condensed)
            await audit.log(AuditEvent(
                session_id=session_id,
                event_type=AuditEventType.COMPRESSION_COMPLETED,
                agent_name="compressor",
                metadata={
                    "before_tokens": before_tokens,
                    "after_tokens": after_tokens,
                    "ratio": round(after_tokens / before_tokens, 3) if before_tokens > 0 else 0,
                },
            ))

            logger.info("Context compressed and written to CLAUDE.md")
            return condensed

        except Exception as e:
            logger.error(f"Compression failed: {e}")
            # Return last 20 messages as fallback
            return messages[-20:]

    def _summarize_sync(self, prompt: str, settings) -> str:
        client = self._get_client()
        response = client.messages.create(
            model=settings.anthropic_low_llm_model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    @staticmethod
    def _atomic_write(path: Path, content: str):
        """Atomic write via temp file + rename."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            delete=False,
            suffix=".tmp",
        ) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        os.replace(tmp_path, path)

    def load_claude_md(self) -> Optional[str]:
        """Load existing CLAUDE.md if present."""
        if CLAUDE_MD_PATH.exists():
            return CLAUDE_MD_PATH.read_text(encoding="utf-8")
        return None
