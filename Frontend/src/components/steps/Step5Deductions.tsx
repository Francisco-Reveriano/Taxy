import React from 'react'
import { useWizardStore } from '../../store/useWizardStore'

const STANDARD_DEDUCTIONS_2025: Record<string, number> = {
  'Single': 15750,
  'Married Filing Jointly': 31500,
  'Married Filing Separately': 15750,
  'Head of Household': 23625,
  'Qualifying Surviving Spouse': 31500,
}

const AVAILABLE_CREDITS = [
  { id: 'child-tax-credit', label: 'Child Tax Credit ($2,000/child)', amount: 2000 },
  { id: 'earned-income-credit', label: 'Earned Income Tax Credit', amount: 500 },
  { id: 'education-credit', label: 'American Opportunity Credit', amount: 2500 },
  { id: 'savers-credit', label: "Saver's Credit", amount: 1000 },
]

export default function Step5Deductions() {
  const filingStatus = useWizardStore((s) => s.filingStatus)
  const itemizedTotal = useWizardStore((s) => s.itemizedTotal)
  const setItemizedTotal = useWizardStore((s) => s.setItemizedTotal)
  const selectedCredits = useWizardStore((s) => s.selectedCredits)
  const setSelectedCredits = useWizardStore((s) => s.setSelectedCredits)
  const deductionChoice = useWizardStore((s) => s.deductionChoice)
  const setDeductionChoice = useWizardStore((s) => s.setDeductionChoice)

  const standardDeduction = STANDARD_DEDUCTIONS_2025[filingStatus || 'Single'] || 15750
  const recommended = itemizedTotal > standardDeduction ? 'itemized' : 'standard'

  const toggleCredit = (id: string) => {
    const next = selectedCredits.includes(id)
      ? selectedCredits.filter((c) => c !== id)
      : [...selectedCredits, id]
    setSelectedCredits(next)
  }

  return (
    <div>
      <h3 style={{ fontSize: 15, marginBottom: 12 }}>Deduction Comparison</h3>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: 16,
          marginBottom: 24,
        }}
      >
        <div
          onClick={() => setDeductionChoice('standard')}
          style={{
            padding: 16,
            border: `2px solid ${deductionChoice === 'standard' || (!deductionChoice && recommended === 'standard') ? '#27ae60' : '#e2e8f0'}`,
            borderRadius: 10,
            background: deductionChoice === 'standard' || (!deductionChoice && recommended === 'standard') ? '#f0fdf4' : 'white',
            cursor: 'pointer',
          }}
        >
          <div style={{ fontWeight: 700, marginBottom: 4 }}>Standard Deduction</div>
          <div style={{ fontSize: 22, fontWeight: 800, color: '#1a1a2e' }}>
            ${standardDeduction.toLocaleString()}
          </div>
          <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
            {filingStatus || 'Single'} — Tax Year 2025
          </div>
          {(deductionChoice === 'standard' || (!deductionChoice && recommended === 'standard')) && (
            <div style={{ marginTop: 8, color: '#27ae60', fontSize: 13, fontWeight: 600 }}>
              {recommended === 'standard' ? '✓ Recommended' : '✓ Selected'}
            </div>
          )}
        </div>

        <div
          onClick={() => setDeductionChoice('itemized')}
          style={{
            padding: 16,
            border: `2px solid ${deductionChoice === 'itemized' || (!deductionChoice && recommended === 'itemized') ? '#27ae60' : '#e2e8f0'}`,
            borderRadius: 10,
            background: deductionChoice === 'itemized' || (!deductionChoice && recommended === 'itemized') ? '#f0fdf4' : 'white',
            cursor: 'pointer',
          }}
        >
          <div style={{ fontWeight: 700, marginBottom: 4 }}>Itemized Deductions</div>
          <input
            type="number"
            value={itemizedTotal}
            onChange={(e) => setItemizedTotal(Number(e.target.value))}
            onClick={(e) => e.stopPropagation()}
            style={{
              fontSize: 22,
              fontWeight: 800,
              color: '#1a1a2e',
              border: 'none',
              borderBottom: '2px solid #4a90d9',
              width: '100%',
              background: 'transparent',
              outline: 'none',
            }}
          />
          {(deductionChoice === 'itemized' || (!deductionChoice && recommended === 'itemized')) && (
            <div style={{ marginTop: 8, color: '#27ae60', fontSize: 13, fontWeight: 600 }}>
              {recommended === 'itemized' ? '✓ Recommended' : '✓ Selected'}
            </div>
          )}
        </div>
      </div>

      <h3 style={{ fontSize: 15, marginBottom: 12 }}>Available Credits</h3>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {AVAILABLE_CREDITS.map((credit) => (
          <label
            key={credit.id}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              padding: '12px 16px',
              border: `1px solid ${selectedCredits.includes(credit.id) ? '#4a90d9' : '#e2e8f0'}`,
              borderRadius: 8,
              cursor: 'pointer',
              background: selectedCredits.includes(credit.id) ? '#f0f7ff' : 'white',
            }}
          >
            <input
              type="checkbox"
              checked={selectedCredits.includes(credit.id)}
              onChange={() => toggleCredit(credit.id)}
              style={{ width: 18, height: 18, accentColor: '#4a90d9' }}
            />
            <span style={{ flex: 1 }}>{credit.label}</span>
          </label>
        ))}
      </div>
    </div>
  )
}
