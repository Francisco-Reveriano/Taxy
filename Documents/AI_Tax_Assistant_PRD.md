**Product Requirement Document**

AI-Powered Tax Assistant (TurboTax Mirror)


| Document Title | Product Requirement Document: AI Tax Assistant |
| --- | --- |
| Version | 1.0 |
| Author | Francisco (Expert Engagement Manager, McKinsey & Company) |
| Date | February 27, 2026 |
| Status | Draft |
| Classification | Internal / Personal Project |


# 1. Executive Summary

This document defines the product requirements for an AI-powered personal tax preparation tool that mirrors the TurboTax experience. The system is built on a Claude Code–inspired agentic architecture where a single-threaded master loop (n0) powered by the Anthropic SDK autonomously orchestrates tax document processing, dual-LLM analysis, and interactive user guidance through a step-by-step wizard.

At its core, the system combines Mistral OCR 3 for document field extraction, a dual-LLM architecture (Anthropic Claude for primary tax computation and OpenAI Assistants with RAG for independent validation), and a confidence scoring engine that flags any result below 90% or with significant inter-model disagreement. The n0 agent loop drives this process autonomously using a TodoWrite → Execute → Evaluate planning cycle, with an async dual-buffer queue (h2A) enabling mid-task user interjections without restart, and a Compressor (wU2) managing context window utilization by persisting state to a CLAUDE.md project memory file.

The frontend is a React + Vite single-page application receiving real-time agent output via Server-Sent Events (SSE), rendering a TurboTax-style wizard with 7 steps from filing status through results review. The FastAPI middleware serves both REST endpoints and the SSE stream, running locally via uvicorn. The tool targets W-2 and 1099-series forms at MVP as a single-user personal tool.

Enterprise-grade observability is built in from day one: a three-tier logging system produces operational logs (structlog), an append-only JSONL audit trail capturing every tax-relevant action with PII masking, and a comprehensive PDF/JSON audit report suitable for CPA review and IRS audit defense. OpenTelemetry distributed tracing instruments the full agentic lifecycle with hierarchical spans (Agent → Cycle → Model Invoke → Tool), exported to a local Jaeger dashboard for interactive trace visualization, latency analysis, and session debugging.

The PRD specifies 20 sections covering system architecture (including the 9-component agentic backend), 30+ functional requirements, a structured OpenAI RAG agent reference architecture adapted from a production Legal Expert Agent pattern, a digital twin testing framework with 12 scenario configurations, a comprehensive test plan with 112+ test cases, and the full observability stack. The document is designed to serve as the complete engineering specification for implementation.


# 2. Product Vision & Goals


## 2.1 Vision Statement

Deliver a locally-hosted, AI-native tax preparation experience that matches TurboTax’s guided simplicity while providing transparent, dual-validated tax analysis with confidence scoring and RAG-grounded accuracy.


## 2.2 Core Objectives


| ID | Objective |
| --- | --- |
| OBJ-1 | Enable upload and OCR extraction of W-2 and 1099-series tax documents with >95% field-level accuracy via Mistral OCR 3. |
| OBJ-2 | Implement dual-LLM tax analysis using Anthropic Claude and OpenAI Assistants operating independently, with confidence score comparison. |
| OBJ-3 | Provide a TurboTax-style step-by-step wizard that dynamically adapts questions based on extracted data and user inputs. |
| OBJ-4 | Leverage a user-managed knowledge base via OpenAI Assistants Vector Store for RAG-grounded tax guidance. |
| OBJ-5 | Flag any analysis result scoring below 90% confidence for manual human review. |


# 3. Scope & Boundaries


## 3.1 In Scope (MVP)


| Feature | Description |
| --- | --- |
| Document Upload | Upload PDF, JPEG, PNG tax documents via drag-and-drop or file picker in the React UI. |
| OCR Processing | Mistral OCR 3 extracts structured fields (employer EIN, wages, withholding, etc.) from W-2 and 1099-series forms. |
| Knowledge Base RAG | OpenAI Assistants API with user-provided Vector Store ID (via .env) for retrieval-augmented tax guidance. |
| Dual-LLM Analysis | Anthropic Claude performs primary tax computation/advisory; OpenAI performs independent RAG-grounded analysis; scores are compared. |
| Step-by-Step Wizard | TurboTax-style interview flow: filing status, income, deductions, credits, review, and summary. |
| Confidence Scoring | Both LLMs produce independent confidence scores; discrepancies and sub-90% scores trigger human review flags. |
| Local Deployment | Runs entirely on local filesystem via uvicorn (FastAPI) with React + Vite frontend. |


## 3.2 Out of Scope (MVP)


| Feature | Rationale |
| --- | --- |
| E-Filing | No direct IRS e-file submission; generates summary reports for manual filing or CPA review. |
| Multi-User / Auth | Single-user personal tool; no authentication, user accounts, or multi-tenancy. |
| State Tax Forms | Federal forms only at MVP; state-specific forms deferred to v2. |
| Schedule C / K-1 | Business income forms deferred; MVP focuses on W-2 and 1099-series. |
| Cloud Deployment | No AWS/GCP/Azure hosting; local-only at MVP. |
| Payment Processing | No payment or subscription logic. |


# 4. System Architecture


## 4.1 Architecture Overview

The system follows a three-tier architecture: a React + Vite single-page application (SPA) serving as the frontend, a FastAPI middleware layer handling routing, orchestration, and LLM coordination, and a Python backend managing OCR processing, file I/O, knowledge base integration, and LLM API calls.


## 4.2 Technology Stack


| Layer | Technology | Purpose |
| --- | --- | --- |
| Frontend | React 18+ with Vite build tool | Dynamic step-by-step wizard UI, document upload, results dashboard, SSE event rendering |
| Middleware | FastAPI (Python) | REST API routing, SSE streaming (StreamingResponse), request validation, CORS handling |
| Agent Core (n0) | Anthropic SDK (Python) | Single-threaded master agent loop; Claude drives orchestration natively via tool_use protocol |
| Async Queue (h2A) | asyncio + custom dual-buffer | Async message queue enabling mid-task user interjections without restart; pause/resume support |
| Streaming (StreamGen) | FastAPI StreamingResponse (SSE) | Server-Sent Events delivering typed events (thought, tool_call, tool_result, answer, ask_user) to React |
| Context Compressor (wU2) | Anthropic SDK (Haiku tier) | Automatic conversation compression at ~92% context utilization; writes to CLAUDE.md |
| Project Memory | CLAUDE.md (Markdown on disk) | Persistent long-term memory; loaded at session start; survives restarts |
| Planning System | TodoWrite / Execute / Evaluate | Fully autonomous TODO-based planning loop; full-list updates; context injection after each tool call |
| OCR Engine | Mistral OCR 3 (via API) | Structured field extraction from W-2 and 1099 documents; registered as mistral_ocr_tool |
| Primary LLM | Anthropic Claude (tiered: Opus/Sonnet/Haiku) | Tax computation, advisory analysis, agent orchestration (n0 uses advance tier) |
| Validation LLM | OpenAI Assistants API (tiered: GPT-5.2 Pro/Standard/Mini) | RAG-grounded independent analysis via LEGA RAG Agent Tool + TAX_VECTOR_STORE |
| Knowledge Base | OpenAI Vector Store (user-managed) | User populates; provides TAX_VECTOR_STORE ID in .env; accessed via FileSearchTool |
| Tool: Calculator | Python (deterministic arithmetic) | Exact tax bracket, deduction, credit, FICA/SE calculations; no LLM approximation |
| Tool: Ask User | SSE + h2A integration | Non-blocking human-in-the-loop; queues question via SSE; continues other tasks while waiting |
| Runtime | uvicorn | ASGI server for local FastAPI deployment |
| State Management | React Context / Zustand | Wizard step state, SSE event buffer, extracted data, analysis results |


## 4.3 Data Flow

The end-to-end data flow proceeds through the following stages:

**Step 1 – Document Upload: **User uploads tax documents (PDF/JPEG/PNG) via the React UI. Files are sent to the FastAPI backend via multipart form upload.

**Step 2 – OCR Processing: **FastAPI forwards documents to Mistral OCR 3 API. Structured JSON is returned with extracted fields (employer name, EIN, wages, federal tax withheld, state info, etc.).

**Step 3 – Data Validation & Wizard Population: **Extracted fields pre-populate wizard steps. User reviews and corrects any OCR misreads.

**Step 4 – Parallel LLM Analysis: **FastAPI dispatches the validated tax data to both Anthropic Claude and OpenAI Assistants concurrently (via asyncio.gather). Each LLM independently produces: tax liability estimate, applicable deductions/credits, advisory notes, and a confidence score (0–100).

**Step 5 – Score Comparison & Flagging: **The scoring engine compares both confidence scores. If either score is below 90% or the inter-model delta exceeds 10 points, the result is flagged for human review.

**Step 6 – Results Presentation: **The wizard’s final step displays a comprehensive summary: side-by-side LLM results, confidence scores, flags, and actionable recommendations.


## 4.4 Backend Agentic Architecture (Claude Code–Inspired)

The backend implements a single-threaded master agent loop architecture inspired by Claude Code’s production design. Rather than a traditional request–response API, the backend operates as an autonomous agentic system where Claude (via the Anthropic SDK) serves as the sole orchestrator, driving a continuous think → act → observe → correct loop. This design prioritizes debuggability, transparency, and controllable autonomy over complex multi-agent swarm patterns.


### 4.4.1 Architecture Component Map

The backend consists of nine interconnected components organized in three layers:


| Component | Layer | Description | Role |
| --- | --- | --- | --- |
| n0 (Anthropic Agent) | Agent Core | Single-threaded master agent loop. Pure Anthropic SDK agent where Claude drives the loop natively. Implements a classic while-loop that continues execution as long as the model’s responses include tool calls. When Claude produces a plain text response without tool invocations, the loop terminates and returns control to the user via StreamGen. Maintains one flat message history, avoiding threaded conversations or competing agent personas. | Central orchestrator |
| h2A (Async Dual-Buffer) | Agent Core | Asynchronous dual-buffer message queue that enables mid-task user interjections without requiring a full restart. Supports pause/resume and cooperates with n0 to create truly interactive streaming conversations. When a user injects new instructions mid-task, h2A seamlessly incorporates them into the agent’s queue, and Claude adjusts its plan on the fly. | Real-time steering |
| StreamGen (Streaming Output) | User Interface Layer | Server-Sent Events (SSE) streaming via FastAPI StreamingResponse. Delivers real-time agent output (reasoning steps, tool call results, partial answers) to the React frontend. Each SSE event is typed (thought, tool_call, tool_result, answer, ask_user, error) enabling the frontend to render progressive UI updates. | Frontend delivery |
| Compressor wU2 | Context Management | Automatic context window compressor. Triggers at approximately 92% context window utilization. When triggered, pauses the agent loop, summarizes the conversation using a dedicated summarization prompt, and replaces the message history with a compact summary. Critical state (file modifications, current TODO list, extracted tax data) is preserved through the compression. | Memory efficiency |
| CLAUDE.md (Project Memory) | Context Management | Persistent markdown file on disk that serves as long-term project memory. The Compressor writes compressed context here. Survives server restarts and persists across sessions. Loaded into the agent’s system prompt at session start. Contains: session history summaries, user preferences, previously extracted tax data references, recurring patterns, and known corrections. | Persistent state |
| Logs / Message History | Observability | Flat, append-only audit trail of all tool calls, model responses, and user messages. Every agent action is logged with timestamp, tool name, input, output, and latency. Enables full replay and debugging of any session. Message history feeds back into n0 as context for the next inference cycle. | Auditability |
| ToolEngine & Scheduler | Tool Layer | Orchestrates tool dispatch from n0. Maintains a tool registry with metadata (name, schema, timeout, retry policy). Routes tool calls to the appropriate handler. Supports parallel tool calls when Claude requests multiple tools simultaneously. Manages tool timeouts and error propagation back to the agent. | Tool orchestration |
| TodoWrite (Plan) | Execution Layer | TODO-based planning system. When Claude determines a multi-step approach is needed, it writes a structured TODO list. The system uses full-list updates (not partial). After each tool use, the current TODO state is injected into the context as a system message, preventing the model from losing track of objectives in long sessions. | Task planning |
| Execute → Evaluate | Execution Layer | Execution and self-evaluation loop. Execute runs the planned tool calls. Evaluate assesses the results against the TODO objectives. Fully autonomous: loops back to TodoWrite for re-planning without user intervention until all TODO items are resolved or a terminal condition is reached (error, max iterations, or explicit Ask User). | Autonomous execution |


### 4.4.2 Tool Registry

The ToolEngine manages four registered tools, each exposed to Claude as a callable function via the Anthropic SDK’s tool_use mechanism:


| Tool ID | Display Name | Behavior | Execution | Error Handling |
| --- | --- | --- | --- | --- |
| calculator_tool | Calculator Tool | Performs deterministic tax arithmetic: bracket calculations, deduction comparisons (standard vs. itemized), credit phase-outs, FICA/SE tax, AGI computation. Results are exact (no LLM approximation). Returns structured JSON with calculation steps for auditability. | Sync | None |
| legal_rag_agent_tool | LEGA RAG Agent Tool | Invokes the OpenAI Assistants-based Legal/Tax RAG Agent (Section 10). Sends the current tax context to the OpenAI agent, which performs RAG retrieval from TAX_VECTOR_STORE and returns structured analysis (regulation, requirements, permissions, prohibitions, interpretation, confidence). Returns the full LEGAL_EXPERT_AGENT_OUTPUT schema. | Async | 3 retries, exponential backoff |
| mistral_ocr_tool | Mistral OCR Tool | Sends uploaded tax documents (PDF/JPEG/PNG) to Mistral OCR 3 API. Returns structured JSON with extracted fields per form type (W-2, 1099 variants). Includes per-field confidence metadata from Mistral. Handles multi-page documents. | Async | 3 retries, 30s timeout |
| ask_user_tool | Ask User | Human-in-the-loop tool for requesting user input when the agent encounters ambiguity, low-confidence decisions, or needs clarification. Non-blocking: queues the question via SSE to the frontend and continues processing other tasks. When the user responds, h2A injects the answer into the agent’s message queue for seamless continuation. | Non-blocking async | None (waits indefinitely) |


### 4.4.3 Agentic Loop Data Flow

The n0 master loop executes the following cycle for each user interaction:

**Phase 1 – Initialize: **Load CLAUDE.md into system prompt. Load Logs/Message History. Inject user’s message into the flat message history. Check context window utilization against 92% threshold.

**Phase 2 – Inference: **Send message history + system prompt + tool definitions to Anthropic Claude API (model from ANTHROPIC_ADVANCE_LLM_MODEL in .env). Stream response tokens to StreamGen → SSE → React frontend in real-time.

**Phase 3 – Tool Detection: **Parse Claude’s response for tool_use blocks. If no tool calls detected, the loop terminates and the text response is delivered as the final answer. If tool calls detected, proceed to Phase 4.

**Phase 4 – Tool Execution: **ToolEngine dispatches each tool call to its registered handler. Parallel tool calls execute concurrently via asyncio.gather. Each tool result is appended to message history as a tool_result block. StreamGen emits tool_call and tool_result SSE events for frontend progress display.

**Phase 5 – TodoWrite Check: **If a TODO list exists, inject current TODO state as a system message. Evaluate checks completed items against the plan. If items remain, loop returns to Phase 2 (re-inference with updated context). If all items resolved, proceed to final answer.

**Phase 6 – Compression Check: **If context utilization exceeds 92%, trigger Compressor wU2. Summarize conversation, write summary to CLAUDE.md, replace message history with compressed version. Resume loop with reduced context.

**Phase 7 – Recursion: **Re-enter Phase 2 with updated message history (user input + assistant output + tool results). The loop only exits when Claude produces a final text response with no tool calls, or a terminal condition is reached (max iterations, unrecoverable error).


### 4.4.4 h2A Async Dual-Buffer Queue Detail

The h2A queue is critical for real-time interactivity. It maintains two buffers: Buffer A (active) holds the current stream of agent events being processed, while Buffer B (staging) accepts incoming user interjections. When a user sends a message mid-task (e.g., “actually use itemized deductions, not standard”), the message enters Buffer B. At the next natural pause point (between tool calls or at Phase 5), h2A swaps or merges Buffer B into the active stream, and n0 sees the interjection as part of its message history. This enables course correction without restart.

The Ask User tool leverages h2A in reverse: the agent emits a question to Buffer A (delivered via StreamGen/SSE to the frontend), and the user’s response arrives in Buffer B. Because Ask User is non-blocking, the agent continues executing other pending tool calls or TODO items while waiting. When the response arrives, h2A injects it at the next processing checkpoint.


### 4.4.5 Compressor wU2 & CLAUDE.md Specification

The compressor ensures the agent can operate across long, complex tax sessions without losing critical state:


| Parameter | Specification |
| --- | --- |
| Trigger Threshold | ~92% of the model’s context window (e.g., ~184K tokens for a 200K window) |
| Summarization Model | ANTHROPIC_LOW_LLM_MODEL (claude-haiku-4-5) for cost efficiency |
| Preserved State | Current TODO list; all extracted tax data (OCR fields); user corrections; filing status; confidence scores from prior analyses; active tool call queue |
| Discarded State | Verbose intermediate reasoning; completed tool call details (retained in Logs); conversational filler |
| CLAUDE.md Location | /backend/memory/CLAUDE.md (persistent on disk, excluded from version control via .gitignore) |
| CLAUDE.md Structure | Sections: ## Session Summary, ## Extracted Tax Data, ## User Preferences, ## Known Corrections, ## TODO History |
| Load Behavior | Read and injected into system prompt at session initialization. If file does not exist, agent starts with a blank memory context. |
| Write Behavior | Appended/overwritten on compression trigger and on graceful session end. Atomic write (temp file + rename) to prevent corruption. |


### 4.4.6 TodoWrite Planning Specification

The TodoWrite system provides structured task planning for multi-step tax operations. When Claude determines that a task requires multiple steps (e.g., process three uploaded documents, then analyze, then compare deductions), it writes a TODO list via the TodoWrite tool:


| Parameter | Specification |
| --- | --- |
| TODO Format | JSON array of objects: [{id, description, status, dependencies}]. Status values: pending, in_progress, completed, failed, blocked. |
| Update Semantics | Full-list replacement on every update (no partial patches). Claude rewrites the entire TODO list to reflect current state. |
| Context Injection | After every tool call, the current TODO state is injected as a system message: “Current plan status: [N] of [M] items complete. Next: [description].” |
| Autonomy Model | Fully autonomous. Execute → Evaluate loops back to TodoWrite without user approval. The loop continues until all items are completed, failed (with max retry), or the agent explicitly invokes ask_user_tool for human guidance. |
| Max Iterations | Configurable via TODO_MAX_ITERATIONS env var (default: 25). Safety valve to prevent infinite loops. |
| Failure Handling | If a TODO item fails 3 times, it is marked “failed” and the agent re-plans around it, explaining the failure in its next response. |


### 4.4.7 StreamGen SSE Event Types

StreamGen delivers typed SSE events to the React frontend via FastAPI’s StreamingResponse. Each event has a type field enabling the frontend to render appropriate UI components:


| Event Type | Payload Description | Frontend Rendering |
| --- | --- | --- |
| thought | Agent’s reasoning step (partial or complete) | Display in “thinking” collapsible panel |
| tool_call | Tool invocation with name and parameters | Show tool badge + spinner in progress timeline |
| tool_result | Tool response with structured data | Update progress timeline; populate data panels |
| answer | Final or partial answer text | Render in main response area (supports streaming tokens) |
| ask_user | Agent question requiring user input | Display input prompt/modal; pause wizard progression until answered |
| todo_update | Updated TODO list state | Update plan/progress sidebar showing completed/pending items |
| compression | Context compression event | Brief notification: “Optimizing memory…” |
| error | Error with code and message | Display error banner with retry option |


### 4.4.8 Architectural Decisions & Rationale


| Decision | Rationale |
| --- | --- |
| Single-threaded master loop (no multi-agent swarm) | Debuggability and transparency. A flat message history with one orchestrator eliminates race conditions, conflicting agent decisions, and non-deterministic interleaving. Every action has a single causal chain that can be replayed from logs. |
| Pure Anthropic SDK (Claude drives the loop) | Leverages Claude’s native tool_use protocol and structured output. No custom loop management code to maintain. Model upgrades automatically improve orchestration quality. |
| OpenAI Agent as a TOOL, not a co-orchestrator | The LEGA RAG Agent is invoked as a tool call within n0’s loop, not as a parallel orchestrator. This preserves the single-threaded simplicity: Claude decides when to call the RAG agent, receives its structured output, and incorporates it into its reasoning. No inter-agent negotiation or conflict resolution needed. |
| Non-blocking Ask User | Tax analysis often involves multiple independent steps. Blocking the entire loop for a user question (e.g., “Did you contribute to a Roth IRA?”) would waste time when other documents can be processed in parallel. Non-blocking allows the agent to continue productive work. |
| SSE over WebSockets | SSE is simpler, unidirectional (server → client), and sufficient for streaming agent output. User input goes through standard HTTP POST to FastAPI endpoints. Avoids WebSocket connection management complexity. h2A handles the bidirectional coordination server-side. |
| Persistent CLAUDE.md over database | Markdown is human-readable, version-controllable (if desired), and trivially editable. No database dependency for a single-user local tool. Aligns with Claude Code’s proven pattern. |
| 92% compression threshold | Matches Claude Code’s production-validated threshold. Provides enough headroom (~8%) for the compression prompt itself plus the compressed summary injection without exceeding the context window. |


# 5. Functional Requirements


## 5.1 Document Upload & Management


| ID | Priority | Requirement |
| --- | --- | --- |
| FR-101 | Must | System shall accept PDF, JPEG, and PNG file uploads up to 20MB per file. |
| FR-102 | Must | System shall provide drag-and-drop and file picker upload interfaces. |
| FR-103 | Must | System shall display upload progress and file thumbnails post-upload. |
| FR-104 | Should | System shall allow users to remove or replace uploaded documents before processing. |
| FR-105 | Should | System shall auto-detect document type (W-2 vs 1099 variant) from OCR output. |


## 5.2 OCR Processing (Mistral OCR 3)


| ID | Priority | Requirement |
| --- | --- | --- |
| FR-201 | Must | System shall send uploaded documents to Mistral OCR 3 API and receive structured JSON field extraction. |
| FR-202 | Must | System shall extract all standard W-2 fields: Employee SSN (masked), Employer EIN, Wages (Box 1), Federal Tax Withheld (Box 2), Social Security Wages (Box 3), Medicare Wages (Box 5), State wages and tax. |
| FR-203 | Must | System shall extract all standard 1099-NEC, 1099-INT, 1099-DIV, and 1099-MISC fields. |
| FR-204 | Must | System shall display extracted fields for user review and correction before analysis. |
| FR-205 | Should | System shall highlight low-confidence OCR fields (per Mistral’s confidence metadata) in the UI for user attention. |
| FR-206 | Should | System shall handle multi-page documents and batch processing of multiple forms. |


## 5.3 Knowledge Base & RAG (OpenAI Assistants)


| ID | Priority | Requirement |
| --- | --- | --- |
| FR-301 | Must | System shall read the OpenAI Vector Store ID from the OPENAI_VECTOR_STORE_ID environment variable in the .env file. |
| FR-302 | Must | System shall use OpenAI Assistants API with file_search tool type, referencing the configured Vector Store for retrieval. |
| FR-303 | Must | System shall construct prompts that include retrieved context from the Vector Store alongside the user’s tax data for analysis. |
| FR-304 | Must | The knowledge base folder shall be user-managed; the system shall not auto-populate or modify its contents. |
| FR-305 | Should | System shall log which Vector Store chunks were retrieved for each analysis (for auditability). |


## 5.4 Dual-LLM Tax Analysis


| ID | Priority | Requirement |
| --- | --- | --- |
| FR-401 | Must | System shall send validated tax data to Anthropic Claude API for primary tax analysis including: estimated tax liability, applicable standard/itemized deductions, eligible credits, and advisory notes. |
| FR-402 | Must | System shall send the same validated tax data to OpenAI Assistants (with RAG context) for independent analysis producing the same output categories. |
| FR-403 | Must | Both LLM calls shall execute concurrently (asyncio.gather) to minimize latency. |
| FR-404 | Must | Each LLM response shall include a confidence score from 0 to 100. |
| FR-405 | Must | System shall implement a scoring engine that compares both scores and flags results where: (a) either score is below 90, or (b) the inter-model delta exceeds 10 points. |
| FR-406 | Must | Flagged results shall display a prominent warning banner in the UI recommending human/CPA review. |
| FR-407 | Should | System shall display a side-by-side comparison of both LLM outputs on the results screen. |
| FR-408 | Should | System shall provide a combined “consensus” result when both models agree above threshold. |


## 5.5 Step-by-Step Wizard UI


| ID | Priority | Requirement |
| --- | --- | --- |
| FR-501 | Must | System shall implement a TurboTax-style sequential wizard with the following steps: (1) Welcome / Filing Status, (2) Document Upload, (3) OCR Review & Correction, (4) Income Summary, (5) Deductions & Credits, (6) Analysis (dual-LLM), (7) Results & Review. |
| FR-502 | Must | Wizard shall dynamically show/hide steps and questions based on uploaded document types and extracted data. |
| FR-503 | Must | Wizard shall support forward and backward navigation with state persistence across steps. |
| FR-504 | Must | Wizard shall display a progress indicator showing current step and completion status. |
| FR-505 | Should | Each wizard step shall include contextual help tooltips explaining tax concepts in plain language. |
| FR-506 | Should | Wizard shall auto-save progress to local state so browser refresh does not lose data. |


# 6. Non-Functional Requirements


| ID | Category | Requirement |
| --- | --- | --- |
| NFR-01 | Performance | OCR processing shall complete within 15 seconds per document. Dual-LLM analysis shall complete within 30 seconds (parallel execution). |
| NFR-02 | Security | All API keys (Anthropic, OpenAI, Mistral) shall be stored in .env and never exposed to the frontend. SSN and sensitive PII shall be masked in the UI and logs. |
| NFR-03 | Reliability | System shall gracefully handle API failures with retry logic (3 attempts, exponential backoff) and user-friendly error messages. |
| NFR-04 | Usability | Wizard shall be accessible (WCAG 2.1 AA) with keyboard navigation and screen reader support. |
| NFR-05 | Maintainability | Codebase shall follow clear separation of concerns: /api (FastAPI routes), /services (LLM, OCR logic), /models (Pydantic schemas), /frontend (React). |
| NFR-06 | Data Privacy | No tax data shall be persisted to disk beyond the active session. All data shall remain in memory during processing. |
| NFR-07 | Extensibility | Architecture shall support adding new form types (Schedule C, K-1, state forms) and additional LLM providers without structural refactoring. |


# 7. API Design (FastAPI Endpoints)


| Method | Endpoint | Description | Response |
| --- | --- | --- | --- |
| POST | /api/upload | Upload tax document(s); returns file ID and metadata | multipart/form-data |
| POST | /api/ocr/{file_id} | Trigger Mistral OCR 3 processing on uploaded file | JSON (extracted fields) |
| PUT | /api/ocr/{file_id}/fields | Submit user corrections to OCR-extracted fields | JSON (corrected fields) |
| POST | /api/analyze | Trigger dual-LLM analysis on validated tax data | JSON (both results + scores) |
| GET | /api/analyze/{session_id}/results | Retrieve analysis results and confidence scores | JSON (results + flags) |
| GET | /api/wizard/state | Get current wizard state and step data | JSON (wizard state) |
| PUT | /api/wizard/state | Update wizard state (step navigation, form data) | JSON (updated state) |
| GET | /api/health | Health check endpoint | JSON ({ status: ok }) |
| GET | /api/audit/trail/{session_id} | Retrieve raw JSONL audit trail for a session | application/jsonl stream |
| GET | /api/audit/report/{session_id} | Generate and download PDF audit report | application/pdf |
| GET | /api/audit/report/{session_id}/json | Generate and download JSON audit report | application/json |


# 8. Environment Configuration

The following environment variables must be configured in the project’s .env file. The variable names and groupings below reflect the actual production .env structure. All secret values (API keys, store IDs) must never be committed to version control.


## 8.1 .env Variable Reference


| Variable | Group | Description | Example Value | Required |
| --- | --- | --- | --- | --- |
| OPENAI_API_KEY | Personal API Keys | OpenAI platform API key for Assistants, RAG, and GPT model access | sk-proj-xxxxx… | Required |
| ANTHROPIC_API_KEY | Personal API Keys | Anthropic platform API key for Claude tax analysis | sk-ant-api03-xxxxx… | Required |
| MISTRAL_API_KEY | Personal API Keys | Mistral platform API key for OCR 3 document processing | xxxxx… | Required |
| ANTHROPIC_ADVANCE_LLM_MODEL | LLM Models | Anthropic high-capability model for complex tax analysis | claude-opus-4-6 | Required |
| ANTHROPIC_MEDIUM_LLM_MODEL | LLM Models | Anthropic mid-tier model for standard analysis tasks | claude-sonnet-4-6 | Required |
| ANTHROPIC_LOW_LLM_MODEL | LLM Models | Anthropic lightweight model for validation and simple queries | claude-haiku-4-5 | Required |
| OPENAI_VERY_ADVANCE_LLM_MODEL | LLM Models | OpenAI highest-capability model for complex RAG analysis | gpt-5.2-pro-2025-12-11 | Required |
| OPENAI_ADVANCE_LLM_MODEL | LLM Models | OpenAI high-capability model for standard RAG analysis | gpt-5.2-2025-12-11 | Required |
| OPENAI_MEDIUM_LLM_MODEL | LLM Models | OpenAI mid-tier model for lightweight tasks | gpt-5-mini-2025-08-07 | Required |
| TAX_VECTOR_STORE | Vector Store | OpenAI Vector Store ID for tax knowledge base (user-managed) | vs_xxxxx… | Required |
| CONFIDENCE_THRESHOLD | Scoring | Minimum confidence score before flagging (default: 90) | 90 | Optional |
| DELTA_THRESHOLD | Scoring | Max acceptable inter-model score delta (default: 10) | 10 | Optional |
| TODO_MAX_ITERATIONS | Agent | Max autonomous loop iterations before safety halt (default: 25) | 25 | Optional |
| COMPRESSION_THRESHOLD | Agent | Context window utilization % triggering compression (default: 92) | 92 | Optional |
| LOG_LEVEL | Logging | Operational log level: DEBUG, INFO, WARN, ERROR (default: INFO) | INFO | Optional |
| AUDIT_DIR | Logging | Directory for audit trail and report files (default: /backend/audit/) | /backend/audit/ | Optional |
| OTEL_EXPORTER_OTLP_ENDPOINT | Tracing | OTLP collector endpoint for OpenTelemetry traces | http://localhost:4318 | Required (tracing) |
| OTEL_SERVICE_NAME | Tracing | Service name in OTel traces (default: tax-assistant-n0) | tax-assistant-n0 | Optional |
| OTEL_CONSOLE_EXPORT | Tracing | Enable console span export for development (default: false) | false | Optional |
| FASTAPI_HOST | Server | Host binding for uvicorn (default: 0.0.0.0) | 0.0.0.0 | Optional |
| FASTAPI_PORT | Server | Port binding for uvicorn (default: 8000) | 8000 | Optional |
| VITE_API_URL | Server | Frontend API base URL (default: http://localhost:8000) | http://localhost:8000 | Optional |


## 8.2 .env File Template

The project shall include a .env.example file (committed to version control) with all variable names and placeholder values. The actual .env file shall be listed in .gitignore. The template follows the three-group structure below:

**Group 1 – Personal API Keys: **OPENAI_API_KEY, ANTHROPIC_API_KEY, MISTRAL_API_KEY. These are platform-issued secret keys and must never appear in logs, frontend code, or API responses.

**Group 2 – LLM Models: **Six model identifiers across Anthropic (3 tiers: advance, medium, low) and OpenAI (3 tiers: very advance, advance, medium). These allow model swapping without code changes, supporting A/B testing and cost optimization. The tiered structure enables routing simple validation tasks to lightweight models while reserving high-capability models for complex tax analysis.

**Group 3 – Vector Store: **TAX_VECTOR_STORE holds the OpenAI Vector Store ID referencing the user-managed knowledge base. The user populates the Vector Store independently via the OpenAI platform; the application only reads from it via the Assistants API file_search tool.


# 9. Project Structure

The recommended directory layout supports clear separation of frontend and backend concerns:


| Path | Purpose |
| --- | --- |
| / | Project root with .env, .env.example, docker-compose.yml (future), README.md, .gitignore |
| /backend | Python FastAPI application root |
| /backend/main.py | FastAPI app initialization, CORS config, SSE streaming setup, uvicorn entrypoint |
| /backend/api/ | Route modules: upload.py, ocr.py, analyze.py, wizard.py, stream.py (SSE endpoint) |
| /backend/agent/ | Agentic core: n0_loop.py (master loop), h2a_queue.py (async dual-buffer), streamgen.py (SSE emitter) |
| /backend/agent/compressor.py | Compressor wU2: context summarization at 92% threshold |
| /backend/agent/todo_manager.py | TodoWrite / Execute / Evaluate planning loop |
| /backend/tools/ | Tool implementations: calculator_tool.py, mistral_ocr_tool.py, legal_rag_tool.py, ask_user_tool.py |
| /backend/tools/registry.py | ToolEngine & Scheduler: tool registration, dispatch, parallel execution, error handling |
| /backend/agents/ | OpenAI Agent definitions: tax_analysis_agent.py (adapted from Legal Expert Agent pattern) |
| /backend/agents/schemas/ | Pydantic output schemas for agent structured responses |
| /backend/services/ | Business logic: anthropic_analyzer.py, openai_assistant.py, scoring_engine.py |
| /backend/models/ | Pydantic schemas: tax_document.py, analysis_result.py, wizard_state.py, sse_events.py |
| /backend/config.py | Environment variable loading via pydantic-settings (all .env groups) |
| /backend/memory/ | Persistent memory: CLAUDE.md (auto-generated, .gitignore’d), logs/ |
| /backend/audit/ | Audit trail storage: session_{id}.jsonl files (append-only, .gitignore’d) |
| /backend/audit/reports/ | Generated audit reports: audit_report_{id}.pdf and .json files |
| /backend/audit/audit_logger.py | AuditLogger class: event schema validation, PII masking, async JSONL writer |
| /backend/audit/report_generator.py | Audit report builder: reads JSONL trail, generates PDF + JSON report |
| /backend/telemetry/ | OpenTelemetry instrumentation: tracer.py (span creation), config.py (OTel setup), attributes.py (custom attribute definitions) |
| /scripts/start-tracing.sh | Convenience script to pull/run Jaeger Docker container with port mappings |
| /backend/knowledge_base/ | User-managed folder for knowledge base documents (contents not version-controlled) |
| /frontend | React + Vite application root |
| /frontend/src/components/ | Wizard steps, upload UI, results display, confidence gauge, SSE event renderer |
| /frontend/src/components/agent/ | Agent-specific UI: thinking panel, tool progress timeline, ask-user modal, TODO sidebar |
| /frontend/src/hooks/ | Custom hooks: useWizard, useUpload, useAnalysis, useSSE (SSE event stream consumer) |
| /frontend/src/services/ | API client functions for all backend endpoints |
| /frontend/src/store/ | State management (Context or Zustand): wizard state, SSE event buffer, agent state |


# 10. OpenAI RAG Agent Reference Architecture

This section defines the reference architecture for the OpenAI Assistants-based RAG agent used for independent tax analysis and validation. The design follows a structured-output, RAG-grounded agent pattern using the OpenAI Agents SDK with FileSearchTool. The architecture below is derived from a production-validated agent pattern (Legal Expert Agent) and adapted for the tax analysis use case.


## 10.1 Agent Design Pattern

The agent follows a strict RAG-grounded pattern: it must base all analysis exclusively on retrieved excerpts from the tax knowledge base (Vector Store), never relying on general model knowledge for factual tax claims. This ensures auditability and reduces hallucination risk in a high-stakes domain.


### 10.1.1 Core Agent Components


| Component | Implementation | Purpose |
| --- | --- | --- |
| Agent Class | agents.Agent | Top-level agent definition with name, instructions (system prompt), model, output schema, model settings, and tools. |
| System Prompt | LEGAL_EXPERT_AGENT_PROMPT pattern | Detailed instructions enforcing RAG grounding, structured output, citation requirements, and safety guardrails. Adapted for tax domain. |
| Output Schema | Pydantic BaseModel | Strongly-typed structured output ensuring consistent JSON responses across all invocations. Enforced via output_type parameter. |
| Model Settings | ModelSettings with Reasoning | Configures reasoning effort (high for complex tax analysis) and enables parallel tool calls for multi-document retrieval. |
| FileSearchTool | agents.FileSearchTool | RAG retrieval tool connected to the TAX_VECTOR_STORE Vector Store. Configured with max_num_results and include_search_results for auditability. |
| Runner | agents.Runner | Async execution engine that manages the agent lifecycle, tool invocations, and structured output parsing. |


## 10.2 Structured Output Schema

The agent returns a Pydantic BaseModel ensuring type safety and consistent structure. The schema captures the five core analysis dimensions plus metadata for auditability:


| Field | Type | Required | Description |
| --- | --- | --- | --- |
| Regulation | str | Required | Exact citation header from retrieved text (e.g., “IRC § XXX” or “26 CFR § 1.XXXX-1”). Must match retrieved source verbatim. |
| Business_Requirement | str | Required | “MUST …” statements extracted from operative “shall/must” language in the regulation. Semicolon-delimited if multiple. |
| Business_Permission | str | Required | “MAY …” statements from permissive language, or “None stated in retrieved sources” if absent. |
| Business_Prohibition | str | Required | “MUST NOT / PROHIBITED …” statements, or “None stated in retrieved sources” if absent. |
| Business_Interpretation | str | Required | Plain-English explanation of practical meaning, including key conditions, thresholds, effective dates, and safe harbors. |
| Source_Evidence | Optional[str] | Recommended | Key supporting excerpts with document identifiers and short quotes for audit trail. |
| Confidence | Optional[str] | Recommended | High / Medium / Low based on completeness of retrieved sources. Feeds into the dual-LLM confidence scoring engine. |


## 10.3 RAG Grounding Rules (Non-Negotiable)

The agent’s system prompt enforces strict RAG grounding rules that must be preserved in all implementations and prompt iterations:


| ID | Rule | Description |
| --- | --- | --- |
| RG-01 | Source Exclusivity | Agent must use ONLY retrieved excerpts (FileSearchTool results) as the factual basis for all analysis. General model knowledge is prohibited for factual tax claims. |
| RG-02 | Insufficient Evidence Handling | If retrieved excerpts do not contain enough information, the agent must explicitly state “Insufficient support in retrieved sources” and attempt additional search terms before responding. |
| RG-03 | Verbatim Citation | Regulation names, headers, and citations must match retrieved text exactly. The agent must never invent citations, section numbers, or numeric thresholds. |
| RG-04 | Multi-Regulation Separation | If multiple regulations apply, produce separate structured outputs per regulation unless the knowledge base explicitly links them. |
| RG-05 | Legal Language Mapping | Operative language is mapped systematically: “shall/must” → Requirement; “may” → Permission; “may not/shall not/prohibited” → Prohibition. |
| RG-06 | Qualifier Preservation | All legal qualifiers must be preserved: thresholds, exceptions, effective dates, definitions, safe harbors, and scope limitations. |
| RG-07 | Ambiguity Surfacing | If retrieved excerpts appear inconsistent or incomplete, the agent must state what is missing in the Business_Interpretation field. |
| RG-08 | Safety Boundary | Agent provides informational support only, never legal advice. Must not recommend evasion or wrongdoing. |


## 10.4 Agent Configuration Parameters

The following parameters control agent behavior and should be tunable via environment variables or configuration:


| Parameter | Default Value | Description |
| --- | --- | --- |
| model | os.getenv("OPENAI_ADVANCE_LLM_MODEL") | LLM model for the agent. Defaults to the advance tier from .env. Can be overridden to very_advance for complex scenarios. |
| reasoning.effort | "high" | Reasoning effort level. Set to “high” for tax analysis to maximize accuracy. Can be reduced to “medium” for simple validation tasks. |
| parallel_tool_calls | True | Enables concurrent FileSearchTool invocations when the agent generates multiple search queries, reducing latency. |
| max_num_results | 20 | Maximum number of Vector Store chunks returned per FileSearchTool invocation. Set high (20) for comprehensive tax analysis. |
| vector_store_ids | [os.getenv("TAX_VECTOR_STORE")] | List of Vector Store IDs. Loaded from .env. Supports multiple stores if knowledge is partitioned. |
| include_search_results | True | Includes raw search results in the agent’s context for transparency and Source_Evidence population. |
| output_type | Pydantic BaseModel class | Enforces structured JSON output matching the defined schema. Rejects malformed responses. |


## 10.5 Agent Invocation Pattern

The agent is invoked asynchronously from the FastAPI backend via the OpenAI Agents SDK Runner. The calling service (openai_assistant.py) constructs the user message with validated tax data, invokes the agent, and parses the structured output. The invocation follows this pattern:

**Step 1 – Construct Prompt: **The FastAPI service assembles the user’s tax data (filing status, income, deductions, document-level details) into a structured prompt string.

**Step 2 – Execute Agent: **Call Runner.run(agent=Tax_Analysis_Agent, input=prompt) asynchronously. The SDK handles thread creation, FileSearchTool invocation (RAG retrieval from TAX_VECTOR_STORE), and response generation.

**Step 3 – Parse Structured Output: **The Runner returns the agent’s response as an instance of the Pydantic output schema. Access fields directly (result.Regulation, result.Confidence, etc.).

**Step 4 – Feed to Scoring Engine: **The parsed output’s Confidence field (High/Medium/Low) is mapped to a numeric score (e.g., High=95, Medium=80, Low=65) and passed to the confidence scoring engine alongside the Anthropic Claude result.


## 10.6 Adaptation from Legal Expert Agent

The reference implementation is adapted from a production Legal Expert Agent pattern. The following table maps the original legal domain concepts to their tax analysis equivalents:


| Concept | Legal Expert Agent (Source) | Tax Analysis Agent (Target) |
| --- | --- | --- |
| Agent Name | Legal_Expert_Agent | Tax_Analysis_Agent |
| Knowledge Base | Tax Codes and Regulations (legal domain) | IRS Publications, IRC excerpts, W-2/1099 instructions (tax filing domain) |
| Vector Store Env Var | LRR_VECTOR_STORE | TAX_VECTOR_STORE |
| Regulation Field | Legal regulation citations | IRC sections, IRS publication references, CFR citations |
| Business_Requirement | Legal compliance requirements | Filing requirements, reporting obligations, payment deadlines |
| Business_Permission | Legal permissions/safe harbors | Elective provisions, filing options, deduction choices |
| Business_Prohibition | Legal prohibitions | Prohibited deductions, ineligible credits, filing restrictions |
| Business_Interpretation | Legal plain-language explanation | Tax plain-language guidance for the filing scenario |
| Model | gpt-5-2025-08-07 | Per .env tier (OPENAI_ADVANCE_LLM_MODEL or OPENAI_VERY_ADVANCE_LLM_MODEL) |


# 11. Wizard Flow Detail

Each wizard step is designed to mirror the TurboTax guided experience, with dynamic adaptation based on data:


| Step | Name | Description | Dependencies |
| --- | --- | --- | --- |
| 1 | Welcome & Filing Status | User selects filing status (Single, MFJ, MFS, HoH, QW). System sets tax bracket parameters. | N/A |
| 2 | Document Upload | Drag-and-drop or file picker for W-2 / 1099 uploads. Displays thumbnails and file type detection. | Accepted file types, size limit |
| 3 | OCR Review | Displays extracted fields in editable form. Low-confidence fields highlighted in amber. User corrects as needed. | OCR output from Step 2 |
| 4 | Income Summary | Aggregated income display across all uploaded documents: wages, interest, dividends, other income. | Corrected OCR data from Step 3 |
| 5 | Deductions & Credits | Dynamic questions based on income types. Standard vs. itemized deduction comparison. Eligible credit suggestions. | Income data from Step 4 |
| 6 | AI Analysis | Triggers dual-LLM analysis. Shows progress spinner with estimated wait time. Both models process concurrently. | All data from Steps 1–5 |
| 7 | Results & Review | Side-by-side LLM comparison, confidence gauges, flag alerts, consensus summary, and downloadable report. | Analysis output from Step 6 |


# 12. Confidence Scoring Framework

The dual-LLM scoring framework is the core differentiator of this tool. It provides transparency and safety in a high-stakes domain.


## 12.1 Scoring Rules


| Condition | Status | Behavior |
| --- | --- | --- |
| Both scores ≥ 90 AND delta ≤ 10 | Green – High Confidence | Display consensus result with combined score. |
| Either score < 90 | Amber – Flagged for Review | Display both results with warning banner. Recommend CPA review. |
| Delta > 10 points | Red – Significant Disagreement | Display both results with prominent alert. Require acknowledgment before proceeding. |
| API failure on one LLM | Yellow – Partial Analysis | Display available result with notice that dual validation was incomplete. |


## 12.2 Score Composition

Each LLM is prompted to self-assess confidence across four dimensions: data completeness (are all required fields present?), regulatory alignment (does the analysis match current tax code?), calculation certainty (are numeric computations deterministic?), and edge case risk (are there unusual situations that reduce reliability?). The weighted average of these four dimensions produces the 0–100 confidence score.


# 13. Risk Assessment


## 13.1 Core System Risks


| ID | Severity | Risk | Mitigation |
| --- | --- | --- | --- |
| R-01 | High | OCR misreads on poor-quality scans | User review step with highlighted low-confidence fields; option to manually override all fields. |
| R-02 | High | LLM hallucination in tax calculations | Dual-LLM cross-validation; RAG grounding via Vector Store; sub-90% flagging. |
| R-03 | Medium | API rate limits or outages (Mistral, Anthropic, OpenAI) | Retry logic with exponential backoff; graceful degradation to single-LLM mode. |
| R-04 | Medium | Knowledge base out of date (e.g., new tax law changes) | User-managed knowledge base; system does not auto-update; user responsible for current content. |
| R-05 | Low | PII exposure in API calls | SSN masking before LLM submission; .env-based key management; no data persistence to disk beyond session. |
| R-06 | Medium | User relies solely on tool for filing without CPA review | Prominent disclaimers; flagging system; results page includes CPA consultation recommendation; audit report attestation block. |


## 13.2 Agentic Architecture Risks

The n0 master loop’s autonomous execution introduces risks specific to agentic systems that do not exist in traditional request–response architectures:


| ID | Severity | Risk | Mitigation |
| --- | --- | --- | --- |
| R-07 | High | Infinite loop: TodoWrite never resolves all items, causing the agent to cycle indefinitely | TODO_MAX_ITERATIONS safety valve (default: 25). After max iterations, loop force-terminates with an error state, logs the incomplete TODO list, and surfaces a user-facing message: “Analysis could not complete within the iteration limit. Please simplify your request or try again.” Agent Execution Timeline in audit trail enables post-mortem analysis. |
| R-08 | High | Context window exhaustion: conversation grows faster than expected, exceeding the window before Compressor wU2 triggers | Compressor triggers at 92% utilization with a dedicated headroom budget (~8%) for the compression prompt itself. If the remaining 8% is insufficient (e.g., a single tool result exceeds the budget), the system force-compresses with a minimal preservation set (TODO list + filing status only) and logs a compression.emergency event. Token count checked before every Phase 2 inference call. |
| R-09 | Medium | Non-blocking Ask User proceeds with wrong assumptions: agent continues work while waiting for user input and makes decisions based on incomplete information | Ask User responses are injected into h2A Buffer B and processed at the next checkpoint. If the user’s response contradicts work already done, the agent re-plans via TodoWrite (marking affected items as “invalidated”). The SSE stream emits ask_user events with a “pending” indicator so the frontend can warn the user that analysis is proceeding with assumptions. Agent’s assumption is logged in the audit trail for transparency. |
| R-10 | Medium | SSE connection drop during long autonomous run: frontend loses real-time visibility of agent progress | SSE endpoint implements automatic reconnection with Last-Event-ID header support. Agent state persisted server-side (wizard state + TODO list); frontend reconnects and receives a state-sync event with current progress. If disconnected for >60 seconds, frontend displays “Reconnecting…” banner. Agent execution continues regardless of frontend connection state. |
| R-11 | Medium | h2A queue race condition: user interjection arrives during a critical phase (e.g., mid-scoring), corrupting the analysis state | Buffer B contents are only merged at defined safe checkpoints (between tool calls, at Phase 5 TodoWrite Check). Interjections are never injected mid-inference or mid-tool-execution. Queue merge operations are atomic. Comprehensive logging of merge events in audit trail. |
| R-12 | Medium | Compressor discards critical state: conversation summary loses important tax data or user corrections during compression | Preserved state is explicitly defined: TODO list, all extracted tax data, user corrections, filing status, confidence scores. A post-compression validation step checks that all required state keys are present in the compressed context. If validation fails, compression is retried with a broader preservation set. CLAUDE.md serves as a backup; all preserved data is written to disk before compression replaces in-memory history. |
| R-13 | Low | Model tier mismatch: agent inadvertently uses low-tier model (Haiku) for complex tax analysis due to misconfiguration | n0 loop hardcodes the advance tier model for primary inference. Low tier is only used by the Compressor. Model ID is logged in every Model Invoke span (OTel) and every analysis audit event. Startup validation checks that all required model IDs in .env are non-empty and follow expected naming patterns. |


## 13.3 Audit & Observability Risks


| ID | Severity | Risk | Mitigation |
| --- | --- | --- | --- |
| R-14 | High | Audit trail corruption or data loss: JSONL file becomes corrupted mid-session, destroying the audit record | Atomic writes using write-to-temp-file + rename pattern. JSONL is append-only (no in-place edits). Session-end integrity check computes SHA-256 hash and stores it in the audit report. Operational logs (Tier 1) serve as a secondary record if JSONL is lost. |
| R-15 | Medium | PII leak in audit trail or OTel traces despite masking rules | PII masking is applied at the AuditLogger and OTel instrumentation layer before write/export—never at the application layer. Masking logic has its own unit test suite covering all PII patterns (SSN, EIN, names, addresses, bank accounts). Regular expressions validated against edge cases (partial SSNs, hyphenated names). Audit trail includes no raw LLM prompts containing PII; only masked summaries or prompt hashes. |
| R-16 | Medium | OTel tracing overhead degrades agent loop performance beyond 2% threshold | Batch span processor with async export (spans buffered and sent in background). Span attribute truncation (prompts >10K chars truncated; tool results >5K truncated). Configurable sampling (OTEL_TRACES_SAMPLER) for future high-volume scenarios. Performance baseline established during digital twin testing with tracing enabled vs. disabled. |
| R-17 | Low | Jaeger container unavailable or crashes, causing trace data loss | OTel exporter uses a buffered queue; if collector is unreachable, spans are retained in memory for a configurable period before being dropped. Console export fallback (OTEL_CONSOLE_EXPORT=true) writes spans to stdout/file as a safety net. Agent execution is never blocked by tracing failures—exporter errors are logged but do not affect the n0 loop. |
| R-18 | Medium | Audit report generation fails for long sessions (large JSONL files) | Report generator streams JSONL events rather than loading entire file into memory. PDF generation uses incremental page construction. Report generation timeout set to 120 seconds; if exceeded, a partial report is generated with a “truncated” warning. |


# 14. Future Roadmap


| Version | Features | Target |
| --- | --- | --- |
| v1.0 (MVP) | W-2 / 1099 support, dual-LLM analysis, step-by-step wizard, local deployment | Current |
| v1.1 | Schedule C and K-1 business income forms; expanded OCR field coverage | Q3 2026 |
| v1.2 | State tax form support (major states: CA, TX, NY, FL); multi-state filing logic | Q4 2026 |
| v2.0 | Multi-user with authentication (OAuth2); session persistence; cloud deployment (AWS ECS) | Q1 2027 |
| v2.1 | E-filing integration via IRS MeF (Modernized e-File); direct submission capability | Q2 2027 |
| v2.5 | Additional LLM providers (Gemini, Llama) for tri-model validation; model A/B testing framework | Q3 2027 |


# 15. Acceptance Criteria


## 15.1 Core Functionality


| ID | Criterion |
| --- | --- |
| AC-01 | User can upload a W-2 PDF and see correctly extracted fields within 15 seconds. |
| AC-02 | User can correct any OCR-extracted field and changes persist through subsequent wizard steps. |
| AC-03 | Dual-LLM analysis completes within 30 seconds and displays side-by-side results. |
| AC-04 | Results with confidence below 90% display a prominent review flag and warning banner. |
| AC-05 | Results with inter-model delta > 10 points display a red disagreement alert requiring acknowledgment. |
| AC-06 | Wizard supports full forward/backward navigation without data loss across all 7 steps. |
| AC-07 | All API keys are loaded from .env and never appear in frontend code, browser network requests, or any log tier. |
| AC-08 | System starts successfully via a single uvicorn command and serves both API and SSE stream. |
| AC-09 | OCR correctly extracts all standard W-2 fields (Boxes 1–6, employer EIN, state info) from a clean PDF scan. |
| AC-10 | OCR correctly extracts fields from 1099-NEC, 1099-INT, 1099-DIV, and 1099-MISC forms. |
| AC-11 | SSN is masked (***-**-XXXX) everywhere: UI, logs, audit trail, OTel traces, and LLM prompts. |
| AC-12 | OpenAI RAG Agent retrieves relevant Vector Store chunks and cites regulation sources in its structured output. |


## 15.2 Agentic Architecture


| ID | Criterion |
| --- | --- |
| AC-13 | n0 master loop autonomously completes a multi-step tax analysis (upload → OCR → analyze → score) without manual intervention for a standard W-2 filing. |
| AC-14 | TodoWrite creates a structured plan for multi-document sessions and TODO state is injected into context after every tool call. |
| AC-15 | Execute → Evaluate loop autonomously re-plans and completes remaining TODO items without pausing for user approval. |
| AC-16 | Agent loop terminates cleanly when TODO_MAX_ITERATIONS (25) is reached, with a user-facing error message and complete audit trail. |
| AC-17 | h2A async dual-buffer accepts a user interjection mid-task (e.g., changing filing status during analysis) and the agent adjusts its plan without restarting. |
| AC-18 | Compressor wU2 triggers at ~92% context utilization, produces a compressed summary, writes to CLAUDE.md, and the agent continues without losing critical tax data. |
| AC-19 | CLAUDE.md persists on disk, is loaded at session start, and survives server restart. |
| AC-20 | Ask User tool sends a non-blocking question via SSE, the agent continues processing other tasks, and the user’s response is incorporated at the next checkpoint. |
| AC-21 | StreamGen delivers typed SSE events (thought, tool_call, tool_result, answer, ask_user, todo_update, compression, error) and the React frontend renders each type correctly. |
| AC-22 | All four registered tools (calculator_tool, legal_rag_agent_tool, mistral_ocr_tool, ask_user_tool) can be invoked by the agent and return structured results. |
| AC-23 | Parallel tool calls execute concurrently via asyncio.gather and total latency approximates max(individual latencies), not sum. |


## 15.3 Audit Trail & Report


| ID | Criterion |
| --- | --- |
| AC-24 | Every tax-relevant action produces an audit trail event in the session’s JSONL file conforming to the 16-field schema (Section 18.2.1). |
| AC-25 | Audit trail is append-only; no events are modified or deleted during or after a session. |
| AC-26 | All 24 audit event types (Section 18.2.2) are emitted at the correct points in the agent lifecycle. |
| AC-27 | User corrections to OCR fields produce ocr.field_corrected events with original_value and corrected_value. |
| AC-28 | The scoring engine’s flag decision produces a scoring.comparison event with both scores, delta, thresholds, and flag_status. |
| AC-29 | PDF audit report generates successfully at session end and contains all 16 sections (Section 18.3.1). |
| AC-30 | JSON audit report generates with schema_version field and identical data to the PDF. |
| AC-31 | Audit report cover page includes the SHA-256 hash of the JSONL audit trail file for integrity verification. |
| AC-32 | All PII in the audit trail and reports is masked per Section 18.2.3 rules; no unmasked SSN, EIN, or full address appears anywhere. |
| AC-33 | “Generate Audit Report” button on the wizard’s Results step (Step 7) produces and downloads the PDF report. |


## 15.4 OpenTelemetry & Tracing


| ID | Criterion |
| --- | --- |
| AC-34 | Each user interaction produces a root Agent Span with aggregated token counts and session.id attribute. |
| AC-35 | Each n0 loop iteration produces a child Cycle Span with a unique cycle_id. |
| AC-36 | Every Anthropic Claude API call produces a Model Invoke Span with input_tokens, output_tokens, and model_id. |
| AC-37 | Every tool execution produces a Tool Span with tool name, call ID, status, and latency. |
| AC-38 | Spans are exported to the Jaeger collector and visible in the Jaeger UI at http://localhost:16686. |
| AC-39 | Traces can be searched by session.id, filing_status, and flag_status in the Jaeger UI. |
| AC-40 | OTel trace_id is included in the audit report’s Session Summary section with a clickable Jaeger URL. |
| AC-41 | Tracing overhead does not increase agent loop latency by more than 2% (verified via digital twin benchmark). |
| AC-42 | PII masking is applied to all OTel span attributes containing user tax data. |


# 16. Digital Twin Testing Framework

Given the system’s reliance on three external APIs (Mistral OCR 3, Anthropic Claude, OpenAI Assistants) that are non-deterministic, rate-limited, and costly per call, a comprehensive digital twin is essential for continuous validation. The digital twin is not merely a set of mocks—it is a fully simulated tax universe with synthetic taxpayers, known-correct tax outcomes, and controllable failure modes, enabling end-to-end testing against ground truth at zero API cost.


## 16.1 Layer 1: Synthetic Tax Data Generator

The foundation of the digital twin is a Python module that generates synthetic taxpayer profiles with mathematically verifiable tax outcomes. A TaxpayerFactory class produces realistic data across archetypes: single filer with one W-2, freelancer with multiple 1099-NECs, mixed income (W-2 + 1099-INT + 1099-DIV), and edge cases such as exceeding the Social Security wage base or AMT triggers. Each profile carries a deterministic ground truth tax computation—correct federal liability, applicable deductions, and eligible credits—calculated independently of any LLM, serving as the test oracle.

A companion DocumentRenderer takes synthetic data and generates realistic PDF and JPEG images of W-2 and 1099 forms using reportlab or a template system. The renderer produces documents at varying quality levels—clean scan, slightly skewed, low-DPI, and faded ink—to stress-test OCR accuracy across realistic conditions.


| Profile ID | Archetype | Characteristics | Tests |
| --- | --- | --- | --- |
| PROF-01 | Single W-2 Filer | One employer, standard deduction, no credits | Baseline happy path |
| PROF-02 | Multi-1099 Freelancer | Three 1099-NEC forms, estimated tax payments, Schedule SE | Multi-document aggregation |
| PROF-03 | Mixed Income | W-2 + 1099-INT + 1099-DIV, qualified dividends | Cross-form income types |
| PROF-04 | High Earner Edge Case | Wages exceeding SS wage base ($168,600), additional Medicare tax | Boundary computation |
| PROF-05 | Low-Quality Document | Same as PROF-01 but rendered at 72 DPI with skew and noise | OCR resilience |
| PROF-06 | Itemized Deductions | Mortgage interest, SALT, charitable contributions exceed standard deduction | Deduction comparison logic |


## 16.2 Layer 2: API Simulation Layer (Mock Services)

Each external API is replaced with a controllable twin running as a local FastAPI service on a dedicated port. All mock services share a common TwinConfig object that can be swapped per test scenario, enabling precise control over system behavior.


### 16.2.1 Mistral OCR Twin

A FastAPI service that accepts document uploads and returns structured JSON matching Mistral OCR 3’s response schema. It operates in configurable modes: “perfect” mode returns exact ground truth fields from the synthetic profile; “realistic” mode introduces controlled OCR errors such as digit transposition, misread characters, and low-confidence field metadata; “degraded” mode simulates partial extraction failures where some fields return null; and “failure” mode returns HTTP 500 or connection timeouts for resilience testing.


### 16.2.2 Anthropic Claude Twin

A mock that accepts the same prompt format the anthropic_analyzer.py service sends and returns structured analysis responses. Configurable response profiles include: “accurate_high_confidence” which returns correct analysis with scores of 92–98; “accurate_low_confidence” which returns correct analysis but with scores of 75–88 to test flagging logic; “hallucinated” which returns plausible but incorrect deductions to test cross-validation detection; “slow” which adds 15–25 second delays to test timeout handling; and “partial_failure” which drops the connection mid-stream.


### 16.2.3 OpenAI Assistants Twin

Mimics the full Assistants API contract including thread creation, message submission, and run polling. The twin also simulates RAG retrieval by returning pre-configured Vector Store chunks, enabling testing of whether the system correctly surfaces and incorporates retrieved context. Supports the same mode profiles as the Claude twin, plus a “no_retrieval” mode that returns empty RAG context to test degraded knowledge base scenarios.


| Mode | Applicable To | Behavior | Tests |
| --- | --- | --- | --- |
| perfect | All Services | Returns exact ground truth data | Baseline validation, wizard flow testing |
| realistic | OCR Twin | Controlled errors: digit transposition, misreads, low-confidence fields | OCR review step, field correction UX |
| accurate_high_confidence | LLM Twins | Correct analysis, scores 92–98 | Happy path, consensus display |
| accurate_low_confidence | LLM Twins | Correct analysis, scores 75–88 | Flag triggering, warning banner display |
| hallucinated | LLM Twins | Plausible but incorrect deductions/credits | Cross-validation, delta detection |
| slow | LLM Twins | 15–25 second response delay | Timeout handling, progress UX |
| failure | All Services | HTTP 500, connection timeout, mid-stream drop | Retry logic, graceful degradation |
| no_retrieval | OpenAI Twin | Empty RAG context returned | Knowledge base dependency testing |


## 16.3 Layer 3: Scenario Orchestrator & Evaluation Harness

The orchestrator ties the twin layers together into a comprehensive test runner. Test scenarios are defined declaratively in YAML files, each specifying: the taxpayer profile ID, OCR twin mode, Claude twin mode, OpenAI twin mode, expected wizard behavior, and expected final outcome (flag status, correct liability within a dollar tolerance). The orchestrator hits the real FastAPI endpoints, walks through the wizard programmatically via API calls (or via Playwright for full UI testing), and captures the complete output.

After each run, the evaluation harness compares the system’s tax liability estimate against the deterministic ground truth, validates that flagging behavior matches expectations (flag precision and recall), checks wizard step visibility logic, and produces a scorecard with accuracy rates, latency percentiles, and a regression diff against the previous run.


### 16.3.1 Critical Test Scenarios


| ID | Scenario | Configuration | Expected Outcome | Validates |
| --- | --- | --- | --- | --- |
| TS-01 | Happy Path | PROF-01, all perfect modes | Correct liability, no flags, scores ≥ 90 | Baseline |
| TS-02 | OCR Misread Cascade | PROF-01, OCR realistic (Box 1 wages off by $10K) | LLM layer detects implausibility; flags raised | Reasonableness check |
| TS-03 | Boundary Score: Both at 90 | PROF-03, both LLMs at exactly 90, delta = 0 | No flag (score equals threshold) | Boundary condition |
| TS-04 | Boundary Score: One at 89 | PROF-03, Claude at 89, OpenAI at 95 | Flag raised (sub-90 on one model) | Threshold trigger |
| TS-05 | High Delta Disagreement | PROF-02, Claude at 95, OpenAI at 82 | Red disagreement alert (delta = 13 > 10) | Delta detection |
| TS-06 | LLM Hallucination Detection | PROF-06, Claude hallucinated, OpenAI accurate | Delta triggers flag; side-by-side shows discrepancy | Cross-validation value |
| TS-07 | Single LLM Failure | PROF-01, Claude failure mode, OpenAI perfect | Partial analysis warning; single result displayed | Graceful degradation |
| TS-08 | Both LLMs Fail | PROF-01, both failure mode | Error state; user prompted to retry | Full failure resilience |
| TS-09 | Empty Knowledge Base | PROF-03, OpenAI no_retrieval mode | OpenAI score drops; flag likely raised | RAG dependency |
| TS-10 | Wizard State Integrity | PROF-01, perfect modes; navigate fwd to Step 5, back to Step 3, correct field, fwd again | Step 4 income summary updates; Step 6 uses corrected data | State persistence |
| TS-11 | Low-Quality Document | PROF-05, OCR realistic mode | Multiple low-confidence fields highlighted; user corrects | OCR resilience + UX |
| TS-12 | Concurrent Latency | PROF-01, Claude slow (20s), OpenAI perfect (2s) | Both results appear after slower model completes; progress UX accurate | Async orchestration |


## 16.4 Evaluation Metrics & Scorecard


| Metric | Definition | Target |
| --- | --- | --- |
| Tax Liability Accuracy | Absolute dollar difference between system estimate and ground truth | ≤ $50 for standard returns |
| Flag Precision | Percentage of raised flags that were justified (true positives / all flags) | ≥ 95% |
| Flag Recall | Percentage of scenarios requiring flags that were correctly flagged | 100% (zero missed flags) |
| OCR Field Accuracy | Percentage of fields correctly extracted vs. ground truth | ≥ 95% in perfect mode; ≥ 80% in realistic mode |
| End-to-End Latency (P95) | 95th percentile total time from upload to results (mock APIs) | ≤ 5 seconds (excluding intentional slow modes) |
| Wizard State Integrity | Percentage of navigation scenarios with correct data propagation | 100% |
| Graceful Degradation Rate | Percentage of failure scenarios handled without crash or data loss | 100% |


## 16.5 Infrastructure & Execution

The digital twin lives in a /tests/digital_twin/ directory within the project. Mock services are self-contained FastAPI apps, orchestrated via a docker-compose.twin.yml (or simple shell script for local-only runs) that spins up mock APIs on dedicated ports alongside the real system. The test harness uses pytest with async support (pytest-asyncio) and generates HTML reports via pytest-html. A CI-friendly entry point allows the full suite to run before every commit, ensuring regressions are caught immediately—all at zero API cost.


| Path | Purpose |
| --- | --- |
| /tests/digital_twin/ | Digital twin root directory |
| /tests/digital_twin/factories/ | TaxpayerFactory, DocumentRenderer, ground truth calculator |
| /tests/digital_twin/mocks/ | Mock FastAPI services: mistral_mock.py, claude_mock.py, openai_mock.py |
| /tests/digital_twin/mocks/twin_config.py | Shared TwinConfig for mode selection per scenario |
| /tests/digital_twin/scenarios/ | YAML scenario definitions (one file per scenario or grouped) |
| /tests/digital_twin/orchestrator.py | Scenario runner: loads YAML, configures twins, executes, evaluates |
| /tests/digital_twin/evaluation.py | Scorecard generator: accuracy, precision, recall, latency metrics |
| /tests/digital_twin/fixtures/ | Pre-rendered synthetic documents (PDF/JPEG) for deterministic runs |
| /tests/digital_twin/conftest.py | Pytest fixtures for mock service startup/teardown |
| docker-compose.twin.yml | Orchestrates mock services + real system for isolated test runs |


# 17. Comprehensive Test Plan

This section defines a thorough test plan organized by use case area. Each test case specifies an ID, description, preconditions, test steps, expected results, and pass/fail criteria. Tests are designed to validate all functional requirements (Section 5), non-functional requirements (Section 6), and integration behaviors. Where applicable, tests reference the digital twin infrastructure (Section 15) for mock service configurations.


## 17.1 Test Plan Overview


| Use Case Area | ID Range | Test Count | Requirements Covered |
| --- | --- | --- | --- |
| UC-1: Document Upload & Management | TC-1xx | 14 | FR-101 through FR-105 |
| UC-2: OCR Processing | TC-2xx | 16 | FR-201 through FR-206 |
| UC-3: Knowledge Base & RAG | TC-3xx | 12 | FR-301 through FR-305 |
| UC-4: Dual-LLM Tax Analysis | TC-4xx | 18 | FR-401 through FR-408 |
| UC-5: Step-by-Step Wizard UI | TC-5xx | 16 | FR-501 through FR-506 |
| UC-6: Confidence Scoring Engine | TC-6xx | 14 | FR-405, FR-406, Section 11 |
| UC-7: Non-Functional Requirements | TC-7xx | 12 | NFR-01 through NFR-07 |
| UC-8: End-to-End Integration | TC-8xx | 10 | Cross-cutting |
| UC-9: Agentic Architecture (n0 / h2A / wU2) | TC-9xx | 16 | Section 4.4 |
| UC-10: Audit Trail & Report | TC-10xx | 14 | Section 18 (FR-1801–FR-1834) |
| UC-11: OpenTelemetry Tracing & Dashboard | TC-11xx | 12 | Section 19 (FR-1901–FR-1915) |
| Total |  | 154 |  |


## 17.2 UC-1: Document Upload & Management


| ID | Test Case | Preconditions | Steps | Expected Result | Priority |
| --- | --- | --- | --- | --- | --- |
| TC-101 | Single PDF Upload via File Picker | Application running; wizard at Step 2 | 1. Click file picker button. 2. Select a single W-2 PDF (< 5MB). 3. Observe upload progress. 4. Verify file thumbnail appears. | File uploads successfully. Progress bar reaches 100%. Thumbnail displays. Backend returns file ID and metadata with HTTP 200. | Must |
| TC-102 | Single JPEG Upload via Drag-and-Drop | Application running; wizard at Step 2 | 1. Drag a W-2 JPEG file onto the upload zone. 2. Observe visual drop indicator. 3. Verify upload completes. | Drop zone highlights on dragover. File uploads successfully. Thumbnail displays correct image preview. | Must |
| TC-103 | Single PNG Upload | Application running; wizard at Step 2 | 1. Upload a 1099 PNG file via either method. 2. Verify acceptance and thumbnail. | PNG file accepted. Thumbnail renders correctly. File metadata returned. | Must |
| TC-104 | Upload File at Maximum Size (20MB) | Application running; 20MB PDF prepared | 1. Upload a 20MB PDF. 2. Monitor progress. 3. Verify completion. | File uploads successfully despite large size. Progress bar updates smoothly. No timeout. | Must |
| TC-105 | Reject File Exceeding 20MB | Application running; 25MB PDF prepared | 1. Attempt to upload a 25MB PDF. 2. Observe error handling. | Upload is rejected before or immediately after transmission. User-friendly error message displayed: “File exceeds 20MB limit.” | Must |
| TC-106 | Reject Unsupported File Type | Application running; .docx and .xlsx files prepared | 1. Attempt to upload a .docx file. 2. Attempt to upload a .xlsx file. | Both uploads rejected. Error message: “Unsupported file type. Please upload PDF, JPEG, or PNG.” File picker filters to accepted types. | Must |
| TC-107 | Multiple File Upload | Application running; two W-2 PDFs and one 1099 JPEG prepared | 1. Select all three files via file picker. 2. Verify all upload simultaneously or sequentially. 3. Verify all thumbnails appear. | All three files upload successfully. Individual progress bars or combined progress shown. Three thumbnails with correct file names displayed. | Must |
| TC-108 | Remove Uploaded Document Before Processing | Application running; one file already uploaded at Step 2 | 1. Click remove/delete button on uploaded file thumbnail. 2. Confirm removal if prompted. 3. Verify file is removed from list. | File removed from upload list. Thumbnail disappears. Backend confirms deletion. File ID invalidated. | Should |
| TC-109 | Replace Uploaded Document | Application running; one W-2 uploaded | 1. Upload a different W-2 to replace. 2. Verify old file removed and new file displayed. | Previous file replaced. Only new file thumbnail shown. New file ID returned. | Should |
| TC-110 | Auto-Detect W-2 Document Type | Application running; W-2 PDF uploaded and OCR completed | 1. Upload a W-2 PDF. 2. Trigger OCR. 3. Check document type label in UI. | System labels document as “W-2” based on OCR output structure. Correct icon or badge displayed. | Should |
| TC-111 | Auto-Detect 1099-NEC Document Type | Application running; 1099-NEC uploaded and OCR completed | 1. Upload a 1099-NEC. 2. Trigger OCR. 3. Check document type label. | System labels document as “1099-NEC.” Correct form fields displayed in review step. | Should |
| TC-112 | Upload with Network Interruption | Application running; large file upload in progress | 1. Begin uploading a 15MB PDF. 2. Simulate network drop mid-upload (disconnect Wi-Fi or throttle). 3. Observe error handling. | Upload fails gracefully. Error message displayed: “Upload failed. Please try again.” No partial files left in corrupted state. Retry button available. | Must |
| TC-113 | Empty File Upload | Application running; 0-byte PDF prepared | 1. Upload a 0-byte PDF file. | File rejected with error: “File is empty. Please upload a valid document.” | Must |
| TC-114 | Corrupted File Upload | Application running; corrupted PDF (random bytes with .pdf extension) | 1. Upload a corrupted PDF. 2. System may accept upload but should handle at OCR stage. | Upload accepted (file type check passes). OCR step returns clear error: “Unable to process document. File may be corrupted.” | Must |


## 17.3 UC-2: OCR Processing (Mistral OCR 3)


| ID | Test Case | Preconditions | Steps | Expected Result | Priority |
| --- | --- | --- | --- | --- | --- |
| TC-201 | W-2 Field Extraction – Clean Scan | W-2 PDF uploaded (PROF-01 from digital twin, perfect quality) | 1. Trigger OCR on uploaded W-2. 2. Compare each extracted field against ground truth. | All standard W-2 fields extracted: Employee SSN (masked), Employer EIN, Box 1 Wages, Box 2 Federal Tax, Box 3 SS Wages, Box 5 Medicare Wages, State info. All match ground truth. | Must |
| TC-202 | 1099-NEC Field Extraction | 1099-NEC PDF uploaded (synthetic, perfect quality) | 1. Trigger OCR. 2. Verify payer TIN, recipient TIN, Box 1 nonemployee compensation extracted. | All 1099-NEC fields correctly extracted and structured in JSON response. | Must |
| TC-203 | 1099-INT Field Extraction | 1099-INT PDF uploaded (synthetic, perfect quality) | 1. Trigger OCR. 2. Verify Box 1 interest income, Box 3 savings bond interest, payer info. | All 1099-INT fields correctly extracted. | Must |
| TC-204 | 1099-DIV Field Extraction | 1099-DIV PDF uploaded (synthetic, perfect quality) | 1. Trigger OCR. 2. Verify Box 1a ordinary dividends, Box 1b qualified dividends, Box 2a capital gains. | All 1099-DIV fields correctly extracted. | Must |
| TC-205 | 1099-MISC Field Extraction | 1099-MISC PDF uploaded (synthetic, perfect quality) | 1. Trigger OCR. 2. Verify Box 3 other income, Box 10 crop insurance, payer/recipient info. | All 1099-MISC fields correctly extracted. | Must |
| TC-206 | OCR on Low-Quality Scan (72 DPI, Skewed) | Low-quality W-2 image uploaded (PROF-05 from digital twin) | 1. Trigger OCR. 2. Check which fields extracted. 3. Check confidence metadata per field. | Most fields extracted. Low-confidence fields include confidence scores below threshold in Mistral metadata. Some fields may be null or incorrect. | Should |
| TC-207 | Low-Confidence Field Highlighting | OCR completed with at least two low-confidence fields | 1. Navigate to OCR Review step (Step 3). 2. Inspect field styling. | Low-confidence fields highlighted in amber/yellow. Tooltip or icon indicates confidence issue. User can click to manually edit. | Should |
| TC-208 | User Correction of OCR Fields | OCR Review step displayed with extracted fields | 1. Identify an incorrectly extracted field (e.g., wages off by a digit). 2. Click field, type correct value. 3. Save/proceed. | Field becomes editable. Corrected value persists. Changed field visually marked as “user-corrected.” Corrected data flows to subsequent steps. | Must |
| TC-209 | Multi-Page W-2 Processing | Multi-page W-2 PDF uploaded (e.g., Copy A + Copy B on separate pages) | 1. Upload multi-page PDF. 2. Trigger OCR. | System processes all pages. Extracts fields from the correct copy. Does not duplicate data from redundant copies. | Should |
| TC-210 | Batch Processing Multiple Forms | Three files uploaded: one W-2, one 1099-NEC, one 1099-INT | 1. Trigger OCR on all three. 2. Verify each returns correct field structure. | All three processed independently. Each returns form-specific JSON structure. Results distinguished by file ID and form type. | Should |
| TC-211 | SSN Masking in OCR Output | W-2 with SSN extracted via OCR | 1. Complete OCR. 2. Inspect JSON response and UI display for SSN field. | SSN displayed as ***-**-XXXX (last 4 only) in UI. Full SSN never exposed in frontend network requests. Backend logs show masked value. | Must |
| TC-212 | OCR API Timeout Handling | Mistral OCR twin in “slow” mode (30s+ response time) | 1. Upload document. 2. Trigger OCR. 3. Wait for timeout threshold. | System displays timeout error after configured threshold. User prompted to retry. No zombie processes or hung state. | Must |
| TC-213 | OCR API 500 Error with Retry | Mistral OCR twin in “failure” mode (first 2 calls return 500, third succeeds) | 1. Trigger OCR. 2. Observe retry behavior. | System retries up to 3 times with exponential backoff. On third attempt (success), results displayed normally. User sees “Processing...” during retries. | Must |
| TC-214 | OCR API Permanent Failure | Mistral OCR twin in “failure” mode (all calls return 500) | 1. Trigger OCR. 2. Wait through all retry attempts. | After 3 failed retries, user-friendly error: “Document processing failed. Please try again later.” Option to retry or upload a different file. | Must |
| TC-215 | OCR Response Schema Validation | Any uploaded document | 1. Trigger OCR. 2. Inspect backend Pydantic model validation. | Response validated against expected schema (TaxDocumentOCR Pydantic model). Any unexpected fields ignored. Missing required fields flagged for user input. | Must |
| TC-216 | OCR on JPEG Input Format | W-2 uploaded as JPEG (not PDF) | 1. Upload JPEG W-2. 2. Trigger OCR. 3. Compare accuracy to PDF version. | JPEG processed successfully. Fields extracted comparably to PDF. No format-specific errors. | Must |


## 17.4 UC-3: Knowledge Base & RAG (OpenAI Assistants)


| ID | Test Case | Preconditions | Steps | Expected Result | Priority |
| --- | --- | --- | --- | --- | --- |
| TC-301 | Vector Store ID Loaded from .env | .env file contains valid OPENAI_VECTOR_STORE_ID | 1. Start FastAPI server. 2. Check startup logs for Vector Store configuration. | Server starts successfully. Logs confirm Vector Store ID loaded. No error about missing configuration. | Must |
| TC-302 | Missing Vector Store ID in .env | .env file has OPENAI_VECTOR_STORE_ID commented out or missing | 1. Start FastAPI server. 2. Observe startup behavior. | Server starts with warning: “Vector Store ID not configured. RAG retrieval will be unavailable.” Analysis endpoint returns partial results (Anthropic only). | Must |
| TC-303 | Invalid Vector Store ID | .env contains an invalid/nonexistent Vector Store ID | 1. Start server. 2. Trigger analysis that invokes OpenAI Assistant. | OpenAI API returns error. System logs the error. Falls back to single-LLM (Anthropic) mode with warning to user. | Must |
| TC-304 | Successful RAG Retrieval | Valid Vector Store with IRS Pub 17 content; PROF-01 tax data submitted | 1. Submit tax data for analysis. 2. Monitor OpenAI Assistant thread. 3. Verify file_search tool invoked. | Assistant retrieves relevant chunks from Vector Store. Response references specific tax code provisions. Retrieval logged with chunk IDs. | Must |
| TC-305 | RAG Context Included in Analysis Prompt | Valid Vector Store configured; analysis triggered | 1. Trigger dual-LLM analysis. 2. Inspect prompt sent to OpenAI Assistant (via logging). | Prompt includes user tax data combined with instruction to use file_search. Retrieved context appears in thread messages before final response. | Must |
| TC-306 | Empty Vector Store (No Documents) | Valid Vector Store ID pointing to an empty store | 1. Trigger analysis. | OpenAI Assistant attempts retrieval but gets no results. Analysis completes but confidence score is lower. Log entry: “No relevant documents retrieved from Vector Store.” | Should |
| TC-307 | Knowledge Base Folder Is User-Managed | Project deployed with /backend/knowledge_base/ directory | 1. Verify directory exists but is empty. 2. Add a PDF to the directory. 3. Verify system does not auto-ingest. | System never reads from /backend/knowledge_base/ directly for RAG. Directory exists for user convenience only. Vector Store is managed independently via OpenAI platform. | Must |
| TC-308 | Retrieval Chunk Auditability | Valid Vector Store; analysis triggered | 1. Trigger analysis. 2. Check backend logs or audit endpoint. | Log entries include: Vector Store ID, retrieved chunk IDs, chunk text snippets (truncated), and relevance scores. | Should |
| TC-309 | OpenAI Assistant ID Loaded from .env | .env file contains valid OPENAI_ASSISTANT_ID | 1. Start server. 2. Trigger analysis. | Assistant ID used in thread creation. No “Assistant not found” errors. | Must |
| TC-310 | Missing OpenAI API Key | .env file has OPENAI_API_KEY removed | 1. Start server. 2. Trigger analysis. | Server warns at startup about missing key. Analysis degrades to Anthropic-only mode. User notified: “OpenAI analysis unavailable.” | Must |
| TC-311 | OpenAI Rate Limit Handling | OpenAI twin configured to return 429 rate limit response | 1. Trigger analysis. 2. Observe retry behavior. | System retries with exponential backoff respecting Retry-After header. If retries exhausted, falls back to single-LLM mode with user warning. | Should |
| TC-312 | Thread Isolation Between Sessions | Two separate analysis sessions | 1. Run analysis for PROF-01. 2. Run analysis for PROF-02 in a new session. | Each session creates a new OpenAI thread. No data leakage between sessions. Thread IDs are distinct. | Must |


## 17.5 UC-4: Dual-LLM Tax Analysis


| ID | Test Case | Preconditions | Steps | Expected Result | Priority |
| --- | --- | --- | --- | --- | --- |
| TC-401 | Successful Parallel Execution (Both LLMs) | Valid API keys for both Anthropic and OpenAI; validated tax data from wizard | 1. Submit tax data via /api/analyze. 2. Monitor server logs for concurrent execution. 3. Verify both responses returned. | Both API calls execute via asyncio.gather. Total latency is approximately max(Claude_time, OpenAI_time), not sum. Both results returned in single response. | Must |
| TC-402 | Anthropic Claude – Correct Tax Liability | PROF-01 synthetic data (ground truth liability known); Claude twin in accurate_high_confidence mode | 1. Submit PROF-01 data. 2. Compare Claude’s estimated liability against ground truth. | Claude’s estimate within $50 of ground truth. Correct filing status applied. Standard deduction correctly identified. | Must |
| TC-403 | OpenAI Assistant – Correct Tax Liability with RAG | PROF-01 data; OpenAI twin in accurate_high_confidence mode with populated Vector Store | 1. Submit PROF-01 data. 2. Compare OpenAI’s estimate against ground truth. | OpenAI’s estimate within $50 of ground truth. Response references relevant Vector Store content. | Must |
| TC-404 | Both LLMs Return Confidence Scores | Any valid tax data submitted | 1. Submit data. 2. Inspect response JSON. | Response includes claude_confidence (0–100) and openai_confidence (0–100) as integer or float fields. | Must |
| TC-405 | Side-by-Side Comparison Display | Analysis completed with both results | 1. Navigate to Results step (Step 7). 2. Verify layout. | Two-column layout showing: Claude’s analysis (left) and OpenAI’s analysis (right). Each column shows: liability estimate, deductions, credits, advisory notes, and confidence score. | Should |
| TC-406 | Consensus Result When Both Agree | Both LLMs return scores ≥ 90 with delta ≤ 10; liability estimates within $100 | 1. Submit data. 2. Check results display. | A “Consensus” section displayed prominently showing the averaged/reconciled result with a combined confidence score. Green status indicator. | Should |
| TC-407 | Applicable Deductions Identified | PROF-06 (itemized deductions exceed standard) | 1. Submit PROF-06 data. 2. Check both LLM outputs for deduction recommendations. | Both LLMs identify that itemized deductions exceed standard. Mortgage interest, SALT, and charitable contributions listed. Recommendation to itemize. | Must |
| TC-408 | Eligible Credits Identified | Synthetic profile with qualifying child (eligible for Child Tax Credit) | 1. Submit data with dependent info. 2. Check credit identification. | Both LLMs identify Child Tax Credit eligibility. Correct credit amount calculated based on income phase-out. | Must |
| TC-409 | Advisory Notes Generated | Any valid tax data | 1. Submit data. 2. Check advisory notes section. | Both LLMs produce human-readable advisory notes: estimated refund/owed, key assumptions, and recommendations (e.g., “Consider contributing to a traditional IRA to reduce taxable income”). | Must |
| TC-410 | Anthropic API Failure – Graceful Degradation | Claude twin in failure mode; OpenAI twin in perfect mode | 1. Submit data. 2. Observe response. | System returns OpenAI results only. Warning banner: “Partial analysis – Anthropic Claude unavailable. Results based on single model.” Yellow status indicator. No crash. | Must |
| TC-411 | OpenAI API Failure – Graceful Degradation | OpenAI twin in failure mode; Claude twin in perfect mode | 1. Submit data. 2. Observe response. | System returns Claude results only. Warning banner about partial analysis. Single-column display. | Must |
| TC-412 | Both APIs Fail | Both twins in failure mode | 1. Submit data. 2. Observe response. | Error state displayed: “Analysis could not be completed. Both AI services are currently unavailable.” Retry button. No partial or misleading data shown. | Must |
| TC-413 | Retry Logic – Exponential Backoff | Claude twin: first call fails (500), second succeeds | 1. Submit data. 2. Monitor logs for retry timing. | First attempt fails. Retry after ~1s. Second attempt succeeds. Total delay visible but reasonable. User sees “Analyzing...” throughout. | Must |
| TC-414 | Prompt Includes All Validated Tax Data | OCR completed with user corrections applied | 1. Complete wizard through Step 5. 2. Trigger analysis. 3. Inspect prompts in server logs. | Prompts to both LLMs include: filing status, all income sources (wages, interest, dividends), user-corrected OCR fields, and deduction elections. | Must |
| TC-415 | Hallucination Cross-Detection | Claude twin: hallucinated mode (invents fake deduction); OpenAI twin: accurate | 1. Submit PROF-01 data. 2. Compare outputs. | Claude produces a deduction not present in OpenAI’s output. High delta between results. Red flag raised. User can see discrepancy in side-by-side view. | Must |
| TC-416 | Handling Large Multi-Form Tax Data | PROF-03 (W-2 + 1099-INT + 1099-DIV); all data validated | 1. Submit full multi-form data. 2. Verify both LLMs handle aggregate income. | Both LLMs correctly sum income across forms. Total AGI matches sum of individual sources. No double-counting. | Must |
| TC-417 | Latency Under 30 Seconds (Parallel) | Both twins in accurate_high_confidence mode (normal response time) | 1. Submit data. 2. Measure total elapsed time. | Total time from request to response ≤ 30 seconds. Parallel execution confirmed in logs (overlapping timestamps). | Must |
| TC-418 | Analysis Response Schema Validation | Any analysis response | 1. Submit data. 2. Validate response against AnalysisResult Pydantic model. | Response JSON conforms to schema: estimated_liability, deductions[], credits[], advisory_notes[], confidence_score, model_id, timestamp. | Must |


## 17.6 UC-5: Step-by-Step Wizard UI


| ID | Test Case | Preconditions | Steps | Expected Result | Priority |
| --- | --- | --- | --- | --- | --- |
| TC-501 | Wizard Initializes at Step 1 (Welcome / Filing Status) | Application loaded at root URL | 1. Open application. 2. Verify initial wizard state. | Wizard displays Step 1: Welcome with filing status selection (Single, MFJ, MFS, HoH, QW). Progress indicator shows Step 1 of 7. Forward button enabled; back button disabled or hidden. | Must |
| TC-502 | Filing Status Selection | Wizard at Step 1 | 1. Select “Married Filing Jointly.” 2. Click Next. | Filing status saved to wizard state. Progress advances to Step 2. Back button on Step 2 returns to Step 1 with MFJ still selected. | Must |
| TC-503 | Forward Navigation – Steps 1 Through 7 | Wizard at Step 1; PROF-01 data; all twins in perfect mode | 1. Complete Step 1 (filing status). 2. Upload document at Step 2. 3. Review OCR at Step 3. 4. Confirm income at Step 4. 5. Review deductions at Step 5. 6. Trigger analysis at Step 6. 7. View results at Step 7. | Each step loads correctly. Progress indicator advances. Data from previous steps visible in subsequent steps. No errors or blank screens. | Must |
| TC-504 | Backward Navigation with State Persistence | Wizard at Step 5; data entered in Steps 1–4 | 1. Click Back from Step 5 to Step 4. 2. Verify income summary unchanged. 3. Click Back to Step 3. 4. Verify OCR fields unchanged. 5. Navigate forward again to Step 5. | All data persists across backward and forward navigation. No fields cleared or reset. State intact. | Must |
| TC-505 | Progress Indicator Accuracy | Wizard at any step | 1. Navigate through steps 1–7. 2. At each step, verify progress indicator. | Progress indicator correctly shows: current step number, step name, total steps (7), and visual progress bar or stepper. Completed steps visually distinct from upcoming steps. | Must |
| TC-506 | Dynamic Step Visibility – Single W-2 | PROF-01 (single W-2 only) | 1. Upload only a W-2. 2. Navigate to Step 4. 3. Check income summary. | Income summary shows only wage income. No sections for interest, dividends, or other 1099 income. Deductions step tailored to W-2 scenario. | Must |
| TC-507 | Dynamic Step Visibility – Mixed Income | PROF-03 (W-2 + 1099-INT + 1099-DIV) | 1. Upload all three documents. 2. Navigate to Step 4. | Income summary shows all three income types: wages, interest, dividends. Deductions step includes investment-related questions. | Must |
| TC-508 | Dynamic Question Adaptation at Step 5 | PROF-06 (itemized deduction candidate) | 1. Reach Step 5 with income data suggesting itemization. 2. Check questions displayed. | System asks about mortgage interest, SALT, charitable contributions, medical expenses. Shows standard vs. itemized comparison dynamically. | Must |
| TC-509 | Contextual Help Tooltips | Wizard at any step with form fields | 1. Hover over or click the help icon on any field (e.g., “Federal Tax Withheld”). | Tooltip appears with plain-language explanation: “This is the amount your employer sent to the IRS on your behalf (Box 2 of your W-2).” | Should |
| TC-510 | Wizard State Survives Browser Refresh | Wizard at Step 4 with data entered in Steps 1–3 | 1. Press F5 / refresh browser. 2. Verify wizard state. | Wizard reloads at Step 4 (or last active step). All entered data preserved. Upload references intact. No data loss. | Should |
| TC-511 | Cannot Skip Steps (Validation) | Wizard at Step 1; no filing status selected | 1. Attempt to click Next without selecting filing status. 2. Attempt to navigate directly to Step 5 via URL. | Step 1: Next button disabled or shows validation error: “Please select a filing status.” Direct URL navigation redirected to current valid step. | Must |
| TC-512 | Step 6 – Analysis Progress UI | Wizard at Step 6; analysis triggered | 1. Click “Run Analysis” at Step 6. 2. Observe progress display. | Spinner/progress animation displayed. Estimated wait time shown. Status updates: “Sending to Claude...” “Sending to OpenAI...” “Comparing results...” Next enabled only after completion. | Must |
| TC-513 | Step 7 – Results Display Complete | Analysis completed; both LLMs returned results | 1. Arrive at Step 7. 2. Verify all result components rendered. | Results page includes: estimated liability/refund, side-by-side LLM comparison, confidence gauges, flag status (green/amber/red), advisory notes, and a “Download Report” button. | Must |
| TC-514 | Wizard State After Correction and Re-analysis | Wizard at Step 7; user wants to correct data | 1. Navigate back to Step 3. 2. Correct an OCR field. 3. Navigate forward to Step 6. 4. Re-trigger analysis. | Step 4 income summary updates with corrected data. Step 6 re-runs analysis with corrected inputs. Step 7 shows new results. Old results cleared. | Must |
| TC-515 | Responsive Layout – Desktop | Browser window at 1440px width | 1. Navigate through all wizard steps. 2. Check layout at each step. | All elements properly aligned. Tables and forms fit within viewport. No horizontal scroll. Side-by-side comparison renders correctly. | Must |
| TC-516 | Keyboard Navigation (Accessibility) | Wizard at any step | 1. Tab through all form fields. 2. Use Enter to activate buttons. 3. Use arrow keys for radio/select inputs. | All interactive elements reachable via keyboard. Focus indicators visible. Tab order logical. Screen reader announces step names and field labels. | Should |


## 17.7 UC-6: Confidence Scoring Engine


| ID | Test Case | Preconditions | Steps | Expected Result | Priority |
| --- | --- | --- | --- | --- | --- |
| TC-601 | Green Status: Both Scores ≥ 90, Delta ≤ 10 | Claude score: 95, OpenAI score: 93 (delta = 2) | 1. Submit analysis. 2. Check scoring engine output. 3. Verify UI status. | Status: Green – High Confidence. Consensus result displayed. No warning banners. Confidence gauges show green. | Must |
| TC-602 | Amber Status: One Score Below 90 | Claude score: 88, OpenAI score: 94 (delta = 6) | 1. Submit analysis. 2. Check scoring engine output. | Status: Amber – Flagged for Review. Warning banner: “One model reported lower confidence. CPA review recommended.” Both results displayed. | Must |
| TC-603 | Amber Status: Both Scores Below 90 | Claude score: 82, OpenAI score: 85 (delta = 3) | 1. Submit analysis. 2. Check output. | Status: Amber. Warning banner present. Both results shown with emphasis on low confidence. | Must |
| TC-604 | Red Status: Delta Exceeds 10 Points | Claude score: 95, OpenAI score: 82 (delta = 13) | 1. Submit analysis. 2. Check output. | Status: Red – Significant Disagreement. Prominent alert: “Models significantly disagree. Do not rely on these results without professional review.” Acknowledgment required before proceeding. | Must |
| TC-605 | Boundary: Both at Exactly 90 | Claude score: 90, OpenAI score: 90 (delta = 0) | 1. Submit analysis. 2. Check threshold logic. | Status: Green (scores are ≥ 90, delta ≤ 10). No flags raised. Boundary condition handled correctly (inclusive). | Must |
| TC-606 | Boundary: Score at 89 | Claude score: 89, OpenAI score: 92 | 1. Submit analysis. 2. Check threshold logic. | Status: Amber (89 < 90 threshold). Flag raised. One-point below boundary correctly triggers. | Must |
| TC-607 | Boundary: Delta at Exactly 10 | Claude score: 95, OpenAI score: 85 (delta = 10) | 1. Submit analysis. | Status: Amber (85 < 90), and delta = 10 which is at threshold (not exceeding). Flag due to sub-90 score but not due to delta. | Must |
| TC-608 | Boundary: Delta at 11 | Claude score: 96, OpenAI score: 85 (delta = 11) | 1. Submit analysis. | Status: Red (delta 11 > 10 AND OpenAI below 90). Both conditions trigger. Red takes precedence over amber. | Must |
| TC-609 | Yellow Status: Partial Analysis (One LLM Failed) | Claude: failure mode; OpenAI: accurate at 94 | 1. Submit analysis. 2. Observe partial result handling. | Status: Yellow – Partial Analysis. Single result displayed. Warning: “Dual validation incomplete. One AI service was unavailable.” No confidence comparison possible; single score shown. | Must |
| TC-610 | Score Composition – Four Dimensions Prompted | Any analysis submission; inspect LLM prompts in logs | 1. Trigger analysis. 2. Read prompts sent to both LLMs. | Prompts instruct each LLM to self-assess across: data completeness, regulatory alignment, calculation certainty, and edge case risk. Weighted average produces final 0–100 score. | Must |
| TC-611 | Confidence Gauge Visual Display | Analysis completed with scores 95 and 87 | 1. Navigate to Step 7 results. 2. Inspect confidence gauges. | Two visual gauges (e.g., circular progress or bar). Claude: 95 (green). OpenAI: 87 (amber). Numeric values displayed alongside visual. | Should |
| TC-612 | Acknowledgment Required for Red Status | Red flag scenario (delta > 10) | 1. Arrive at Step 7 with red flag. 2. Attempt to download report or proceed. | Download/proceed disabled until user clicks “I understand these results require professional review” checkbox or button. | Must |
| TC-613 | Flag History in Session | Multiple analyses run in same session (corrections and re-runs) | 1. Run analysis (green). 2. Go back, corrupt data, re-run (red). 3. Go back, fix data, re-run (green). | Each re-run produces fresh scores. Previous flag status cleared. Current status always reflects latest analysis. | Must |
| TC-614 | Configurable Thresholds via .env | .env with CONFIDENCE_THRESHOLD=85 and DELTA_THRESHOLD=15 | 1. Start server with custom thresholds. 2. Submit data with scores 86 and 88. | With threshold at 85: both scores ≥ 85, delta = 2 ≤ 15 → Green. Default (90) would have flagged. Confirms .env override works. | Should |


## 17.8 UC-7: Non-Functional Requirements


| ID | Test Case | Preconditions | Steps | Expected Result | Req |
| --- | --- | --- | --- | --- | --- |
| TC-701 | OCR Latency ≤ 15 Seconds | Single W-2 PDF; Mistral API (real or twin in perfect mode) | 1. Upload W-2. 2. Trigger OCR. 3. Measure time from request to response. | OCR completes in ≤ 15 seconds. Measured at backend (excludes network to frontend). | NFR-01 |
| TC-702 | Dual-LLM Latency ≤ 30 Seconds | Valid tax data; both APIs or twins in normal mode | 1. Trigger analysis. 2. Measure total elapsed time. | Both results returned in ≤ 30 seconds (parallel execution). | NFR-01 |
| TC-703 | API Keys Not Exposed to Frontend | Application running; browser DevTools open | 1. Open Network tab. 2. Navigate through full wizard. 3. Search all requests/responses for API key patterns. | No API keys appear in any request headers, query params, response bodies, or JavaScript bundles. All API calls proxied through FastAPI backend. | NFR-02 |
| TC-704 | SSN Masked in UI and Logs | W-2 processed with SSN field | 1. Check OCR Review step for SSN display. 2. Check server logs. 3. Check network requests from frontend. | UI shows ***-**-XXXX. Logs show masked value. Network requests to LLM APIs contain masked SSN. | NFR-02 |
| TC-705 | .env File Not Served by Frontend | Application running | 1. Attempt to access /.env, /backend/.env via browser URL. 2. Attempt path traversal. | All attempts return 404 or are blocked. .env never served as a static asset. | NFR-02 |
| TC-706 | Retry Logic – 3 Attempts, Exponential Backoff | Any API twin configured to fail twice, succeed on third | 1. Trigger the relevant API call. 2. Monitor logs for retry timing. | Attempt 1: immediate. Attempt 2: ~1s delay. Attempt 3: ~2–4s delay. Successful on third. Total time reasonable. | NFR-03 |
| TC-707 | User-Friendly Error Messages | Various failure scenarios (API down, invalid file, timeout) | 1. Trigger each failure. 2. Check UI error message. | All errors display clear, non-technical messages. No stack traces, HTTP codes, or JSON visible to user. Each error includes actionable next step. | NFR-03 |
| TC-708 | Keyboard Accessibility (WCAG 2.1 AA) | All wizard steps | 1. Navigate entire wizard using only keyboard. 2. Verify focus indicators. 3. Test with screen reader. | All interactive elements reachable. Focus visible at all times. Logical tab order. Screen reader announces all labels, errors, and state changes. | NFR-04 |
| TC-709 | Color Contrast Compliance | All UI screens | 1. Run automated contrast checker (e.g., axe-core). 2. Verify text/background contrast ratios. | All text meets WCAG 2.1 AA minimum: 4.5:1 for normal text, 3:1 for large text. Flag colors distinguishable to color-blind users. | NFR-04 |
| TC-710 | No Data Persisted to Disk | Complete a full wizard session; check file system | 1. Run full wizard from upload through results. 2. Inspect /tmp, project directory, and system temp files. | No tax data, OCR results, or analysis outputs written to disk. All data held in memory. Uploaded files in temp memory only during processing. | NFR-06 |
| TC-711 | Data Cleared After Session | Complete analysis; start new session | 1. Complete full wizard. 2. Refresh browser / restart session. 3. Check for residual data. | New session starts fresh. No data from previous session accessible. In-memory stores cleared. | NFR-06 |
| TC-712 | Extensibility – Add New Form Type | Developer adds Schedule C OCR model and fields | 1. Add new Pydantic model. 2. Add new OCR service method. 3. Add wizard step. 4. Test. | New form integrates without modifying existing OCR, analysis, or wizard infrastructure. Existing tests still pass. | NFR-07 |


## 17.9 UC-8: End-to-End Integration Tests

End-to-end integration tests validate the complete user journey from document upload through final results, exercising all system layers simultaneously. These tests are designed to run against either the digital twin mock services or real APIs (for smoke testing).


| ID | Test Case | Preconditions | Steps | Expected Result | Priority |
| --- | --- | --- | --- | --- | --- |
| TC-801 | E2E Happy Path – Single W-2 | PROF-01 synthetic W-2; all twins in perfect mode | 1. Launch app. 2. Select “Single” filing status. 3. Upload W-2 PDF. 4. Verify OCR fields correct. 5. Confirm income. 6. Accept standard deduction. 7. Run analysis. 8. Verify results. | Full wizard completes without errors. Tax liability within $50 of ground truth. Green confidence status. Total E2E time < 60 seconds. | Must |
| TC-802 | E2E Happy Path – Mixed Income (3 Forms) | PROF-03 (W-2 + 1099-INT + 1099-DIV); all twins in perfect mode | 1. Select “Married Filing Jointly.” 2. Upload all 3 documents. 3. Review OCR for each. 4. Confirm aggregated income. 5. Run analysis. 6. Verify results. | All three forms processed. Income correctly aggregated. Tax liability within $50 of ground truth for MFJ with mixed income. Green status. | Must |
| TC-803 | E2E with OCR Corrections | PROF-01; OCR twin in realistic mode (digit transposition on wages) | 1. Upload W-2. 2. OCR returns incorrect wages. 3. User corrects at Step 3. 4. Complete wizard. | User correction propagates. Income summary reflects corrected amount. LLM analysis uses corrected data. Final liability correct. | Must |
| TC-804 | E2E with Flagged Results | PROF-02; Claude twin: accurate_low_confidence (score 82); OpenAI: accurate_high_confidence (score 95) | 1. Complete wizard through analysis. 2. Check Step 7 results. | Amber flag displayed. Warning banner present. Both results shown. CPA review recommended. User can still view all data. | Must |
| TC-805 | E2E with Red Disagreement | PROF-06; Claude twin: hallucinated; OpenAI twin: accurate | 1. Complete wizard. 2. Check results. | Red disagreement flag. Side-by-side shows different deduction recommendations. Acknowledgment required. Delta > 10 highlighted. | Must |
| TC-806 | E2E with Single LLM Failure | PROF-01; Claude twin: failure; OpenAI twin: perfect | 1. Complete wizard. 2. Observe analysis step and results. | Analysis step shows partial completion. Results display single-model output. Yellow partial analysis warning. No crash or hang. | Must |
| TC-807 | E2E Full Wizard Navigation Stress | PROF-01; all twins perfect | 1. Complete Steps 1–5. 2. Go back to Step 1, change filing status. 3. Go forward to Step 3, edit OCR. 4. Jump to Step 5, change deduction. 5. Run analysis. | All changes propagate correctly. No stale data. Analysis reflects final state of all inputs including mid-wizard changes. | Must |
| TC-808 | E2E via API Only (Headless) | PROF-01; all twins perfect; using pytest + httpx | 1. POST /api/wizard/state (filing status). 2. POST /api/upload. 3. POST /api/ocr/{id}. 4. PUT /api/ocr/{id}/fields. 5. POST /api/analyze. 6. GET /api/analyze/{session}/results. | All API endpoints return correct HTTP status codes and valid JSON. Final results match expected ground truth. No UI required. | Must |
| TC-809 | E2E via Playwright (Full UI) | PROF-01; all twins perfect; Playwright test suite | 1. Playwright opens browser. 2. Automates full wizard flow including file upload. 3. Asserts on UI elements at each step. 4. Screenshots captured. | All UI elements render correctly. Wizard navigation works via button clicks. File upload via Playwright file chooser. Screenshots match baselines. | Should |
| TC-810 | E2E Performance Benchmark | PROF-01; all twins perfect; 10 sequential runs | 1. Run TC-801 ten times sequentially. 2. Record timing for each phase: upload, OCR, wizard nav, analysis, total. | P50 total < 45s. P95 total < 60s. No memory leaks (process RSS stable). No increasing latency across runs. | Should |


## 17.10 UC-9: Agentic Architecture (n0 / h2A / wU2)


| ID | Test Case | Preconditions | Steps | Expected Result | Priority |
| --- | --- | --- | --- | --- | --- |
| TC-901 | n0 Loop – Single Tool Call Cycle | Agent receives a simple query requiring one tool (calculator_tool) | 1. Send user message requiring a tax calculation. 2. Monitor n0 loop phases. | Agent produces one Cycle Span. Claude calls calculator_tool. Tool result feeds back. Claude produces final text answer. Loop terminates after 1 cycle. | Must |
| TC-902 | n0 Loop – Multi-Cycle with TodoWrite | Agent receives a complex query: process 2 documents + analyze + score | 1. Submit multi-document session. 2. Monitor TODO creation and cycle count. | TodoWrite creates plan with 4+ items. Multiple cycles execute. TODO state injected after each tool call (visible in logs). All items reach “completed”. Loop terminates. | Must |
| TC-903 | n0 Loop – Max Iterations Safety Valve | TODO_MAX_ITERATIONS=5; agent given a task requiring 10+ cycles | 1. Set low iteration limit. 2. Submit complex task. 3. Observe termination. | Loop terminates after 5 iterations. Error state surfaced: “Analysis could not complete within iteration limit.” Incomplete TODO logged. Audit trail contains all 5 cycles. | Must |
| TC-904 | n0 Loop – Clean Termination (No Tool Calls) | Agent receives a simple text question (no tools needed) | 1. Send “What filing status should I choose?” 2. Observe loop behavior. | Claude responds with text only (no tool_use blocks). Loop exits after 1 cycle. No tool spans created. | Must |
| TC-905 | h2A – Mid-Task User Interjection | Agent processing a 3-document session; user injects new instruction mid-analysis | 1. Start multi-doc analysis. 2. After first OCR completes, inject “Actually change filing status to Head of Household.” 3. Observe agent behavior. | h2A Buffer B receives interjection. At next safe checkpoint, interjection merged into context. Agent re-plans (TodoWrite updates). Subsequent analysis uses new filing status. Audit trail logs the interjection event. | Must |
| TC-906 | h2A – Interjection During Tool Execution (Safe Checkpoint) | Agent executing mistral_ocr_tool; user sends message simultaneously | 1. Trigger OCR. 2. Send user message during OCR API call. 3. Monitor merge timing. | Interjection queued in Buffer B. NOT merged during OCR execution. Merged only after tool_result received and before next inference. No corruption of OCR results. | Must |
| TC-907 | StreamGen – All 8 SSE Event Types Delivered | Full session exercising all agent behaviors | 1. Run a session that triggers: thought, tool_call, tool_result, answer, ask_user, todo_update, compression (force low threshold), error (mock one failure). 2. Capture SSE stream. | All 8 event types received by frontend. Each event has correct type field. Frontend renders each type appropriately (verified via Playwright or manual). | Must |
| TC-908 | StreamGen – SSE Reconnection After Disconnect | SSE connection drops mid-session | 1. Start analysis. 2. Simulate SSE disconnect (close browser tab, reopen). 3. Verify reconnection. | Frontend reconnects with Last-Event-ID. State-sync event received with current progress. No duplicate events. Agent execution was not affected by disconnect. | Should |
| TC-909 | Compressor wU2 – Triggers at 92% Threshold | Session with progressively increasing context (many tool calls with verbose results) | 1. Set COMPRESSION_THRESHOLD=92. 2. Run session until context approaches limit. 3. Monitor compression event. | Compressor triggers when context hits ~92%. Compression SSE event emitted. CLAUDE.md updated. Post-compression context significantly smaller. Agent continues without losing TODO state or tax data. | Must |
| TC-910 | Compressor wU2 – Preserved State Validation | Session compressed after OCR + user corrections + partial analysis | 1. Complete OCR with corrections. 2. Trigger compression (lower threshold for testing). 3. Inspect post-compression context. | Post-compression context contains: TODO list, all extracted tax data, user corrections, filing status, confidence scores. Verbose intermediate reasoning discarded. CLAUDE.md contains all preserved data. | Must |
| TC-911 | CLAUDE.md – Persistence Across Restart | Session with CLAUDE.md written; server restarted | 1. Run session until compression writes CLAUDE.md. 2. Stop server. 3. Restart server. 4. Start new session. | CLAUDE.md file exists on disk at /backend/memory/CLAUDE.md. New session loads CLAUDE.md into system prompt. Agent has context from previous session. | Must |
| TC-912 | CLAUDE.md – Blank State (First Run) | No CLAUDE.md file exists (fresh install) | 1. Delete CLAUDE.md if exists. 2. Start server. 3. Start session. | Agent starts with blank memory context. No errors. CLAUDE.md created on first compression or session end. | Must |
| TC-913 | Ask User – Non-Blocking Behavior | Agent needs clarification but has other TODO items pending | 1. Submit ambiguous data. 2. Agent invokes ask_user_tool. 3. Do NOT respond immediately. 4. Monitor agent behavior. | ask_user SSE event emitted with question. Agent continues executing other pending TODO items (e.g., processing remaining documents). User’s eventual response incorporated at next checkpoint. | Must |
| TC-914 | Ask User – Response Incorporation | Agent asked a question; user responds | 1. Agent asks “Did you contribute to a Roth IRA?” 2. User responds “Yes, $6,500.” 3. Monitor agent behavior. | Response enters h2A Buffer B. At next checkpoint, merged into context. Agent incorporates Roth IRA contribution into analysis. audit.agent.user_response event logged. | Must |
| TC-915 | Parallel Tool Calls | Agent needs to OCR two documents simultaneously | 1. Upload two documents. 2. Agent invokes mistral_ocr_tool for both in parallel. | asyncio.gather executes both tool calls concurrently. Total latency ≈ max(ocr1, ocr2), not sum. Both tool_result events received. Logs show overlapping timestamps. | Should |
| TC-916 | Tool Failure – Retry and Recovery | mistral_ocr_tool fails twice then succeeds (mock) | 1. Configure OCR mock: fail 2x, succeed 3rd. 2. Agent invokes OCR. | ToolEngine retries with exponential backoff. Third attempt succeeds. Tool span shows retry_count=2. Agent continues normally. Audit trail logs all 3 attempts. | Must |


## 17.11 UC-10: Audit Trail & Audit Report


| ID | Test Case | Preconditions | Steps | Expected Result | Priority |
| --- | --- | --- | --- | --- | --- |
| TC-1001 | Audit Trail Created on Session Start | Application running; no prior session | 1. Start a new session. 2. Check /backend/audit/ directory. | New file created: session_{uuid}.jsonl. First event: session.start with session_id, timestamp, config hash. | Must |
| TC-1002 | All 24 Event Types Emitted | Full session: upload, OCR, corrections, wizard nav, analysis, scoring, results | 1. Complete a full wizard flow. 2. Parse the JSONL file. 3. Count distinct event_type values. | All applicable event types present. At minimum: session.start, document.uploaded, ocr.request, ocr.response, wizard.step_entered, wizard.data_submitted, agent.inference, agent.tool_call, agent.tool_result, analysis.claude_request, analysis.claude_response, analysis.openai_request, analysis.openai_response, scoring.comparison, session.end. | Must |
| TC-1003 | Audit Event Schema Validation | Any session with audit events | 1. Parse JSONL file. 2. Validate each event against Pydantic schema (Section 18.2.1). | Every event has all 16 required fields. No malformed events. event_id is unique UUID4. timestamp is valid ISO 8601. status is a valid enum value. | Must |
| TC-1004 | Append-Only Integrity | Session in progress | 1. Write 10 audit events. 2. Inspect file. 3. Write 10 more. 4. Verify first 10 unchanged. | File only grows. Earlier lines byte-identical after new events appended. No in-place modifications. | Must |
| TC-1005 | OCR Correction Audit | OCR completed with errors; user corrects 2 fields | 1. Correct wages field and SSN field. 2. Check audit trail. | Two ocr.field_corrected events. Each contains: field_name, original_value (masked if PII), corrected_value (masked if PII), original_confidence. | Must |
| TC-1006 | Scoring Decision Audit | Dual-LLM analysis completed with amber flag | 1. Complete analysis. 2. Find scoring.comparison event in trail. | Event contains: claude_score, openai_score, delta, threshold_used (90), delta_threshold_used (10), flag_status (“amber”), flag_reason. | Must |
| TC-1007 | PII Masking in Audit Trail | Session with W-2 containing SSN, EIN, full name, address | 1. Complete session. 2. grep JSONL for raw SSN pattern (\d{3}-\d{2}-\d{4}). 3. grep for full street address. | Zero matches for unmasked SSN. SSN appears only as ***-**-XXXX. EIN masked. Full name as initial + last. Street address stripped (city/state/ZIP only). | Must |
| TC-1008 | PDF Audit Report Generation | Complete session with results | 1. Click “Generate Audit Report” on Step 7. 2. Download PDF. | PDF generates within 30 seconds. Contains all 16 sections (Section 18.3.1). Cover page has session ID, timestamp, SHA-256 hash of JSONL. Table of contents with hyperlinks. | Must |
| TC-1009 | JSON Audit Report Generation | Same session as TC-1008 | 1. Request JSON report via /api/audit/report/{session_id}/json. | JSON file generated. Contains schema_version field. Data matches PDF content. All sections represented as structured objects. | Must |
| TC-1010 | Report SHA-256 Integrity Hash | PDF report generated | 1. Extract SHA-256 hash from PDF cover page. 2. Compute SHA-256 of the JSONL file independently. 3. Compare. | Hashes match exactly. Proves JSONL was not tampered with after report generation. | Must |
| TC-1011 | Audit API Endpoint – Trail Retrieval | Session completed with JSONL file | 1. GET /api/audit/trail/{session_id}. 2. Verify response. | Returns application/jsonl stream. Content matches the file on disk byte-for-byte. 404 for nonexistent session_id. | Should |
| TC-1012 | Report Generation for Long Session | Session with 500+ audit events (simulated via digital twin) | 1. Run extended digital twin scenario producing many events. 2. Generate report. | Report generates within 120 seconds. No out-of-memory errors. Agent Execution Timeline section contains all events. PDF renders correctly. | Should |
| TC-1013 | Async Audit Writing Performance | Agent loop executing rapidly (multiple tool calls per second) | 1. Run high-throughput scenario. 2. Measure agent loop latency with audit writing enabled vs. disabled. | Audit writing adds <1% latency overhead. JSONL writes are non-blocking (async). No events dropped. | Must |
| TC-1014 | Session End Event on Graceful Close | User completes wizard and closes session | 1. Navigate through full wizard. 2. Close session (navigate away or explicit close). 3. Check last JSONL event. | Last event is session.end with: total_duration, total_events count, final_status (“completed”). | Must |


## 17.12 UC-11: OpenTelemetry Tracing & Dashboard


| ID | Test Case | Preconditions | Steps | Expected Result | Priority |
| --- | --- | --- | --- | --- | --- |
| TC-1101 | Root Agent Span Created Per Interaction | OTel tracing enabled; Jaeger running | 1. Send a user message. 2. Query Jaeger for traces with service=tax-assistant-n0. | One root span with gen_ai.agent.name, gen_ai.user.message, session.id, aggregated token counts. Span duration matches session time. | Must |
| TC-1102 | Cycle Spans Nested Under Agent Span | Session requiring 3 agent cycles | 1. Run multi-cycle session. 2. Open trace in Jaeger waterfall view. | 3 child Cycle Spans under the root Agent Span. Each has unique event_loop.cycle_id. Spans are sequential (non-overlapping). | Must |
| TC-1103 | Model Invoke Spans with Token Counts | Any Anthropic Claude API call | 1. Trigger analysis. 2. Find Model Invoke span in Jaeger. | Span contains: gen_ai.request.model (e.g., claude-opus-4-6), gen_ai.usage.input_tokens, output_tokens, total_tokens, cache_read_input_tokens. Latency matches API call duration. | Must |
| TC-1104 | Tool Spans with Status and Latency | Agent invokes calculator_tool and mistral_ocr_tool | 1. Run session using both tools. 2. Find Tool spans in Jaeger. | Two Tool spans with gen_ai.tool.name, gen_ai.tool.call.id, tool.status=success, gen_ai.event.start_time/end_time. Latency reflects actual tool execution time. | Must |
| TC-1105 | Sub-Tool Spans for External API Calls | legal_rag_agent_tool invokes OpenAI Assistants API | 1. Trigger RAG analysis. 2. Find nested spans under the legal_rag_agent_tool span. | Child span for OpenAI API call with service name, endpoint, HTTP status, latency. Hierarchical nesting visible in Jaeger waterfall. | Should |
| TC-1106 | Custom Tax Attributes Searchable | Session with filing_status=MFJ and flag_status=amber | 1. Complete session. 2. Search Jaeger: tag filing_status=MFJ. 3. Search: tag flag_status=amber. | Both searches return the correct trace. Custom attributes visible in span detail panel. | Must |
| TC-1107 | PII Masking in Span Attributes | Session processing W-2 with SSN | 1. Complete session. 2. Search all span attributes in Jaeger for raw SSN pattern. | No unmasked SSN in any span attribute. gen_ai.user.message contains masked data only. Tool input_summary contains masked data. | Must |
| TC-1108 | Trace-to-Audit Correlation | Session completed with both OTel trace and JSONL audit trail | 1. Get trace_id from Jaeger. 2. Search JSONL for same trace_id in metadata. 3. Get session_id from JSONL, search Jaeger. | Bidirectional: trace_id found in audit events’ metadata; session.id on OTel spans matches JSONL session_id. Both point to same session. | Must |
| TC-1109 | Tracing Overhead < 2% | Digital twin: 10 identical sessions with tracing enabled, 10 with tracing disabled | 1. Run 10 sessions with OTEL_EXPORTER_OTLP_ENDPOINT set. 2. Run 10 sessions with tracing disabled. 3. Compare P50 latencies. | Tracing-enabled P50 is within 2% of tracing-disabled P50. Batch span processor confirmed async. | Must |
| TC-1110 | Jaeger Dashboard Accessible | Docker running; Jaeger container started via scripts/start-tracing.sh | 1. Run start-tracing.sh. 2. Open http://localhost:16686. | Jaeger UI loads. Service “tax-assistant-n0” appears in service dropdown. Traces searchable. | Must |
| TC-1111 | Console Export Fallback | OTEL_CONSOLE_EXPORT=true; no Jaeger container running | 1. Set env var. 2. Run session without Jaeger. 3. Check console/stdout. | Span data printed to console in JSON format. No errors about unreachable collector. Agent execution unaffected. | Should |
| TC-1112 | Collector Unavailable – Graceful Degradation | OTEL endpoint configured but Jaeger not running | 1. Set OTEL_EXPORTER_OTLP_ENDPOINT to unreachable host. 2. Run session. | Agent executes normally. Spans buffered then dropped silently after timeout. Warning in operational logs: “OTel collector unreachable.” No user-facing impact. | Must |


## 17.13 Test Execution Strategy

Tests are organized into three execution tiers to balance coverage with speed and cost:


| Tier | Tooling | Frequency | Scope | Target Duration | Gate Criteria |
| --- | --- | --- | --- | --- | --- |
| Tier 1: Unit & Component | pytest + React Testing Library | Every commit | All TC-xxx tests via mocks at function level; Pydantic schema validation; scoring engine logic; audit event schema validation; PII masking unit tests; individual React component rendering. | < 3 minutes | 100% before merge |
| Tier 2: Integration (Digital Twin) | pytest-asyncio + Digital Twin services | Every PR / nightly | All TC-xxx tests via digital twin mock APIs; full API endpoint testing (TC-808); wizard state transitions; OCR→Analysis pipeline; n0 loop lifecycle (TC-901–916); audit trail completeness (TC-1001–1014); OTel span hierarchy (TC-1101–1112). | < 15 minutes | 100% before release |
| Tier 3: E2E + Smoke (Real APIs) | Playwright + real API keys + Jaeger | Weekly / pre-release | TC-801 through TC-810 against real APIs; visual regression; performance benchmarks; audit report generation with real data; Jaeger dashboard verification. | < 30 minutes | All “Must” pass |


## 17.14 Defect Classification


| Severity | Definition | Response |
| --- | --- | --- |
| P0 – Critical | Tax liability calculation error > $500; data loss; PII exposure; system crash | Immediate hotfix; blocks release |
| P1 – High | Flag logic incorrect (missed flag or false flag); API failure not handled gracefully; wizard data loss on navigation | Fix within 24 hours; blocks release |
| P2 – Medium | UI rendering issues; help tooltips missing; minor latency above threshold; non-critical accessibility gaps | Fix within 1 week; does not block release |
| P3 – Low | Cosmetic issues; typos in advisory text; minor UX improvements | Backlog; fix in next sprint |


# 18. Logging, Audit Trail & Audit Report

Tax preparation is a high-stakes, regulated domain where every computational decision must be traceable, reproducible, and defensible. This section specifies the comprehensive logging infrastructure, structured audit trail, and final audit report file that enables full reconstruction of any tax analysis session for IRS audit defense, CPA review, or internal quality assurance.


## 18.1 Logging Architecture

The system implements a three-tier logging architecture: operational logs for debugging and monitoring, a structured audit trail for regulatory traceability, and a final audit report file for external review.


| Tier | Implementation | Log Level | Output Location | Contents |
| --- | --- | --- | --- | --- |
| Tier 1: Operational Logs | Python logging (structlog) | DEBUG/INFO/WARN/ERROR | Console + rotating file (backend/logs/app.log) | Server performance, API call latency, error stack traces, system health. Standard development and ops debugging. NOT included in audit output. |
| Tier 2: Audit Trail | Custom AuditLogger class | AUDIT level (always written) | Append-only JSON Lines file (backend/audit/session_{id}.jsonl) | Every tax-relevant action: document uploads, OCR extractions, LLM prompts/responses, tool calls, user corrections, confidence scores, flag decisions. Immutable within session. |
| Tier 3: Audit Report | Generated at session close | N/A (structured output) | PDF + JSON (backend/audit/reports/audit_report_{id}.pdf/.json) | Human-readable and machine-readable final report summarizing the complete tax analysis session. Designed for CPA review, IRS audit defense, and record retention. |


## 18.2 Audit Trail Specification (Tier 2)

The audit trail is the foundational data source for all audit purposes. Every tax-relevant event is captured as a structured JSON object appended to the session’s JSONL file. The trail is append-only and must never be modified after write.


### 18.2.1 Audit Event Schema


| Field | Type | Required | Description |
| --- | --- | --- | --- |
| event_id | str (UUID4) | Required | Globally unique event identifier |
| session_id | str (UUID4) | Required | Links all events in a single tax preparation session |
| timestamp | str (ISO 8601 with timezone) | Required | Exact time of event (e.g., 2026-02-28T14:30:00.123Z) |
| event_type | str (enum) | Required | Categorized event type (see Event Type Catalog below) |
| component | str | Required | System component that generated the event (n0, h2A, ToolEngine, Compressor, etc.) |
| action | str | Required | Specific action taken (e.g., “tool_call”, “ocr_field_extracted”, “user_correction”) |
| input_data | dict \| null | Conditional | Input to the action. For LLM calls: the prompt (or prompt hash if too large). For tool calls: parameters. Sensitive fields (SSN) are masked. |
| output_data | dict \| null | Conditional | Output of the action. For LLM calls: full response. For OCR: extracted fields. For scoring: both scores + flag decision. |
| input_tokens | int \| null | Conditional | Token count for LLM calls (input). Enables cost tracking and context window monitoring. |
| output_tokens | int \| null | Conditional | Token count for LLM calls (output). |
| model_id | str \| null | Conditional | Model identifier used (e.g., claude-opus-4-6, gpt-5.2-2025-12-11). Present for all LLM events. |
| latency_ms | int \| null | Conditional | Wall-clock time in milliseconds for the action to complete. |
| status | str (enum) | Required | success \| failure \| timeout \| retrying \| user_pending |
| error_detail | str \| null | Conditional | Error message and code if status is failure or timeout. |
| parent_event_id | str \| null | Conditional | Links to parent event for nested actions (e.g., a tool_call spawned by a specific n0 inference cycle). |
| metadata | dict \| null | Optional | Freeform metadata: file IDs, form types, TODO state, compression stats, etc. |


### 18.2.2 Audit Event Type Catalog


| Event Type | Category | Description & Included Data |
| --- | --- | --- |
| session.start | Session | New tax preparation session initialized. Includes: session_id, timestamp, CLAUDE.md loaded (yes/no), .env config hash. |
| session.end | Session | Session completed or terminated. Includes: total duration, total events, final status (completed/abandoned/error). |
| document.uploaded | Document | Tax document uploaded by user. Includes: file_id, filename, file_type (PDF/JPEG/PNG), file_size_bytes, SHA-256 hash (for integrity verification). |
| document.deleted | Document | User removed an uploaded document. Includes: file_id, reason. |
| ocr.request | OCR | OCR processing requested via Mistral OCR 3. Includes: file_id, form_type_hint (if auto-detected). |
| ocr.response | OCR | OCR results received. Includes: file_id, detected_form_type, field_count, per-field confidence scores, raw extracted fields (SSN masked), latency_ms. |
| ocr.field_corrected | OCR | User manually corrected an OCR-extracted field. Includes: file_id, field_name, original_value, corrected_value, original_confidence. Critical for audit: proves human review of OCR output. |
| wizard.step_entered | Wizard | User navigated to a wizard step. Includes: step_number, step_name, direction (forward/backward). |
| wizard.data_submitted | Wizard | User submitted data at a wizard step. Includes: step_number, field_values (SSN masked), filing_status, deduction_election. |
| agent.inference | Agent (n0) | Claude inference cycle. Includes: cycle_number, input_tokens, output_tokens, model_id, has_tool_calls (bool), latency_ms, prompt_hash. |
| agent.tool_call | Agent (n0) | Tool invocation by Claude. Includes: tool_id, tool_name, input_parameters (sensitive data masked), parent inference cycle event_id. |
| agent.tool_result | Agent (n0) | Tool returned result. Includes: tool_id, status, output_data (structured), latency_ms, parent tool_call event_id. |
| agent.todo_update | Agent (n0) | TODO list updated. Includes: todo_items (full list with statuses), items_completed, items_remaining, items_failed. |
| agent.ask_user | Agent (n0) | Agent queued a question for user. Includes: question_text, context_reason, blocking (always false). |
| agent.user_response | Agent (n0) | User responded to ask_user. Includes: question_event_id, response_text, response_latency_ms. |
| agent.compression | Agent (wU2) | Context compression triggered. Includes: pre_compression_tokens, post_compression_tokens, compression_ratio, preserved_state_keys, claude_md_updated (bool). |
| analysis.claude_request | Analysis | Tax data sent to Anthropic Claude for analysis. Includes: model_id, input_tokens, prompt_hash, tax_data_summary (AGI, filing_status, form_count). |
| analysis.claude_response | Analysis | Claude analysis received. Includes: model_id, output_tokens, estimated_liability, deductions_identified, credits_identified, confidence_score, latency_ms, full_response_hash. |
| analysis.openai_request | Analysis | Tax data sent to OpenAI LEGA RAG Agent. Includes: model_id, vector_store_id, input_tokens, prompt_hash. |
| analysis.openai_response | Analysis | OpenAI RAG analysis received. Includes: model_id, output_tokens, regulation_cited, confidence (High/Medium/Low), retrieved_chunk_ids, retrieved_chunk_count, latency_ms. |
| scoring.comparison | Scoring | Dual-LLM scores compared. Includes: claude_score, openai_score, delta, threshold_used, delta_threshold_used, flag_status (green/amber/red/yellow), flag_reason. |
| scoring.flag_raised | Scoring | A confidence flag was raised. Includes: flag_level (amber/red/yellow), trigger_condition, claude_score, openai_score, recommended_action. |
| error.api_failure | Error | External API call failed. Includes: service (mistral/anthropic/openai), endpoint, http_status, error_message, retry_attempt, will_retry (bool). |
| error.unhandled | Error | Unhandled exception. Includes: exception_type, message, stack_trace_hash (full trace in operational logs only). |


### 18.2.3 PII Masking Rules

All audit trail entries must comply with the following PII masking rules before write. Masking is applied at the AuditLogger level and cannot be bypassed:


| Data Element | Masked Format | Applied In | Notes |
| --- | --- | --- | --- |
| Social Security Number (SSN) | ***-**-{last4} | All events containing SSN fields | Original SSN never written to any log tier |
| Employer Identification Number (EIN) | **-***{last4} | OCR events, analysis events | Partially masked; last 4 retained for matching |
| API Keys | ***REDACTED*** | All events | Never logged in any tier; .env config logged as hash only |
| Full Name (from W-2) | First initial + last name | OCR events | e.g., “J. Smith” |
| Bank Account / Routing Numbers | ***REDACTED*** | If present in any form | Fully redacted; never logged |
| Full Address | City, State, ZIP only | OCR events, wizard data | Street address stripped |


## 18.3 Audit Report File (Tier 3)

At session completion (or on explicit user request), the system generates a comprehensive audit report in both PDF (human-readable) and JSON (machine-readable) formats. This file is the primary deliverable for CPA review, IRS audit defense, and personal record retention.


### 18.3.1 Audit Report Structure


| Section | Contents |
| --- | --- |
| 1. Cover Page | Report title, session ID, generation timestamp, tool version, disclaimer (“This is an AI-assisted analysis, not professional tax advice”). |
| 2. Session Summary | Session start/end time, total duration, filing status selected, number of documents processed, number of agent loop iterations, total LLM calls made, total tokens consumed (Anthropic + OpenAI). |
| 3. Document Inventory | Table of all uploaded documents: file_id, filename, file_type, form_type_detected, SHA-256 hash, upload timestamp, OCR processing status, number of fields extracted, number of fields user-corrected. |
| 4. Extracted Data Summary | All OCR-extracted fields organized by form. For each field: original OCR value, OCR confidence score, user-corrected value (if any), final value used in analysis. Clearly marks which fields were human-reviewed vs. accepted as-is. |
| 5. User Corrections Log | Complete list of every user correction: field_name, form_id, original_value, corrected_value, timestamp. This section proves human oversight of OCR output. |
| 6. Income Summary | Aggregated income by category: wages (W-2), nonemployee compensation (1099-NEC), interest (1099-INT), dividends (1099-DIV), other. Total AGI computation with source breakdown. |
| 7. Deduction Analysis | Standard deduction amount vs. itemized total. If itemized: each deduction category with amount and source. Deduction election (standard/itemized) with rationale from LLM analysis. |
| 8. Credit Analysis | Eligible credits identified by each LLM. Credit amounts with phase-out calculations (via Calculator Tool). Credits applied to final liability. |
| 9. Dual-LLM Analysis Comparison | Side-by-side table: Claude’s analysis vs. OpenAI’s analysis. For each: estimated liability, identified deductions, identified credits, advisory notes, confidence score, model_id used, tokens consumed, latency. Differences highlighted. |
| 10. Confidence Scoring Report | Claude score, OpenAI score, delta, threshold used (from .env), delta threshold, flag status (green/amber/red/yellow), flag reason, recommended action. If flagged: specific areas of disagreement or low confidence. |
| 11. RAG Retrieval Evidence | For OpenAI’s RAG-grounded analysis: Vector Store ID used, number of chunks retrieved, chunk IDs, truncated chunk excerpts (first 200 chars each), relevance scores. Proves the analysis was grounded in the knowledge base, not hallucinated. |
| 12. Agent Execution Timeline | Chronological list of all agent actions: timestamp, event_type, component, action, status, latency. Provides a complete replay-capable timeline of the session. |
| 13. TODO Plan History | All TODO list versions created during the session. For each version: items, statuses, which items changed from prior version. Shows the agent’s planning and re-planning decisions. |
| 14. Error & Retry Log | All API failures, retries, timeouts, and degradation events. For each: service, error, retry count, final status. Explains any gaps in analysis coverage. |
| 15. Token & Cost Summary | Total tokens by model tier: Anthropic (Opus/Sonnet/Haiku) and OpenAI (Pro/Standard/Mini). Estimated cost per model at current pricing. Total estimated session cost. |
| 16. Signatures & Attestation | System-generated attestation: “This report was generated by [tool name] v[version] on [date]. All data was processed by AI models and has not been reviewed by a licensed tax professional unless separately noted.” Placeholder for user signature and CPA countersignature (if applicable). |


### 18.3.2 Report Generation Requirements


| ID | Priority | Requirement |
| --- | --- | --- |
| FR-1801 | Must | System shall generate a PDF audit report at session completion containing all 16 sections defined in 18.3.1. |
| FR-1802 | Must | System shall generate a companion JSON audit report containing identical data in machine-readable format. |
| FR-1803 | Must | Both report files shall be named with the session ID: audit_report_{session_id}.pdf and audit_report_{session_id}.json. |
| FR-1804 | Must | Reports shall be saved to /backend/audit/reports/ and made available for download via the React frontend. |
| FR-1805 | Must | All PII in reports shall be masked per the rules in Section 18.2.3. The report shall contain NO unmasked SSNs, bank accounts, or full addresses. |
| FR-1806 | Must | The PDF report shall include a table of contents with hyperlinked section headers. |
| FR-1807 | Must | The Agent Execution Timeline (Section 12) shall contain every audit trail event from the JSONL file, formatted as a human-readable chronological table. |
| FR-1808 | Should | The PDF report shall be digitally signed with a SHA-256 hash of the JSONL audit trail, printed on the cover page, enabling integrity verification. |
| FR-1809 | Should | System shall offer a “Generate Audit Report” button on the wizard’s Results step (Step 7) that triggers on-demand report generation. |
| FR-1810 | Should | System shall auto-generate the audit report on session end (graceful close) without requiring explicit user action. |
| FR-1811 | Must | The JSON report shall include a schema_version field to support future format evolution. |
| FR-1812 | Must | Reports shall be retained on the local filesystem indefinitely (no auto-deletion). User manages their own retention. |


## 18.4 Logging Infrastructure Requirements


| ID | Priority | Requirement |
| --- | --- | --- |
| FR-1821 | Must | All audit trail events shall be written to an append-only JSONL file. Once written, events shall never be modified or deleted during the session. |
| FR-1822 | Must | Each audit event shall conform to the schema defined in 18.2.1. Pydantic validation shall reject malformed events. |
| FR-1823 | Must | Audit trail writing shall be asynchronous (non-blocking) to avoid impacting agent loop performance. |
| FR-1824 | Must | Operational logs (Tier 1) shall use structured logging (structlog) with JSON output for machine parseability. |
| FR-1825 | Must | Operational logs shall rotate at 50MB with 5 backup files retained. |
| FR-1826 | Must | All LLM API calls (both Anthropic and OpenAI) shall log: model_id, input_tokens, output_tokens, latency_ms, status. |
| FR-1827 | Must | All tool calls shall log: tool_id, input_parameters (masked), output_summary, latency_ms, status, parent_event_id. |
| FR-1828 | Must | All user corrections to OCR fields shall log: field_name, original_value, corrected_value, original_confidence. This is a critical audit requirement. |
| FR-1829 | Must | The scoring engine’s flag decision shall log: both scores, delta, thresholds used, flag_status, and flag_reason. This must be fully reproducible. |
| FR-1830 | Must | Context compression events shall log: pre/post token counts, compression ratio, and which state was preserved vs. discarded. |
| FR-1831 | Should | System shall provide a /api/audit/trail/{session_id} endpoint that returns the raw JSONL audit trail for a given session. |
| FR-1832 | Should | System shall provide a /api/audit/report/{session_id} endpoint that triggers on-demand report generation and returns the PDF. |
| FR-1833 | Must | No audit trail event shall contain unmasked PII. The AuditLogger shall apply masking rules (Section 18.2.3) before write. |
| FR-1834 | Must | Audit trail files shall be stored in /backend/audit/ and excluded from version control via .gitignore. |


## 18.5 Audit File Retention & Integrity


| Artifact | Location | Retention | Integrity |
| --- | --- | --- | --- |
| JSONL Audit Trail | /backend/audit/session_{id}.jsonl | Indefinite (user-managed) | SHA-256 hash computed at session end and stored in report cover page |
| PDF Audit Report | /backend/audit/reports/audit_report_{id}.pdf | Indefinite (user-managed) | Contains JSONL hash for cross-verification |
| JSON Audit Report | /backend/audit/reports/audit_report_{id}.json | Indefinite (user-managed) | schema_version field for forward compatibility |
| Operational Logs | /backend/logs/app.log | Rolling (50MB x 5 backups) | Not audit-grade; for debugging only |
| CLAUDE.md | /backend/memory/CLAUDE.md | Persistent across sessions | Compressed session memory; not a primary audit source |

*For IRS audit purposes, the recommended retention period is a minimum of 7 years from the tax filing date, consistent with IRS statute of limitations guidance. The system does not auto-delete any audit files; the user is responsible for managing retention and backup.*


# 19. OpenTelemetry Observability & Tracing Dashboard

The system shall implement full OpenTelemetry (OTel) distributed tracing to provide deep, real-time visibility into the agentic loop’s execution. This goes beyond the audit trail (Section 18) by capturing hierarchical, time-correlated spans across every agent cycle, LLM invocation, and tool call—enabling performance analysis, bottleneck identification, and interactive trace visualization via a dedicated dashboard. The implementation follows the Strands Agents SDK tracing pattern, adapted for the n0 master loop architecture.


## 19.1 OTel Integration Architecture

The tracing layer sits alongside the n0 master loop and instruments every phase of the agentic lifecycle without impacting execution performance. Traces are exported via the OTLP (OpenTelemetry Protocol) to a local collector, which feeds a visualization backend accessible through a browser-based dashboard.


| Component | Implementation | Description |
| --- | --- | --- |
| Instrumentation Layer | opentelemetry-sdk + opentelemetry-api (Python) | Auto-creates spans for each agent cycle, model invocation, and tool call. Injects trace context into all internal calls. Non-blocking; uses batch span processor. |
| Span Exporter | OTLPSpanExporter (HTTP, port 4318) | Exports spans to the local OTel Collector via OTLP/HTTP. Also supports console export for development debugging. |
| OTel Collector | Jaeger all-in-one (Docker container) | Receives spans via OTLP. Stores traces locally. Provides query API for the dashboard. Runs as a sidecar container or background process. |
| Tracing Dashboard | Jaeger UI (http://localhost:16686) | Browser-based trace visualization. Hierarchical span view, latency flamegraphs, service dependency maps, search by trace ID or attributes. |
| Custom Attributes | Tax-domain semantic attributes | session.id, filing_status, form_type, tool.name, confidence_score, flag_status—injected into spans for tax-specific filtering and analysis. |


## 19.2 Trace Structure (Span Hierarchy)

Traces follow a hierarchical span model that mirrors the n0 agentic loop’s execution layers. Each user interaction produces a single root trace containing nested spans:


| Depth | Span Name | Maps To (n0 Architecture) | Contents |
| --- | --- | --- | --- |
| 1 (Root) | Agent Span | n0 Master Loop | Entire agent invocation from user message to final response. Contains aggregated token usage, total cycle count, user prompt, and final answer. |
| 2 | Cycle Span | n0 Inference Cycle | One iteration of the think → act → observe loop. Contains cycle_id, the formatted prompt for this cycle, model response, and tool results. Multiple cycle spans per agent span. |
| 3a | Model Invoke Span | Anthropic Claude API Call | Single LLM inference call. Contains: model_id, prompt tokens, completion tokens, cache tokens, latency, full model response (including tool_use blocks). |
| 3b | Tool Span | ToolEngine Dispatch | Single tool execution. Contains: tool name, tool call ID, input parameters, output result, execution status (success/error), and latency. One span per tool call. |
| 4 (Nested) | Sub-Tool Span | External API Call within Tool | For tools that make external API calls (e.g., legal_rag_agent_tool calling OpenAI, mistral_ocr_tool calling Mistral API). Captures the outbound HTTP call as a child span with service name, endpoint, status code, and latency. |


## 19.3 Captured Attributes (OTel Semantic Conventions)

All spans follow OpenTelemetry’s gen_ai semantic conventions, extended with tax-domain custom attributes. This ensures compatibility with any OTel-compatible visualization tool.


### 19.3.1 Agent-Level Attributes


| Attribute | Type | Description |
| --- | --- | --- |
| gen_ai.system | str | Agent system identifier: “tax-assistant-n0” |
| gen_ai.agent.name | str | Agent name: “Tax_Analysis_Agent” |
| gen_ai.operation.name | str | Operation type: “tax_analysis”, “ocr_processing”, “scoring” |
| gen_ai.request.model | str | Model identifier from .env (e.g., claude-opus-4-6) |
| gen_ai.user.message | str | User’s initial prompt or wizard-submitted data (PII masked) |
| gen_ai.choice | str | Agent’s final response text |
| gen_ai.event.start_time | timestamp | When agent processing began |
| gen_ai.event.end_time | timestamp | When agent processing completed |
| gen_ai.usage.input_tokens | int | Total input tokens across all cycles in this invocation |
| gen_ai.usage.output_tokens | int | Total output tokens across all cycles |
| gen_ai.usage.total_tokens | int | Sum of input + output tokens |
| gen_ai.usage.cache_read_input_tokens | int | Tokens read from Anthropic prompt cache (0 if unsupported) |
| gen_ai.usage.cache_write_input_tokens | int | Tokens written to prompt cache |
| session.id | str (custom) | Tax session UUID linking trace to audit trail |
| filing_status | str (custom) | User’s filing status (Single, MFJ, etc.) |
| document_count | int (custom) | Number of tax documents in this session |


### 19.3.2 Cycle-Level Attributes


| Attribute | Type | Description |
| --- | --- | --- |
| event_loop.cycle_id | str | Unique identifier for this reasoning cycle within the agent invocation |
| gen_ai.user.message | str | Formatted prompt for this cycle (includes context, TODO state injection) |
| gen_ai.assistant.message | str | Model’s response for this cycle |
| gen_ai.choice.tool.result | str | Results from tool calls in this cycle (if any) |
| gen_ai.event.end_time | timestamp | When the cycle completed |
| todo.items_total | int (custom) | Total TODO items at end of cycle |
| todo.items_completed | int (custom) | Completed TODO items at end of cycle |
| compression.triggered | bool (custom) | Whether Compressor wU2 fired in this cycle |


### 19.3.3 Model Invoke Attributes


| Attribute | Type | Description |
| --- | --- | --- |
| gen_ai.system | str | Provider: “anthropic” or “openai” |
| gen_ai.request.model | str | Exact model ID (e.g., claude-opus-4-6, gpt-5.2-2025-12-11) |
| gen_ai.operation.name | str | Operation: “chat”, “assistant_run”, “compress” |
| gen_ai.user.message | str | Prompt sent to the model (PII masked, truncated if >10K chars) |
| gen_ai.choice | str | Model response (may include tool_use blocks) |
| gen_ai.usage.input_tokens | int | Input tokens for this specific invocation |
| gen_ai.usage.output_tokens | int | Output tokens for this invocation |
| gen_ai.usage.total_tokens | int | Total tokens for this invocation |
| gen_ai.event.start_time | timestamp | Invocation start |
| gen_ai.event.end_time | timestamp | Invocation end |
| model.tier | str (custom) | Model tier from .env: advance, medium, or low |
| model.estimated_cost_usd | float (custom) | Estimated cost for this invocation based on token pricing |


### 19.3.4 Tool-Level Attributes


| Attribute | Type | Description |
| --- | --- | --- |
| gen_ai.tool.name | str | Tool name: calculator_tool, legal_rag_agent_tool, mistral_ocr_tool, ask_user_tool |
| gen_ai.tool.call.id | str | Unique tool call identifier (from Anthropic tool_use block) |
| gen_ai.operation.name | str | Operation: “tool_execute” |
| gen_ai.choice | str | Formatted tool result (truncated if >5K chars) |
| tool.status | str | Execution status: success, error, timeout, retrying |
| gen_ai.event.start_time | timestamp | Tool execution start |
| gen_ai.event.end_time | timestamp | Tool execution end |
| tool.retry_count | int (custom) | Number of retries before final result (0 = first attempt succeeded) |
| tool.input_summary | str (custom) | Abbreviated input parameters (PII masked) |
| tool.form_type | str (custom) | For OCR tool: W-2, 1099-NEC, 1099-INT, 1099-DIV, 1099-MISC |
| tool.confidence | str (custom) | For RAG tool: High/Medium/Low confidence from LEGA agent output |


## 19.4 Tracing Dashboard Specification

The tracing dashboard provides a visual, interactive interface for inspecting agent execution. It is accessible at http://localhost:16686 (Jaeger UI) and serves both development debugging and production session review.


### 19.4.1 Dashboard Views


| View | Description | Example Use Cases |
| --- | --- | --- |
| Trace Search | Search traces by session.id, time range, service name, min/max duration, or custom attributes (filing_status, flag_status). Returns a list of matching traces with summary metrics. | Find all sessions that triggered a red flag; find sessions longer than 60 seconds; find all sessions processing 1099-DIV forms. |
| Trace Timeline (Waterfall) | Hierarchical waterfall view of a single trace. Shows all spans as horizontal bars on a timeline, nested by parent-child relationships. Clicking a span reveals its full attributes. | Identify which tool call took the longest in a session; see exactly when Compressor wU2 fired; trace the full lifecycle of a hallucination detection. |
| Span Detail Panel | Detailed view of a single span’s attributes, including all gen_ai.* and custom attributes. For model invokes: shows prompt tokens, output tokens, cache usage, and latency. For tool spans: shows input, output, status, and retry count. | Inspect the exact prompt sent to Claude during cycle 3; see how many Vector Store chunks the RAG agent retrieved; verify PII masking in tool inputs. |
| Latency Flamegraph | Flamegraph visualization showing proportional time spent in each span. Enables rapid identification of the slowest components in the agentic loop. | Discover that 70% of session time is spent in legal_rag_agent_tool; identify that model invocations average 3s but spike to 15s on complex prompts. |
| Service Dependency Map | Visual graph of service interactions: n0 → Anthropic API, n0 → ToolEngine → Mistral API, n0 → ToolEngine → OpenAI API. Shows request counts and error rates per edge. | Verify that all external API calls route through ToolEngine; identify elevated error rates on a specific provider. |
| Compare Traces | Side-by-side comparison of two traces. Useful for comparing a flagged session vs. a clean session, or before/after a prompt engineering change. | Compare a green-confidence session against a red-flag session to identify where divergence occurred. |


### 19.4.2 Dashboard-Specific Queries

The following pre-configured saved queries shall be available in the dashboard for common operational needs:


| Query Name | Filter | Purpose |
| --- | --- | --- |
| Flagged Sessions | flag_status=amber OR flag_status=red | All sessions that triggered confidence flags |
| Slow Sessions (>60s) | duration > 60s | Sessions exceeding the 60-second E2E target |
| OCR Retries | gen_ai.tool.name=mistral_ocr_tool AND tool.retry_count > 0 | OCR calls that required retries (potential API instability) |
| RAG Low Confidence | gen_ai.tool.name=legal_rag_agent_tool AND tool.confidence=Low | RAG calls where the knowledge base provided insufficient grounding |
| Compression Events | compression.triggered=true | Sessions where the context compressor activated (long/complex sessions) |
| API Errors | tool.status=error OR tool.status=timeout | All failed tool calls across all sessions |
| High Token Usage | gen_ai.usage.total_tokens > 100000 | Sessions consuming >100K tokens (cost optimization targets) |
| Ask User Delays | gen_ai.tool.name=ask_user_tool | All human-in-the-loop interactions with response latency |


## 19.5 Environment Configuration

The following environment variables control OpenTelemetry tracing behavior:


| Variable | Description | Required |
| --- | --- | --- |
| OTEL_EXPORTER_OTLP_ENDPOINT | OTLP collector endpoint (default: http://localhost:4318) | Required (for tracing) |
| OTEL_EXPORTER_OTLP_HEADERS | Custom headers for OTLP export (key=value pairs) | Optional |
| OTEL_TRACES_SAMPLER | Sampling strategy: always_on (default), traceidratio, parentbased_always_on | Optional |
| OTEL_TRACES_SAMPLER_ARG | Sampler argument (e.g., 0.5 for 50% sampling with traceidratio) | Optional |
| OTEL_SERVICE_NAME | Service name in traces (default: tax-assistant-n0) | Optional |
| OTEL_CONSOLE_EXPORT | Enable console span export for development (default: false) | Optional |
| JAEGER_DOCKER_IMAGE | Jaeger container image (default: jaegertracing/all-in-one:latest) | Optional |


## 19.6 Local Development Setup

For local development, the tracing stack runs as a single Docker container alongside the FastAPI application. The startup script (or docker-compose.yml) shall launch the Jaeger all-in-one container exposing the following ports:


| Port | Protocol | Purpose |
| --- | --- | --- |
| 4317 | gRPC | OTLP gRPC receiver (alternative to HTTP) |
| 4318 | HTTP | OTLP HTTP receiver (primary; used by OTLPSpanExporter) |
| 16686 | HTTP | Jaeger UI dashboard (browser access) |
| 14268 | HTTP | Jaeger collector HTTP endpoint |
| 9411 | HTTP | Zipkin-compatible receiver (optional, for multi-tool compatibility) |

A convenience script (scripts/start-tracing.sh) shall be provided that pulls and runs the Jaeger container with all required port mappings, verifies connectivity, and prints the dashboard URL. For environments where Docker is unavailable, console export provides a fallback for trace inspection.


## 19.7 Functional Requirements


| ID | Priority | Requirement |
| --- | --- | --- |
| FR-1901 | Must | System shall instrument the n0 master loop with OpenTelemetry tracing, producing a root Agent Span for each user interaction. |
| FR-1902 | Must | Each agentic loop iteration shall produce a child Cycle Span with a unique cycle_id attribute. |
| FR-1903 | Must | Every Anthropic Claude API call shall produce a Model Invoke Span with full token usage attributes (input, output, total, cache read, cache write). |
| FR-1904 | Must | Every tool execution shall produce a Tool Span with tool name, call ID, input summary, result, status, and latency. |
| FR-1905 | Must | Tool spans for legal_rag_agent_tool and mistral_ocr_tool shall produce nested Sub-Tool Spans for their outbound API calls (OpenAI Assistants, Mistral OCR 3). |
| FR-1906 | Must | All spans shall include the session.id custom attribute, enabling correlation between traces and the JSONL audit trail (Section 18). |
| FR-1907 | Must | All spans shall apply PII masking to any attribute containing user tax data (same rules as Section 18.2.3). |
| FR-1908 | Must | Spans shall be exported to the configured OTLP endpoint via OTLPSpanExporter using the batch span processor (non-blocking). |
| FR-1909 | Must | System shall include a docker-compose service or startup script for the Jaeger all-in-one container, accessible at http://localhost:16686. |
| FR-1910 | Should | The React frontend shall include a “View Trace” link on the Results page (Step 7) that opens the Jaeger UI filtered to the current session’s trace. |
| FR-1911 | Should | System shall support console span export (OTEL_CONSOLE_EXPORT=true) for development environments without Docker. |
| FR-1912 | Should | System shall support configurable sampling via OTEL_TRACES_SAMPLER for future high-volume scenarios. |
| FR-1913 | Must | Tracing overhead shall not increase agent loop latency by more than 2% (batch processor with async export). |
| FR-1914 | Should | The 8 pre-configured saved queries (Section 19.4.2) shall be importable via a Jaeger configuration file or documented as copy-paste filters. |
| FR-1915 | Must | Custom attributes (session.id, filing_status, flag_status, tool.form_type, tool.confidence, model.tier, model.estimated_cost_usd, todo.*, compression.triggered) shall be captured on the appropriate span levels as specified in Section 19.3. |


## 19.8 Trace-to-Audit Correlation

The OpenTelemetry traces and the JSONL audit trail (Section 18) serve complementary purposes and must be cross-referenced. The session.id attribute on every OTel span matches the session_id field in every audit trail event. Additionally, the AuditLogger shall write the OTel trace_id and span_id into each audit event’s metadata field, enabling bidirectional lookup: from a trace span, find the corresponding audit event, and vice versa.

The audit report (Section 18.3) shall include the root trace_id in its Session Summary section, along with a clickable URL (http://localhost:16686/trace/{trace_id}) for direct dashboard access.


# 20. Appendix: Legal & Compliance Disclaimers

*This tool is designed as a personal tax preparation assistant and does not constitute professional tax advice. All analysis results should be reviewed by a qualified tax professional (CPA or Enrolled Agent) before filing. The dual-LLM confidence scoring system is designed to surface uncertainty, not to guarantee accuracy. The user is solely responsible for the accuracy of their tax filings.*

*Tax data processed by this tool is sent to third-party APIs (Anthropic, OpenAI, Mistral) and is subject to their respective data processing and retention policies. Users should review these policies before processing sensitive tax information. No data is persisted locally beyond the active session.*
