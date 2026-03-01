"""JSON file-based span exporter — zero external dependencies.

Writes completed spans as JSON-lines to backend/traces/<date>.jsonl.
Each line is a self-contained JSON object with trace_id, span hierarchy,
timing, attributes, and status.  Files rotate daily.
"""
import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.trace import StatusCode

logger = logging.getLogger(__name__)

_TRACES_DIR = Path(__file__).resolve().parent.parent / "traces"


def _span_to_dict(span: ReadableSpan) -> dict:
    """Convert a ReadableSpan to a JSON-serialisable dict."""
    ctx = span.get_span_context()
    parent = span.parent

    return {
        "trace_id": format(ctx.trace_id, "032x"),
        "span_id": format(ctx.span_id, "016x"),
        "parent_span_id": format(parent.span_id, "016x") if parent else None,
        "name": span.name,
        "kind": span.kind.name if span.kind else "INTERNAL",
        "start_time": span.start_time and _nano_to_iso(span.start_time),
        "end_time": span.end_time and _nano_to_iso(span.end_time),
        "duration_ms": (
            round((span.end_time - span.start_time) / 1_000_000, 2)
            if span.start_time and span.end_time
            else None
        ),
        "status": span.status.status_code.name if span.status else "UNSET",
        "status_description": (
            span.status.description if span.status else None
        ),
        "attributes": dict(span.attributes) if span.attributes else {},
        "events": [
            {
                "name": e.name,
                "timestamp": _nano_to_iso(e.timestamp) if e.timestamp else None,
                "attributes": dict(e.attributes) if e.attributes else {},
            }
            for e in (span.events or [])
        ],
        "resource": {
            k: v
            for k, v in (span.resource.attributes or {}).items()
        },
    }


def _nano_to_iso(ns: int) -> str:
    """Convert nanosecond epoch to ISO-8601 string."""
    return datetime.fromtimestamp(ns / 1e9, tz=timezone.utc).isoformat()


class JSONFileSpanExporter(SpanExporter):
    """Exports spans as JSON-lines to daily rolling files in backend/traces/."""

    def __init__(self, traces_dir: str | Path | None = None):
        self._traces_dir = Path(traces_dir) if traces_dir else _TRACES_DIR
        self._traces_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        logger.info("JSONFileSpanExporter writing to %s", self._traces_dir)

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        path = self._traces_dir / f"{today}.jsonl"

        try:
            lines = []
            for span in spans:
                lines.append(json.dumps(_span_to_dict(span), default=str))

            with self._lock:
                with open(path, "a", encoding="utf-8") as f:
                    f.write("\n".join(lines) + "\n")

            return SpanExportResult.SUCCESS
        except Exception:
            logger.exception("Failed to write spans to %s", path)
            return SpanExportResult.FAILURE

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True
