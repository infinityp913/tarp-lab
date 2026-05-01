import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import type { SUEntry } from '../types'

interface Props {
  entry: SUEntry
  onClick: () => void
}

export function SUCard({ entry, onClick }: Props) {
  const {
    attributes, listeners, setNodeRef, transform, transition, isDragging,
  } = useSortable({ id: entry.su_id })

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
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
        <span style={{ fontWeight: 700, fontSize: 14, color: '#1e293b' }}>{entry.su_id}</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ color: '#cbd5e1', fontSize: 14, lineHeight: 1 }} title="Drag to move">⠿</span>
        </div>
      </div>
      {entry.parent_job_id && (
        <div style={{ fontSize: 12, color: '#475569', marginTop: 2 }}>
          ↳ {entry.parent_job_id}
        </div>
      )}
      <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 4 }}>{entry.trench}</div>
    </div>
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
