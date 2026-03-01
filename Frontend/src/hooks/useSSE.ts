import { useEffect, useRef } from 'react'
import { useWizardStore } from '../store/useWizardStore'

export default function useSSE(sessionId: string) {
  const addSSEEvent = useWizardStore((s) => s.addSSEEvent)
  const setTodoItems = useWizardStore((s) => s.setTodoItems)
  const setAnalysisResult = useWizardStore((s) => s.setAnalysisResult)
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
        } catch {}
      }

      const types = ['thought', 'tool_call', 'tool_result', 'answer', 'ask_user', 'todo_update', 'compression', 'error']
      types.forEach((t) => es.addEventListener(t, handleEvent(t)))

      es.onerror = () => {
        es.close()
        // Reconnect after 3s
        setTimeout(connect, 3000)
      }
    }

    connect()
    return () => esRef.current?.close()
  }, [sessionId])
}
