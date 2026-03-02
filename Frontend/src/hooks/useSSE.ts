import { useEffect, useRef } from 'react'
import { useWizardStore } from '../store/useWizardStore'
import { getForm1040Status } from '../services/api'

export default function useSSE(sessionId: string) {
  const addSSEEvent = useWizardStore((s) => s.addSSEEvent)
  const setTodoItems = useWizardStore((s) => s.setTodoItems)
  const setAnalysisResult = useWizardStore((s) => s.setAnalysisResult)
  const setIsAnalyzing = useWizardStore((s) => s.setIsAnalyzing)
  const setCurrentStep = useWizardStore((s) => s.setCurrentStep)
  const setForm1040Ready = useWizardStore((s) => s.setForm1040Ready)
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    if (!sessionId) return

    let reconnectTimer: ReturnType<typeof setTimeout> | null = null
    let streamDone = false

    const connect = () => {
      const es = new EventSource(`/api/stream?session_id=${sessionId}`)
      esRef.current = es

      const handleEvent = (type: string) => (e: MessageEvent) => {
        try {
          const payload = JSON.parse(e.data)
          addSSEEvent({
            id: e.lastEventId || Date.now().toString(),
            event_type: type,
            payload,
            timestamp: Date.now(),
          })

          if (type === 'todo_update' && Array.isArray(payload)) {
            setTodoItems(payload)
          }

          // Track form1040_tool success from SSE tool_result (arrives before answer)
          if (type === 'tool_result') {
            const p = payload as Record<string, unknown>
            const output = p?.output as Record<string, unknown> | undefined
            if (p?.tool_name === 'form1040_tool' && output?.success === true) {
              setForm1040Ready(true)
            }
          }

          if (type === 'answer') {
            setIsAnalyzing(false)
            const answerText = typeof payload === 'string' ? payload : ''
            const formOk = useWizardStore.getState().form1040Ready

            if (formOk) {
              // Fast path: we already know form was generated from tool_result
              setAnalysisResult({
                flag_status: 'GREEN',
                consensus_liability: null,
                liability_delta: 0,
                scoring_rationale: answerText || 'Analysis completed via n0 agent.',
                claude_result: null,
                openai_result: null,
                form1040_status: { success: true, missing_required_fields: [], fields_written_count: 0 },
              })
              setTimeout(() => setCurrentStep(9), 1500)
            } else {
              // Fallback: check API (handles reconnection where tool_result was missed)
              getForm1040Status(sessionId)
                .then((status) => {
                  const ok = status?.success ?? false
                  if (ok) setForm1040Ready(true)
                  setAnalysisResult({
                    flag_status: ok ? 'GREEN' : 'YELLOW',
                    consensus_liability: null,
                    liability_delta: 0,
                    scoring_rationale: answerText || 'Analysis completed via n0 agent.',
                    claude_result: null,
                    openai_result: null,
                    form1040_status: {
                      success: ok,
                      missing_required_fields: status?.missing_required_fields ?? [],
                      fields_written_count: status?.fields_written_count ?? 0,
                    },
                  })
                  if (ok) setTimeout(() => setCurrentStep(9), 1500)
                })
                .catch(() => {
                  setAnalysisResult({
                    flag_status: answerText.toLowerCase().includes('success') ? 'GREEN' : 'YELLOW',
                    consensus_liability: null,
                    liability_delta: 0,
                    scoring_rationale: answerText || 'Analysis completed via n0 agent.',
                    claude_result: null,
                    openai_result: null,
                  })
                })
            }
          }

          // Stop reconnecting when the backend signals stream is finished
          if (type === 'done') {
            streamDone = true
          }
        } catch (err) {
          console.error('[useSSE] Failed to process SSE event:', type, err)
        }
      }

      const types = [
        'thought', 'tool_call', 'tool_result', 'answer', 'ask_user',
        'todo_update', 'compression', 'error', 'analysis_progress', 'done',
      ]
      types.forEach((t) => es.addEventListener(t, handleEvent(t)))

      es.onerror = () => {
        es.close()
        if (!streamDone) {
          reconnectTimer = setTimeout(connect, 3000)
        }
      }
    }

    connect()
    return () => {
      if (reconnectTimer) clearTimeout(reconnectTimer)
      esRef.current?.close()
    }
  }, [sessionId])
}
