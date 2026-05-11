import { useState } from 'react'
import { TRENCHES, inferTrench } from '../types'
import { createEntry } from '../api/su'
import type { SUEntry } from '../types'
import { toast } from './Toast'
import { T } from '../tokens'

interface Props {
  onClose: () => void
  onCreated: (entry: SUEntry) => void
}

export function CreateSUModal({ onClose, onCreated }: Props) {
  const [suId, setSuId] = useState('')
  const [topPgram, setTopPgram] = useState('')
  const [botPgram, setBotPgram] = useState('')
  const [manualTrench, setManualTrench] = useState(TRENCHES[0])
  const [saving, setSaving] = useState(false)

  const inferredTrench = inferTrench(suId)
  const trench = inferredTrench ?? manualTrench

  async function handleCreate() {
    if (!suId.trim()) return
    setSaving(true)
    try {
      const entry = await createEntry({
        su_id: suId.trim(),
        top_pgram: topPgram.trim() || undefined,
        bot_pgram: botPgram.trim() || undefined,
        trench,
      })
      toast(`Created ${entry.su_id}`, 'success')
      onCreated(entry)
      onClose()
    } catch (e: unknown) {
      toast((e as Error).message || 'Failed to create SU entry', 'error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={overlay} onClick={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div style={dialog}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <h3 style={{ margin: 0, fontSize: 18, color: T.text }}>New SU Entry</h3>
          <button onClick={onClose} style={closeBtn}>✕</button>
        </div>

        <div style={fieldRow}>
          <label style={label}>SU ID <span style={asterisk}>*</span></label>
          <input
            value={suId}
            onChange={(e) => setSuId(e.target.value)}
            placeholder="e.g. 16014 or 16014-16015"
            style={inputStyle}
            autoFocus
          />
          {inferredTrench && (
            <span style={inferred}>Trench inferred: <strong>{inferredTrench}</strong></span>
          )}
        </div>

        <div style={fieldRow}>
          <label style={label}>Top Pgram</label>
          <input
            value={topPgram}
            onChange={(e) => setTopPgram(e.target.value)}
            placeholder="e.g. 696 (optional)"
            style={inputStyle}
          />
        </div>

        <div style={fieldRow}>
          <label style={label}>Bottom Pgram</label>
          <input
            value={botPgram}
            onChange={(e) => setBotPgram(e.target.value)}
            placeholder="e.g. 697 (optional)"
            style={inputStyle}
          />
        </div>

        {!inferredTrench && (
          <div style={fieldRow}>
            <label style={label}>Trench <span style={asterisk}>*</span></label>
            <select value={manualTrench} onChange={(e) => setManualTrench(e.target.value)} style={inputStyle}>
              {TRENCHES.map((t) => <option key={t}>{t}</option>)}
            </select>
          </div>
        )}

        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 20 }}>
          <button onClick={onClose} style={btnSecondary}>Cancel</button>
          <button
            onClick={handleCreate}
            disabled={saving || !suId.trim()}
            style={{ ...btnPrimary, ...(saving || !suId.trim() ? disabledStyle : {}) }}
          >
            {saving ? 'Creating…' : 'Create SU Entry'}
          </button>
        </div>
      </div>
    </div>
  )
}

const overlay: React.CSSProperties = {
  position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.65)',
  display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
}
const dialog: React.CSSProperties = {
  background: T.surface, borderRadius: 12, padding: 28, width: 440,
  boxShadow: '0 8px 40px rgba(0,0,0,0.5)', border: `1px solid ${T.border}`,
}
const fieldRow: React.CSSProperties = { display: 'flex', flexDirection: 'column', gap: 4, marginBottom: 14 }
const label: React.CSSProperties = { fontWeight: 600, color: T.textSub, fontSize: 13 }
const asterisk: React.CSSProperties = { color: '#f87171' }
const inputStyle: React.CSSProperties = {
  padding: '8px 10px', border: `1px solid ${T.inputBorder}`, borderRadius: 6,
  fontSize: 14, fontFamily: 'inherit', outline: 'none',
  width: '100%', boxSizing: 'border-box',
  background: T.inputBg, color: T.text,
}
const inferred: React.CSSProperties = { fontSize: 12, color: '#34d399' }
const closeBtn: React.CSSProperties = {
  background: 'none', border: 'none', cursor: 'pointer', fontSize: 18, color: T.textMuted, padding: 4,
}
const disabledStyle: React.CSSProperties = { opacity: 0.45, cursor: 'not-allowed' }
const btnPrimary: React.CSSProperties = {
  padding: '8px 20px', borderRadius: 6, border: 'none', cursor: 'pointer',
  background: T.accent, color: '#fff', fontWeight: 600, fontSize: 14,
}
const btnSecondary: React.CSSProperties = {
  padding: '8px 20px', borderRadius: 6, border: `1px solid ${T.border}`,
  cursor: 'pointer', background: T.surface, color: T.textSub, fontWeight: 600, fontSize: 14,
}
