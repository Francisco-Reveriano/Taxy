import React from 'react'
import { useWizardStore } from '../store/useWizardStore'
import { useWizard } from '../hooks/useWizard'
import Step1FilingStatus from './steps/Step1FilingStatus'
import Step2Upload from './steps/Step2Upload'
import Step3OCRReview from './steps/Step3OCRReview'
import Step4Income from './steps/Step4Income'
import Step5Deductions from './steps/Step5Deductions'
import Step6Analysis from './steps/Step6Analysis'
import Step7Results from './steps/Step7Results'

const STEP_COMPONENTS: Record<number, React.FC> = {
  1: Step1FilingStatus,
  2: Step2Upload,
  3: Step3OCRReview,
  4: Step4Income,
  5: Step5Deductions,
  6: Step6Analysis,
  7: Step7Results,
}

export default function WizardShell() {
  const currentStep = useWizardStore((s) => s.currentStep)
  const setCurrentStep = useWizardStore((s) => s.setCurrentStep)
  const { visibleSteps } = useWizard()

  // Find current position in visible steps
  const currentVisibleIndex = visibleSteps.findIndex((s) => s.index === currentStep)
  const effectiveStep = currentVisibleIndex >= 0 ? currentStep : visibleSteps[0]?.index ?? 1

  const StepComponent = STEP_COMPONENTS[effectiveStep] || Step1FilingStatus
  const currentTitle = visibleSteps.find((s) => s.index === effectiveStep)?.title || ''
  const progress = visibleSteps.length > 1
    ? (Math.max(currentVisibleIndex, 0) / (visibleSteps.length - 1)) * 100
    : 0

  const goNext = () => {
    const idx = visibleSteps.findIndex((s) => s.index === effectiveStep)
    if (idx < visibleSteps.length - 1) {
      setCurrentStep(visibleSteps[idx + 1].index)
    }
  }

  const goPrev = () => {
    const idx = visibleSteps.findIndex((s) => s.index === effectiveStep)
    if (idx > 0) {
      setCurrentStep(visibleSteps[idx - 1].index)
    }
  }

  const isFirst = currentVisibleIndex <= 0
  const isLast = currentVisibleIndex >= visibleSteps.length - 1

  return (
    <div style={{ maxWidth: 800, margin: '0 auto' }}>
      {/* Progress bar */}
      <div style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
          <span style={{ fontSize: 14, color: '#666' }}>
            Step {currentVisibleIndex + 1} of {visibleSteps.length}: {currentTitle}
          </span>
          <span style={{ fontSize: 14, color: '#666' }}>{Math.round(progress)}%</span>
        </div>
        <div style={{ height: 8, background: '#e2e8f0', borderRadius: 4, overflow: 'hidden' }}>
          <div
            style={{
              height: '100%',
              width: `${progress}%`,
              background: '#4a90d9',
              transition: 'width 0.3s ease',
            }}
          />
        </div>
        <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
          {visibleSteps.map((step, i) => (
            <div
              key={step.index}
              style={{
                flex: 1,
                height: 4,
                borderRadius: 2,
                background: i <= currentVisibleIndex ? '#4a90d9' : '#e2e8f0',
              }}
            />
          ))}
        </div>
      </div>

      {/* Step content */}
      <div
        style={{
          background: 'white',
          borderRadius: 12,
          padding: 32,
          boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
          marginBottom: 24,
        }}
      >
        <h2 style={{ fontSize: '1.25rem', marginBottom: 24, color: '#1a1a2e' }}>
          {currentTitle}
        </h2>
        <StepComponent />
      </div>

      {/* Navigation */}
      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <button
          onClick={goPrev}
          disabled={isFirst}
          style={{
            padding: '10px 24px',
            borderRadius: 8,
            border: '1px solid #e2e8f0',
            background: isFirst ? '#f5f5f5' : 'white',
            cursor: isFirst ? 'not-allowed' : 'pointer',
            color: isFirst ? '#999' : '#333',
          }}
        >
          Back
        </button>
        {!isLast && (
          <button
            onClick={goNext}
            style={{
              padding: '10px 24px',
              borderRadius: 8,
              border: 'none',
              background: '#4a90d9',
              color: 'white',
              cursor: 'pointer',
              fontWeight: 600,
            }}
          >
            Next
          </button>
        )}
      </div>
    </div>
  )
}
