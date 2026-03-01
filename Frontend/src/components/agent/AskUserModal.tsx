import React, { useEffect, useState } from 'react'
import { useWizardStore } from '../../store/useWizardStore'

interface PendingQuestion {
  question: string
  question_id: string
  session_id: string
  options?: string[]
}

function renderMarkdown(text: string): React.ReactNode[] {
  const lines = text.split('\n')
  const nodes: React.ReactNode[] = []
  let listItems: React.ReactNode[] = []
  let listType: 'ol' | 'ul' | null = null

  const flushList = () => {
    if (listItems.length > 0 && listType) {
      const Tag = listType
      nodes.push(
        <Tag key={`list-${nodes.length}`} style={{ margin: '8px 0', paddingLeft: 24, color: '#334155' }}>
          {listItems}
        </Tag>
      )
      listItems = []
      listType = null
    }
  }

  const inlineFormat = (str: string): React.ReactNode[] => {
    const parts: React.ReactNode[] = []
    const regex = /\*\*(.+?)\*\*/g
    let last = 0
    let match: RegExpExecArray | null
    while ((match = regex.exec(str)) !== null) {
      if (match.index > last) parts.push(str.slice(last, match.index))
      parts.push(<strong key={`b-${match.index}`}>{match[1]}</strong>)
      last = match.index + match[0].length
    }
    if (last < str.length) parts.push(str.slice(last))
    return parts
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const olMatch = line.match(/^\s*(\d+)[.)]\s+(.*)/)
    const ulMatch = !olMatch && line.match(/^\s*[-*]\s+(.*)/)

    if (olMatch) {
      if (listType !== 'ol') { flushList(); listType = 'ol' }
      listItems.push(<li key={`li-${i}`} style={{ marginBottom: 4, lineHeight: 1.5 }}>{inlineFormat(olMatch[2])}</li>)
    } else if (ulMatch) {
      if (listType !== 'ul') { flushList(); listType = 'ul' }
      listItems.push(<li key={`li-${i}`} style={{ marginBottom: 4, lineHeight: 1.5 }}>{inlineFormat(ulMatch[1])}</li>)
    } else {
      flushList()
      const trimmed = line.trim()
      if (trimmed) {
        nodes.push(<p key={`p-${i}`} style={{ margin: '6px 0', lineHeight: 1.6, color: '#334155' }}>{inlineFormat(trimmed)}</p>)
      }
    }
  }
  flushList()
  return nodes
}

export default function AskUserModal() {
  const sseEvents = useWizardStore((s) => s.sseEvents)
  const [pending, setPending] = useState<PendingQuestion | null>(null)
  const [answer, setAnswer] = useState('')
  const [selectedOption, setSelectedOption] = useState<string | null>(null)
  const [isOther, setIsOther] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [answeredIds, setAnsweredIds] = useState<Set<string>>(new Set())

  useEffect(() => {
    const hasAnswer = sseEvents.some((e) => e.event_type === 'answer')
    if (hasAnswer) {
      setPending(null)
      return
    }

    const askEvent = sseEvents.find(
      (e) => e.event_type === 'ask_user' &&
        !answeredIds.has((e.payload as PendingQuestion)?.question_id)
    )
    if (askEvent) {
      const payload = askEvent.payload as PendingQuestion
      if (pending?.question_id !== payload.question_id) {
        setPending(payload)
        setSelectedOption(null)
        setIsOther(false)
        setAnswer('')
      }
    }
  }, [sseEvents, answeredIds])

  const effectiveAnswer = pending?.options
    ? (isOther ? answer : selectedOption || '')
    : answer

  const handleSubmit = async () => {
    if (!pending || !effectiveAnswer.trim()) return
    setSubmitting(true)
    const qid = pending.question_id
    await fetch('/api/stream/respond', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: pending.session_id,
        question_id: qid,
        answer: effectiveAnswer,
      }),
    })
    setAnsweredIds((prev) => new Set(prev).add(qid))
    setPending(null)
    setAnswer('')
    setSelectedOption(null)
    setIsOther(false)
    setSubmitting(false)
  }

  if (!pending) return null

  const hasOptions = pending.options && pending.options.length > 0

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
          maxWidth: 540,
          width: '90%',
          maxHeight: '80vh',
          overflowY: 'auto',
          boxShadow: '0 20px 60px rgba(0,0,0,0.2)',
        }}
      >
        <h3 style={{ marginBottom: 12, color: '#1a1a2e', fontSize: 17 }}>Agent Question</h3>
        <div style={{ marginBottom: 20, fontSize: 14 }}>
          {renderMarkdown(pending.question)}
        </div>

        {hasOptions ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 16 }}>
            {pending.options!.map((opt) => (
              <label
                key={opt}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: '10px 14px',
                  border: `2px solid ${selectedOption === opt && !isOther ? '#4a90d9' : '#e2e8f0'}`,
                  borderRadius: 8,
                  cursor: 'pointer',
                  background: selectedOption === opt && !isOther ? '#f0f7ff' : 'white',
                }}
              >
                <input
                  type="radio"
                  name="ask-user-option"
                  checked={selectedOption === opt && !isOther}
                  onChange={() => { setSelectedOption(opt); setIsOther(false) }}
                  style={{ width: 18, height: 18, accentColor: '#4a90d9' }}
                />
                <span style={{ fontSize: 14 }}>{opt}</span>
              </label>
            ))}
            <label
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '10px 14px',
                border: `2px solid ${isOther ? '#4a90d9' : '#e2e8f0'}`,
                borderRadius: 8,
                cursor: 'pointer',
                background: isOther ? '#f0f7ff' : 'white',
              }}
            >
              <input
                type="radio"
                name="ask-user-option"
                checked={isOther}
                onChange={() => { setIsOther(true); setSelectedOption(null) }}
                style={{ width: 18, height: 18, accentColor: '#4a90d9' }}
              />
              <span style={{ fontSize: 14 }}>Other</span>
            </label>
            {isOther && (
              <textarea
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                rows={2}
                placeholder="Type your answer..."
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  border: '1px solid #e2e8f0',
                  borderRadius: 8,
                  fontSize: 14,
                  resize: 'vertical',
                  boxSizing: 'border-box',
                }}
              />
            )}
          </div>
        ) : (
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
              boxSizing: 'border-box',
            }}
          />
        )}

        <button
          onClick={handleSubmit}
          disabled={submitting || !effectiveAnswer.trim()}
          style={{
            width: '100%',
            padding: '12px',
            borderRadius: 8,
            border: 'none',
            background: submitting || !effectiveAnswer.trim() ? '#ccc' : '#4a90d9',
            color: 'white',
            fontSize: 15,
            fontWeight: 700,
            cursor: submitting || !effectiveAnswer.trim() ? 'not-allowed' : 'pointer',
          }}
        >
          {submitting ? 'Submitting...' : 'Submit Answer'}
        </button>
      </div>
    </div>
  )
}
