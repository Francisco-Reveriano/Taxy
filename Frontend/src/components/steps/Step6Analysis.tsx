import React, { useState } from 'react'
import { useWizardStore } from '../../store/useWizardStore'
import { runAnalysis } from '../../services/api'

export default function Step6Analysis() {
  const sessionId = useWizardStore((s) => s.sessionId)
  const filingStatus = useWizardStore((s) => s.filingStatus)
  const setAnalysisResult = useWizardStore((s) => s.setAnalysisResult)
  const setIsAnalyzing = useWizardStore((s) => s.setIsAnalyzing)
  const isAnalyzing = useWizardStore((s) => s.isAnalyzing)
  const sseEvents = useWizardStore((s) => s.sseEvents)
  const [error, setError] = useState<string | null>(null)
  const [showThinking, setShowThinking] = useState(false)

  const handleRunAnalysis = async () => {
    setIsAnalyzing(true)
    setError(null)
    try {
      const taxData = {
        filing_status: filingStatus || 'Single',
        tax_year: 2025,
        total_income: 55000,
        wages: 55000,
        other_income: 0,
        itemized_deductions: 0,
        credits: [],
      }
      const result = await runAnalysis(sessionId, taxData)
      setAnalysisResult(result)
    } catch (err) {
      setError(`Analysis failed: ${err}`)
    }
    setIsAnalyzing(false)
  }

  const toolCallEvents = sseEvents.filter((e) => e.event_type === 'tool_call' || e.event_type === 'tool_result')
  const thoughtEvents = sseEvents.filter((e) => e.event_type === 'thought')

  return (
    <div>
      {!isAnalyzing && sseEvents.length === 0 && (
        <div style={{ textAlign: 'center', padding: 32 }}>
          <p style={{ color: '#555', marginBottom: 20 }}>
            Ready to analyze your tax situation with dual AI models (Claude + GPT-5).
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

      {isAnalyzing && (
        <div style={{ textAlign: 'center', padding: 24 }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>⚙️</div>
          <p style={{ color: '#4a90d9', fontWeight: 600 }}>Analyzing your tax situation...</p>
          <p style={{ color: '#888', fontSize: 13, marginTop: 4 }}>Running dual LLM analysis with IRS RAG</p>
        </div>
      )}

      {error && <p style={{ color: '#e74c3c', marginBottom: 16 }}>{error}</p>}

      {/* SSE Event Timeline */}
      {sseEvents.length > 0 && (
        <div style={{ marginTop: 24 }}>
          <h3 style={{ fontSize: 14, color: '#333', marginBottom: 8 }}>Agent Activity</h3>
          <div style={{ maxHeight: 300, overflowY: 'auto', border: '1px solid #e2e8f0', borderRadius: 8 }}>
            {sseEvents.slice(0, 20).map((ev, i) => (
              <div
                key={i}
                style={{
                  display: 'flex',
                  gap: 10,
                  padding: '8px 12px',
                  borderBottom: '1px solid #f0f0f0',
                  fontSize: 13,
                }}
              >
                <span
                  style={{
                    padding: '2px 8px',
                    borderRadius: 4,
                    fontSize: 11,
                    fontWeight: 600,
                    background: ev.event_type === 'tool_call' ? '#e3f2fd' : ev.event_type === 'tool_result' ? '#e8f5e9' : '#f3e5f5',
                    color: ev.event_type === 'tool_call' ? '#1565c0' : ev.event_type === 'tool_result' ? '#2e7d32' : '#6a1b9a',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {ev.event_type}
                </span>
                <span style={{ color: '#555', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {typeof ev.payload === 'object' ? JSON.stringify(ev.payload).slice(0, 80) : String(ev.payload)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Thinking panel */}
      {thoughtEvents.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <button
            onClick={() => setShowThinking(!showThinking)}
            style={{ background: 'none', border: '1px solid #e2e8f0', padding: '6px 14px', borderRadius: 6, cursor: 'pointer', fontSize: 13 }}
          >
            {showThinking ? 'Hide' : 'Show'} Agent Thinking ({thoughtEvents.length})
          </button>
          {showThinking && (
            <div style={{ marginTop: 8, padding: 12, background: '#f8f8f8', borderRadius: 8, fontSize: 12, fontFamily: 'monospace', maxHeight: 200, overflowY: 'auto' }}>
              {thoughtEvents.map((ev, i) => (
                <div key={i} style={{ marginBottom: 8, color: '#555' }}>
                  {String(ev.payload).slice(0, 300)}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
