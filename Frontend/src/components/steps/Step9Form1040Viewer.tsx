import React, { useEffect, useRef, useState } from 'react'
import { useWizardStore } from '../../store/useWizardStore'
import { downloadFinalForm1040, getForm1040Status } from '../../services/api'

export default function Step9Form1040Viewer() {
  const sessionId = useWizardStore((s) => s.sessionId)
  const form1040Ready = useWizardStore((s) => s.form1040Ready)
  const iframeRef = useRef<HTMLIFrameElement>(null)
  const [ready, setReady] = useState<boolean | null>(form1040Ready ? true : null)
  const [downloading, setDownloading] = useState(false)

  const pdfUrl = `/api/forms/1040/${sessionId}`

  useEffect(() => {
    // If store already knows it's ready (from SSE tool_result), skip API call
    if (form1040Ready) {
      setReady(true)
      return
    }
    // Fallback: check API (handles page refresh where store is reset)
    getForm1040Status(sessionId)
      .then((status) => setReady(status?.success === true))
      .catch(() => setReady(false))
  }, [sessionId, form1040Ready])

  const handleDownload = async () => {
    setDownloading(true)
    try {
      await downloadFinalForm1040(sessionId)
    } catch {}
    setDownloading(false)
  }

  const handleFullScreen = () => {
    iframeRef.current?.requestFullscreen?.()
  }

  if (ready === null) {
    return (
      <div style={{ textAlign: 'center', padding: 48, color: '#888' }}>
        Loading Form 1040...
      </div>
    )
  }

  if (!ready) {
    return (
      <div style={{ textAlign: 'center', padding: 48 }}>
        <p style={{ color: '#991b1b', fontSize: 15, marginBottom: 12 }}>
          Form 1040 has not been generated yet.
        </p>
        <p style={{ color: '#666', fontSize: 13 }}>
          Go back to the Analysis step and run the analysis to generate your Form 1040.
        </p>
      </div>
    )
  }

  return (
    <div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'flex-end',
          gap: 10,
          marginBottom: 16,
        }}
      >
        <button
          onClick={handleDownload}
          disabled={downloading}
          style={{
            padding: '10px 22px',
            borderRadius: 8,
            border: 'none',
            background: '#0f766e',
            color: 'white',
            fontWeight: 600,
            fontSize: 14,
            cursor: downloading ? 'wait' : 'pointer',
          }}
        >
          {downloading ? 'Downloading...' : 'Download PDF'}
        </button>
        <button
          onClick={handleFullScreen}
          style={{
            padding: '10px 22px',
            borderRadius: 8,
            border: '1px solid #4a90d9',
            background: 'white',
            color: '#4a90d9',
            fontWeight: 600,
            fontSize: 14,
            cursor: 'pointer',
          }}
        >
          Full Screen
        </button>
      </div>

      <iframe
        ref={iframeRef}
        src={pdfUrl}
        title="Form 1040"
        style={{
          width: '100%',
          height: 650,
          border: '1px solid #e2e8f0',
          borderRadius: 10,
          background: '#f8fafc',
        }}
      />
    </div>
  )
}
