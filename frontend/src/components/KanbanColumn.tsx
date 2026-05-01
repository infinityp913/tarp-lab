import { useDroppable } from '@dnd-kit/core'
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable'

interface Props<T> {
  id: string
  title: string
  items: T[]
  getId: (item: T) => string
  renderCard: (item: T) => React.ReactNode
  count: number
  color?: string
}

export function KanbanColumn<T>({ id, title, items, getId, renderCard, count, color = '#3b82f6' }: Props<T>) {
  const { setNodeRef, isOver } = useDroppable({ id })

  return (
    <div style={{
      minWidth: 240, maxWidth: 260,
      background: isOver ? '#eff6ff' : '#f8fafc',
      borderRadius: 10,
      border: isOver ? '2px dashed #3b82f6' : '2px solid transparent',
      display: 'flex', flexDirection: 'column',
      flexShrink: 0,
      transition: 'border-color 0.15s, background 0.15s',
    }}>
      <div style={{
        padding: '12px 14px 10px',
        borderBottom: '1px solid #e2e8f0',
        display: 'flex', alignItems: 'center', gap: 8,
      }}>
        <span style={{
          display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
          background: color, flexShrink: 0,
        }} />
        <span style={{ fontWeight: 700, fontSize: 13, color: '#1e293b', flex: 1 }}>{title}</span>
        <span style={{
          background: '#e2e8f0', color: '#475569', borderRadius: 20,
          padding: '1px 8px', fontSize: 12, fontWeight: 600,
        }}>{count}</span>
      </div>

      <div
        ref={setNodeRef}
        style={{
          padding: '10px 10px',
          display: 'flex', flexDirection: 'column', gap: 8,
          minHeight: 120, flex: 1,
          overflowY: 'auto', maxHeight: 'calc(100vh - 220px)',
        }}
      >
        <SortableContext
          items={items.map(getId)}
          strategy={verticalListSortingStrategy}
        >
          {items.map(renderCard)}
        </SortableContext>
        {items.length === 0 && (
          <div style={{
            textAlign: 'center', color: '#cbd5e1', fontSize: 12,
            paddingTop: 24, paddingBottom: 8,
          }}>
            Drop here
          </div>
        )}
      </div>
    </div>
  )
}
