import { useCallback, useEffect, useRef, useState } from 'react'
import { PgramTab } from './components/PgramTab'
import { SUTab } from './components/SUTab'
import { ToastContainer } from './components/Toast'
import { pullFieldData, syncSheets } from './api/su'
import { fetchSeason } from './api/pgram'
import type { Season } from './api/pgram'
import { T } from './tokens'

type Tab = 'pgram' | 'su'
type SyncState = 'idle' | 'pulling' | 'pushing' | 'ok' | 'error'
type ReauthState = 'idle' | 'waiting' | 'ok' | 'error'

function timeAgo(ts: number): string {
  const s = Math.floor((Date.now() - ts) / 1000)
  if (s < 60) return `${s}s ago`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m ago`
  return `${Math.floor(m / 60)}h ago`
}

async function handleQuit() {
  if (!window.confirm('Shut down the TARP Lab server and close the app?')) return
  await fetch('/api/shutdown', { method: 'POST' }).catch(() => {})
  window.close()
}

export function App() {
  const [tab, setTab] = useState<Tab>('pgram')
  const [sheetUrl, setSheetUrl] = useState<string | null>(null)
  const [authError, setAuthError] = useState(false)
  const [hasCredentials, setHasCredentials] = useState(false)
  const [reauthState, setReauthState] = useState<ReauthState>('idle')
  const [syncState, setSyncState] = useState<SyncState>('idle')
  const [lastSyncAt, setLastSyncAt] = useState<number | null>(null)
  const [pgramRefreshKey, setPgramRefreshKey] = useState(0)
  const [season, setSeason] = useState<Season | null>(null)
  const [, forceUpdate] = useState(0)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetchStatus = useCallback(() => {
    fetch('/api/sheets/status')
      .then((r) => r.json())
      .then((d) => {
        setSheetUrl(d.sheet_url ?? null)
        setAuthError(d.auth_error ?? false)
        setHasCredentials(d.has_credentials ?? false)
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    fetchStatus()
    const t = setInterval(fetchStatus, 60_000)
    return () => clearInterval(t)
  }, [fetchStatus])

  // Season label + trench range — fetched once from config.yaml.
  useEffect(() => { fetchSeason().then(setSeason) }, [])

  const handleReauth = useCallback(async () => {
    setReauthState('waiting')
    try {
      const res = await fetch('/api/sheets/auth', { method: 'POST' })
      if (!res.ok) throw new Error()
      setReauthState('ok')
      setAuthError(false)
      await fetchStatus()
    } catch {
      setReauthState('error')
    }
  }, [fetchStatus])

  // Tick display every 30s so "X ago" stays fresh
  useEffect(() => {
    const t = setInterval(() => forceUpdate(n => n + 1), 30_000)
    return () => clearInterval(t)
  }, [])

  const handleSync = useCallback(async () => {
    if (syncState === 'pulling' || syncState === 'pushing') return
    try {
      setSyncState('pulling')
      await pullFieldData()
      setSyncState('pushing')
      await syncSheets()
      setSyncState('ok')
      setLastSyncAt(Date.now())
      setPgramRefreshKey(k => k + 1)
    } catch {
      setSyncState('error')
      setLastSyncAt(Date.now())
    }
  }, [syncState])

  // Auto-sync every 300s
  useEffect(() => {
    intervalRef.current = setInterval(handleSync, 300_000)
    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
  }, [handleSync])

  const syncBtnLabel =
    syncState === 'pulling' ? '↓ Pulling…' :
    syncState === 'pushing' ? '↑ Pushing…' :
    syncState === 'ok' ? '✓ Synced' :
    syncState === 'error' ? '✕ Sync failed' :
    '⇅ Sync now'

  const syncBtnBg =
    syncState === 'pulling' ? '#f59e0b' :
    syncState === 'pushing' ? '#f59e0b' :
    syncState === 'ok' ? '#16a34a' :
    syncState === 'error' ? '#dc2626' :
    T.accent

  const lastSyncLabel =
    lastSyncAt
      ? `Last synced ${timeAgo(lastSyncAt)}`
      : 'Not synced yet'

  return (
    <div style={{ minHeight: '100vh', background: T.bg, color: T.text }}>
      <header style={headerStyle}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div>
            <div style={{ fontWeight: 800, fontSize: 16, color: T.text, letterSpacing: '-0.01em' }}>
              TARP Lab Dashboard (MSI Laptop)
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 2 }}>
              <span style={{ fontSize: 12, color: T.textMuted }}>
                Season {season?.year ?? '…'}
              </span>
              {season && (
                <span
                  style={seasonTrenchBadge}
                  title="Only these trenches are scanned, run, and flagged. Edit current_year_trenches in config.yaml to change."
                >
                  Trenches {season.trench_min}–{season.trench_max}
                </span>
              )}
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {sheetUrl && (
            <a href={sheetUrl} target="_blank" rel="noopener noreferrer" style={openSheetBtn}>
              ↗ Open Sheet
            </a>
          )}
          <span style={{
            fontSize: 12,
            color: syncState === 'error' ? '#f87171' : T.textMuted,
            fontWeight: syncState === 'error' ? 600 : 400,
            whiteSpace: 'nowrap',
          }}>
            {lastSyncLabel}
          </span>
          <button
            onClick={handleSync}
            disabled={syncState === 'pulling' || syncState === 'pushing'}
            title="Pull field data then push lab data to Google Sheets (auto every 5m)"
            style={{
              padding: '7px 16px',
              borderRadius: 6,
              border: 'none',
              background: syncBtnBg,
              color: '#fff',
              fontWeight: 700,
              fontSize: 13,
              cursor: (syncState === 'pulling' || syncState === 'pushing') ? 'default' : 'pointer',
              opacity: (syncState === 'pulling' || syncState === 'pushing') ? 0.7 : 1,
              transition: 'background 0.2s',
              whiteSpace: 'nowrap',
            }}
          >
            {syncBtnLabel}
          </button>
          <button onClick={handleQuit} style={quitBtn} title="Shut down server and close app">
            ✕ Quit
          </button>
        </div>
      </header>

      <div style={tabBarStyle}>
        <button
          onClick={() => setTab('pgram')}
          style={{ ...tabBtn, ...(tab === 'pgram' ? tabBtnActive : {}) }}
        >
          Model Production
        </button>
        <button
          onClick={() => setTab('su')}
          style={{ ...tabBtn, ...(tab === 'su' ? tabBtnActive : {}) }}
        >
          SU Volumes
        </button>
      </div>

      {(authError || (reauthState === 'error')) && hasCredentials && (
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '10px 24px',
          background: '#7f1d1d',
          borderBottom: '1px solid #991b1b',
          gap: 12,
        }}>
          <span style={{ fontSize: 13, color: '#fca5a5', fontWeight: 600 }}>
            {reauthState === 'error'
              ? 'Re-authentication failed. Try again or restart the server.'
              : 'Google Sheets token is invalid or was revoked. Re-authenticate to restore sync.'}
          </span>
          <button
            onClick={handleReauth}
            disabled={reauthState === 'waiting'}
            style={{
              padding: '6px 14px', borderRadius: 6, border: 'none',
              background: reauthState === 'waiting' ? '#6b7280' : '#dc2626',
              color: '#fff', fontWeight: 700, fontSize: 12,
              cursor: reauthState === 'waiting' ? 'default' : 'pointer',
              whiteSpace: 'nowrap', flexShrink: 0,
            }}
          >
            {reauthState === 'waiting' ? '⟳ Waiting for browser…' : '↻ Re-authenticate'}
          </button>
        </div>
      )}

      <main style={{ padding: '0 24px 32px' }}>
        {tab === 'pgram' ? <PgramTab refreshKey={pgramRefreshKey} /> : <SUTab />}
      </main>

      <ToastContainer />
    </div>
  )
}

const headerStyle: React.CSSProperties = {
  background: T.surface,
  borderBottom: `1px solid ${T.border}`,
  padding: '14px 24px',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  position: 'sticky',
  top: 0,
  zIndex: 100,
}

const seasonTrenchBadge: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  background: T.chipBg,
  color: T.chipText,
  borderRadius: 20,
  padding: '1px 10px',
  fontSize: 11,
  fontWeight: 600,
  cursor: 'default',
}

const tabBarStyle: React.CSSProperties = {
  display: 'flex',
  gap: 0,
  padding: '0 24px',
  background: T.surface,
  borderBottom: `1px solid ${T.border}`,
  marginBottom: 24,
}

const tabBtn: React.CSSProperties = {
  padding: '12px 20px',
  border: 'none',
  background: 'none',
  cursor: 'pointer',
  fontSize: 14,
  fontWeight: 600,
  color: T.textMuted,
  borderBottom: '2px solid transparent',
  transition: 'color 0.15s, border-color 0.15s',
}

const tabBtnActive: React.CSSProperties = {
  color: T.accentText,
  borderBottom: `2px solid ${T.accent}`,
}

const openSheetBtn: React.CSSProperties = {
  padding: '6px 12px',
  borderRadius: 6,
  border: `1px solid ${T.border}`,
  background: T.surface,
  fontSize: 13,
  fontWeight: 600,
  color: T.textSub,
  textDecoration: 'none',
}

const quitBtn: React.CSSProperties = {
  padding: '6px 12px',
  borderRadius: 6,
  border: '1px solid #7f1d1d',
  background: 'transparent',
  fontSize: 12,
  fontWeight: 600,
  color: '#f87171',
  cursor: 'pointer',
}
