import { useDraggable } from '@dnd-kit/core'
import { CSS } from '@dnd-kit/utilities'
import type { PgramJob } from '../types'
import type { RunJobStatus } from '../api/pgram'
import { openApp } from '../api/pgram'
import { toast } from './Toast'
import { T } from '../tokens'

interface Props {
  job: PgramJob
  onClick: () => void
  onAdvance?: () => void          // advance one stage forward; omit to hide the → arrow
  nextStageLabel?: string         // tooltip for the → arrow, e.g. "Move to To Overnight"
  runStatus?: RunJobStatus        // this job's state in the active run, if any
  runStep?: string | null         // which script is running (alignment / overnight)
  runError?: string | null        // failure detail, shown in the failed badge's tooltip
}

const RUN_BADGE: Record<RunJobStatus, { icon: string; color: string; bg: string }> = {
  queued:    { icon: '•',  color: '#cbd5e1', bg: '#33415555' },
  running:   { icon: '⏳', color: '#fde68a', bg: '#78350f55' },
  done:      { icon: '✓',  color: '#86efac', bg: '#14532d55' },
  failed:    { icon: '✗',  color: '#fca5a5', bg: '#7f1d1d55' },
  cancelled: { icon: '⊘',  color: '#cbd5e1', bg: '#33415555' },
}

export function JobCard({ job, onClick, onAdvance, nextStageLabel, runStatus, runStep, runError }: Props) {
  const {
    attributes, listeners, setNodeRef, transform, isDragging,
  } = useDraggable({ id: job.job_id })

  const inRun = runStatus === 'running' || runStatus === 'queued'
  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    opacity: isDragging ? 0.4 : 1,
  }

  async function handleOpen(app: string, e: React.MouseEvent) {
    e.stopPropagation()
    try {
      await openApp(job.job_id, app)
      toast(`Opening ${app}…`, 'info')
    } catch (err: unknown) {
      toast((err as Error).message, 'error')
    }
  }

  const hasFieldNotes = Boolean(job.notes_from_field)
  const hasFieldData = Boolean(job.sus_opened || job.sus_closed)

  return (
    <div
      ref={setNodeRef}
      style={{ ...cardStyle, ...style }}
      {...attributes}
      {...listeners}
      onClick={onClick}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <span style={{ fontWeight: 700, fontSize: 14, color: T.text }}>{job.job_id}</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {runStatus && (
            <span
              title={
                runStatus === 'failed' && runError
                  ? `failed${runStep ? ` — ${runStep}` : ''}\n\n${runError}`
                  : runStep ? `${runStatus} — ${runStep}` : runStatus
              }
              style={{
                fontSize: 10, fontWeight: 700, lineHeight: 1.4, borderRadius: 10,
                padding: '1px 6px', color: RUN_BADGE[runStatus].color, background: RUN_BADGE[runStatus].bg,
                display: 'inline-flex', alignItems: 'center', gap: 3, whiteSpace: 'nowrap',
                cursor: runStatus === 'failed' && runError ? 'help' : undefined,
              }}
            >
              {RUN_BADGE[runStatus].icon}{runStatus === 'running' && runStep ? ` ${runStep}` : ''}
            </span>
          )}
          {hasFieldNotes && (
            <span style={{ fontSize: 12, lineHeight: 1 }} title="Open for notes from field">📝</span>
          )}
          {onAdvance && (
            <button
              onPointerDown={(e) => e.stopPropagation()}
              onClick={(e) => { e.stopPropagation(); onAdvance() }}
              disabled={inRun}
              title={nextStageLabel ?? 'Move to next stage'}
              style={{
                border: 'none', background: 'transparent', cursor: inRun ? 'default' : 'pointer',
                color: inRun ? T.textMuted : T.textSub, fontSize: 15, lineHeight: 1, padding: 0,
                opacity: inRun ? 0.4 : 1,
              }}
            >→</button>
          )}
          <span style={{ color: T.textMuted, fontSize: 14, lineHeight: 1 }} title="Drag to move">⠿</span>
        </div>
      </div>
      {job.su_string && (
        <div style={{ fontSize: 12, color: T.textSub, marginTop: 2 }}>{job.su_string}</div>
      )}
      <div style={{ fontSize: 11, color: T.textMuted, marginTop: 4 }}>{job.trench}</div>

      <div
        style={{ display: 'flex', gap: 4, marginTop: 10, flexWrap: 'wrap' }}
        onPointerDown={(e) => e.stopPropagation()}
        onClick={(e) => e.stopPropagation()}
      >
        <AppButton label="↗ Metashape" onClick={(e) => handleOpen('metashape', e)} color="#7c3aed" />
      </div>

      {hasFieldData && (
        <div style={{ borderTop: `1px solid ${T.border}`, marginTop: 10, paddingTop: 8, display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          {job.sus_opened && (
            <span style={{ fontSize: 11, color: '#86efac' }}>▲ {job.sus_opened}</span>
          )}
          {job.sus_closed && (
            <span style={{ fontSize: 11, color: '#fca5a5' }}>▼ {job.sus_closed}</span>
          )}
        </div>
      )}
    </div>
  )
}

function AppButton({ label, onClick, color }: {
  label: string; onClick: (e: React.MouseEvent) => void; color: string
}) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: '3px 8px', borderRadius: 4, border: 'none', cursor: 'pointer',
        background: `${color}28`, color, fontWeight: 600, fontSize: 11, lineHeight: 1.4,
      }}
    >
      {label}
    </button>
  )
}

const cardStyle: React.CSSProperties = {
  background: T.surface,
  borderRadius: 8,
  padding: '12px 14px',
  boxShadow: '0 1px 4px rgba(0,0,0,0.3)',
  cursor: 'grab',
  border: `1px solid ${T.border}`,
  userSelect: 'none',
}
