import React, { useEffect, useState } from 'react'
import { useWizardStore } from '../../store/useWizardStore'

interface PendingQuestion {
  question: string
  question_id: string
  session_id: string
}

export default function AskUserModal() {
  const sseEvents = useWizardStore((s) => s.sseEvents)
  const [pending, setPending] = useState<PendingQuestion | null>(null)
  const [answer, setAnswer] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    const askEvent = sseEvents.find((e) => e.event_type === 'ask_user')
    if (askEvent) {
      setPending(askEvent.payload as PendingQuestion)
    }
  }, [sseEvents])

  const handleSubmit = async () => {
    if (!pending || !answer.trim()) return
    setSubmitting(true)
    await fetch('/api/stream/respond', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: pending.session_id,
        question_id: pending.question_id,
        answer,
      }),
    })
    setPending(null)
    setAnswer('')
    setSubmitting(false)
  }

  if (!pending) return null

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.5)',
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
          boxShadow: '0 20px 60px rgba(0,0,0,0.2)',
        }}
      >
        <h3 style={{ marginBottom: 16, color: '#1a1a2e' }}>Agent Question</h3>
        <p style={{ color: '#555', marginBottom: 20, lineHeight: 1.6 }}>{pending.question}</p>
        <textarea
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          rows={3}
          placeholder="Type your answer..."
          style={{
            width: '100%',
            padding: '10px 14px',
            border: '1px solid #e2e8f0',
            borderRadius: 8,
            fontSize: 14,
            marginBottom: 16,
            resize: 'vertical',
          }}
        />
        <button
          onClick={handleSubmit}
          disabled={submitting || !answer.trim()}
          style={{
            width: '100%',
            padding: '12px',
            borderRadius: 8,
            border: 'none',
            background: '#4a90d9',
            color: 'white',
            fontSize: 15,
            fontWeight: 700,
            cursor: submitting ? 'not-allowed' : 'pointer',
          }}
        >
          {submitting ? 'Submitting...' : 'Submit Answer'}
        </button>
      </div>
    </div>
  )
}
