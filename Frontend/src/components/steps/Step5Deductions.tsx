import React, { useState } from 'react'
import { useWizardStore } from '../../store/useWizardStore'

const STANDARD_DEDUCTION = 14600

const AVAILABLE_CREDITS = [
  { id: 'child-tax-credit', label: 'Child Tax Credit ($2,000/child)', amount: 2000 },
  { id: 'earned-income-credit', label: 'Earned Income Tax Credit', amount: 500 },
  { id: 'education-credit', label: 'American Opportunity Credit', amount: 2500 },
  { id: 'savers-credit', label: "Saver's Credit", amount: 1000 },
]

export default function Step5Deductions() {
  const [itemizedTotal, setItemizedTotal] = useState(0)
  const [selectedCredits, setSelectedCredits] = useState<string[]>([])
  const recommended = itemizedTotal > STANDARD_DEDUCTION ? 'itemized' : 'standard'

  const toggleCredit = (id: string) => {
    setSelectedCredits((prev) =>
      prev.includes(id) ? prev.filter((c) => c !== id) : [...prev, id],
    )
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
          style={{
            padding: 16,
            border: `2px solid ${recommended === 'standard' ? '#27ae60' : '#e2e8f0'}`,
            borderRadius: 10,
            background: recommended === 'standard' ? '#f0fdf4' : 'white',
          }}
        >
          <div style={{ fontWeight: 700, marginBottom: 4 }}>Standard Deduction</div>
          <div style={{ fontSize: 22, fontWeight: 800, color: '#1a1a2e' }}>
            ${STANDARD_DEDUCTION.toLocaleString()}
          </div>
          {recommended === 'standard' && (
            <div style={{ marginTop: 8, color: '#27ae60', fontSize: 13, fontWeight: 600 }}>✓ Recommended</div>
          )}
        </div>

        <div
          style={{
            padding: 16,
            border: `2px solid ${recommended === 'itemized' ? '#27ae60' : '#e2e8f0'}`,
            borderRadius: 10,
            background: recommended === 'itemized' ? '#f0fdf4' : 'white',
          }}
        >
          <div style={{ fontWeight: 700, marginBottom: 4 }}>Itemized Deductions</div>
          <input
            type="number"
            value={itemizedTotal}
            onChange={(e) => setItemizedTotal(Number(e.target.value))}
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
          {recommended === 'itemized' && (
            <div style={{ marginTop: 8, color: '#27ae60', fontSize: 13, fontWeight: 600 }}>✓ Recommended</div>
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
