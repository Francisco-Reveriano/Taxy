const BASE = '/api'

async function throwApiError(res: Response): Promise<never> {
  const text = await res.text()
  let message = text
  try {
    const json = JSON.parse(text)
    const detail = json.detail
    if (typeof detail === 'string') {
      message = detail
    } else if (detail && typeof detail === 'object') {
      message = detail.message || detail.error || JSON.stringify(detail)
    }
  } catch {
    // not JSON — use raw text
  }
  throw new Error(message)
}

export async function uploadDocument(file: File, sessionId: string) {
  const form = new FormData()
  form.append('file', file)
  form.append('session_id', sessionId)
  const res = await fetch(`${BASE}/upload`, { method: 'POST', body: form })
  if (!res.ok) await throwApiError(res)
  return res.json()
}

export async function removeDocument(fileId: string, sessionId: string) {
  const res = await fetch(`${BASE}/upload/${fileId}?session_id=${sessionId}`, { method: 'DELETE' })
  if (!res.ok) await throwApiError(res)
  return res.json()
}

export async function runOCR(fileId: string, sessionId: string) {
  const res = await fetch(`${BASE}/ocr/${fileId}?session_id=${sessionId}`, { method: 'POST' })
  if (!res.ok) await throwApiError(res)
  return res.json()
}

export async function runAnalysis(sessionId: string, taxData: Record<string, unknown>) {
  const res = await fetch(`${BASE}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, tax_data: taxData }),
  })
  if (!res.ok) await throwApiError(res)
  return res.json()
}

export async function startAgentChat(sessionId: string, message: string) {
  const res = await fetch(`${BASE}/stream/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, message }),
  })
  if (!res.ok) await throwApiError(res)
  return res.json()
}

export async function getWizardState(sessionId: string) {
  const res = await fetch(`${BASE}/wizard/state?session_id=${sessionId}`)
  if (!res.ok) await throwApiError(res)
  return res.json()
}

export async function updateWizardState(state: Record<string, unknown>) {
  const res = await fetch(`${BASE}/wizard/state`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(state),
  })
  if (!res.ok) await throwApiError(res)
  return res.json()
}

export async function generateAuditReport(sessionId: string) {
  const res = await fetch(`${BASE}/audit/report/${sessionId}`)
  if (!res.ok) await throwApiError(res)
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `audit_report_${sessionId}.pdf`
  a.click()
}

export async function fetchTraces(limit = 50) {
  const res = await fetch(`${BASE}/traces?limit=${limit}`)
  if (!res.ok) await throwApiError(res)
  return res.json()
}

export async function fetchTrace(traceId: string) {
  const res = await fetch(`${BASE}/traces/${traceId}`)
  if (!res.ok) await throwApiError(res)
  return res.json()
}

export async function getForm1040Status(sessionId: string) {
  const res = await fetch(`${BASE}/forms/1040/${sessionId}/status`)
  if (!res.ok) await throwApiError(res)
  return res.json()
}

export async function getForm1040TemplateFields() {
  const res = await fetch(`${BASE}/forms/1040/template-fields`)
  if (!res.ok) await throwApiError(res)
  return res.json()
}

export async function downloadFinalForm1040(sessionId: string) {
  const res = await fetch(`${BASE}/forms/1040/${sessionId}`)
  if (!res.ok) await throwApiError(res)
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `form1040_${sessionId}.pdf`
  a.click()
}
