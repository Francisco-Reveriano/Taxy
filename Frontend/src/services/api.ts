const BASE = '/api'

export async function uploadDocument(file: File, sessionId: string) {
  const form = new FormData()
  form.append('file', file)
  form.append('session_id', sessionId)
  const res = await fetch(`${BASE}/upload`, { method: 'POST', body: form })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function removeDocument(fileId: string, sessionId: string) {
  const res = await fetch(`${BASE}/upload/${fileId}?session_id=${sessionId}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function runOCR(fileId: string, sessionId: string) {
  const res = await fetch(`${BASE}/ocr/${fileId}?session_id=${sessionId}`, { method: 'POST' })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function runAnalysis(sessionId: string, taxData: Record<string, unknown>) {
  const res = await fetch(`${BASE}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, tax_data: taxData }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function getWizardState(sessionId: string) {
  const res = await fetch(`${BASE}/wizard/state?session_id=${sessionId}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function updateWizardState(state: Record<string, unknown>) {
  const res = await fetch(`${BASE}/wizard/state`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(state),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function generateAuditReport(sessionId: string) {
  const res = await fetch(`${BASE}/audit/report/${sessionId}`)
  if (!res.ok) throw new Error(await res.text())
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `audit_report_${sessionId}.pdf`
  a.click()
}

export async function fetchTraces(limit = 50) {
  const res = await fetch(`${BASE}/traces?limit=${limit}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function fetchTrace(traceId: string) {
  const res = await fetch(`${BASE}/traces/${traceId}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
