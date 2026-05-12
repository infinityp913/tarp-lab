import { useDroppable } from '@dnd-kit/core'
import { T } from '../tokens'

interface Props<T> {
  id: string
  title: string
  items: T[]
  renderCard: (item: T) => React.ReactNode
  count: number
  color?: string
  isValidTarget?: boolean
}

export function KanbanColumn<T>({ id, title, items, renderCard, count, color = '#3b82f6', isValidTarget = true }: Props<T>) {
  const { setNodeRef, isOver } = useDroppable({ id })

  const invalidHover = isOver && !isValidTarget

  return (
    <div style={{
      minWidth: 240, maxWidth: 260,
      background: invalidHover ? '#2d0808' : isOver ? T.colBgOver : T.colBg,
      borderRadius: 10,
      border: invalidHover ? '2px dashed #ef4444' : isOver ? `2px dashed ${color}` : '2px solid transparent',
      display: 'flex', flexDirection: 'column',
      flexShrink: 0,
      transition: 'border-color 0.15s, background 0.15s',
    }}>
      <div style={{
        padding: '12px 14px 10px',
        borderBottom: `1px solid ${T.border}`,
        display: 'flex', alignItems: 'center', gap: 8,
      }}>
        <span style={{
          display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
          background: color, flexShrink: 0,
        }} />
        <span style={{ fontWeight: 700, fontSize: 13, color: T.text, flex: 1 }}>{title}</span>
        <span style={{
          background: T.badgeBg, color: T.badgeText, borderRadius: 20,
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
          {items.map(renderCard)}
        {items.length === 0 && (
          <div style={{
            textAlign: 'center', color: T.textMuted, fontSize: 12,
            paddingTop: 24, paddingBottom: 8,
          }}>
            Drop here
          </div>
        )}
      </div>
    </div>
  )
}
