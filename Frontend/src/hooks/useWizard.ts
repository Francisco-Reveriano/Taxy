import { useMemo } from 'react'
import { useWizardStore } from '../store/useWizardStore'

export interface VisibleStep {
  index: number // 1-based step number
  title: string
}

const ALL_STEPS: VisibleStep[] = [
  { index: 1, title: 'Filing Status' },
  { index: 2, title: 'Upload Documents' },
  { index: 3, title: 'Review OCR' },
  { index: 4, title: 'Income Summary' },
  { index: 5, title: 'Deductions & Credits' },
  { index: 6, title: 'Analysis' },
  { index: 7, title: 'Results' },
]

export function useWizard() {
  const documents = useWizardStore((s) => s.documents)
  const filingStatus = useWizardStore((s) => s.filingStatus)
  const ocrReviewComplete = useWizardStore((s) => s.ocrReviewComplete)

  const visibleSteps = useMemo(() => {
    const steps: VisibleStep[] = [ALL_STEPS[0], ALL_STEPS[1]] // Steps 1-2 always visible

    // Step 3 (OCR Review) — only if documents uploaded
    if (documents.length > 0) {
      steps.push(ALL_STEPS[2])
    }

    // Step 4 (Income) — always visible after step 2
    steps.push(ALL_STEPS[3])

    // Step 5 (Deductions) — only if filing status selected
    if (filingStatus) {
      steps.push(ALL_STEPS[4])
    }

    // Steps 6-7 — only if OCR review complete (or no docs to review)
    if (ocrReviewComplete || documents.length === 0) {
      steps.push(ALL_STEPS[5])
      steps.push(ALL_STEPS[6])
    }

    return steps
  }, [documents.length, filingStatus, ocrReviewComplete])

  const isStepVisible = (stepIndex: number) =>
    visibleSteps.some((s) => s.index === stepIndex)

  return { visibleSteps, isStepVisible, allSteps: ALL_STEPS }
}
