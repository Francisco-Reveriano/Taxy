import React, { useEffect, useState } from 'react'
import { useWizardStore } from '../../store/useWizardStore'
import {
  downloadFinalForm1040,
  generateAuditReport,
  getForm1040Status,
  getForm1040TemplateFields,
} from '../../services/api'
import ConfidenceGauge from '../ConfidenceGauge'

const FLAG_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  GREEN: { bg: '#f0fdf4', text: '#166534', border: '#22c55e' },
  AMBER: { bg: '#fffbeb', text: '#92400e', border: '#f59e0b' },
  RED: { bg: '#fef2f2', text: '#991b1b', border: '#ef4444' },
  YELLOW: { bg: '#fffbeb', text: '#78350f', border: '#f59e0b' },
}

const FLAG_TOOLTIPS: Record<string, string> = {
  GREEN: 'GREEN: Both AI models agree with high confidence. Low risk.',
  AMBER: 'AMBER: Moderate confidence or minor disagreement. Review recommended.',
  RED: 'RED: Significant disagreement between models. Manual review required.',
  YELLOW: 'YELLOW: One AI model failed. Partial results only.',
}

type Form1040TemplateDiagnostics = {
  template_file?: string
  field_count?: number
  fields?: Array<{ name?: string }>
  semantic_mapping?: {
    required_missing_mapping?: string[]
    resolved_semantic_to_pdf_field?: Record<string, string>
  }
}

export default function Step7Results() {
  const analysisResult = useWizardStore((s) => s.analysisResult)
  const sessionId = useWizardStore((s) => s.sessionId)
  const [acknowledged, setAcknowledged] = useState(false)
  const [ackChecked, setAckChecked] = useState(false)
  const [formStatus, setFormStatus] = useState<{
    success: boolean
    missing_required_fields?: string[]
    error?: string
  } | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const [templateDiagnostics, setTemplateDiagnostics] = useState<Form1040TemplateDiagnostics | null>(null)
  const [diagnosticsLoading, setDiagnosticsLoading] = useState(false)
  const [diagnosticsError, setDiagnosticsError] = useState<string | null>(null)

  useEffect(() => {
    // Use form1040_status from analysis result as initial value if available
    if (analysisResult?.form1040_status) {
      setFormStatus(analysisResult.form1040_status)
    }
    // Also fetch from dedicated endpoint to pick up any server-side updates
    getForm1040Status(sessionId)
      .then((status) => setFormStatus(status))
      .catch(() => {
        if (!analysisResult?.form1040_status) setFormStatus(null)
      })
  }, [sessionId, analysisResult?.form1040_status])

  useEffect(() => {
    if (formStatus?.success === true) {
      setTemplateDiagnostics(null)
      setDiagnosticsError(null)
      setDiagnosticsLoading(false)
      return
    }

    let cancelled = false
    setDiagnosticsLoading(true)
    setDiagnosticsError(null)
    getForm1040TemplateFields()
      .then((payload) => {
        if (!cancelled) setTemplateDiagnostics(payload as Form1040TemplateDiagnostics)
      })
      .catch(() => {
        if (!cancelled) setDiagnosticsError('Unable to load mapping diagnostics right now.')
      })
      .finally(() => {
        if (!cancelled) setDiagnosticsLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [formStatus?.success])

  if (!analysisResult) {
    return (
      <p style={{ color: '#888' }}>
        No analysis results yet. Please complete Step 6 first.
      </p>
    )
  }

  const isRed = analysisResult.flag_status === 'RED'
  const showModal = isRed && !acknowledged

  const handleAcknowledge = async () => {
    try {
      await fetch('/api/audit/acknowledge', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId }),
      })
    } catch {}
    setAcknowledged(true)
  }

  const flagColors = FLAG_COLORS[analysisResult.flag_status] || FLAG_COLORS.AMBER
  const claudeResult = analysisResult.claude_result as Record<string, unknown> | null
  const openaiResult = analysisResult.openai_result as Record<string, unknown> | null
  const requiredMissingMapping = templateDiagnostics?.semantic_mapping?.required_missing_mapping ?? []
  const mappingPreview = Object.entries(
    templateDiagnostics?.semantic_mapping?.resolved_semantic_to_pdf_field ?? {}
  ).slice(0, 6)
  const fieldPreview = (templateDiagnostics?.fields ?? [])
    .map((field) => field.name)
    .filter((name): name is string => Boolean(name))
    .slice(0, 6)

  return (
    <div style={{ position: 'relative' }}>
      {/* RED Flag Acknowledgment Modal */}
      {showModal && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0,0,0,0.6)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
          }}
        >
          <div
            style={{
              background: 'white',
              borderRadius: 12,
              padding: 32,
              maxWidth: 480,
              width: '90%',
              boxShadow: '0 8px 32px rgba(0,0,0,0.2)',
            }}
          >
            <div style={{ fontSize: 32, textAlign: 'center', marginBottom: 16 }}>🚨</div>
            <h3 style={{ textAlign: 'center', color: '#991b1b', marginBottom: 12 }}>
              RED Flag — Significant Discrepancy Detected
            </h3>
            <p style={{ color: '#555', fontSize: 14, marginBottom: 20, lineHeight: 1.6 }}>
              The dual-LLM analysis has identified a significant disagreement between
              Claude and OpenAI results. The liability delta exceeds the 10% threshold.
              Manual review of these results is strongly recommended before proceeding.
            </p>
            <label
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 10,
                marginBottom: 20,
                cursor: 'pointer',
                fontSize: 14,
              }}
            >
              <input
                type="checkbox"
                checked={ackChecked}
                onChange={(e) => setAckChecked(e.target.checked)}
                style={{ marginTop: 3, width: 18, height: 18, accentColor: '#ef4444' }}
              />
              <span>
                I acknowledge the discrepancy and understand that these results require
                manual review before relying on them for tax filing.
              </span>
            </label>
            <button
              onClick={handleAcknowledge}
              disabled={!ackChecked}
              style={{
                width: '100%',
                padding: '12px 24px',
                borderRadius: 8,
                border: 'none',
                background: ackChecked ? '#ef4444' : '#ccc',
                color: 'white',
                fontWeight: 700,
                cursor: ackChecked ? 'pointer' : 'not-allowed',
                fontSize: 15,
              }}
            >
              Continue to Results
            </button>
          </div>
        </div>
      )}

      {/* Flag Banner */}
      <div
        title={FLAG_TOOLTIPS[analysisResult.flag_status] || ''}
        style={{
          padding: '16px 20px',
          borderRadius: 10,
          border: `2px solid ${flagColors.border}`,
          background: flagColors.bg,
          marginBottom: 24,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 24 }}>
            {analysisResult.flag_status === 'GREEN' ? '✅' : analysisResult.flag_status === 'RED' ? '🚨' : '⚠️'}
          </span>
          <div>
            <div style={{ fontWeight: 700, color: flagColors.text, fontSize: 16 }}>
              {analysisResult.flag_status} — {(analysisResult.scoring_rationale ?? '').slice(0, 100)}
            </div>
            {analysisResult.consensus_liability !== null && (
              <div style={{ color: flagColors.text, fontSize: 14, marginTop: 4 }}>
                Estimated Liability: <strong>${analysisResult.consensus_liability?.toLocaleString('en-US', { minimumFractionDigits: 2 })}</strong>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Side-by-side LLM comparison */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 24 }}>
        {/* Claude */}
        <div style={{ border: '1px solid #e2e8f0', borderRadius: 10, padding: 16 }}>
          <h3 style={{ fontSize: 15, marginBottom: 12, color: '#1a1a2e' }}>
            Claude Analysis
          </h3>
          {claudeResult ? (
            <>
              <div style={{ marginBottom: 12 }}>
                <ConfidenceGauge score={Number(claudeResult.confidence_score || 0)} />
              </div>
              <div style={{ fontSize: 13, color: '#555' }}>
                <div><strong>Liability:</strong> ${Number(claudeResult.estimated_liability || 0).toLocaleString()}</div>
                <div><strong>Model:</strong> {String(claudeResult.model_id || 'N/A')}</div>
                {((claudeResult.advisory_notes as string[] | undefined) ?? []).slice(0, 2).map((note, i) => (
                  <div key={i} style={{ marginTop: 6, padding: '4px 8px', background: '#f0f7ff', borderRadius: 4, fontSize: 12 }}>
                    💡 {note}
                  </div>
                ))}
              </div>
            </>
          ) : (
            <p style={{ color: '#888', fontSize: 13 }}>Analysis not available</p>
          )}
        </div>

        {/* OpenAI */}
        <div style={{ border: '1px solid #e2e8f0', borderRadius: 10, padding: 16 }}>
          <h3 style={{ fontSize: 15, marginBottom: 12, color: '#1a1a2e' }}>
            GPT-5 RAG Analysis
          </h3>
          {openaiResult ? (
            <>
              <div style={{ marginBottom: 12 }}>
                <ConfidenceGauge score={Number(openaiResult.confidence_score || 0)} />
              </div>
              <div style={{ fontSize: 13, color: '#555' }}>
                <div><strong>Liability:</strong> ${Number(openaiResult.estimated_liability || 0).toLocaleString()}</div>
                <div><strong>Model:</strong> {String(openaiResult.model_id || 'N/A')}</div>
              </div>
            </>
          ) : (
            <p style={{ color: '#888', fontSize: 13 }}>Analysis not available</p>
          )}
        </div>
      </div>

      {/* Delta */}
      <div style={{ marginBottom: 24, padding: '12px 16px', background: '#f8f9fa', borderRadius: 8, fontSize: 14 }}>
        <strong>Liability Delta:</strong> {(analysisResult.liability_delta ?? 0).toFixed(1)}%
        {' · '}
        <strong>Rationale:</strong> {analysisResult.scoring_rationale ?? 'N/A'}
      </div>

      {/* Actions */}
      {formStatus?.success !== true && (
        <>
          <div
            style={{
              marginBottom: 12,
              padding: '10px 12px',
              borderRadius: 8,
              border: '1px solid #fecaca',
              background: '#fef2f2',
              color: '#991b1b',
              fontSize: 13,
            }}
          >
            Final Form 1040 has not been successfully generated yet.
            {formStatus?.error && (
              <div style={{ marginTop: 6, fontWeight: 600 }}>
                {formStatus.error}
              </div>
            )}
            {formStatus?.missing_required_fields && formStatus.missing_required_fields.length > 0 && (
              <div style={{ marginTop: 6 }}>
                Missing required fields: {formStatus.missing_required_fields.join(', ')}
              </div>
            )}
          </div>

          <div
            style={{
              marginBottom: 16,
              padding: '12px 14px',
              borderRadius: 8,
              border: '1px solid #fcd34d',
              background: '#fffbeb',
              color: '#78350f',
              fontSize: 13,
            }}
          >
            <div style={{ fontWeight: 700, marginBottom: 6 }}>Mapping diagnostics</div>
            {diagnosticsLoading && <div>Loading template diagnostics…</div>}
            {!diagnosticsLoading && diagnosticsError && <div>{diagnosticsError}</div>}
            {!diagnosticsLoading && !diagnosticsError && templateDiagnostics && (
              <>
                <div>
                  Template: <strong>{templateDiagnostics.template_file || 'N/A'}</strong>
                  {' · '}
                  Fields: <strong>{templateDiagnostics.field_count ?? 0}</strong>
                </div>
                <div style={{ marginTop: 6 }}>
                  Required missing mappings:{' '}
                  {requiredMissingMapping.length > 0 ? (
                    <strong>{requiredMissingMapping.join(', ')}</strong>
                  ) : (
                    <strong>none</strong>
                  )}
                </div>
                {mappingPreview.length > 0 && (
                  <div style={{ marginTop: 6 }}>
                    Mapping preview:{' '}
                    {mappingPreview.map(([semantic, field]) => `${semantic} → ${field}`).join(' · ')}
                  </div>
                )}
                {fieldPreview.length > 0 && (
                  <div style={{ marginTop: 6 }}>
                    Template field preview: {fieldPreview.join(', ')}
                  </div>
                )}
              </>
            )}
            {!diagnosticsLoading && !diagnosticsError && !templateDiagnostics && (
              <div>Diagnostics are not available for this template yet.</div>
            )}
            <div style={{ marginTop: 8, opacity: 0.85 }}>
              This panel helps identify unmapped 1040 fields when generation fails.
            </div>
          </div>
        </>
      )}

      <div style={{ display: 'flex', gap: 12 }}>
        <button
          onClick={() => generateAuditReport(sessionId)}
          style={{
            padding: '12px 24px',
            borderRadius: 8,
            border: 'none',
            background: '#1a1a2e',
            color: 'white',
            cursor: 'pointer',
            fontWeight: 600,
          }}
        >
          📄 Generate Audit Report
        </button>
        <button
          onClick={async () => {
            setFormError(null)
            try {
              await downloadFinalForm1040(sessionId)
            } catch (err) {
              setFormError(`Failed to download final 1040: ${err}`)
            }
          }}
          style={{
            padding: '12px 24px',
            borderRadius: 8,
            border: '1px solid #0f766e',
            background: formStatus?.success ? '#0f766e' : '#f0fdfa',
            color: formStatus?.success ? 'white' : '#0f766e',
            cursor: 'pointer',
            fontWeight: 600,
          }}
        >
          🧾 Download Final 1040
        </button>
        <button
          onClick={() => {
            // Switch to the Traces tab in the main app
            const tabBtn = document.querySelector<HTMLButtonElement>('[data-tab="traces"]')
            if (tabBtn) tabBtn.click()
          }}
          style={{
            padding: '12px 24px',
            borderRadius: 8,
            border: '1px solid #4a90d9',
            background: 'white',
            color: '#4a90d9',
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          View Traces
        </button>
      </div>
      {formError && (
        <p style={{ color: '#b91c1c', marginTop: 10, fontSize: 13 }}>{formError}</p>
      )}
    </div>
  )
}
