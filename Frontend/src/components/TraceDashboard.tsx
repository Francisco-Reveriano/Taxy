import React, { useEffect, useMemo, useState } from 'react'
import { fetchTraces, fetchTrace } from '../services/api'

interface TraceSummary {
  trace_id: string
  root_span: string
  start_time: string
  span_count: number
  status: string
  service: string | null
  input_tokens: number
  output_tokens: number
  total_tokens: number
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

const STATUS_PRIORITY: Record<string, number> = {
  ERROR: 0,
  UNSET: 1,
  OK: 2,
}

const PANEL_STYLE: React.CSSProperties = {
  background: 'white',
  borderRadius: 12,
  padding: 20,
  boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
}

const KPI_CARD_STYLE: React.CSSProperties = {
  background: 'white',
  border: '1px solid #e5e7eb',
  borderRadius: 12,
  padding: 14,
}

const KPI_LABEL_STYLE: React.CSSProperties = {
  fontSize: 11,
  color: '#64748b',
  textTransform: 'uppercase',
  letterSpacing: '0.03em',
}

const BUTTON_STYLE: React.CSSProperties = {
  padding: '6px 16px',
  borderRadius: 6,
  border: '1px solid #cbd5e1',
  background: 'white',
  cursor: 'pointer',
  fontSize: 13,
  color: '#1f2937',
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

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`
}

function useIsMobile(breakpoint = 768): boolean {
  const [isMobile, setIsMobile] = useState(
    typeof window !== 'undefined' ? window.innerWidth < breakpoint : false
  )

  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth < breakpoint)
    onResize()
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [breakpoint])

  return isMobile
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
              aria-label={expanded ? 'Collapse child spans' : 'Expand child spans'}
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
  const [tokenTotals, setTokenTotals] = useState({ input: 0, output: 0, total: 0 })
  const [loading, setLoading] = useState(true)
  const isMobile = useIsMobile()

  useEffect(() => {
    setLoading(true)
    fetchTrace(traceId)
      .then((data) => {
        setSpans(data.spans || [])
        setTokenTotals({
          input: data.input_tokens || 0,
          output: data.output_tokens || 0,
          total: data.total_tokens || 0,
        })
      })
      .catch(() => {
        setSpans([])
        setTokenTotals({ input: 0, output: 0, total: 0 })
      })
      .finally(() => setLoading(false))
  }, [traceId])

  const { roots, children, minStart, maxEnd } = buildTree(spans)
  const totalDuration = maxEnd - minStart
  const traceStatus = useMemo(() => {
    if (spans.some((s) => s.status === 'ERROR')) return 'ERROR'
    if (spans.some((s) => s.status === 'OK')) return 'OK'
    return 'UNSET'
  }, [spans])

  return (
    <div>
      <button
        onClick={onBack}
        style={{ ...BUTTON_STYLE, marginBottom: 16 }}
        onFocus={(e) => { e.currentTarget.style.boxShadow = '0 0 0 3px rgba(59,130,246,0.35)' }}
        onBlur={(e) => { e.currentTarget.style.boxShadow = '' }}
      >
        Back to traces
      </button>

      <div
        style={PANEL_STYLE}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h3 style={{ fontSize: 16, color: '#1a1a2e', margin: 0 }}>
            Trace {traceId.slice(0, 12)}...
          </h3>
          <span style={{ fontSize: 12, color: '#888' }}>
            {spans.length} spans · {tokenTotals.total.toLocaleString()} tokens
          </span>
        </div>

        {!loading && (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: `repeat(auto-fit, minmax(${isMobile ? 130 : 160}px, 1fr))`,
              gap: 10,
              marginBottom: 16,
            }}
          >
            <div style={{ background: '#f8fafc', border: '1px solid #e5e7eb', borderRadius: 8, padding: 10 }}>
              <div style={KPI_LABEL_STYLE}>Status</div>
              <div style={{ marginTop: 4 }}>
                <StatusBadge status={traceStatus} />
              </div>
            </div>
            <div style={{ background: '#f8fafc', border: '1px solid #e5e7eb', borderRadius: 8, padding: 10 }}>
              <div style={KPI_LABEL_STYLE}>Total Tokens</div>
              <div style={{ fontSize: 18, fontWeight: 700, color: '#0f172a', marginTop: 4 }}>
                {tokenTotals.total.toLocaleString()}
              </div>
            </div>
            <div style={{ background: '#f8fafc', border: '1px solid #e5e7eb', borderRadius: 8, padding: 10 }}>
              <div style={KPI_LABEL_STYLE}>Input / Output</div>
              <div style={{ fontSize: 13, color: '#0f172a', marginTop: 4 }}>
                {tokenTotals.input.toLocaleString()} / {tokenTotals.output.toLocaleString()}
              </div>
            </div>
            <div style={{ background: '#f8fafc', border: '1px solid #e5e7eb', borderRadius: 8, padding: 10 }}>
              <div style={KPI_LABEL_STYLE}>Span Count</div>
              <div style={{ fontSize: 18, fontWeight: 700, color: '#0f172a', marginTop: 4 }}>
                {spans.length.toLocaleString()}
              </div>
            </div>
          </div>
        )}

        {loading ? (
          <p style={{ color: '#888', fontSize: 14 }}>Loading spans...</p>
        ) : spans.length === 0 ? (
          <p style={{ color: '#888', fontSize: 14 }}>No spans found for this trace.</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', minWidth: isMobile ? 560 : 720, borderCollapse: 'collapse' }}>
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
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedTrace, setSelectedTrace] = useState<string | null>(null)
  const isMobile = useIsMobile()

  const sortedTraces = useMemo(() => {
    return [...traces].sort((a, b) => {
      const statusDelta =
        (STATUS_PRIORITY[a.status || 'UNSET'] ?? STATUS_PRIORITY.UNSET) -
        (STATUS_PRIORITY[b.status || 'UNSET'] ?? STATUS_PRIORITY.UNSET)
      if (statusDelta !== 0) return statusDelta
      return new Date(b.start_time || 0).getTime() - new Date(a.start_time || 0).getTime()
    })
  }, [traces])

  const executiveMetrics = useMemo(() => {
    const total = traces.length
    const ok = traces.filter((t) => t.status === 'OK').length
    const error = traces.filter((t) => t.status === 'ERROR').length
    const unset = traces.filter((t) => t.status === 'UNSET').length
    const totalTokens = traces.reduce((sum, t) => sum + (t.total_tokens || 0), 0)
    const successRate = total > 0 ? ok / total : 0
    const errorRate = total > 0 ? error / total : 0
    return { total, ok, error, unset, totalTokens, successRate, errorRate }
  }, [traces])

  const reliabilityHeadline = useMemo(() => {
    if (executiveMetrics.total === 0) return 'No session activity yet.'
    if (executiveMetrics.errorRate === 0) return 'Reliability is healthy for this session.'
    if (executiveMetrics.errorRate <= 0.1) return 'Reliability is stable with minor issues to review.'
    return 'Attention needed: elevated error rate in this session.'
  }, [executiveMetrics])

  const loadTraces = () => {
    setLoading(true)
    fetchTraces(50)
      .then((data) => {
        setTraces(data.traces || [])
        setActiveSessionId(data.session_id || null)
      })
      .catch(() => {
        setTraces([])
        setActiveSessionId(null)
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => { loadTraces() }, [])

  if (selectedTrace) {
    return <TraceDetail traceId={selectedTrace} onBack={() => setSelectedTrace(null)} />
  }

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 16 }}>
        <p style={{ fontSize: 14, color: '#475569', margin: 0 }}>
          Current-session traces and token usage only.
        </p>
        <button
          onClick={loadTraces}
          style={BUTTON_STYLE}
          onFocus={(e) => { e.currentTarget.style.boxShadow = '0 0 0 3px rgba(59,130,246,0.35)' }}
          onBlur={(e) => { e.currentTarget.style.boxShadow = '' }}
        >
          Refresh
        </button>
      </div>

      {!loading && (
        <>
          <h3 style={{ fontSize: 15, color: '#0f172a', margin: '0 0 10px' }}>Executive Snapshot</h3>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: `repeat(auto-fit, minmax(${isMobile ? 140 : 180}px, 1fr))`,
              gap: 12,
              marginBottom: 14,
            }}
          >
            <div style={KPI_CARD_STYLE}>
              <div style={KPI_LABEL_STYLE}>Session Total Tokens</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: '#0f172a', marginTop: 6 }}>
                {executiveMetrics.totalTokens.toLocaleString()}
              </div>
            </div>
            <div style={KPI_CARD_STYLE}>
              <div style={KPI_LABEL_STYLE}>Success Rate</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: '#0f172a', marginTop: 6 }}>
                {formatPercent(executiveMetrics.successRate)}
              </div>
            </div>
            <div style={KPI_CARD_STYLE}>
              <div style={KPI_LABEL_STYLE}>Error Count</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: '#991b1b', marginTop: 6 }}>
                {executiveMetrics.error.toLocaleString()}
              </div>
            </div>
            <div style={KPI_CARD_STYLE}>
              <div style={KPI_LABEL_STYLE}>Total Traces</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: '#0f172a', marginTop: 6 }}>
                {executiveMetrics.total.toLocaleString()}
              </div>
            </div>
          </div>

          <div
            style={{
              background: '#fcfcfd',
              border: '1px solid #e5e7eb',
              borderRadius: 12,
              padding: 14,
              marginBottom: 14,
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              gap: 12,
              flexWrap: 'wrap',
            }}
          >
            <div>
              <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4 }}>Session Reliability</div>
              <div style={{ fontSize: 14, color: '#334155' }}>{reliabilityHeadline}</div>
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <span style={{ background: '#f0fdf4', color: '#166534', borderRadius: 999, fontSize: 12, padding: '4px 10px' }}>
                OK: {executiveMetrics.ok}
              </span>
              <span style={{ background: '#fef2f2', color: '#991b1b', borderRadius: 999, fontSize: 12, padding: '4px 10px' }}>
                ERROR: {executiveMetrics.error}
              </span>
              <span style={{ background: '#f0f4f8', color: '#475569', borderRadius: 999, fontSize: 12, padding: '4px 10px' }}>
                UNSET: {executiveMetrics.unset}
              </span>
            </div>
          </div>
        </>
      )}

      <div
        style={PANEL_STYLE}
      >
        <h3 style={{ fontSize: 15, color: '#0f172a', margin: '0 0 10px' }}>Trace Runs</h3>
        {activeSessionId && (
          <div style={{ marginBottom: 12, fontSize: 12, color: '#475569' }}>
            Active session: <span style={{ fontFamily: 'monospace' }}>{activeSessionId}</span>
          </div>
        )}
        {loading ? (
          <p style={{ color: '#888', fontSize: 14 }}>Loading session performance...</p>
        ) : traces.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 32 }}>
            <p style={{ color: '#888', fontSize: 14, marginBottom: 8 }}>No session activity yet.</p>
            <p style={{ color: '#aaa', fontSize: 13 }}>
              Upload and analyze a file in this session to generate executive metrics.
            </p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', minWidth: isMobile ? 520 : 720, borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid #e2e8f0' }}>
                  <th style={{ padding: isMobile ? '8px' : '8px 12px', textAlign: 'left', fontSize: 12, color: '#888', fontWeight: 600 }}>
                    Trace ID
                  </th>
                  {!isMobile && (
                    <th style={{ padding: '8px 12px', textAlign: 'left', fontSize: 12, color: '#888', fontWeight: 600 }}>
                      Root Span
                    </th>
                  )}
                  <th style={{ padding: isMobile ? '8px' : '8px 12px', textAlign: 'center', fontSize: 12, color: '#888', fontWeight: 600 }}>
                    Spans
                  </th>
                  <th style={{ padding: isMobile ? '8px' : '8px 12px', textAlign: 'center', fontSize: 12, color: '#888', fontWeight: 600 }}>
                    Status
                  </th>
                  <th style={{ padding: isMobile ? '8px' : '8px 12px', textAlign: 'right', fontSize: 12, color: '#888', fontWeight: 600 }}>
                    Tokens
                  </th>
                  {!isMobile && (
                    <th style={{ padding: '8px 12px', textAlign: 'right', fontSize: 12, color: '#888', fontWeight: 600 }}>
                      Time
                    </th>
                  )}
                </tr>
              </thead>
              <tbody>
                {sortedTraces.map((t) => (
                  <tr
                    key={t.trace_id}
                    onClick={() => setSelectedTrace(t.trace_id)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        setSelectedTrace(t.trace_id)
                      }
                    }}
                    tabIndex={0}
                    role="button"
                    aria-label={`Open trace ${t.trace_id}`}
                    style={{
                      borderBottom: '1px solid #f0f0f0',
                      cursor: 'pointer',
                      transition: 'background 0.15s',
                      background: t.status === 'ERROR' ? '#fff7f7' : undefined,
                      borderLeft: t.status === 'ERROR' ? '3px solid #ef4444' : '3px solid transparent',
                      outline: 'none',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = t.status === 'ERROR' ? '#ffecec' : '#f8f9fa'
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = t.status === 'ERROR' ? '#fff7f7' : ''
                    }}
                    onFocus={(e) => {
                      e.currentTarget.style.background = t.status === 'ERROR' ? '#ffecec' : '#f8f9fa'
                      e.currentTarget.style.boxShadow = 'inset 0 0 0 2px rgba(59,130,246,0.35)'
                    }}
                    onBlur={(e) => {
                      e.currentTarget.style.background = t.status === 'ERROR' ? '#fff7f7' : ''
                      e.currentTarget.style.boxShadow = ''
                    }}
                  >
                    <td style={{ padding: isMobile ? '10px 8px' : '10px 12px', fontSize: 13, fontFamily: 'monospace', color: '#4a90d9' }}>
                      {t.trace_id.slice(0, isMobile ? 8 : 12)}...
                    </td>
                    {!isMobile && (
                      <td style={{ padding: '10px 12px', fontSize: 13, color: '#1a1a2e' }}>
                        {t.root_span || '—'}
                      </td>
                    )}
                    <td style={{ padding: isMobile ? '10px 8px' : '10px 12px', fontSize: 13, color: '#666', textAlign: 'center' }}>
                      {t.span_count}
                    </td>
                    <td style={{ padding: isMobile ? '10px 8px' : '10px 12px', textAlign: 'center' }}>
                      <StatusBadge status={t.status || 'UNSET'} />
                    </td>
                    <td style={{ padding: isMobile ? '10px 8px' : '10px 12px', fontSize: 12, color: '#444', textAlign: 'right', whiteSpace: 'nowrap' }}>
                      {t.total_tokens.toLocaleString()}
                    </td>
                    {!isMobile && (
                      <td style={{ padding: '10px 12px', fontSize: 12, color: '#888', textAlign: 'right', whiteSpace: 'nowrap' }}>
                        {formatDate(t.start_time)}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
