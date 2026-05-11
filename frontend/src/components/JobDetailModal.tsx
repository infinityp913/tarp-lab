import { useEffect, useRef, useState } from 'react'
import type { PgramJob } from '../types'
import { updateNotes } from '../api/pgram'
import { toast } from './Toast'
import { T } from '../tokens'

interface Props {
  job: PgramJob
  onClose: () => void
  onUpdated: (job: PgramJob) => void
}

function savedAgo(ts: number | null): string {
  if (ts === null) return ''
  const s = Math.floor((Date.now() - ts) / 1000)
  if (s < 60) return 'just now'
  return `${Math.floor(s / 60)}m ago`
}

export function JobDetailModal({ job, onClose, onUpdated }: Props) {
  const [notes, setNotes] = useState(job.notes)
  const [savedNotes, setSavedNotes] = useState(job.notes)
  const [saving, setSaving] = useState(false)
  const [lastSaved, setLastSaved] = useState<number | null>(null)
  const [, tick] = useState(0)

  const isDirty = notes !== savedNotes

  useEffect(() => {
    const iv = setInterval(() => tick(n => n + 1), 30_000)
    return () => clearInterval(iv)
  }, [])

  const notesRef = useRef(notes)
  useEffect(() => { notesRef.current = notes }, [notes])
  const savedNotesRef = useRef(savedNotes)

  async function doSave(currentNotes: string, closeAfter: boolean) {
    setSaving(true)
    try {
      await updateNotes(job.job_id, currentNotes)
      setSavedNotes(currentNotes)
      savedNotesRef.current = currentNotes
      setLastSaved(Date.now())
      onUpdated({ ...job, notes: currentNotes })
      if (closeAfter) {
        toast('Notes saved', 'success')
        onClose()
      }
    } catch (e: unknown) {
      toast((e as Error).message || 'Failed to save notes', 'error')
    } finally {
      setSaving(false)
    }
  }

  // 15-min auto-save if dirty
  useEffect(() => {
    const iv = setInterval(() => {
      if (notesRef.current !== savedNotesRef.current) {
        doSave(notesRef.current, false)
      }
    }, 15 * 60 * 1000)
    return () => clearInterval(iv)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const hasFieldData = job.notes_from_field || job.sus_opened || job.sus_closed

  return (
    <div style={overlay} onClick={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div style={dialog}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <h3 style={{ margin: 0, fontSize: 18, color: T.text }}>{job.job_id}</h3>
          <button onClick={onClose} style={closeBtn}>✕</button>
        </div>

        <div style={field}>
          <span style={label}>SU</span>
          <span style={{ color: T.text }}>{job.su_string || '—'}</span>
        </div>
        <div style={field}>
          <span style={label}>Trench</span>
          <span style={{ color: T.text }}>{job.trench}</span>
        </div>
        <div style={field}>
          <span style={label}>Stage</span>
          <span style={{
            background: '#1e3a8a', color: '#93c5fd',
            padding: '2px 8px', borderRadius: 4, fontSize: 12, fontWeight: 600,
          }}>
            {job.stage.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
          </span>
        </div>
        {job.last_updated && (
          <div style={field}>
            <span style={label}>Last updated</span>
            <span style={{ fontSize: 13, color: T.textMuted }}>{job.last_updated}</span>
          </div>
        )}

        {/* Field-sourced data — read-only */}
        {hasFieldData && (
          <div style={fieldSection}>
            <div style={sectionTitle}>From Field</div>
            {(job.sus_opened || job.sus_closed) && (
              <div style={{ display: 'flex', gap: 24, marginBottom: 6 }}>
                {job.sus_opened && (
                  <div>
                    <span style={subLabel}>SUs Opened</span>
                    <span style={readonlyValue}>{job.sus_opened}</span>
                  </div>
                )}
                {job.sus_closed && (
                  <div>
                    <span style={subLabel}>SUs Closed</span>
                    <span style={readonlyValue}>{job.sus_closed}</span>
                  </div>
                )}
              </div>
            )}
            {job.notes_from_field && (
              <div>
                <span style={subLabel}>Field Notes</span>
                <div style={readonlyTextarea}>{job.notes_from_field}</div>
              </div>
            )}
          </div>
        )}

        {/* Lab notes — editable */}
        <div style={{ marginTop: hasFieldData ? 16 : 20 }}>
          <label style={{ ...label, display: 'block', marginBottom: 6 }}>Lab Notes</label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Processing observations, alignment notes, issues..."
            style={{
              width: '100%', minHeight: 100, padding: '8px 10px',
              border: `1px solid ${T.inputBorder}`, borderRadius: 6, fontSize: 14,
              resize: 'vertical', fontFamily: 'inherit', outline: 'none',
              background: T.inputBg, color: T.text, boxSizing: 'border-box',
            }}
          />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 16 }}>
          <div style={{ fontSize: 12, color: T.textMuted }}>
            {isDirty && (
              <span style={{ color: '#f59e0b', fontWeight: 600 }}>● Unsaved changes</span>
            )}
            {!isDirty && lastSaved && (
              <span>Saved {savedAgo(lastSaved)}</span>
            )}
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            <button onClick={onClose} style={btnSecondary}>Cancel</button>
            <button onClick={() => doSave(notes, true)} disabled={saving || !isDirty} style={{
              ...btnPrimary,
              opacity: !isDirty ? 0.5 : 1,
              cursor: !isDirty ? 'default' : 'pointer',
            }}>
              {saving ? 'Saving…' : 'Save Notes'}
            </button>
          </div>
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
  background: T.surface, borderRadius: 12, padding: 28, width: 500,
  boxShadow: '0 8px 40px rgba(0,0,0,0.5)', border: `1px solid ${T.border}`,
  maxHeight: '85vh', overflowY: 'auto',
}
const field: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10, fontSize: 14,
}
const label: React.CSSProperties = {
  fontWeight: 600, color: T.textMuted, minWidth: 90, fontSize: 13,
}
const closeBtn: React.CSSProperties = {
  background: 'none', border: 'none', cursor: 'pointer',
  fontSize: 18, color: T.textMuted, padding: 4,
}
const btnPrimary: React.CSSProperties = {
  padding: '8px 20px', borderRadius: 6, border: 'none', cursor: 'pointer',
  background: T.accent, color: '#fff', fontWeight: 600, fontSize: 14,
}
const btnSecondary: React.CSSProperties = {
  padding: '8px 20px', borderRadius: 6, border: `1px solid ${T.border}`,
  cursor: 'pointer', background: T.surface, color: T.textSub, fontWeight: 600, fontSize: 14,
}
const fieldSection: React.CSSProperties = {
  marginTop: 16, padding: '12px 14px',
  background: '#0f2040', borderRadius: 8,
  border: '1px solid #1e3a5f',
}
const sectionTitle: React.CSSProperties = {
  fontSize: 11, fontWeight: 700, color: '#60a5fa',
  textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8,
}
const subLabel: React.CSSProperties = {
  display: 'block', fontSize: 11, fontWeight: 600, color: T.textMuted,
  textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 2,
}
const readonlyValue: React.CSSProperties = {
  display: 'block', fontSize: 14, color: T.text,
}
const readonlyTextarea: React.CSSProperties = {
  fontSize: 13, color: T.textSub, lineHeight: 1.5,
  whiteSpace: 'pre-wrap', wordBreak: 'break-word',
}
