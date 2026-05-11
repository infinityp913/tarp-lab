import { useState } from 'react'
import { TRENCHES, inferTrench } from '../types'
import { createJob } from '../api/pgram'
import type { PgramJob } from '../types'
import { toast } from './Toast'
import { T } from '../tokens'

interface Props {
  onClose: () => void
  onCreated: (job: PgramJob) => void
}

export function CreateJobModal({ onClose, onCreated }: Props) {
  const [jobSuffix, setJobSuffix] = useState('')
  const [suString, setSuString] = useState('')
  const [manualTrench, setManualTrench] = useState(TRENCHES[0])
  const [saving, setSaving] = useState(false)

  const inferredTrench = inferTrench(suString)
  const trench = inferredTrench ?? manualTrench
  const jobId = `Pgram_Job_${jobSuffix}`

  const suffixError = jobSuffix.trim() === ''
    ? 'Job number is required'
    : !/^\d/.test(jobSuffix.trim())
      ? 'Must start with a number (e.g. 001)'
      : null

  async function handleCreate() {
    if (suffixError) return
    setSaving(true)
    try {
      const job = await createJob({ job_id: jobId, su_string: suString.trim(), trench })
      toast(`Created ${job.job_id}`, 'success')
      onCreated(job)
      onClose()
    } catch (e: unknown) {
      toast((e as Error).message || 'Failed to create job', 'error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={overlay} onClick={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div style={dialog}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <h3 style={{ margin: 0, fontSize: 18, color: T.text }}>New Pgram Job</h3>
          <button onClick={onClose} style={closeBtn}>✕</button>
        </div>

        <div style={fieldRow}>
          <label style={label}>Job ID <span style={asterisk}>*</span></label>
          <div style={prefixInputWrap}>
            <span style={prefix}>Pgram_Job_</span>
            <input
              value={jobSuffix}
              onChange={(e) => setJobSuffix(e.target.value)}
              placeholder="001"
              style={{ ...inputStyle, borderRadius: '0 6px 6px 0', borderLeft: 'none', flex: 1 }}
              autoFocus
            />
          </div>
          {suffixError && jobSuffix !== '' && (
            <span style={errorText}>{suffixError}</span>
          )}
        </div>

        <div style={fieldRow}>
          <label style={label}>SU String <span style={asterisk}>*</span></label>
          <input
            value={suString}
            onChange={(e) => setSuString(e.target.value)}
            placeholder="e.g. 16015-16016"
            style={inputStyle}
          />
          {inferredTrench && (
            <span style={inferred}>Trench inferred: <strong>{inferredTrench}</strong></span>
          )}
        </div>

        {!inferredTrench && (
          <div style={fieldRow}>
            <label style={label}>Trench <span style={asterisk}>*</span></label>
            <select value={manualTrench} onChange={(e) => setManualTrench(e.target.value)} style={inputStyle}>
              {TRENCHES.map((t) => <option key={t}>{t}</option>)}
            </select>
          </div>
        )}

        <p style={{ fontSize: 13, color: T.textMuted, margin: '12px 0 20px' }}>
          Creates folder:{' '}
          <code style={{ background: T.bg, color: T.textSub, padding: '2px 6px', borderRadius: 3 }}>
            To Be Processed\{trench}\{jobId}{suString.trim() ? `_${suString.trim()}` : ''}
          </code>
        </p>

        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
          <button onClick={onClose} style={btnSecondary}>Cancel</button>
          <button
            onClick={handleCreate}
            disabled={saving || !!suffixError || !suString.trim()}
            style={{ ...btnPrimary, ...(saving || !!suffixError || !suString.trim() ? disabledStyle : {}) }}
          >
            {saving ? 'Creating…' : 'Create Job'}
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
  background: T.surface, borderRadius: 12, padding: 28, width: 480,
  boxShadow: '0 8px 40px rgba(0,0,0,0.5)', border: `1px solid ${T.border}`,
}
const fieldRow: React.CSSProperties = { display: 'flex', flexDirection: 'column', gap: 4, marginBottom: 14 }
const label: React.CSSProperties = { fontWeight: 600, color: T.textSub, fontSize: 13 }
const asterisk: React.CSSProperties = { color: '#f87171' }
const inputStyle: React.CSSProperties = {
  padding: '8px 10px', border: `1px solid ${T.inputBorder}`, borderRadius: 6,
  fontSize: 14, fontFamily: 'inherit', outline: 'none', width: '100%', boxSizing: 'border-box',
  background: T.inputBg, color: T.text,
}
const prefixInputWrap: React.CSSProperties = {
  display: 'flex', alignItems: 'stretch',
}
const prefix: React.CSSProperties = {
  padding: '8px 10px', background: T.bg, border: `1px solid ${T.inputBorder}`,
  borderRadius: '6px 0 0 6px', fontSize: 14, color: T.textMuted, whiteSpace: 'nowrap',
  display: 'flex', alignItems: 'center',
}
const errorText: React.CSSProperties = { fontSize: 12, color: '#f87171' }
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
