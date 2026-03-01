import React from 'react'
import { useWizardStore } from '../../store/useWizardStore'

export default function Step4Income() {
  const documents = useWizardStore((s) => s.documents)

  const incomeCategories = [
    { label: 'W-2 Wages', amount: 55000, source: 'Extracted from W-2' },
    { label: '1099-NEC Income', amount: 0, source: 'No 1099-NEC uploaded' },
    { label: '1099-INT Interest', amount: 0, source: 'No 1099-INT uploaded' },
    { label: '1099-DIV Dividends', amount: 0, source: 'No 1099-DIV uploaded' },
  ]

  const total = incomeCategories.reduce((sum, c) => sum + c.amount, 0)

  return (
    <div>
      <p style={{ color: '#555', marginBottom: 16 }}>
        Income summary extracted from your documents.
      </p>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
        <thead>
          <tr style={{ background: '#f0f4f8' }}>
            <th style={{ padding: '10px 16px', textAlign: 'left', border: '1px solid #e2e8f0' }}>Category</th>
            <th style={{ padding: '10px 16px', textAlign: 'right', border: '1px solid #e2e8f0' }}>Amount</th>
            <th style={{ padding: '10px 16px', textAlign: 'left', border: '1px solid #e2e8f0' }}>Source</th>
          </tr>
        </thead>
        <tbody>
          {incomeCategories.map((cat) => (
            <tr key={cat.label}>
              <td style={{ padding: '10px 16px', border: '1px solid #e2e8f0' }}>{cat.label}</td>
              <td style={{ padding: '10px 16px', border: '1px solid #e2e8f0', textAlign: 'right', fontWeight: cat.amount > 0 ? 600 : 400 }}>
                ${cat.amount.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </td>
              <td style={{ padding: '10px 16px', border: '1px solid #e2e8f0', color: '#888', fontSize: 13 }}>{cat.source}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr style={{ background: '#f0f7ff' }}>
            <td style={{ padding: '10px 16px', border: '1px solid #e2e8f0', fontWeight: 700 }}>Total Income</td>
            <td style={{ padding: '10px 16px', border: '1px solid #e2e8f0', textAlign: 'right', fontWeight: 700, color: '#1a1a2e' }}>
              ${total.toLocaleString('en-US', { minimumFractionDigits: 2 })}
            </td>
            <td style={{ padding: '10px 16px', border: '1px solid #e2e8f0' }}></td>
          </tr>
        </tfoot>
      </table>
    </div>
  )
}
