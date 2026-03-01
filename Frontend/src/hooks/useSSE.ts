import { useEffect, useRef } from 'react'
import { useWizardStore } from '../store/useWizardStore'
import { getForm1040Status } from '../services/api'

export default function useSSE(sessionId: string) {
  const addSSEEvent = useWizardStore((s) => s.addSSEEvent)
  const setTodoItems = useWizardStore((s) => s.setTodoItems)
  const setAnalysisResult = useWizardStore((s) => s.setAnalysisResult)
  const setIsAnalyzing = useWizardStore((s) => s.setIsAnalyzing)
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    if (!sessionId) return

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

          if (type === 'answer') {
            setIsAnalyzing(false)
            const answerText = typeof payload === 'string' ? payload : ''
            const isSuccess = answerText.toLowerCase().includes('success')
            getForm1040Status(sessionId)
              .then((status) => {
                setAnalysisResult({
                  flag_status: status?.success ? 'GREEN' : 'YELLOW',
                  consensus_liability: null,
                  liability_delta: 0,
                  scoring_rationale: answerText || 'Analysis completed via n0 agent.',
                  claude_result: null,
                  openai_result: null,
                  form1040_status: {
                    success: status?.success ?? false,
                    missing_required_fields: status?.missing_required_fields ?? [],
                    fields_written_count: status?.fields_written_count ?? 0,
                  },
                })
              })
              .catch(() => {
                setAnalysisResult({
                  flag_status: isSuccess ? 'GREEN' : 'YELLOW',
                  consensus_liability: null,
                  liability_delta: 0,
                  scoring_rationale: answerText || 'Analysis completed via n0 agent.',
                  claude_result: null,
                  openai_result: null,
                })
              })
          }
        } catch {}
      }

      const types = ['thought', 'tool_call', 'tool_result', 'answer', 'ask_user', 'todo_update', 'compression', 'error', 'analysis_progress']
      types.forEach((t) => es.addEventListener(t, handleEvent(t)))

      es.onerror = () => {
        es.close()
        setTimeout(connect, 3000)
      }
    }

    connect()
    return () => esRef.current?.close()
  }, [sessionId])
}
