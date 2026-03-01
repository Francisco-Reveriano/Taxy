"""API endpoints for viewing locally-stored trace data."""
import json
from collections import defaultdict
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Query

router = APIRouter()

_TRACES_DIR = Path(__file__).resolve().parent.parent / "traces"


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
    spans = _read_spans(limit=limit * 10)

    grouped: dict[str, dict] = {}
    for span in spans:
        tid = span.get("trace_id", "")
        if tid not in grouped:
            grouped[tid] = {
                "trace_id": tid,
                "root_span": span.get("name"),
                "start_time": span.get("start_time"),
                "span_count": 0,
                "status": span.get("status"),
                "service": span.get("resource", {}).get("service.name"),
            }
        grouped[tid]["span_count"] += 1

    traces = sorted(grouped.values(), key=lambda t: t.get("start_time") or "", reverse=True)
    return {"traces": traces[:limit]}


@router.get("/traces/{trace_id}")
async def get_trace(trace_id: str):
    """Get all spans for a specific trace."""
    spans = _read_spans(limit=500, trace_id=trace_id)
    spans.sort(key=lambda s: s.get("start_time") or "")
    return {"trace_id": trace_id, "spans": spans}
