import React, { useEffect, useState } from 'react'
import { useWizardStore } from '../../store/useWizardStore'

interface OCRField {
  field_name: string
  field_value: string
  confidence: number
  page_number: number
  is_corrected: boolean
}

export default function Step3OCRReview() {
  const documents = useWizardStore((s) => s.documents)
  const sessionId = useWizardStore((s) => s.sessionId)
  const [ocrData, setOcrData] = useState<Record<string, OCRField[]>>({})
  const [loading, setLoading] = useState<Record<string, boolean>>({})

  const runOcr = async (fileId: string) => {
    setLoading((p) => ({ ...p, [fileId]: true }))
    try {
      const res = await fetch(`/api/ocr/${fileId}?session_id=${sessionId}`, { method: 'POST' })
      const data = await res.json()
      setOcrData((p) => ({ ...p, [fileId]: data.fields || [] }))
    } catch (e) {
      console.error('OCR failed', e)
    }
    setLoading((p) => ({ ...p, [fileId]: false }))
  }

  const handleFieldEdit = (fileId: string, fieldName: string, newValue: string) => {
    setOcrData((prev) => ({
      ...prev,
      [fileId]: prev[fileId].map((f) =>
        f.field_name === fieldName ? { ...f, field_value: newValue, is_corrected: true } : f,
      ),
    }))
  }

  if (documents.length === 0) {
    return <p style={{ color: '#888' }}>No documents uploaded yet. Go back to Step 2.</p>
  }

  return (
    <div>
      {documents.map((doc) => (
        <div key={doc.file_id} style={{ marginBottom: 24 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
            <h3 style={{ fontSize: 15, color: '#333' }}>{doc.original_filename}</h3>
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
              {loading[doc.file_id] ? 'Processing...' : 'Run OCR'}
            </button>
          </div>

          {ocrData[doc.file_id] && (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ background: '#f0f4f8' }}>
                  <th style={{ padding: '8px 12px', textAlign: 'left', border: '1px solid #e2e8f0' }}>Field</th>
                  <th style={{ padding: '8px 12px', textAlign: 'left', border: '1px solid #e2e8f0' }}>Value</th>
                  <th
                    style={{ padding: '8px 12px', textAlign: 'center', border: '1px solid #e2e8f0' }}
                    title="OCR confidence score: >=85% is high, <85% flagged for review"
                  >Confidence</th>
                </tr>
              </thead>
              <tbody>
                {ocrData[doc.file_id].map((field) => (
                  <tr
                    key={field.field_name}
                    style={{ background: field.confidence < 0.85 ? '#fff8e1' : 'white' }}
                  >
                    <td style={{ padding: '8px 12px', border: '1px solid #e2e8f0', color: '#555' }}>
                      {field.field_name}
                    </td>
                    <td style={{ padding: '8px 12px', border: '1px solid #e2e8f0' }}>
                      <input
                        value={field.field_value}
                        onChange={(e) => handleFieldEdit(doc.file_id, field.field_name, e.target.value)}
                        style={{
                          width: '100%',
                          border: field.is_corrected ? '1px solid #f39c12' : '1px solid transparent',
                          padding: '4px 8px',
                          borderRadius: 4,
                          background: field.is_corrected ? '#fff8e1' : 'transparent',
                        }}
                      />
                    </td>
                    <td style={{ padding: '8px 12px', border: '1px solid #e2e8f0', textAlign: 'center' }}>
                      <span
                        title={field.confidence >= 0.85 ? 'High confidence — likely accurate' : 'Low confidence — please verify this value'}
                        style={{
                          color: field.confidence >= 0.85 ? '#27ae60' : '#e67e22',
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
      ))}
    </div>
  )
}
