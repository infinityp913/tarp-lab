import { useState } from 'react'
import { toast } from './Toast'
import { T } from '../tokens'

// One failed script invocation. Reused by the pgram run banner and (later) the
// volume-section script buttons — any script run that can fail feeds this shape.
export interface ScriptError {
  label: string          // what failed, e.g. the job_id or SU card name
  step?: string | null   // which script, e.g. "alignment" / "overnight"
  error: string          // the captured stderr/stdout tail
}

/**
 * Collapsible list of per-script failures. Renders nothing when there are no
 * errors, so callers can drop it in unconditionally. Full info/debug logging
 * still lives in tarp-dashboard.log; this only surfaces the failure detail.
 */
export function ScriptErrorList({ errors }: { errors: ScriptError[] }) {
  const [open, setOpen] = useState(true)
  if (!errors.length) return null

  return (
    <div style={{ marginTop: 10 }}>
      <button
        onClick={() => setOpen((v) => !v)}
        style={{
          background: 'none', border: 'none', cursor: 'pointer', padding: 0,
          color: '#fca5a5', fontSize: 12, fontWeight: 700,
          display: 'inline-flex', alignItems: 'center', gap: 6,
        }}
      >
        <span style={{ fontSize: 10 }}>{open ? '▾' : '▸'}</span>
        {errors.length} script error{errors.length === 1 ? '' : 's'}
      </button>

      {open && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 8 }}>
          {errors.map((e, i) => (
            <div
              key={`${e.label}-${i}`}
              style={{
                border: '1px solid #7f1d1d', borderRadius: 6,
                background: '#7f1d1d22', padding: '8px 10px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                <span style={{ fontSize: 12, fontWeight: 700, color: T.text }}>
                  {e.label}
                  {e.step && <span style={{ color: T.textSub, fontWeight: 500 }}>{` · ${e.step}`}</span>}
                </span>
                <button
                  onClick={() => {
                    navigator.clipboard?.writeText(e.error).then(
                      () => toast('Error copied', 'success'),
                      () => toast('Copy failed', 'error'),
                    )
                  }}
                  title="Copy error text"
                  style={{
                    background: 'none', border: `1px solid ${T.border}`, borderRadius: 4,
                    cursor: 'pointer', color: T.textSub, fontSize: 10, fontWeight: 600,
                    padding: '2px 6px', flexShrink: 0,
                  }}
                >
                  ⧉ Copy
                </button>
              </div>
              <pre
                style={{
                  margin: '6px 0 0', maxHeight: 160, overflow: 'auto',
                  fontSize: 11, lineHeight: 1.45, color: '#fecaca',
                  fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
                  whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                }}
              >
                {e.error}
              </pre>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
