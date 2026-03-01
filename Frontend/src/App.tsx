import React, { useState } from 'react'
import WizardShell from './components/WizardShell'
import TraceDashboard from './components/TraceDashboard'
import { useWizardStore } from './store/useWizardStore'
import useSSE from './hooks/useSSE'
import TodoSidebar from './components/agent/TodoSidebar'

type Tab = 'wizard' | 'traces'

export default function App() {
  const sessionId = useWizardStore((s) => s.sessionId)
  useSSE(sessionId)

  const [activeTab, setActiveTab] = useState<Tab>('wizard')

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      <main style={{ flex: 1, padding: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
          <h1 style={{ fontSize: '1.5rem', margin: 0, color: '#1a1a2e' }}>
            Tax AI Assistant
          </h1>
          <div style={{ display: 'flex', gap: 4, background: '#f0f4f8', borderRadius: 8, padding: 3 }}>
            {(['wizard', 'traces'] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                style={{
                  padding: '6px 16px',
                  borderRadius: 6,
                  border: 'none',
                  background: activeTab === tab ? 'white' : 'transparent',
                  boxShadow: activeTab === tab ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
                  cursor: 'pointer',
                  fontSize: 13,
                  fontWeight: activeTab === tab ? 600 : 400,
                  color: activeTab === tab ? '#1a1a2e' : '#888',
                }}
              >
                {tab === 'wizard' ? 'Wizard' : 'Traces'}
              </button>
            ))}
          </div>
        </div>

        {activeTab === 'wizard' ? <WizardShell /> : <TraceDashboard />}
      </main>
      <TodoSidebar />
    </div>
  )
}
