"""Constants for custom OpenTelemetry attribute keys."""

# Agent attributes
ATTR_AGENT_NAME = "tax.agent.name"
ATTR_AGENT_ITERATION = "tax.agent.iteration"
ATTR_AGENT_SESSION_ID = "tax.agent.session_id"

# Cycle / loop attributes
ATTR_CYCLE_PHASE = "tax.cycle.phase"
ATTR_CYCLE_ITERATION = "tax.cycle.iteration"
ATTR_CYCLE_TOOL_COUNT = "tax.cycle.tool_count"

# Model invocation attributes
ATTR_MODEL_PROVIDER = "tax.model.provider"
ATTR_MODEL_ID = "tax.model.id"
ATTR_MODEL_INPUT_TOKENS = "tax.model.input_tokens"
ATTR_MODEL_OUTPUT_TOKENS = "tax.model.output_tokens"
ATTR_MODEL_LATENCY_MS = "tax.model.latency_ms"
ATTR_MODEL_HAS_TOOL_CALLS = "tax.model.has_tool_calls"

# Tool attributes
ATTR_TOOL_NAME = "tax.tool.name"
ATTR_TOOL_SUCCESS = "tax.tool.success"
ATTR_TOOL_LATENCY_MS = "tax.tool.latency_ms"
ATTR_TOOL_RETRY_COUNT = "tax.tool.retry_count"

# Document attributes
ATTR_DOCUMENT_TYPE = "tax.document.type"
ATTR_DOCUMENT_FILE_ID = "tax.document.file_id"
ATTR_DOCUMENT_SHA256 = "tax.document.sha256"
ATTR_DOCUMENT_FIELD_COUNT = "tax.document.field_count"
ATTR_DOCUMENT_AVG_CONFIDENCE = "tax.document.avg_confidence"

# Analysis attributes
ATTR_ANALYSIS_FLAG_STATUS = "tax.analysis.flag_status"
ATTR_ANALYSIS_LIABILITY_DELTA = "tax.analysis.liability_delta"
ATTR_ANALYSIS_CLAUDE_CONFIDENCE = "tax.analysis.claude_confidence"
ATTR_ANALYSIS_OPENAI_CONFIDENCE = "tax.analysis.openai_confidence"

# Compression attributes
ATTR_COMPRESSION_BEFORE_TOKENS = "tax.compression.before_tokens"
ATTR_COMPRESSION_AFTER_TOKENS = "tax.compression.after_tokens"
ATTR_COMPRESSION_RATIO = "tax.compression.ratio"

# Audit attributes
ATTR_AUDIT_EVENT_TYPE = "tax.audit.event_type"
ATTR_AUDIT_PII_MASKED = "tax.audit.pii_masked"
