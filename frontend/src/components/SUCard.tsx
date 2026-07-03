import { useRef, useState } from 'react'
import { useDraggable } from '@dnd-kit/core'
import { CSS } from '@dnd-kit/utilities'
import type { SUEntry } from '../types'
import {
  openPly, openBothPly, updatePgrams,
  openBins, openPostSnipBin, openVolume, openTopVolume, openSuSheet, openDebugImage, openLidar, startVolumeRun,
  updateReadyForSheet, updateFlagged,
} from '../api/su'
import { toast } from './Toast'
import { T } from '../tokens'

interface Props {
  entry: SUEntry
  onClick: () => void
  onUpdated: (entry: SUEntry) => void
  onAdvance?: () => void
  nextStageLabel?: string
  runActive?: boolean
  onRunStarted?: () => void
}

export function SUCard({ entry, onClick, onUpdated, onAdvance, nextStageLabel, runActive, onRunStarted }: Props) {
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

  async function handlePostSnipOne(e: React.MouseEvent) {
    e.stopPropagation()
    setActionLoading('postsnip')
    try {
      await startVolumeRun('post_snip', entry.su_id)
      toast(`Started post-snip on SU ${entry.su_id}…`, 'info')
      onRunStarted?.()
    } catch (err: unknown) {
      toast((err as Error).message || 'Failed to start post-snip', 'error')
    } finally {
      setActionLoading(null)
    }
  }

  async function handleFlagToggle(e: React.MouseEvent) {
    e.stopPropagation()
    const next = !entry.flagged
    setActionLoading('flag')
    try {
      await updateFlagged(entry.su_id, next)
      onUpdated({ ...entry, flagged: next })
    } catch (err: unknown) {
      toast((err as Error).message || 'Failed to update flag', 'error')
    } finally {
      setActionLoading(null)
    }
  }

  async function handleReadyForSheetToggle(e: React.ChangeEvent<HTMLInputElement>) {
    const next = e.target.checked
    setActionLoading('readysheet')
    try {
      await updateReadyForSheet(entry.su_id, next)
      onUpdated({ ...entry, ready_for_sheet: next })
    } catch (err: unknown) {
      toast((err as Error).message || 'Failed to update readiness', 'error')
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
      style={{ ...cardStyle, ...(entry.flagged ? flaggedCardStyle : null), ...style }}
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
              title="Ready to extract — both top & bottom PLYs are processed and a LiDAR scan exists"
            >
              ✓ Ready
            </span>
          )}
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <button
            onPointerDown={(e) => e.stopPropagation()}
            onClick={handleFlagToggle}
            disabled={actionLoading === 'flag'}
            title={entry.flagged ? 'Flagged — click to clear' : 'Flag this card'}
            style={{
              border: 'none', background: 'transparent',
              cursor: actionLoading === 'flag' ? 'default' : 'pointer',
              fontSize: 13, lineHeight: 1, padding: 0,
              opacity: actionLoading === 'flag' ? 0.4 : (entry.flagged ? 1 : 0.35),
              filter: entry.flagged ? 'none' : 'grayscale(1)',
            }}
          >🚩</button>
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

        {stage === 'to_be_snipped' && entry.has_lidar && (
          <button
            style={{ ...actionBtn, borderColor: '#f59e0b66', color: '#fbbf24' }}
            disabled={busy}
            title="Reveal this SU's LiDAR scan in Explorer and open the USDZ web viewer (drag the file in)"
            onClick={(e) => handleAction(e, 'lidar', () => openLidar(entry.su_id))}
          >
            {actionLoading === 'lidar' ? '…' : 'LiDAR ↗'}
          </button>
        )}

        {stage === 'to_be_post_snipped' && (
          <button
            style={{ ...actionBtn, borderColor: '#ec489966', color: '#f472b6' }}
            disabled={busy || runActive}
            title={runActive
              ? 'A volume run is already in progress'
              : `Run post-snip on just this SU (${entry.su_id}) — test a single card`}
            onClick={handlePostSnipOne}
          >
            {actionLoading === 'postsnip' ? '…' : 'Post-Snip ↗'}
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
            style={{ ...actionBtn, borderColor: '#8b5cf666', color: '#a78bfa' }}
            disabled={busy}
            title="Open the post-snip debug .bin in CloudCompare"
            onClick={(e) => handleAction(e, 'postsnipbin', () => openPostSnipBin(entry.su_id))}
          >
            {actionLoading === 'postsnipbin' ? '…' : 'Debug in CC ↗'}
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

        {stage === 'volumetrics_created' && (
          <button
            style={{ ...actionBtn, borderColor: '#14b8a666', color: '#2dd4bf' }}
            disabled={busy}
            title="Open the SU top OBJ mesh"
            onClick={(e) => handleAction(e, 'topvolume', () => openTopVolume(entry.su_id))}
          >
            {actionLoading === 'topvolume' ? '…' : 'Top Volume ↗'}
          </button>
        )}

        {stage === 'su_sheet_created' && (
          <button
            style={{ ...actionBtn, borderColor: '#22c55e66', color: '#4ade80' }}
            disabled={busy}
            title="Open the generated SU sheet PDF"
            onClick={(e) => handleAction(e, 'susheet', () => openSuSheet(entry.su_id))}
          >
            {actionLoading === 'susheet' ? '…' : 'SU Sheet ↗'}
          </button>
        )}
      </div>

      {/* Ready-for-SU-sheet checkbox — Create SU Sheet only runs on checked cards */}
      {stage === 'volumetrics_created' && (
        <label
          style={{
            ...readyForSheetRow,
            ...(entry.ready_for_sheet ? readyForSheetRowChecked : null),
          }}
          onPointerDown={(e) => e.stopPropagation()}
          onClick={(e) => e.stopPropagation()}
          title="Mark this card ready for SU sheet creation — the Create SU Sheet button only runs on checked cards"
        >
          <input
            type="checkbox"
            checked={!!entry.ready_for_sheet}
            disabled={actionLoading === 'readysheet'}
            onChange={handleReadyForSheetToggle}
            style={{ cursor: 'pointer', accentColor: '#22c55e', margin: 0 }}
          />
          <span>
            {actionLoading === 'readysheet' ? 'Saving…' : 'Ready for SU sheet'}
          </span>
        </label>
      )}
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

const flaggedCardStyle: React.CSSProperties = {
  borderColor: '#ef4444',
  borderLeft: '3px solid #ef4444',
}

const readyBadge: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 3,
  background: '#22c55e22', color: '#22c55e',
  border: '1px solid #22c55e66', borderRadius: 20,
  padding: '0 7px', fontSize: 10, fontWeight: 700,
  lineHeight: 1.7, letterSpacing: '0.02em', whiteSpace: 'nowrap',
}

const readyForSheetRow: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 6,
  marginTop: 6, padding: '4px 7px', borderRadius: 4,
  border: '1px solid #22c55e33', background: '#22c55e0d',
  color: T.textMuted, fontSize: 11, fontWeight: 600,
  cursor: 'pointer', userSelect: 'none',
}

const readyForSheetRowChecked: React.CSSProperties = {
  border: '1px solid #22c55e66', background: '#22c55e1f', color: '#4ade80',
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
