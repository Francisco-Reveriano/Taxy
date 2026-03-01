import React, { useState, useMemo, useRef, useEffect } from 'react'
import { useWizardStore, SSEEventRecord } from '../../store/useWizardStore'
import { startAgentChat } from '../../services/api'

interface ProgressStep {
  key: string
  label: string
  icon: string
}

const ANALYSIS_STEPS: ProgressStep[] = [
  { key: 'dual_llm', label: 'Dual-LLM Analysis', icon: '🤖' },
  { key: 'scoring', label: 'Scoring & Comparison', icon: '⚖️' },
  { key: 'form1040', label: 'Form 1040 Generation', icon: '📄' },
  { key: 'complete', label: 'Complete', icon: '✅' },
]

const ACTIVITY_EVENT_TYPES = new Set(['thought', 'tool_call', 'tool_result', 'answer', 'error'])

const BADGE_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  tool_call:   { bg: '#dbeafe', text: '#1d4ed8', label: 'Tool Call' },
  tool_result: { bg: '#d1fae5', text: '#065f46', label: 'Result' },
  thought:     { bg: '#fef3c7', text: '#92400e', label: 'Thought' },
  answer:      { bg: '#ede9fe', text: '#5b21b6', label: 'Answer' },
  error:       { bg: '#fee2e2', text: '#991b1b', label: 'Error' },
}

function formatRelativeTime(ts: number): string {
  const delta = Math.max(0, Math.floor((Date.now() - ts) / 1000))
  if (delta < 2) return 'just now'
  if (delta < 60) return `${delta}s ago`
  return `${Math.floor(delta / 60)}m ago`
}

function ActivityEntry({ ev }: { ev: SSEEventRecord }) {
  const [expanded, setExpanded] = useState(false)
  const badge = BADGE_STYLES[ev.event_type] || BADGE_STYLES.thought
  const payload = ev.payload as Record<string, unknown> | undefined
  const summary = String(payload?.summary ?? '')
  const isLong = summary.length > 200

  return (
    <div
      style={{
        display: 'flex',
        gap: 10,
        padding: '8px 12px',
        borderBottom: '1px solid #f1f5f9',
        fontSize: 13,
        lineHeight: 1.45,
      }}
    >
      <span
        style={{
          flexShrink: 0,
          padding: '2px 8px',
          borderRadius: 4,
          fontSize: 11,
          fontWeight: 600,
          background: badge.bg,
          color: badge.text,
          alignSelf: 'flex-start',
          marginTop: 1,
        }}
      >
        {badge.label}
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <span style={{ color: ev.event_type === 'error' ? '#991b1b' : '#334155' }}>
          {isLong && !expanded ? summary.slice(0, 200) + '...' : summary}
        </span>
        {isLong && (
          <button
            onClick={() => setExpanded(!expanded)}
            style={{
              marginLeft: 6,
              background: 'none',
              border: 'none',
              color: '#3b82f6',
              cursor: 'pointer',
              fontSize: 11,
              padding: 0,
            }}
          >
            {expanded ? 'less' : 'more'}
          </button>
        )}
      </div>
      <span style={{ flexShrink: 0, fontSize: 11, color: '#94a3b8', whiteSpace: 'nowrap' }}>
        {formatRelativeTime(ev.timestamp)}
      </span>
    </div>
  )
}

export default function Step6Analysis() {
  const sessionId = useWizardStore((s) => s.sessionId)
  const filingStatus = useWizardStore((s) => s.filingStatus)
  const taxpayerInfo = useWizardStore((s) => s.taxpayerInfo)
  const incomeSummary = useWizardStore((s) => s.incomeSummary)
  const deductionChoice = useWizardStore((s) => s.deductionChoice)
  const itemizedTotal = useWizardStore((s) => s.itemizedTotal)
  const selectedCredits = useWizardStore((s) => s.selectedCredits)
  const setAnalysisResult = useWizardStore((s) => s.setAnalysisResult)
  const setIsAnalyzing = useWizardStore((s) => s.setIsAnalyzing)
  const isAnalyzing = useWizardStore((s) => s.isAnalyzing)
  const analysisResult = useWizardStore((s) => s.analysisResult)
  const sseEvents = useWizardStore((s) => s.sseEvents)
  const nextStep = useWizardStore((s) => s.nextStep)
  const [error, setError] = useState<string | null>(null)
  const [logCollapsed, setLogCollapsed] = useState(false)
  const logEndRef = useRef<HTMLDivElement>(null)

  // Extract analysis_progress events from SSE
  const progressEvents = useMemo(() => {
    const map: Record<string, { status: string; detail: string }> = {}
    for (const ev of sseEvents) {
      if (ev.event_type === 'analysis_progress') {
        const p = ev.payload as { step?: string; status?: string; detail?: string }
        if (p.step) {
          map[p.step] = { status: p.status || '', detail: p.detail || '' }
        }
      }
    }
    return map
  }, [sseEvents])

  const activityEvents = useMemo(() => {
    return sseEvents
      .filter((ev) => ACTIVITY_EVENT_TYPES.has(ev.event_type))
      .slice(0, 30)
  }, [sseEvents])

  useEffect(() => {
    if (!logCollapsed && logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [activityEvents.length, logCollapsed])

  const handleRunAnalysis = async () => {
    setIsAnalyzing(true)
    setError(null)
    setLogCollapsed(false)
    try {
      const taxData = {
        first_name: taxpayerInfo.firstName,
        last_name: taxpayerInfo.lastName,
        ssn: taxpayerInfo.ssn,
        address: taxpayerInfo.address,
        city: taxpayerInfo.city,
        state: taxpayerInfo.state,
        zip: taxpayerInfo.zip,
        dependents: taxpayerInfo.dependents,
        filing_status: filingStatus || 'Single',
        tax_year: 2025,
        total_income: incomeSummary.totalIncome,
        wages: incomeSummary.wages,
        federal_tax_withheld: incomeSummary.federalWithheld,
        ss_wages: incomeSummary.ssWages,
        medicare_wages: incomeSummary.medicareWages,
        other_income: incomeSummary.otherIncome,
        deduction_type: deductionChoice || 'standard',
        itemized_deductions: deductionChoice === 'itemized' ? itemizedTotal : 0,
        credits: selectedCredits,
      }
      const message =
        `Analyze the following taxpayer data, compute their tax liability, ` +
        `ask any clarifying questions needed, and generate a filled Form 1040 PDF.\n\n` +
        `Taxpayer Data:\n${JSON.stringify(taxData, null, 2)}`
      await startAgentChat(sessionId, message)
    } catch (err) {
      setError(`Analysis failed: ${err}`)
      setIsAnalyzing(false)
    }
  }

  const isComplete = !!analysisResult
  const hasStarted = isAnalyzing || isComplete

  return (
    <div>
      {/* Pre-analysis: Show summary and run button */}
      {!hasStarted && (
        <div style={{ textAlign: 'center', padding: 32 }}>
          <p style={{ color: '#555', marginBottom: 8, fontSize: 15 }}>
            Ready to analyze your tax situation with dual AI models.
          </p>
          <p style={{ color: '#888', fontSize: 13, marginBottom: 24 }}>
            Claude and GPT-5 will independently compute your tax liability using IRS RAG, then results are compared for accuracy.
          </p>
          <button
            onClick={handleRunAnalysis}
            style={{
              padding: '14px 32px',
              borderRadius: 10,
              border: 'none',
              background: '#4a90d9',
              color: 'white',
              fontSize: 16,
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            Run Analysis
          </button>
        </div>
      )}

      {error && <p style={{ color: '#e74c3c', marginBottom: 16 }}>{error}</p>}

      {/* Progress Steps */}
      {hasStarted && (
        <div style={{ maxWidth: 560, margin: '0 auto' }}>
          {ANALYSIS_STEPS.map((step) => {
            const progress = progressEvents[step.key]
            const isDone = progress?.status === 'done'
            const isRunning = progress?.status === 'running'
            const isFailed = progress?.status === 'failed'

            return (
              <div
                key={step.key}
                style={{
                  display: 'flex',
                  gap: 14,
                  padding: '14px 16px',
                  borderRadius: 10,
                  marginBottom: 8,
                  border: `1px solid ${isRunning ? '#4a90d9' : isDone ? '#22c55e' : isFailed ? '#ef4444' : '#e2e8f0'}`,
                  background: isRunning ? '#eff6ff' : isDone ? '#f0fdf4' : isFailed ? '#fef2f2' : '#fafafa',
                  transition: 'all 0.3s ease',
                }}
              >
                {/* Status icon */}
                <div style={{ fontSize: 22, width: 32, textAlign: 'center', flexShrink: 0 }}>
                  {isRunning ? (
                    <span style={{ display: 'inline-block', animation: 'spin 1s linear infinite' }}>⏳</span>
                  ) : isDone ? (
                    '✅'
                  ) : isFailed ? (
                    '❌'
                  ) : (
                    <span style={{ opacity: 0.3 }}>{step.icon}</span>
                  )}
                </div>

                {/* Content */}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div
                    style={{
                      fontWeight: 600,
                      fontSize: 14,
                      color: isRunning ? '#1d4ed8' : isDone ? '#166534' : isFailed ? '#991b1b' : '#888',
                    }}
                  >
                    {step.label}
                  </div>
                  {progress?.detail && (
                    <div
                      style={{
                        fontSize: 12,
                        color: isRunning ? '#3b82f6' : isDone ? '#16a34a' : isFailed ? '#b91c1c' : '#999',
                        marginTop: 2,
                      }}
                    >
                      {progress.detail}
                    </div>
                  )}
                  {isRunning && (
                    <div
                      style={{
                        marginTop: 6,
                        height: 3,
                        borderRadius: 2,
                        background: '#dbeafe',
                        overflow: 'hidden',
                      }}
                    >
                      <div
                        style={{
                          height: '100%',
                          width: '40%',
                          background: '#3b82f6',
                          borderRadius: 2,
                          animation: 'progressSlide 1.5s ease-in-out infinite',
                        }}
                      />
                    </div>
                  )}
                </div>
              </div>
            )
          })}

          {/* Activity Log */}
          {activityEvents.length > 0 && (
            <div
              style={{
                marginTop: 12,
                border: '1px solid #e2e8f0',
                borderRadius: 10,
                overflow: 'hidden',
                background: '#fafbfc',
              }}
            >
              <button
                onClick={() => setLogCollapsed((v) => !v)}
                style={{
                  width: '100%',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '10px 14px',
                  background: '#f8fafc',
                  border: 'none',
                  borderBottom: logCollapsed ? 'none' : '1px solid #e2e8f0',
                  cursor: 'pointer',
                  fontSize: 13,
                  fontWeight: 600,
                  color: '#475569',
                }}
              >
                <span>Activity Log ({activityEvents.length})</span>
                <span style={{ fontSize: 11, color: '#94a3b8' }}>
                  {logCollapsed ? '▸ show' : '▾ hide'}
                </span>
              </button>
              {!logCollapsed && (
                <div style={{ maxHeight: 280, overflowY: 'auto' }}>
                  {[...activityEvents].reverse().map((ev) => (
                    <ActivityEntry key={ev.id} ev={ev} />
                  ))}
                  <div ref={logEndRef} />
                </div>
              )}
            </div>
          )}

          {/* CSS animation for spinner and progress bar */}
          <style>{`
            @keyframes spin {
              from { transform: rotate(0deg); }
              to { transform: rotate(360deg); }
            }
            @keyframes progressSlide {
              0% { transform: translateX(-100%); }
              50% { transform: translateX(150%); }
              100% { transform: translateX(300%); }
            }
          `}</style>
        </div>
      )}

      {/* Completion Summary */}
      {isComplete && (
        <div
          style={{
            marginTop: 20,
            padding: '20px 24px',
            borderRadius: 12,
            background: '#f0f9ff',
            border: '1px solid #bae6fd',
            textAlign: 'center',
          }}
        >
          <div style={{ fontSize: 28, marginBottom: 8 }}>🎉</div>
          <div style={{ fontWeight: 700, fontSize: 16, color: '#0c4a6e', marginBottom: 6 }}>
            Analysis Complete
          </div>
          <p style={{ color: '#0369a1', fontSize: 14, margin: 0 }}>
            Your tax analysis has finished. View detailed results including the dual-LLM comparison,
            confidence scores, and your generated Form 1040 in the next step.
          </p>
          <button
            onClick={() => nextStep()}
            style={{
              marginTop: 16,
              padding: '12px 32px',
              borderRadius: 8,
              border: 'none',
              background: '#0ea5e9',
              color: 'white',
              fontSize: 15,
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            View Results →
          </button>
        </div>
      )}
    </div>
  )
}
