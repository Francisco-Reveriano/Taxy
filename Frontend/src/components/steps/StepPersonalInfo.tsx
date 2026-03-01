import React from 'react'
import { useWizardStore } from '../../store/useWizardStore'

const US_STATES = [
  'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN','IA',
  'KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ',
  'NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT',
  'VA','WA','WV','WI','WY','DC',
]

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '10px 12px',
  borderRadius: 8,
  border: '1px solid #e2e8f0',
  fontSize: 15,
  outline: 'none',
  boxSizing: 'border-box',
}

const labelStyle: React.CSSProperties = {
  display: 'block',
  fontSize: 13,
  fontWeight: 600,
  color: '#555',
  marginBottom: 4,
}

export default function StepPersonalInfo() {
  const info = useWizardStore((s) => s.taxpayerInfo)
  const setInfo = useWizardStore((s) => s.setTaxpayerInfo)

  const formatSSN = (raw: string) => {
    const digits = raw.replace(/\D/g, '').slice(0, 9)
    if (digits.length <= 3) return digits
    if (digits.length <= 5) return `${digits.slice(0, 3)}-${digits.slice(3)}`
    return `${digits.slice(0, 3)}-${digits.slice(3, 5)}-${digits.slice(5)}`
  }

  return (
    <div>
      <p style={{ color: '#555', marginBottom: 20 }}>
        Enter your personal information as it appears on your tax documents.
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
        <div>
          <label style={labelStyle}>First Name</label>
          <input
            style={inputStyle}
            placeholder="John"
            value={info.firstName}
            onChange={(e) => setInfo({ firstName: e.target.value })}
          />
        </div>
        <div>
          <label style={labelStyle}>Last Name</label>
          <input
            style={inputStyle}
            placeholder="Doe"
            value={info.lastName}
            onChange={(e) => setInfo({ lastName: e.target.value })}
          />
        </div>
      </div>

      <div style={{ marginBottom: 16 }}>
        <label style={labelStyle}>Social Security Number</label>
        <input
          style={{ ...inputStyle, maxWidth: 200, fontFamily: 'monospace' }}
          placeholder="000-00-0000"
          value={formatSSN(info.ssn)}
          onChange={(e) => setInfo({ ssn: e.target.value.replace(/\D/g, '').slice(0, 9) })}
        />
      </div>

      <div style={{ marginBottom: 16 }}>
        <label style={labelStyle}>Street Address</label>
        <input
          style={inputStyle}
          placeholder="123 Main St, Apt 4B"
          value={info.address}
          onChange={(e) => setInfo({ address: e.target.value })}
        />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr', gap: 16, marginBottom: 16 }}>
        <div>
          <label style={labelStyle}>City</label>
          <input
            style={inputStyle}
            placeholder="New York"
            value={info.city}
            onChange={(e) => setInfo({ city: e.target.value })}
          />
        </div>
        <div>
          <label style={labelStyle}>State</label>
          <select
            style={{ ...inputStyle, background: 'white' }}
            value={info.state}
            onChange={(e) => setInfo({ state: e.target.value })}
          >
            <option value="">--</option>
            {US_STATES.map((st) => (
              <option key={st} value={st}>{st}</option>
            ))}
          </select>
        </div>
        <div>
          <label style={labelStyle}>ZIP Code</label>
          <input
            style={{ ...inputStyle, fontFamily: 'monospace' }}
            placeholder="10001"
            maxLength={10}
            value={info.zip}
            onChange={(e) => setInfo({ zip: e.target.value.replace(/[^\d-]/g, '').slice(0, 10) })}
          />
        </div>
      </div>

      <div style={{ marginBottom: 16 }}>
        <label style={labelStyle}>Number of Dependents</label>
        <input
          type="number"
          min={0}
          max={20}
          style={{ ...inputStyle, maxWidth: 100 }}
          value={info.dependents}
          onChange={(e) => setInfo({ dependents: Math.max(0, parseInt(e.target.value) || 0) })}
        />
      </div>

      {(!info.firstName || !info.lastName || info.ssn.length < 9) && (
        <div style={{ padding: '10px 12px', borderRadius: 8, background: '#fffbeb', border: '1px solid #fcd34d', color: '#78350f', fontSize: 13 }}>
          Please provide at least your first name, last name, and SSN to continue.
        </div>
      )}
    </div>
  )
}
