import { create } from 'zustand'

export interface SSEEventRecord {
  id: string
  event_type: string
  payload: unknown
  timestamp: number
}

export interface TodoItem {
  id: string
  description: string
  status: 'pending' | 'in_progress' | 'completed' | 'failed'
  priority: number
}

export interface AnalysisResult {
  flag_status: string
  consensus_liability: number | null
  liability_delta: number
  scoring_rationale: string
  claude_result: Record<string, unknown> | null
  openai_result: Record<string, unknown> | null
}

export interface OCRFieldData {
  field_name: string
  field_value: string
  confidence: number
  page_number: number
  is_corrected: boolean
}

interface WizardStore {
  sessionId: string
  currentStep: number
  filingStatus: string | null
  documents: Array<{ file_id: string; original_filename: string; document_type: string }>
  ocrFields: Record<string, OCRFieldData[]>
  ocrReviewComplete: boolean
  analysisResult: AnalysisResult | null
  sseEvents: SSEEventRecord[]
  todoItems: TodoItem[]
  isAnalyzing: boolean

  setSessionId: (id: string) => void
  setCurrentStep: (step: number) => void
  setFilingStatus: (status: string) => void
  addDocument: (doc: { file_id: string; original_filename: string; document_type: string }) => void
  removeDocument: (fileId: string) => void
  setOcrFields: (fileId: string, fields: OCRFieldData[]) => void
  setOcrReviewComplete: (v: boolean) => void
  setAnalysisResult: (result: AnalysisResult) => void
  addSSEEvent: (event: SSEEventRecord) => void
  setTodoItems: (items: TodoItem[]) => void
  setIsAnalyzing: (v: boolean) => void
  nextStep: () => void
  prevStep: () => void
}

// Clear stale data from previous sessions
localStorage.removeItem('tax-ai-wizard')
localStorage.removeItem('tax-ai-session-id')

export const useWizardStore = create<WizardStore>()(
  (set) => ({
    sessionId: crypto.randomUUID(),
    currentStep: 1,
    filingStatus: null,
    documents: [],
    ocrFields: {},
    ocrReviewComplete: false,
    analysisResult: null,
    sseEvents: [],
    todoItems: [],
    isAnalyzing: false,

    setSessionId: (id) => set({ sessionId: id }),
    setCurrentStep: (step) => set({ currentStep: step }),
    setFilingStatus: (status) => set({ filingStatus: status }),
    addDocument: (doc) => set((s) => ({ documents: [...s.documents, doc] })),
    removeDocument: (fileId) =>
      set((s) => ({ documents: s.documents.filter((d) => d.file_id !== fileId) })),
    setOcrFields: (fileId, fields) =>
      set((s) => ({ ocrFields: { ...s.ocrFields, [fileId]: fields } })),
    setOcrReviewComplete: (v) => set({ ocrReviewComplete: v }),
    setAnalysisResult: (result) => set({ analysisResult: result }),
    addSSEEvent: (event) =>
      set((s) => ({ sseEvents: [event, ...s.sseEvents].slice(0, 100) })),
    setTodoItems: (items) => set({ todoItems: items }),
    setIsAnalyzing: (v) => set({ isAnalyzing: v }),
    nextStep: () => set((s) => ({ currentStep: Math.min(s.currentStep + 1, 7) })),
    prevStep: () => set((s) => ({ currentStep: Math.max(s.currentStep - 1, 1) })),
  }),
)
