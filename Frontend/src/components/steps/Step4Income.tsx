import React, { useEffect, useMemo } from 'react'
import { useWizardStore, IncomeSummary } from '../../store/useWizardStore'

/** Exact W-2 box field names produced by the OCR pipeline (w2_box_N). */
const W2_FIELD_MAP: Record<string, 'wages' | 'federalWithheld' | 'ssWages' | 'medicareWages'> = {
  w2_box_1: 'wages',
  w2_box_2: 'federalWithheld',
  w2_box_3: 'ssWages',
  w2_box_5: 'medicareWages',
}

function extractFromOCR(ocrFields: Record<string, Array<{ field_name: string; field_value: string }>>) {
  let wages = 0
  let federalWithheld = 0
  let ssWages = 0
  let medicareWages = 0
  let otherIncome = 0

  for (const fields of Object.values(ocrFields)) {
    for (const f of fields) {
      const name = f.field_name.toLowerCase()
      const val = parseFloat(String(f.field_value).replace(/[$,]/g, '')) || 0
      if (val === 0) continue

      const w2Category = W2_FIELD_MAP[name]
      if (w2Category) {
        if (w2Category === 'wages') wages += val
        else if (w2Category === 'federalWithheld') federalWithheld += val
        else if (w2Category === 'ssWages') ssWages += val
        else if (w2Category === 'medicareWages') medicareWages += val
      } else if (
        name.startsWith('1099') ||
        name.includes('interest') ||
        name.includes('dividend') ||
        name.includes('nec')
      ) {
        otherIncome += val
      } else if (name === 'wages, tips, other compensation') {
        wages += val
      } else if (
        (name.includes('federal') && name.includes('withheld')) ||
        name === 'federal income tax withheld'
      ) {
        federalWithheld += val
      } else if (name.includes('social security wages') || name === 'social security wages') {
        ssWages += val
      } else if (name.includes('medicare wages') || name === 'medicare wages and tips') {
        medicareWages += val
      }
    }
  }

  return { wages, federalWithheld, ssWages, medicareWages, otherIncome, totalIncome: wages + otherIncome }
}

export default function Step4Income() {
  const ocrFields = useWizardStore((s) => s.ocrFields)
  const incomeSummary = useWizardStore((s) => s.incomeSummary)
  const setIncomeSummary = useWizardStore((s) => s.setIncomeSummary)
  const documents = useWizardStore((s) => s.documents)

  const computed = useMemo(() => extractFromOCR(ocrFields), [ocrFields])

  useEffect(() => {
    setIncomeSummary(computed)
  }, [computed, setIncomeSummary])

  const hasOCRData = computed.wages > 0 || computed.otherIncome > 0

  const incomeCategories = [
    { label: 'W-2 Wages (Box 1)', amount: incomeSummary.wages, source: hasOCRData ? 'Extracted from W-2' : 'No W-2 data — upload a document' },
    { label: 'Federal Tax Withheld (Box 2)', amount: incomeSummary.federalWithheld, source: hasOCRData ? 'Extracted from W-2' : 'No data' },
    { label: 'Social Security Wages (Box 3)', amount: incomeSummary.ssWages, source: hasOCRData ? 'Extracted from W-2' : 'No data' },
    { label: 'Medicare Wages (Box 5)', amount: incomeSummary.medicareWages, source: hasOCRData ? 'Extracted from W-2' : 'No data' },
    { label: 'Other Income (1099s)', amount: incomeSummary.otherIncome, source: incomeSummary.otherIncome > 0 ? 'Extracted from 1099' : 'No 1099 uploaded' },
  ]

  return (
    <div>
      <p style={{ color: '#555', marginBottom: 16 }}>
        Income summary extracted from your uploaded documents.
        {!hasOCRData && documents.length === 0 && (
          <span style={{ color: '#b91c1c' }}> Upload a W-2 or 1099 to populate this automatically.</span>
        )}
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
              ${incomeSummary.totalIncome.toLocaleString('en-US', { minimumFractionDigits: 2 })}
            </td>
            <td style={{ padding: '10px 16px', border: '1px solid #e2e8f0' }}></td>
          </tr>
        </tfoot>
      </table>
    </div>
  )
}
