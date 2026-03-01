import React from 'react'
import { useWizardStore } from '../../store/useWizardStore'

const FILING_STATUSES = [
  { value: 'Single', label: 'Single', tooltip: 'Unmarried or legally separated on Dec 31' },
  { value: 'Married Filing Jointly', label: 'Married Filing Jointly', tooltip: 'Married couples combining income and deductions on one return' },
  { value: 'Married Filing Separately', label: 'Married Filing Separately', tooltip: 'Married couples filing individual returns — may limit some credits' },
  { value: 'Head of Household', label: 'Head of Household', tooltip: 'Unmarried with qualifying dependent — lower tax rates than Single' },
  { value: 'Qualifying Surviving Spouse', label: 'Qualifying Surviving Spouse', tooltip: 'Widowed within past 2 years with dependent child — same rates as MFJ' },
]

export default function Step1FilingStatus() {
  const filingStatus = useWizardStore((s) => s.filingStatus)
  const setFilingStatus = useWizardStore((s) => s.setFilingStatus)

  return (
    <div>
      <p style={{ color: '#555', marginBottom: 20 }}>
        Select your filing status for tax year 2025.
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {FILING_STATUSES.map((status) => (
          <label
            key={status.value}
            title={status.tooltip}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              padding: '14px 16px',
              border: `2px solid ${filingStatus === status.value ? '#4a90d9' : '#e2e8f0'}`,
              borderRadius: 8,
              cursor: 'pointer',
              background: filingStatus === status.value ? '#f0f7ff' : 'white',
              transition: 'all 0.15s',
            }}
          >
            <input
              type="radio"
              name="filing-status"
              value={status.value}
              checked={filingStatus === status.value}
              onChange={() => setFilingStatus(status.value)}
              style={{ width: 18, height: 18, accentColor: '#4a90d9' }}
            />
            <span style={{ fontSize: 15, color: '#1a1a2e', fontWeight: filingStatus === status.value ? 600 : 400 }}>
              {status.label}
            </span>
          </label>
        ))}
      </div>
    </div>
  )
}
