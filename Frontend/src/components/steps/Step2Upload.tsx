import React, { useCallback, useRef, useState } from 'react'
import { useWizardStore } from '../../store/useWizardStore'

interface UploadProgress {
  [key: string]: number
}

export default function Step2Upload() {
  const sessionId = useWizardStore((s) => s.sessionId)
  const documents = useWizardStore((s) => s.documents)
  const addDocument = useWizardStore((s) => s.addDocument)
  const removeDocument = useWizardStore((s) => s.removeDocument)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [progress, setProgress] = useState<UploadProgress>({})
  const replaceInputRef = useRef<HTMLInputElement>(null)
  const [replaceTarget, setReplaceTarget] = useState<string | null>(null)

  const handleDrop = useCallback(
    async (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault()
      const files = Array.from(e.dataTransfer.files)
      await handleFiles(files)
    },
    [sessionId],
  )

  const uploadWithProgress = (file: File, sid: string): Promise<any> => {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest()
      const form = new FormData()
      form.append('file', file)
      form.append('session_id', sid)

      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
          const pct = Math.round((e.loaded / e.total) * 100)
          setProgress((p) => ({ ...p, [file.name]: pct }))
        }
      })

      xhr.addEventListener('load', () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(JSON.parse(xhr.responseText))
        } else {
          reject(new Error(xhr.responseText || `Upload failed (${xhr.status})`))
        }
      })

      xhr.addEventListener('error', () => reject(new Error('Upload failed')))
      xhr.open('POST', '/api/upload')
      xhr.send(form)
    })
  }

  const handleFiles = async (files: File[]) => {
    setUploading(true)
    setError(null)
    for (const file of files) {
      try {
        setProgress((p) => ({ ...p, [file.name]: 0 }))
        const doc = await uploadWithProgress(file, sessionId)
        addDocument(doc)
        setProgress((p) => {
          const next = { ...p }
          delete next[file.name]
          return next
        })
      } catch (err) {
        setError(`Upload failed: ${err}`)
        setProgress((p) => {
          const next = { ...p }
          delete next[file.name]
          return next
        })
      }
    }
    setUploading(false)
  }

  const handleRemove = async (fileId: string) => {
    try {
      const res = await fetch(`/api/upload/${fileId}?session_id=${sessionId}`, {
        method: 'DELETE',
      })
      if (!res.ok && res.status !== 404) throw new Error(await res.text())
    } catch (err) {
      setError(`Remove failed: ${err}`)
    }
    removeDocument(fileId)
  }

  const handleReplace = (fileId: string) => {
    setReplaceTarget(fileId)
    replaceInputRef.current?.click()
  }

  const handleReplaceFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !replaceTarget) return
    await handleRemove(replaceTarget)
    await handleFiles([file])
    setReplaceTarget(null)
    if (replaceInputRef.current) replaceInputRef.current.value = ''
  }

  return (
    <div>
      <p style={{ color: '#555', marginBottom: 16 }}>
        Upload your tax documents: W-2, 1099, 1098, etc. (max 20MB per file)
      </p>

      {/* Drop zone */}
      <div
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        style={{
          border: '2px dashed #4a90d9',
          borderRadius: 12,
          padding: 40,
          textAlign: 'center',
          background: '#f8fbff',
          cursor: 'pointer',
          marginBottom: 16,
        }}
      >
        <div style={{ fontSize: 40, marginBottom: 8 }}>📄</div>
        <p style={{ color: '#4a90d9', fontWeight: 600 }}>
          Drag & drop files here
        </p>
        <p style={{ color: '#888', fontSize: 13, marginTop: 4 }}>
          or click to browse
        </p>
        <input
          type="file"
          multiple
          accept=".pdf,.jpg,.jpeg,.png"
          onChange={(e) => handleFiles(Array.from(e.target.files || []))}
          style={{ display: 'none' }}
          id="file-input"
        />
        <label
          htmlFor="file-input"
          style={{
            marginTop: 12,
            display: 'inline-block',
            padding: '8px 20px',
            background: '#4a90d9',
            color: 'white',
            borderRadius: 6,
            cursor: 'pointer',
            fontSize: 14,
          }}
        >
          Browse Files
        </label>
      </div>

      {/* Hidden replace input */}
      <input
        ref={replaceInputRef}
        type="file"
        accept=".pdf,.jpg,.jpeg,.png"
        onChange={handleReplaceFile}
        style={{ display: 'none' }}
      />

      {/* Upload progress bars */}
      {Object.entries(progress).map(([name, pct]) => (
        <div key={name} style={{ marginBottom: 8 }}>
          <div style={{ fontSize: 13, color: '#555', marginBottom: 4 }}>
            Uploading {name}... {pct}%
          </div>
          <div style={{ height: 6, background: '#e2e8f0', borderRadius: 3, overflow: 'hidden' }}>
            <div
              style={{
                height: '100%',
                width: `${pct}%`,
                background: '#4a90d9',
                transition: 'width 0.2s ease',
              }}
            />
          </div>
        </div>
      ))}

      {uploading && Object.keys(progress).length === 0 && (
        <p style={{ color: '#4a90d9' }}>Uploading...</p>
      )}
      {error && <p style={{ color: '#e74c3c' }}>{error}</p>}

      {/* Document list */}
      {documents.length > 0 && (
        <div>
          <h3 style={{ fontSize: 15, marginBottom: 8, color: '#333' }}>
            Uploaded ({documents.length})
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {documents.map((doc) => (
              <div
                key={doc.file_id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  padding: '10px 14px',
                  background: '#f0f7ff',
                  borderRadius: 8,
                  border: '1px solid #cde',
                }}
              >
                <span>📋</span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: 14 }}>{doc.original_filename}</div>
                  <div style={{ fontSize: 12, color: '#666' }}>{doc.document_type}</div>
                </div>
                <button
                  onClick={() => handleReplace(doc.file_id)}
                  title="Replace this document"
                  style={{
                    background: 'none',
                    border: '1px solid #4a90d9',
                    color: '#4a90d9',
                    borderRadius: 4,
                    padding: '4px 10px',
                    cursor: 'pointer',
                    fontSize: 12,
                  }}
                >
                  Replace
                </button>
                <button
                  onClick={() => handleRemove(doc.file_id)}
                  title="Remove this document"
                  style={{
                    background: 'none',
                    border: '1px solid #e74c3c',
                    color: '#e74c3c',
                    borderRadius: 4,
                    padding: '4px 10px',
                    cursor: 'pointer',
                    fontSize: 12,
                  }}
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
