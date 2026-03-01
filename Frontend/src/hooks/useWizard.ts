import { useMemo } from 'react'
import { useWizardStore } from '../store/useWizardStore'

export interface VisibleStep {
  index: number // 1-based step number
  title: string
}

const ALL_STEPS: VisibleStep[] = [
  { index: 1, title: 'Filing Status' },
  { index: 2, title: 'Your Information' },
  { index: 3, title: 'Upload Documents' },
  { index: 4, title: 'Review OCR' },
  { index: 5, title: 'Income Summary' },
  { index: 6, title: 'Deductions & Credits' },
  { index: 7, title: 'Analysis' },
  { index: 8, title: 'Results' },
  { index: 9, title: 'Your Form 1040' },
]

export function useWizard() {
  const documents = useWizardStore((s) => s.documents)
  const filingStatus = useWizardStore((s) => s.filingStatus)
  const ocrReviewComplete = useWizardStore((s) => s.ocrReviewComplete)
  const deductionChoice = useWizardStore((s) => s.deductionChoice)

  const visibleSteps = useMemo(() => {
    // Step 1 (Filing Status) always visible
    const steps: VisibleStep[] = [ALL_STEPS[0]]

    // Step 2 (Your Information) — visible after filing status selected
    if (filingStatus) {
      steps.push(ALL_STEPS[1])
    }

    // Step 3 (Upload Documents) — always visible after filing status
    if (filingStatus) {
      steps.push(ALL_STEPS[2])
    }

    // Step 4 (OCR Review) — only if documents uploaded
    if (documents.length > 0) {
      steps.push(ALL_STEPS[3])
    }

    // Step 5 (Income) — visible after upload step
    if (filingStatus) {
      steps.push(ALL_STEPS[4])
    }

    // Step 6 (Deductions) — visible after filing status selected
    if (filingStatus) {
      steps.push(ALL_STEPS[5])
    }

    // Steps 7-8 — visible once deductions are chosen, OCR is reviewed, or no docs uploaded
    if (deductionChoice || ocrReviewComplete || documents.length === 0) {
      steps.push(ALL_STEPS[6])
      steps.push(ALL_STEPS[7])
      steps.push(ALL_STEPS[8])
    }

    return steps
  }, [documents.length, filingStatus, ocrReviewComplete, deductionChoice])

  const isStepVisible = (stepIndex: number) =>
    visibleSteps.some((s) => s.index === stepIndex)

  return { visibleSteps, isStepVisible, allSteps: ALL_STEPS }
}
