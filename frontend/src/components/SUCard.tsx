import { useRef, useState } from 'react'
import { useDraggable } from '@dnd-kit/core'
import { CSS } from '@dnd-kit/utilities'
import type { SUEntry } from '../types'
import { openPly, openBothPly, updatePgrams } from '../api/su'
import { toast } from './Toast'
import { T } from '../tokens'

interface Props {
  entry: SUEntry
  onClick: () => void
  onUpdated: (entry: SUEntry) => void
}

export function SUCard({ entry, onClick, onUpdated }: Props) {
  const {
    attributes, listeners, setNodeRef, transform, isDragging,
  } = useDraggable({ id: entry.su_id })

  const [top, setTop] = useState(entry.top_pgram)
  const [bot, setBot] = useState(entry.bot_pgram)
  const [plyLoading, setPlyLoading] = useState<'top' | 'bot' | 'both' | null>(null)
  const savedTop = useRef(entry.top_pgram)
  const savedBot = useRef(entry.bot_pgram)

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    opacity: isDragging ? 0.4 : 1,
  }

  async function handleOpenPly(e: React.MouseEvent, type: 'top' | 'bot') {
    e.stopPropagation()
    setPlyLoading(type)
    try {
      await openPly(entry.su_id, type)
    } catch (err: unknown) {
      toast((err as Error).message || 'Failed to open PLY', 'error')
    } finally {
      setPlyLoading(null)
    }
  }

  async function handleOpenBothPly(e: React.MouseEvent) {
    e.stopPropagation()
    setPlyLoading('both')
    try {
      await openBothPly(entry.su_id)
    } catch (err: unknown) {
      toast((err as Error).message || 'Failed to open PLYs', 'error')
    } finally {
      setPlyLoading(null)
    }
  }

  async function handlePgramBlur() {
    if (top === savedTop.current && bot === savedBot.current) return
    try {
      await updatePgrams(entry.su_id, top, bot)
      savedTop.current = top
      savedBot.current = bot
      onUpdated({ ...entry, top_pgram: top, bot_pgram: bot })
    } catch (err: unknown) {
      toast((err as Error).message || 'Failed to save pgram numbers', 'error')
      setTop(savedTop.current)
      setBot(savedBot.current)
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
        <span style={{ fontWeight: 700, fontSize: 14, color: T.text }}>{entry.su_id}</span>
        <span style={{ color: T.textMuted, fontSize: 14, lineHeight: 1 }} title="Drag to move">⠿</span>
      </div>

      {/* Inline pgram number inputs — stop propagation so dragging doesn't interfere */}
      <div
        style={{ display: 'flex', gap: 4, marginTop: 6 }}
        onPointerDown={(e) => e.stopPropagation()}
        onClick={(e) => e.stopPropagation()}
      >
        <input
          value={top}
          onChange={(e) => setTop(e.target.value)}
          onBlur={handlePgramBlur}
          placeholder="Top pgram"
          style={pgramInput}
        />
        <input
          value={bot}
          onChange={(e) => setBot(e.target.value)}
          onBlur={handlePgramBlur}
          placeholder="Bot pgram"
          style={pgramInput}
        />
      </div>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', marginTop: 4 }}>
        <div
          style={{ display: 'flex', gap: 4 }}
          onPointerDown={(e) => e.stopPropagation()}
          onClick={(e) => e.stopPropagation()}
        >
          {entry.top_pgram && (
            <button
              style={plyBtn}
              disabled={plyLoading !== null}
              title={`Open Top PLY (pgram ${entry.top_pgram}) in MeshLab`}
              onClick={(e) => handleOpenPly(e, 'top')}
            >
              {plyLoading === 'top' ? '…' : 'Top PLY ↗'}
            </button>
          )}
          {entry.bot_pgram && (
            <button
              style={plyBtn}
              disabled={plyLoading !== null}
              title={`Open Bottom PLY (pgram ${entry.bot_pgram}) in MeshLab`}
              onClick={(e) => handleOpenPly(e, 'bot')}
            >
              {plyLoading === 'bot' ? '…' : 'Bot PLY ↗'}
            </button>
          )}
          {entry.top_pgram && entry.bot_pgram && (
            <button
              style={plyBtn}
              disabled={plyLoading !== null}
              title={`Open both PLYs (pgrams ${entry.top_pgram} + ${entry.bot_pgram}) together in CloudCompare`}
              onClick={handleOpenBothPly}
            >
              {plyLoading === 'both' ? '…' : 'Both ↗'}
            </button>
          )}
        </div>
      </div>

    </div>
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

const plyBtn: React.CSSProperties = {
  padding: '1px 7px',
  borderRadius: 4,
  border: `1px solid ${T.border}`,
  background: 'transparent',
  color: T.textMuted,
  fontSize: 10,
  fontWeight: 600,
  cursor: 'pointer',
  letterSpacing: '0.03em',
}

const pgramInput: React.CSSProperties = {
  flex: 1,
  padding: '3px 6px',
  borderRadius: 4,
  border: `1px solid ${T.inputBorder}`,
  background: T.inputBg,
  color: T.textSub,
  fontSize: 11,
  fontFamily: 'inherit',
  outline: 'none',
  minWidth: 0,
}
