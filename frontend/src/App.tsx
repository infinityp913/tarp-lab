import { useEffect, useState } from 'react'
import { PgramTab } from './components/PgramTab'
import { SUTab } from './components/SUTab'
import { ToastContainer } from './components/Toast'
import { syncSheets } from './api/su'

type Tab = 'pgram' | 'su'

export function App() {
  const [tab, setTab] = useState<Tab>('pgram')
  const [sheetsAvailable, setSheetsAvailable] = useState<boolean | null>(null)
  const [sheetUrl, setSheetUrl] = useState<string | null>(null)
  const [syncing, setSyncing] = useState(false)

  useEffect(() => {
    fetch('/api/sheets/status')
      .then((r) => r.json())
      .then((d) => { setSheetsAvailable(d.available); setSheetUrl(d.sheet_url ?? null) })
      .catch(() => setSheetsAvailable(false))
  }, [])

  async function handleSync() {
    setSyncing(true)
    try {
      const result = await syncSheets()
      alert(`Sync complete. ${result.pgram_count} Pgram jobs · ${result.su_count} SU entries written to Google Sheets.`)
    } catch (err: unknown) {
      alert('Sync failed: ' + (err as Error).message)
    } finally {
      setSyncing(false)
    }
  }

  return (
    <div style={{ minHeight: '100vh', background: '#f1f5f9' }}>
      <header style={headerStyle}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div>
            <div style={{ fontWeight: 800, fontSize: 16, color: '#1e293b', letterSpacing: '-0.01em' }}>
              TARP Photogrammetry Dashboard
            </div>
            <div style={{ fontSize: 12, color: '#64748b', marginTop: 1 }}>Season 2026</div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {sheetsAvailable === false && (
            <div style={sheetsBanner}>
              Google Sheets unavailable — notes will not persist
            </div>
          )}
          {sheetUrl && (
            <a href={sheetUrl} target="_blank" rel="noopener noreferrer" style={openSheetBtn}>
              ↗ Open Sheet
            </a>
          )}
          <button
            onClick={handleSync}
            disabled={syncing || sheetsAvailable === false}
            style={{ ...syncBtn, opacity: sheetsAvailable === false ? 0.5 : 1 }}
            title={sheetsAvailable === false ? 'Google Sheets not configured' : 'Sync all data to Google Sheets'}
          >
            {syncing ? 'Syncing…' : '⇅ Sync to Sheet'}
          </button>
        </div>
      </header>

      <div style={tabBarStyle}>
        <button
          onClick={() => setTab('pgram')}
          style={{ ...tabBtn, ...(tab === 'pgram' ? tabBtnActive : {}) }}
        >
          Photogrammetry Jobs
        </button>
        <button
          onClick={() => setTab('su')}
          style={{ ...tabBtn, ...(tab === 'su' ? tabBtnActive : {}) }}
        >
          SU Tracking
        </button>
      </div>

      <main style={{ padding: '0 24px 32px' }}>
        {tab === 'pgram' ? <PgramTab /> : <SUTab />}
      </main>

      <ToastContainer />
    </div>
  )
}

const headerStyle: React.CSSProperties = {
  background: '#fff',
  borderBottom: '1px solid #e2e8f0',
  padding: '14px 24px',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  position: 'sticky',
  top: 0,
  zIndex: 100,
}

const tabBarStyle: React.CSSProperties = {
  display: 'flex',
  gap: 0,
  padding: '0 24px',
  background: '#fff',
  borderBottom: '1px solid #e2e8f0',
  marginBottom: 24,
}

const tabBtn: React.CSSProperties = {
  padding: '12px 20px',
  border: 'none',
  background: 'none',
  cursor: 'pointer',
  fontSize: 14,
  fontWeight: 600,
  color: '#64748b',
  borderBottom: '2px solid transparent',
  transition: 'color 0.15s, border-color 0.15s',
}

const tabBtnActive: React.CSSProperties = {
  color: '#2563eb',
  borderBottom: '2px solid #2563eb',
}

const syncBtn: React.CSSProperties = {
  padding: '7px 14px',
  borderRadius: 6,
  border: '1px solid #d1d5db',
  background: '#fff',
  cursor: 'pointer',
  fontSize: 13,
  fontWeight: 600,
  color: '#374151',
}

const openSheetBtn: React.CSSProperties = {
  padding: '7px 14px',
  borderRadius: 6,
  border: '1px solid #d1d5db',
  background: '#fff',
  fontSize: 13,
  fontWeight: 600,
  color: '#374151',
  textDecoration: 'none',
}

const sheetsBanner: React.CSSProperties = {
  background: '#fef3c7',
  border: '1px solid #f59e0b',
  color: '#92400e',
  borderRadius: 6,
  padding: '5px 12px',
  fontSize: 12,
  fontWeight: 600,
}
