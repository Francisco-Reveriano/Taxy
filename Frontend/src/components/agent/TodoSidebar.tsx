import React from 'react'
import { useWizardStore } from '../../store/useWizardStore'

const STATUS_ICONS: Record<string, string> = {
  pending: '⏳',
  in_progress: '🔄',
  completed: '✅',
  failed: '❌',
}

const STATUS_COLORS: Record<string, string> = {
  pending: '#888',
  in_progress: '#4a90d9',
  completed: '#27ae60',
  failed: '#e74c3c',
}

export default function TodoSidebar() {
  const todoItems = useWizardStore((s) => s.todoItems)

  if (todoItems.length === 0) return null

  return (
    <aside
      style={{
        width: 280,
        background: '#1a1a2e',
        color: 'white',
        padding: '24px 16px',
        overflowY: 'auto',
      }}
    >
      <h2 style={{ fontSize: 14, fontWeight: 700, marginBottom: 16, color: '#aaa', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
        Agent Plan
      </h2>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {todoItems.map((item) => (
          <div
            key={item.id}
            style={{
              display: 'flex',
              gap: 10,
              padding: '10px 12px',
              background: 'rgba(255,255,255,0.05)',
              borderRadius: 8,
              border: `1px solid rgba(255,255,255,0.08)`,
              alignItems: 'flex-start',
            }}
          >
            <span style={{ fontSize: 14, flexShrink: 0, marginTop: 1 }}>
              {STATUS_ICONS[item.status] || '⏳'}
            </span>
            <div style={{ flex: 1 }}>
              <div
                style={{
                  fontSize: 13,
                  color: STATUS_COLORS[item.status] || '#888',
                  fontWeight: item.status === 'in_progress' ? 700 : 400,
                  lineHeight: 1.4,
                }}
              >
                {item.description}
              </div>
              <div style={{ fontSize: 11, color: '#666', marginTop: 2 }}>
                {item.status}
              </div>
            </div>
          </div>
        ))}
      </div>
    </aside>
  )
}
