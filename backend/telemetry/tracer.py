from contextlib import contextmanager
from opentelemetry import trace
from opentelemetry.trace import Span
from backend.telemetry.attributes import (
    ATTR_AGENT_NAME, ATTR_AGENT_SESSION_ID, ATTR_CYCLE_PHASE,
    ATTR_CYCLE_ITERATION, ATTR_MODEL_PROVIDER, ATTR_MODEL_ID,
    ATTR_MODEL_INPUT_TOKENS, ATTR_MODEL_OUTPUT_TOKENS,
    ATTR_TOOL_NAME, ATTR_TOOL_SUCCESS
)
from backend.utils.pii import mask_pii


def _mask_span_attr(span: Span, key: str, value):
    """Set span attribute with PII masking for string values."""
    if isinstance(value, str):
        span.set_attribute(key, mask_pii(value))
    else:
        span.set_attribute(key, value)


class TaxTracer:
    SERVICE_NAME = "tax-ai-backend"

    def __init__(self):
        self._tracer = trace.get_tracer(self.SERVICE_NAME)

    @contextmanager
    def start_agent_span(self, agent_name: str, session_id: str = ""):
        with self._tracer.start_as_current_span(f"agent.{agent_name}") as span:
            span.set_attribute(ATTR_AGENT_NAME, agent_name)
            span.set_attribute(ATTR_AGENT_SESSION_ID, session_id)
            yield span

    @contextmanager
    def start_cycle_span(self, phase: str, iteration: int = 0):
        with self._tracer.start_as_current_span(f"cycle.{phase}") as span:
            span.set_attribute(ATTR_CYCLE_PHASE, phase)
            span.set_attribute(ATTR_CYCLE_ITERATION, iteration)
            yield span

    @contextmanager
    def start_model_invoke_span(
        self,
        provider: str,
        model_id: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ):
        with self._tracer.start_as_current_span(f"model.invoke.{provider}") as span:
            span.set_attribute(ATTR_MODEL_PROVIDER, provider)
            span.set_attribute(ATTR_MODEL_ID, model_id)
            if input_tokens:
                span.set_attribute(ATTR_MODEL_INPUT_TOKENS, input_tokens)
            if output_tokens:
                span.set_attribute(ATTR_MODEL_OUTPUT_TOKENS, output_tokens)
            yield span

    @contextmanager
    def start_tool_span(self, tool_name: str, cycle_id: str = ""):
        with self._tracer.start_as_current_span(f"tool.{tool_name}") as span:
            span.set_attribute(ATTR_TOOL_NAME, tool_name)
            if cycle_id:
                span.set_attribute("tax.tool.cycle_id", cycle_id)
            try:
                yield span
                span.set_attribute(ATTR_TOOL_SUCCESS, True)
            except Exception:
                span.set_attribute(ATTR_TOOL_SUCCESS, False)
                raise

    @contextmanager
    def start_sub_tool_span(self, tool_name: str, sub_tool: str):
        """Create a nested sub-tool span inside a parent tool span."""
        with self._tracer.start_as_current_span(f"tool.{tool_name}.{sub_tool}") as span:
            span.set_attribute(ATTR_TOOL_NAME, f"{tool_name}.{sub_tool}")
            try:
                yield span
                span.set_attribute(ATTR_TOOL_SUCCESS, True)
            except Exception:
                span.set_attribute(ATTR_TOOL_SUCCESS, False)
                raise

    def set_span_attribute_masked(self, span: Span, key: str, value):
        """Set a span attribute with PII masking applied."""
        _mask_span_attr(span, key, value)


# Singleton
_tracer_instance: TaxTracer | None = None


def get_tracer() -> TaxTracer:
    global _tracer_instance
    if _tracer_instance is None:
        _tracer_instance = TaxTracer()
    return _tracer_instance
