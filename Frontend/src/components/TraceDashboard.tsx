import React, { useEffect, useState } from 'react'
import { fetchTraces, fetchTrace } from '../services/api'

interface TraceSummary {
  trace_id: string
  root_span: string
  start_time: string
  span_count: number
  status: string
  service: string | null
}

interface Span {
  trace_id: string
  span_id: string
  parent_span_id: string | null
  name: string
  kind: string
  start_time: string
  end_time: string
  duration_ms: number | null
  status: string
  status_description: string | null
  attributes: Record<string, unknown>
  events: { name: string; timestamp: string | null; attributes: Record<string, unknown> }[]
}

const STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  OK: { bg: '#f0fdf4', text: '#166534' },
  UNSET: { bg: '#f0f4f8', text: '#555' },
  ERROR: { bg: '#fef2f2', text: '#991b1b' },
}

function formatTime(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleDateString([], { month: 'short', day: 'numeric' }) + ' ' + formatTime(iso)
}

function formatDuration(ms: number | null): string {
  if (ms === null || ms === undefined) return '—'
  if (ms < 1) return '<1ms'
  if (ms < 1000) return `${Math.round(ms)}ms`
  return `${(ms / 1000).toFixed(2)}s`
}

function StatusBadge({ status }: { status: string }) {
  const colors = STATUS_COLORS[status] || STATUS_COLORS.UNSET
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '2px 8px',
        borderRadius: 4,
        fontSize: 11,
        fontWeight: 600,
        background: colors.bg,
        color: colors.text,
      }}
    >
      {status}
    </span>
  )
}

/* ── Span tree ────────────────────────────────────────────────────────── */

function buildTree(spans: Span[]): { roots: Span[]; children: Map<string, Span[]>; minStart: number; maxEnd: number } {
  const children = new Map<string, Span[]>()
  const spanMap = new Map<string, Span>()
  let minStart = Infinity
  let maxEnd = -Infinity

  for (const s of spans) {
    spanMap.set(s.span_id, s)
    if (s.start_time) minStart = Math.min(minStart, new Date(s.start_time).getTime())
    if (s.end_time) maxEnd = Math.max(maxEnd, new Date(s.end_time).getTime())
  }

  const roots: Span[] = []
  for (const s of spans) {
    if (!s.parent_span_id || !spanMap.has(s.parent_span_id)) {
      roots.push(s)
    } else {
      const list = children.get(s.parent_span_id) || []
      list.push(s)
      children.set(s.parent_span_id, list)
    }
  }

  return { roots, children, minStart, maxEnd }
}

function SpanRow({
  span,
  children,
  depth,
  minStart,
  totalDuration,
}: {
  span: Span
  children: Map<string, Span[]>
  depth: number
  minStart: number
  totalDuration: number
}) {
  const [expanded, setExpanded] = useState(true)
  const [showAttrs, setShowAttrs] = useState(false)
  const kids = children.get(span.span_id) || []
  const hasKids = kids.length > 0

  const startMs = span.start_time ? new Date(span.start_time).getTime() - minStart : 0
  const durationMs = span.duration_ms || 0
  const leftPct = totalDuration > 0 ? (startMs / totalDuration) * 100 : 0
  const widthPct = totalDuration > 0 ? Math.max((durationMs / totalDuration) * 100, 0.5) : 0

  const barColor = span.status === 'ERROR' ? '#ef4444' : '#4a90d9'
  const attrEntries = Object.entries(span.attributes || {})

  return (
    <>
      <tr
        style={{ borderBottom: '1px solid #f0f0f0', cursor: attrEntries.length > 0 ? 'pointer' : 'default' }}
        onClick={() => attrEntries.length > 0 && setShowAttrs(!showAttrs)}
      >
        {/* Name column */}
        <td style={{ padding: '6px 8px', fontSize: 13, whiteSpace: 'nowrap' }}>
          <span style={{ display: 'inline-block', width: depth * 20 }} />
          {hasKids && (
            <button
              onClick={(e) => { e.stopPropagation(); setExpanded(!expanded) }}
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                padding: 0,
                marginRight: 4,
                fontSize: 11,
                color: '#888',
                width: 16,
                textAlign: 'center',
              }}
            >
              {expanded ? '▼' : '▶'}
            </button>
          )}
          {!hasKids && <span style={{ display: 'inline-block', width: 20 }} />}
          <span style={{ color: span.status === 'ERROR' ? '#991b1b' : '#1a1a2e' }}>
            {span.name}
          </span>
        </td>

        {/* Duration */}
        <td style={{ padding: '6px 8px', fontSize: 12, color: '#666', textAlign: 'right', whiteSpace: 'nowrap' }}>
          {formatDuration(span.duration_ms)}
        </td>

        {/* Status */}
        <td style={{ padding: '6px 8px', textAlign: 'center' }}>
          <StatusBadge status={span.status} />
        </td>

        {/* Timeline bar */}
        <td style={{ padding: '6px 8px', width: '40%' }}>
          <div style={{ position: 'relative', height: 14, background: '#f5f7fa', borderRadius: 3 }}>
            <div
              style={{
                position: 'absolute',
                top: 2,
                height: 10,
                borderRadius: 2,
                background: barColor,
                opacity: 0.8,
                left: `${leftPct}%`,
                width: `${widthPct}%`,
                minWidth: 2,
              }}
            />
          </div>
        </td>
      </tr>

      {/* Attribute detail row */}
      {showAttrs && attrEntries.length > 0 && (
        <tr>
          <td colSpan={4} style={{ padding: '0 8px 8px', paddingLeft: depth * 20 + 36 }}>
            <div
              style={{
                background: '#f8f9fa',
                borderRadius: 6,
                padding: '8px 12px',
                fontSize: 12,
                fontFamily: 'monospace',
              }}
            >
              {attrEntries.map(([k, v]) => (
                <div key={k} style={{ marginBottom: 2 }}>
                  <span style={{ color: '#4a90d9' }}>{k}</span>
                  <span style={{ color: '#888' }}>{' = '}</span>
                  <span style={{ color: '#1a1a2e' }}>{String(v)}</span>
                </div>
              ))}
            </div>
          </td>
        </tr>
      )}

      {/* Children */}
      {expanded &&
        kids.map((child) => (
          <SpanRow
            key={child.span_id}
            span={child}
            children={children}
            depth={depth + 1}
            minStart={minStart}
            totalDuration={totalDuration}
          />
        ))}
    </>
  )
}

/* ── Trace detail panel ───────────────────────────────────────────────── */

function TraceDetail({ traceId, onBack }: { traceId: string; onBack: () => void }) {
  const [spans, setSpans] = useState<Span[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    fetchTrace(traceId)
      .then((data) => setSpans(data.spans || []))
      .catch(() => setSpans([]))
      .finally(() => setLoading(false))
  }, [traceId])

  const { roots, children, minStart, maxEnd } = buildTree(spans)
  const totalDuration = maxEnd - minStart

  return (
    <div>
      <button
        onClick={onBack}
        style={{
          padding: '6px 16px',
          borderRadius: 6,
          border: '1px solid #e2e8f0',
          background: 'white',
          cursor: 'pointer',
          fontSize: 13,
          marginBottom: 16,
          color: '#333',
        }}
      >
        Back to traces
      </button>

      <div
        style={{
          background: 'white',
          borderRadius: 12,
          padding: 24,
          boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h3 style={{ fontSize: 16, color: '#1a1a2e', margin: 0 }}>
            Trace {traceId.slice(0, 12)}...
          </h3>
          <span style={{ fontSize: 12, color: '#888' }}>{spans.length} spans</span>
        </div>

        {loading ? (
          <p style={{ color: '#888', fontSize: 14 }}>Loading spans...</p>
        ) : spans.length === 0 ? (
          <p style={{ color: '#888', fontSize: 14 }}>No spans found for this trace.</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid #e2e8f0' }}>
                  <th style={{ padding: '8px', textAlign: 'left', fontSize: 12, color: '#888', fontWeight: 600 }}>
                    Span
                  </th>
                  <th style={{ padding: '8px', textAlign: 'right', fontSize: 12, color: '#888', fontWeight: 600, width: 80 }}>
                    Duration
                  </th>
                  <th style={{ padding: '8px', textAlign: 'center', fontSize: 12, color: '#888', fontWeight: 600, width: 70 }}>
                    Status
                  </th>
                  <th style={{ padding: '8px', textAlign: 'left', fontSize: 12, color: '#888', fontWeight: 600, width: '40%' }}>
                    Timeline
                  </th>
                </tr>
              </thead>
              <tbody>
                {roots.map((root) => (
                  <SpanRow
                    key={root.span_id}
                    span={root}
                    children={children}
                    depth={0}
                    minStart={minStart}
                    totalDuration={totalDuration}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

/* ── Main dashboard ───────────────────────────────────────────────────── */

export default function TraceDashboard() {
  const [traces, setTraces] = useState<TraceSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedTrace, setSelectedTrace] = useState<string | null>(null)

  const loadTraces = () => {
    setLoading(true)
    fetchTraces(50)
      .then((data) => setTraces(data.traces || []))
      .catch(() => setTraces([]))
      .finally(() => setLoading(false))
  }

  useEffect(() => { loadTraces() }, [])

  if (selectedTrace) {
    return <TraceDetail traceId={selectedTrace} onBack={() => setSelectedTrace(null)} />
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <p style={{ fontSize: 14, color: '#666', margin: 0 }}>
          OpenTelemetry spans captured from the backend.
        </p>
        <button
          onClick={loadTraces}
          style={{
            padding: '6px 16px',
            borderRadius: 6,
            border: '1px solid #e2e8f0',
            background: 'white',
            cursor: 'pointer',
            fontSize: 13,
            color: '#333',
          }}
        >
          Refresh
        </button>
      </div>

      <div
        style={{
          background: 'white',
          borderRadius: 12,
          padding: 24,
          boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
        }}
      >
        {loading ? (
          <p style={{ color: '#888', fontSize: 14 }}>Loading traces...</p>
        ) : traces.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 32 }}>
            <p style={{ color: '#888', fontSize: 14, marginBottom: 8 }}>No traces yet.</p>
            <p style={{ color: '#aaa', fontSize: 13 }}>
              Traces appear after the backend processes requests.
            </p>
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #e2e8f0' }}>
                <th style={{ padding: '8px 12px', textAlign: 'left', fontSize: 12, color: '#888', fontWeight: 600 }}>
                  Trace ID
                </th>
                <th style={{ padding: '8px 12px', textAlign: 'left', fontSize: 12, color: '#888', fontWeight: 600 }}>
                  Root Span
                </th>
                <th style={{ padding: '8px 12px', textAlign: 'center', fontSize: 12, color: '#888', fontWeight: 600 }}>
                  Spans
                </th>
                <th style={{ padding: '8px 12px', textAlign: 'center', fontSize: 12, color: '#888', fontWeight: 600 }}>
                  Status
                </th>
                <th style={{ padding: '8px 12px', textAlign: 'right', fontSize: 12, color: '#888', fontWeight: 600 }}>
                  Time
                </th>
              </tr>
            </thead>
            <tbody>
              {traces.map((t) => (
                <tr
                  key={t.trace_id}
                  onClick={() => setSelectedTrace(t.trace_id)}
                  style={{
                    borderBottom: '1px solid #f0f0f0',
                    cursor: 'pointer',
                    transition: 'background 0.15s',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = '#f8f9fa')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = '')}
                >
                  <td style={{ padding: '10px 12px', fontSize: 13, fontFamily: 'monospace', color: '#4a90d9' }}>
                    {t.trace_id.slice(0, 12)}...
                  </td>
                  <td style={{ padding: '10px 12px', fontSize: 13, color: '#1a1a2e' }}>
                    {t.root_span || '—'}
                  </td>
                  <td style={{ padding: '10px 12px', fontSize: 13, color: '#666', textAlign: 'center' }}>
                    {t.span_count}
                  </td>
                  <td style={{ padding: '10px 12px', textAlign: 'center' }}>
                    <StatusBadge status={t.status || 'UNSET'} />
                  </td>
                  <td style={{ padding: '10px 12px', fontSize: 12, color: '#888', textAlign: 'right', whiteSpace: 'nowrap' }}>
                    {formatDate(t.start_time)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
