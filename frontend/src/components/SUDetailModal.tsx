import { useState } from 'react'
import type { SUEntry } from '../types'
import { updateNotes } from '../api/su'
import { toast } from './Toast'
import { T } from '../tokens'

interface Props {
  entry: SUEntry
  onClose: () => void
  onUpdated: (entry: SUEntry) => void
}

export function SUDetailModal({ entry, onClose, onUpdated }: Props) {
  const [notes, setNotes] = useState(entry.notes)
  const [saving, setSaving] = useState(false)

  async function handleSave() {
    setSaving(true)
    try {
      await updateNotes(entry.su_id, notes)
      onUpdated({ ...entry, notes })
      toast('Notes saved', 'success')
      onClose()
    } catch (e: unknown) {
      toast((e as Error).message || 'Failed to save notes', 'error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={overlay} onClick={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div style={dialog}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <h3 style={{ margin: 0, fontSize: 18, color: T.text }}>{entry.su_id}</h3>
          <button onClick={onClose} style={closeBtn}>✕</button>
        </div>

        <div style={field}>
          <span style={label}>Top Pgram</span>
          <span style={{ color: T.text }}>{entry.top_pgram || '—'}</span>
        </div>
        <div style={field}>
          <span style={label}>Bottom Pgram</span>
          <span style={{ color: T.text }}>{entry.bot_pgram || '—'}</span>
        </div>
        <div style={field}>
          <span style={label}>Trench</span>
          <span style={{ color: T.text }}>{entry.trench}</span>
        </div>
        <div style={field}>
          <span style={label}>Stage</span>
          <span style={{
            background: '#14532d', color: '#86efac',
            padding: '2px 8px', borderRadius: 4, fontSize: 12, fontWeight: 600,
          }}>
            {entry.stage.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
          </span>
        </div>

        <div style={{ marginTop: 20 }}>
          <label style={{ ...label, display: 'block', marginBottom: 6 }}>Notes</label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Notes on volumetric processing, SU sheet status..."
            style={{
              width: '100%', minHeight: 100, padding: '8px 10px',
              border: `1px solid ${T.inputBorder}`, borderRadius: 6, fontSize: 14,
              resize: 'vertical', fontFamily: 'inherit', outline: 'none',
              background: T.inputBg, color: T.text, boxSizing: 'border-box',
            }}
          />
        </div>

        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 16 }}>
          <button onClick={onClose} style={btnSecondary}>Cancel</button>
          <button onClick={handleSave} disabled={saving} style={btnPrimary}>
            {saving ? 'Saving…' : 'Save Notes'}
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
const field: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10, fontSize: 14,
}
const label: React.CSSProperties = {
  fontWeight: 600, color: T.textMuted, minWidth: 90, fontSize: 13,
}
const closeBtn: React.CSSProperties = {
  background: 'none', border: 'none', cursor: 'pointer', fontSize: 18, color: T.textMuted, padding: 4,
}
const btnPrimary: React.CSSProperties = {
  padding: '8px 20px', borderRadius: 6, border: 'none', cursor: 'pointer',
  background: T.accent, color: '#fff', fontWeight: 600, fontSize: 14,
}
const btnSecondary: React.CSSProperties = {
  padding: '8px 20px', borderRadius: 6, border: `1px solid ${T.border}`,
  cursor: 'pointer', background: T.surface, color: T.textSub, fontWeight: 600, fontSize: 14,
}
