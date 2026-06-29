import { useRef, useState } from 'react'
import { useDraggable } from '@dnd-kit/core'
import { CSS } from '@dnd-kit/utilities'
import type { SUEntry } from '../types'
import {
  openPly, openBothPly, updatePgrams,
  openBins, openVolume, openDebugImage,
} from '../api/su'
import { toast } from './Toast'
import { T } from '../tokens'

interface Props {
  entry: SUEntry
  onClick: () => void
  onUpdated: (entry: SUEntry) => void
  onAdvance?: () => void
  nextStageLabel?: string
}

export function SUCard({ entry, onClick, onUpdated, onAdvance, nextStageLabel }: Props) {
  const {
    attributes, listeners, setNodeRef, transform, isDragging,
  } = useDraggable({ id: entry.su_id })

  const [top, setTop] = useState(entry.top_pgram)
  const [bot, setBot] = useState(entry.bot_pgram)
  const [plyLoading, setPlyLoading] = useState<'top' | 'bot' | 'both' | null>(null)
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const savedTop = useRef(entry.top_pgram)
  const savedBot = useRef(entry.bot_pgram)

  const stage = entry.stage
  const hasDebugImage = entry.snip_method === 'auto'

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

  async function handleAction(e: React.MouseEvent, key: string, fn: () => Promise<void>) {
    e.stopPropagation()
    setActionLoading(key)
    try {
      await fn()
    } catch (err: unknown) {
      toast((err as Error).message || `Failed: ${key}`, 'error')
    } finally {
      setActionLoading(null)
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

  const busy = plyLoading !== null || actionLoading !== null

  return (
    <div
      ref={setNodeRef}
      style={{ ...cardStyle, ...style }}
      {...attributes}
      {...listeners}
      onClick={onClick}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontWeight: 700, fontSize: 14, color: T.text }}>{entry.su_id}</span>
          {entry.ready && (
            <span
              style={readyBadge}
              title="Ready to extract — both top & bottom PLYs are processed"
            >
              ✓ Ready
            </span>
          )}
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          {onAdvance && (
            <button
              style={advanceBtn}
              title={nextStageLabel ?? 'Move to next stage'}
              onClick={(e) => { e.stopPropagation(); onAdvance() }}
              onPointerDown={(e) => e.stopPropagation()}
            >
              →
            </button>
          )}
          <span style={{ color: T.textMuted, fontSize: 14, lineHeight: 1 }} title="Drag to move">⠿</span>
        </div>
      </div>

      {/* Inline pgram number inputs */}
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

      {/* PLY open buttons (always visible when pgrams are set) */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', marginTop: 4 }}>
        <div
          style={{ display: 'flex', gap: 4 }}
          onPointerDown={(e) => e.stopPropagation()}
          onClick={(e) => e.stopPropagation()}
        >
          {entry.top_pgram && (
            <button
              style={plyBtn}
              disabled={busy}
              title={`Open Top PLY (pgram ${entry.top_pgram}) in MeshLab`}
              onClick={(e) => handleOpenPly(e, 'top')}
            >
              {plyLoading === 'top' ? '…' : 'Top PLY ↗'}
            </button>
          )}
          {entry.bot_pgram && (
            <button
              style={plyBtn}
              disabled={busy}
              title={`Open Bottom PLY (pgram ${entry.bot_pgram}) in MeshLab`}
              onClick={(e) => handleOpenPly(e, 'bot')}
            >
              {plyLoading === 'bot' ? '…' : 'Bot PLY ↗'}
            </button>
          )}
          {entry.top_pgram && entry.bot_pgram && (
            <button
              style={plyBtn}
              disabled={busy}
              title={`Open both PLYs together in CloudCompare`}
              onClick={handleOpenBothPly}
            >
              {plyLoading === 'both' ? '…' : 'Both ↗'}
            </button>
          )}
        </div>
      </div>

      {/* Stage-specific action buttons */}
      <div
        style={{ display: 'flex', gap: 4, marginTop: 4, flexWrap: 'wrap' }}
        onPointerDown={(e) => e.stopPropagation()}
        onClick={(e) => e.stopPropagation()}
      >
        {stage === 'to_be_snipped' && (
          <button
            style={{ ...actionBtn, borderColor: '#8b5cf666', color: '#a78bfa' }}
            disabled={busy}
            title="Open the two pre-snip .bin files in CloudCompare for manual snipping"
            onClick={(e) => handleAction(e, 'bins', () => openBins(entry.su_id))}
          >
            {actionLoading === 'bins' ? '…' : 'Open in CC ↗'}
          </button>
        )}

        {(stage === 'to_be_post_snipped' || stage === 'volumetrics_created') && hasDebugImage && (
          <button
            style={{ ...actionBtn, borderColor: '#06b6d466', color: '#22d3ee' }}
            disabled={busy}
            title="Show auto-snip debug image"
            onClick={(e) => handleAction(e, 'debug', () => openDebugImage(entry.su_id))}
          >
            {actionLoading === 'debug' ? '…' : 'Debug Img ↗'}
          </button>
        )}

        {stage === 'volumetrics_created' && (
          <button
            style={{ ...actionBtn, borderColor: '#22c55e66', color: '#4ade80' }}
            disabled={busy}
            title="Open the final volume OBJ mesh"
            onClick={(e) => handleAction(e, 'volume', () => openVolume(entry.su_id))}
          >
            {actionLoading === 'volume' ? '…' : 'Volume ↗'}
          </button>
        )}
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

const readyBadge: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 3,
  background: '#22c55e22', color: '#22c55e',
  border: '1px solid #22c55e66', borderRadius: 20,
  padding: '0 7px', fontSize: 10, fontWeight: 700,
  lineHeight: 1.7, letterSpacing: '0.02em', whiteSpace: 'nowrap',
}

const advanceBtn: React.CSSProperties = {
  padding: '1px 6px',
  borderRadius: 4,
  border: `1px solid ${T.border}`,
  background: 'transparent',
  color: T.textSub,
  fontSize: 13,
  fontWeight: 600,
  cursor: 'pointer',
  lineHeight: 1.4,
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

const actionBtn: React.CSSProperties = {
  padding: '1px 7px',
  borderRadius: 4,
  border: `1px solid ${T.border}`,
  background: 'transparent',
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
