import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import type { PgramJob } from '../types'
import { openApp } from '../api/pgram'
import { toast } from './Toast'

interface Props {
  job: PgramJob
  onClick: () => void
}

export function JobCard({ job, onClick }: Props) {
  const {
    attributes, listeners, setNodeRef, transform, transition, isDragging,
  } = useSortable({ id: job.job_id })

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
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

  return (
    <div
      ref={setNodeRef}
      style={{ ...cardStyle, ...style }}
      {...attributes}
      {...listeners}
      onClick={onClick}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <span style={{ fontWeight: 700, fontSize: 14, color: '#1e293b' }}>{job.job_id}</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ color: '#cbd5e1', fontSize: 14, lineHeight: 1 }} title="Drag to move">⠿</span>
        </div>
      </div>
      {job.su_string && (
        <div style={{ fontSize: 12, color: '#475569', marginTop: 2 }}>{job.su_string}</div>
      )}
      <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 4 }}>{job.trench}</div>

      <div
        style={{ display: 'flex', gap: 4, marginTop: 10, flexWrap: 'wrap' }}
        onPointerDown={(e) => e.stopPropagation()}
        onClick={(e) => e.stopPropagation()}
      >
        <AppButton label="↗ Metashape" onClick={(e) => handleOpen('metashape', e)} color="#7c3aed" />
        <AppButton label="↗ CloudCompare" onClick={(e) => handleOpen('cloudcompare', e)} color="#0891b2" />
        <AppButton label="↗ QGIS" onClick={(e) => handleOpen('qgis', e)} color="#16a34a" />
      </div>
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
        background: `${color}18`, color, fontWeight: 600, fontSize: 11, lineHeight: 1.4,
      }}
    >
      {label}
    </button>
  )
}

const cardStyle: React.CSSProperties = {
  background: '#fff',
  borderRadius: 8,
  padding: '12px 14px',
  boxShadow: '0 1px 4px rgba(0,0,0,0.08)',
  cursor: 'grab',
  border: '1px solid #e2e8f0',
  userSelect: 'none',
}
