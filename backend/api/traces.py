"""API endpoints for viewing locally-stored trace data."""
import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Query

from backend.telemetry.file_exporter import get_active_trace_session

router = APIRouter()

_TRACES_DIR = Path(__file__).resolve().parent.parent / "traces"


def _to_int(value) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _read_spans(limit: int = 200, trace_id: Optional[str] = None) -> list[dict]:
    """Read spans from JSONL files, newest first."""
    if not _TRACES_DIR.exists():
        return []

    files = sorted(_TRACES_DIR.glob("*.jsonl"), reverse=True)
    spans = []

    for f in files:
        for line in reversed(f.read_text(encoding="utf-8").strip().splitlines()):
            if not line.strip():
                continue
            try:
                span = json.loads(line)
            except json.JSONDecodeError:
                continue
            if trace_id and span.get("trace_id") != trace_id:
                continue
            spans.append(span)
            if len(spans) >= limit:
                return spans
    return spans


@router.get("/traces")
async def list_traces(limit: int = Query(default=50, le=200)):
    """List recent traces grouped by trace_id."""
    active_session_id = get_active_trace_session()
    if not active_session_id:
        return {"session_id": None, "traces": []}

    spans = _read_spans(limit=limit * 10)

    grouped: dict[str, dict] = {}
    for span in spans:
        tid = span.get("trace_id", "")
        attrs = span.get("attributes", {}) or {}
        in_tokens = _to_int(attrs.get("tax.model.input_tokens"))
        out_tokens = _to_int(attrs.get("tax.model.output_tokens"))
        if tid not in grouped:
            grouped[tid] = {
                "trace_id": tid,
                "root_span": span.get("name"),
                "start_time": span.get("start_time"),
                "span_count": 0,
                "status": span.get("status"),
                "service": span.get("resource", {}).get("service.name"),
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
            }
        grouped[tid]["span_count"] += 1
        grouped[tid]["input_tokens"] += in_tokens
        grouped[tid]["output_tokens"] += out_tokens
        grouped[tid]["total_tokens"] += in_tokens + out_tokens

    traces = sorted(grouped.values(), key=lambda t: t.get("start_time") or "", reverse=True)
    return {"session_id": active_session_id, "traces": traces[:limit]}


@router.get("/traces/{trace_id}")
async def get_trace(trace_id: str):
    """Get all spans for a specific trace."""
    spans = _read_spans(limit=500, trace_id=trace_id)
    spans.sort(key=lambda s: s.get("start_time") or "")

    input_tokens = 0
    output_tokens = 0
    for span in spans:
        attrs = span.get("attributes", {}) or {}
        input_tokens += _to_int(attrs.get("tax.model.input_tokens"))
        output_tokens += _to_int(attrs.get("tax.model.output_tokens"))

    return {
        "session_id": get_active_trace_session(),
        "trace_id": trace_id,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "spans": spans,
    }
