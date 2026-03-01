"""
N0AgentLoop — Master orchestration loop.
Implements the 7-phase Claude Code–inspired agentic cycle:
Initialize → Inference → Tool Detection → Tool Execution →
TodoWrite Check → Compression Check → Recursion
"""
import asyncio
import json
import logging
import time
from typing import List, Dict, Any, Optional

import anthropic

from backend.agent.h2a_queue import H2AQueue
from backend.agent.streamgen import StreamGen
from backend.agent.todo_manager import TodoManager, TodoItem, TodoStatus
from backend.agent.compressor import Compressor
from backend.audit.audit_logger import AuditEvent, AuditEventType, get_audit_logger
from backend.config import get_settings
from backend.models.sse_events import SSEEventType
from backend.telemetry.tracer import get_tracer
from backend.tools.registry import TOOL_DEFINITIONS, ToolRegistry
from backend.utils.pii import mask_pii

logger = logging.getLogger(__name__)

N0_SYSTEM_PROMPT = """You are n0, the master tax analysis orchestrator. Your role is to:

1. Analyze the taxpayer's situation comprehensively
2. Orchestrate specialized tools (OCR, RAG, calculator, user queries)
3. Produce a complete dual-LLM tax analysis with audit trail

## Tool Usage Protocol
- Use `mistral_ocr_tool` to extract data from uploaded documents
- Use `legal_rag_agent_tool` to retrieve relevant IRS guidance
- Use `calculator_tool` for precise tax computations
- Use `ask_user_tool` when critical information is missing

## Analysis Workflow
1. Process all uploaded documents via OCR
2. Query IRS publications for applicable regulations
3. Compute tax liability using the calculator
4. Compare standard vs itemized deductions
5. Apply applicable credits
6. Produce final analysis with confidence scores

## Output Requirements
Always produce structured analysis with:
- Estimated federal tax liability
- Applicable deductions and credits
- Confidence level (High/Medium/Low)
- Advisory notes for the taxpayer
- Source citations from IRS publications

Be thorough, accurate, and cite retrieved sources. Never guess at tax rules."""


class N0AgentLoop:
    def __init__(self):
        self._settings = get_settings()
        self._client = anthropic.Anthropic(api_key=self._settings.anthropic_api_key)
        self._tracer = get_tracer()
        self._streamgen: Optional[StreamGen] = None
        self._h2a_queue = H2AQueue()
        self._tool_registry = ToolRegistry()
        self._todo_manager = TodoManager()
        self._compressor = Compressor(threshold=self._settings.context_window_threshold)

    def set_streamgen(self, streamgen: StreamGen):
        self._streamgen = streamgen
        self._tool_registry.set_streamgen(streamgen)
        self._todo_manager.set_streamgen(streamgen)

    async def run(self, user_message: str, session_id: str) -> str:
        """
        Main entry point. Runs the n0 agentic loop.
        Returns final answer text.
        """
        with self._tracer.start_agent_span("n0", session_id):
            return await self._execute_loop(user_message, session_id)

    async def _execute_loop(self, user_message: str, session_id: str) -> str:
        # Phase 1: Initialize
        claude_md = self._compressor.load_claude_md()
        messages: List[Dict[str, Any]] = []

        if claude_md:
            messages.append({
                "role": "user",
                "content": f"[Previous session context:\n{claude_md}]\n\n{user_message}",
            })
        else:
            messages.append({"role": "user", "content": user_message})

        final_answer = ""

        audit = get_audit_logger()

        for iteration in range(self._settings.todo_max_iterations):
            await audit.log(AuditEvent(
                session_id=session_id,
                event_type=AuditEventType.AGENT_CYCLE_STARTED,
                agent_name="n0",
                metadata={"iteration": iteration},
            ))

            with self._tracer.start_cycle_span("inference", iteration):
                # Phase 2: Inference
                response = await self._call_claude(messages, session_id)

                # Emit thinking if present (extended thinking)
                if hasattr(response, "thinking") and response.thinking:
                    if self._streamgen:
                        await self._streamgen.emit(SSEEventType.THOUGHT, response.thinking)

                # Check for tool use
                tool_use_blocks = [
                    block for block in response.content
                    if block.type == "tool_use"
                ]

                text_blocks = [
                    block for block in response.content
                    if block.type == "text"
                ]

                # Auto-create TodoWrite items from structured response
                for block in text_blocks:
                    self._extract_todo_items(block.text, session_id)

                # Phase 3: Tool Detection
                if not tool_use_blocks:
                    # Terminal condition — no more tools needed
                    final_answer = " ".join(b.text for b in text_blocks)
                    if self._streamgen:
                        await self._streamgen.emit(SSEEventType.ANSWER, final_answer)
                    break

                # Emit tool calls
                if self._streamgen:
                    for block in tool_use_blocks:
                        await self._streamgen.emit(
                            SSEEventType.TOOL_CALL,
                            {"tool": block.name, "inputs": block.input},
                        )

                # Add assistant response to messages
                messages.append({"role": "assistant", "content": response.content})

                # Phase 4: Tool Execution
                tool_results = await self._execute_tools(tool_use_blocks, session_id)

                # Emit tool results
                if self._streamgen:
                    for result in tool_results:
                        await self._streamgen.emit(SSEEventType.TOOL_RESULT, result)

                # Format tool results for Claude
                messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": r["tool_use_id"],
                            "content": json.dumps(r["output"]),
                        }
                        for r in tool_results
                    ],
                })

                # Phase 5: TodoWrite Check
                await self._todo_manager.evaluate(
                    [r["output"] for r in tool_results]
                )
                if self._todo_manager.has_pending():
                    messages.append(self._todo_manager.inject_context())

                # Phase 6: Compression Check
                if self._compressor.check_threshold(messages, self._settings.anthropic_advance_llm_model):
                    if self._streamgen:
                        await self._streamgen.emit(
                            SSEEventType.COMPRESSION,
                            {"message": "Compressing conversation context..."},
                        )
                    session_state = {"session_id": session_id}
                    messages = await self._compressor.compress(messages, session_state, session_id=session_id)

                # h2A checkpoint merge
                messages = await self._h2a_queue.checkpoint_merge(messages, session_id=session_id)

                await audit.log(AuditEvent(
                    session_id=session_id,
                    event_type=AuditEventType.AGENT_CYCLE_COMPLETED,
                    agent_name="n0",
                    metadata={"iteration": iteration},
                ))

        else:
            # Max iterations reached
            if self._streamgen:
                await self._streamgen.emit(
                    SSEEventType.ERROR,
                    {"code": "MAX_ITER", "message": "Maximum iterations reached"},
                )

        if self._streamgen:
            await self._streamgen.close()

        return final_answer

    async def _call_claude(self, messages: List[Dict[str, Any]], session_id: str):
        """Call Claude with the current conversation (PII-masked)."""
        # Apply PII masking to user message content before sending
        masked_messages = []
        for m in messages:
            if isinstance(m.get("content"), str):
                masked_messages.append({**m, "content": mask_pii(m["content"])})
            else:
                masked_messages.append(m)

        with self._tracer.start_model_invoke_span(
            "anthropic",
            self._settings.anthropic_advance_llm_model,
        ) as span:
            response = await asyncio.to_thread(
                self._client.messages.create,
                model=self._settings.anthropic_advance_llm_model,
                max_tokens=8192,
                system=N0_SYSTEM_PROMPT,
                tools=TOOL_DEFINITIONS,
                messages=masked_messages,
            )
            # Set token counts on span
            if hasattr(response, "usage") and response.usage:
                span.set_attribute("tax.model.input_tokens", response.usage.input_tokens)
                span.set_attribute("tax.model.output_tokens", response.usage.output_tokens)
            return response

    async def _execute_tools(
        self,
        tool_use_blocks: List[Any],
        session_id: str,
    ) -> List[Dict[str, Any]]:
        """Execute all tool calls in parallel with audit events."""
        audit = get_audit_logger()
        calls = [
            {"name": block.name, "inputs": block.input}
            for block in tool_use_blocks
        ]

        # Emit tool.invoked for each call
        for block in tool_use_blocks:
            await audit.log(AuditEvent(
                session_id=session_id,
                event_type=AuditEventType.TOOL_INVOKED,
                agent_name="n0",
                tool_name=block.name,
                input_summary=json.dumps(block.input)[:200],
            ))

        results_raw = await self._tool_registry.dispatch_parallel(calls, session_id)

        results = []
        for block, output in zip(tool_use_blocks, results_raw):
            is_error = isinstance(output, dict) and "error" in output
            await audit.log(AuditEvent(
                session_id=session_id,
                event_type=AuditEventType.TOOL_FAILED if is_error else AuditEventType.TOOL_COMPLETED,
                agent_name="n0",
                tool_name=block.name,
                output_summary=str(output)[:200],
                error_message=output.get("error") if is_error else None,
            ))
            results.append({
                "tool_use_id": block.id,
                "tool_name": block.name,
                "output": output,
            })

        return results

    def _extract_todo_items(self, text: str, session_id: str):
        """Auto-create TodoItems from Claude's structured plan/checklist in response text."""
        import re
        import uuid as _uuid
        # Look for numbered or bulleted plan items
        lines = text.split("\n")
        items = []
        for line in lines:
            line = line.strip()
            # Match patterns like "1. ...", "- [ ] ...", "- ..."
            match = re.match(r"^(?:\d+[\.\)]\s*|[-*]\s*(?:\[[ x]\]\s*)?)(.*)", line)
            if match and len(match.group(1).strip()) > 10:
                desc = match.group(1).strip()
                items.append(TodoItem(
                    id=str(_uuid.uuid4())[:8],
                    description=desc,
                    priority=len(items),
                ))
        if items and not self._todo_manager.has_pending():
            self._todo_manager.write(items, session_id=session_id)

    async def enqueue_user_message(self, content: str, session_id: str = ""):
        """Inject a user message mid-task (goes to buffer B)."""
        await self._h2a_queue.enqueue_user({"content": content}, session_id=session_id)

    def resolve_user_answer(self, question_id: str, answer: str):
        """Resolve a pending ask_user question."""
        self._tool_registry.resolve_user_answer(question_id, answer)
