import React, { useEffect, useState, useCallback } from 'react'
import { useWizardStore, OCRFieldData } from '../../store/useWizardStore'

export default function Step3OCRReview() {
  const documents = useWizardStore((s) => s.documents)
  const sessionId = useWizardStore((s) => s.sessionId)
  const ocrFields = useWizardStore((s) => s.ocrFields)
  const setOcrFields = useWizardStore((s) => s.setOcrFields)
  const ocrReviewComplete = useWizardStore((s) => s.ocrReviewComplete)
  const setOcrReviewComplete = useWizardStore((s) => s.setOcrReviewComplete)

  const [loading, setLoading] = useState<Record<string, boolean>>({})
  const [errors, setErrors] = useState<Record<string, string>>({})

  const runOcr = useCallback(async (fileId: string) => {
    setLoading((p) => ({ ...p, [fileId]: true }))
    setErrors((p) => ({ ...p, [fileId]: '' }))
    try {
      const res = await fetch(`/api/ocr/${fileId}?session_id=${sessionId}`, { method: 'POST' })
      if (!res.ok) throw new Error(`OCR failed: ${res.statusText}`)
      const data = await res.json()
      const fields: OCRFieldData[] = (data.fields || []).map((f: Record<string, unknown>) => ({
        field_name: f.field_name as string,
        field_value: f.field_value as string,
        confidence: f.confidence as number,
        page_number: f.page_number as number,
        is_corrected: (f.is_corrected as boolean) || false,
        display_label: (f.display_label as string) || '',
      }))
      setOcrFields(fileId, fields)
    } catch (e) {
      console.error('OCR failed', e)
      setErrors((p) => ({ ...p, [fileId]: String(e) }))
    }
    setLoading((p) => ({ ...p, [fileId]: false }))
  }, [sessionId, setOcrFields])

  // Auto-trigger OCR on mount for docs that haven't been processed
  useEffect(() => {
    for (const doc of documents) {
      if (!ocrFields[doc.file_id] && !loading[doc.file_id]) {
        runOcr(doc.file_id)
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [documents.length])

  const handleFieldEdit = (fileId: string, fieldName: string, newValue: string) => {
    const current = ocrFields[fileId] || []
    const updated = current.map((f) =>
      f.field_name === fieldName ? { ...f, field_value: newValue, is_corrected: true } : f,
    )
    setOcrFields(fileId, updated)
  }

  const handleConfirm = () => {
    setOcrReviewComplete(true)
  }

  if (documents.length === 0) {
    return <p style={{ color: '#888' }}>No documents uploaded yet. Go back to Step 3.</p>
  }

  // Helper: determine if a field is a W-2 box field vs a passthrough raw line
  const isW2Field = (f: OCRFieldData) => f.field_name.startsWith('w2_')
  const isJunkField = (f: OCRFieldData) =>
    f.field_name.startsWith('line_') && !f.field_value.match(/\d{2,}/)

  // Format currency values
  const formatValue = (value: string) => {
    const num = parseFloat(value.replace(/,/g, ''))
    if (!isNaN(num) && value.match(/^\d+\.?\d*$/)) {
      return `$${num.toLocaleString('en-US', { minimumFractionDigits: 2 })}`
    }
    return value
  }

  const hasAnyFields = documents.some((doc) => (ocrFields[doc.file_id] || []).length > 0)

  return (
    <div>
      {documents.map((doc) => {
        const fields = ocrFields[doc.file_id] || []
        const w2Fields = fields.filter(isW2Field)
        const otherFields = fields.filter((f) => !isW2Field(f) && !isJunkField(f))
        const displayFields = [...w2Fields, ...otherFields]

        return (
          <div key={doc.file_id} style={{ marginBottom: 24 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
              <h3 style={{ fontSize: 15, color: '#333', margin: 0 }}>{doc.original_filename}</h3>
              <button
                onClick={() => runOcr(doc.file_id)}
                disabled={loading[doc.file_id]}
                style={{
                  padding: '6px 14px',
                  borderRadius: 6,
                  border: 'none',
                  background: '#4a90d9',
                  color: 'white',
                  cursor: loading[doc.file_id] ? 'not-allowed' : 'pointer',
                  fontSize: 13,
                }}
              >
                {loading[doc.file_id] ? 'Processing...' : fields.length > 0 ? 'Re-run OCR' : 'Run OCR'}
              </button>
            </div>

            {errors[doc.file_id] && (
              <p style={{ color: '#b91c1c', fontSize: 13 }}>{errors[doc.file_id]}</p>
            )}

            {loading[doc.file_id] && !fields.length && (
              <div style={{ padding: 16, color: '#666', fontSize: 14 }}>
                Running OCR with 10 concurrent passes + LLM extraction... this may take a moment.
              </div>
            )}

            {displayFields.length > 0 && (
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  <tr style={{ background: '#f0f4f8' }}>
                    <th style={{ padding: '8px 12px', textAlign: 'left', border: '1px solid #e2e8f0' }}>
                      Field
                    </th>
                    <th style={{ padding: '8px 12px', textAlign: 'left', border: '1px solid #e2e8f0' }}>
                      Value
                    </th>
                    <th
                      style={{ padding: '8px 12px', textAlign: 'center', border: '1px solid #e2e8f0', width: 90 }}
                      title="OCR confidence score: >=85% is high, <85% flagged for review"
                    >
                      Confidence
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {displayFields.map((field) => (
                    <tr
                      key={field.field_name}
                      style={{
                        background: field.confidence < 0.85 ? '#fff8e1' : 'white',
                      }}
                    >
                      <td
                        style={{
                          padding: '8px 12px',
                          border: '1px solid #e2e8f0',
                          color: '#555',
                          fontWeight: isW2Field(field) ? 600 : 400,
                        }}
                      >
                        {field.display_label || field.field_name}
                      </td>
                      <td style={{ padding: '8px 12px', border: '1px solid #e2e8f0' }}>
                        <input
                          value={field.field_value}
                          onChange={(e) =>
                            handleFieldEdit(doc.file_id, field.field_name, e.target.value)
                          }
                          style={{
                            width: '100%',
                            border: field.is_corrected
                              ? '1px solid #f39c12'
                              : '1px solid transparent',
                            padding: '4px 8px',
                            borderRadius: 4,
                            background: field.is_corrected ? '#fff8e1' : 'transparent',
                            fontFamily: isW2Field(field) ? 'monospace' : 'inherit',
                          }}
                        />
                      </td>
                      <td
                        style={{
                          padding: '8px 12px',
                          border: '1px solid #e2e8f0',
                          textAlign: 'center',
                        }}
                      >
                        <span
                          title={
                            field.confidence >= 0.85
                              ? 'High confidence — likely accurate'
                              : 'Low confidence — please verify this value'
                          }
                          style={{
                            color: field.confidence >= 0.95
                              ? '#16a34a'
                              : field.confidence >= 0.85
                                ? '#27ae60'
                                : '#e67e22',
                            fontWeight: 600,
                          }}
                        >
                          {(field.confidence * 100).toFixed(0)}%
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )
      })}

      {/* Confirm OCR Review button */}
      {hasAnyFields && (
        <div style={{ marginTop: 16, display: 'flex', alignItems: 'center', gap: 12 }}>
          <button
            onClick={handleConfirm}
            disabled={ocrReviewComplete}
            style={{
              padding: '12px 28px',
              borderRadius: 8,
              border: 'none',
              background: ocrReviewComplete ? '#86efac' : '#16a34a',
              color: 'white',
              cursor: ocrReviewComplete ? 'default' : 'pointer',
              fontWeight: 700,
              fontSize: 15,
            }}
          >
            {ocrReviewComplete ? 'OCR Review Confirmed' : 'Confirm OCR Review'}
          </button>
          {!ocrReviewComplete && (
            <span style={{ fontSize: 13, color: '#666' }}>
              Confirm to proceed to Income Summary and Analysis steps
            </span>
          )}
        </div>
      )}
    </div>
  )
}
