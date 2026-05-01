import { useState } from 'react'
import type { PgramJob } from '../types'
import { updateNotes } from '../api/pgram'
import { toast } from './Toast'

interface Props {
  job: PgramJob
  onClose: () => void
  onUpdated: (job: PgramJob) => void
}

export function JobDetailModal({ job, onClose, onUpdated }: Props) {
  const [notes, setNotes] = useState(job.notes_from_field)
  const [saving, setSaving] = useState(false)

  async function handleSave() {
    setSaving(true)
    try {
      await updateNotes(job.job_id, notes)
      onUpdated({ ...job, notes_from_field: notes })
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
          <h3 style={{ margin: 0, fontSize: 18 }}>{job.job_id}</h3>
          <button onClick={onClose} style={closeBtn}>✕</button>
        </div>

        <div style={field}>
          <span style={label}>SU</span>
          <span>{job.su_string || '—'}</span>
        </div>
        <div style={field}>
          <span style={label}>Trench</span>
          <span>{job.trench}</span>
        </div>
        <div style={field}>
          <span style={label}>Stage</span>
          <span style={{
            background: '#dbeafe', color: '#1d4ed8',
            padding: '2px 8px', borderRadius: 4, fontSize: 12, fontWeight: 600,
          }}>
            {job.stage.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
          </span>
        </div>
        {job.last_updated && (
          <div style={field}>
            <span style={label}>Last updated</span>
            <span style={{ fontSize: 13, color: '#6b7280' }}>
              {new Date(job.last_updated).toLocaleString()}
            </span>
          </div>
        )}

        <div style={{ marginTop: 20 }}>
          <label style={{ ...label, display: 'block', marginBottom: 6 }}>Notes from Field</label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Record which SUs are opened/closed, field observations..."
            style={{
              width: '100%', minHeight: 100, padding: '8px 10px',
              border: '1px solid #d1d5db', borderRadius: 6, fontSize: 14,
              resize: 'vertical', fontFamily: 'inherit', outline: 'none',
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
  position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)',
  display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
}
const dialog: React.CSSProperties = {
  background: '#fff', borderRadius: 12, padding: 28, width: 480,
  boxShadow: '0 8px 40px rgba(0,0,0,0.2)',
}
const field: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10, fontSize: 14,
}
const label: React.CSSProperties = {
  fontWeight: 600, color: '#6b7280', minWidth: 90, fontSize: 13,
}
const closeBtn: React.CSSProperties = {
  background: 'none', border: 'none', cursor: 'pointer',
  fontSize: 18, color: '#9ca3af', padding: 4,
}
const btnPrimary: React.CSSProperties = {
  padding: '8px 20px', borderRadius: 6, border: 'none', cursor: 'pointer',
  background: '#2563eb', color: '#fff', fontWeight: 600, fontSize: 14,
}
const btnSecondary: React.CSSProperties = {
  padding: '8px 20px', borderRadius: 6, border: '1px solid #d1d5db',
  cursor: 'pointer', background: '#fff', color: '#374151', fontWeight: 600, fontSize: 14,
}
