import { Fragment, useCallback, useEffect, useRef, useState } from 'react'
import {
  DndContext, DragEndEvent, DragOverlay, DragStartEvent,
  PointerSensor, useSensor, useSensors,
} from '@dnd-kit/core'
import {
  fetchEntries, provisionFromPly, updateStage,
  startVolumeRun, getVolumeRunStatus, startChainRun,
  batchMoveToPreSnip,
} from '../api/su'
import type { SUEntry, VolumeRunKind, VolumeRunStatus } from '../types'
import { SU_STAGES } from '../types'
import { KanbanColumn } from './KanbanColumn'
import { SUCard } from './SUCard'
import { SUDetailModal } from './SUDetailModal'
import { CreateSUModal } from './CreateSUModal'
import { ConfirmationModal } from './ConfirmationModal'
import { toast } from './Toast'
import { T } from '../tokens'

const SU_ORDER = [
  'not_started',
  'to_be_pre_snipped',
  'to_be_snipped',
  'to_be_post_snipped',
  'volumetrics_created',
  'su_sheet_created',
  'uploaded_air',
]

function isValidSUMove(from: string, to: string): boolean {
  if (from === to) return false
  const fi = SU_ORDER.indexOf(from)
  const ti = SU_ORDER.indexOf(to)
  if (fi < 0 || ti < 0) return false
  // Backward always OK; forward: one step at a time, except:
  // - not_started → to_be_pre_snipped (one step)
  // - to_be_snipped → to_be_post_snipped (manual snip, confirmed via dialog)
  if (ti < fi) return true
  return ti === fi + 1
}

/** Extra gate: forward from not_started requires ready flag; others just check step */
function isValidSUDrop(entry: SUEntry, to: string): boolean {
  if (!isValidSUMove(entry.stage, to)) return false
  if (entry.stage === 'not_started' && to === 'to_be_pre_snipped') return !!entry.ready
  return true
}

const STAGE_COLORS: Record<string, string> = {
  not_started: '#94a3b8',
  to_be_pre_snipped: '#f97316',
  to_be_snipped: '#8b5cf6',
  to_be_post_snipped: '#ec4899',
  volumetrics_created: '#f59e0b',
  su_sheet_created: '#22c55e',
  uploaded_air: '#0ea5e9',
}

export function SUTab() {
  const [entries, setEntries] = useState<SUEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [trenchFilter, setTrenchFilter] = useState('All Trenches')
  const [readyFilter, setReadyFilter] = useState<'all' | 'ready' | 'not_ready'>('all')
  const [detailEntry, setDetailEntry] = useState<SUEntry | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [draggingEntry, setDraggingEntry] = useState<SUEntry | null>(null)
  const [scanning, setScanning] = useState(false)
  const [volRun, setVolRun] = useState<VolumeRunStatus | null>(null)
  const [confirmState, setConfirmState] = useState<{
    message: string; suId: string; targetStage: string
  } | null>(null)
  const [batchMoveState, setBatchMoveState] = useState<{ loading: boolean }>({ loading: false })
  const pollingRef = useRef(false)
  const topScrollRef = useRef<HTMLDivElement>(null)
  const contentScrollRef = useRef<HTMLDivElement>(null)
  const phantomRef = useRef<HTMLDivElement>(null)

  // Keep top scrollbar phantom width in sync with actual content scrollWidth after every render
  useEffect(() => {
    const content = contentScrollRef.current
    const phantom = phantomRef.current
    if (content && phantom) phantom.style.width = `${content.scrollWidth}px`
  })

  function handleTopScroll() {
    if (contentScrollRef.current && topScrollRef.current) {
      contentScrollRef.current.scrollLeft = topScrollRef.current.scrollLeft
    }
  }
  function handleContentScroll() {
    if (contentScrollRef.current && topScrollRef.current) {
      topScrollRef.current.scrollLeft = contentScrollRef.current.scrollLeft
    }
  }

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } })
  )

  const load = useCallback(async () => {
    try {
      const data = await fetchEntries()
      setEntries(data)
    } catch {
      toast('Failed to load SU entries', 'error')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  // --- Volume run polling ---
  const pollOnce = useCallback(async () => {
    let status: VolumeRunStatus
    try {
      status = await getVolumeRunStatus()
    } catch {
      pollingRef.current = false
      return
    }
    setVolRun(status.status !== 'idle' ? status : null)
    await load()
    if (status.active) {
      window.setTimeout(pollOnce, 2500)
    } else {
      pollingRef.current = false
      if (status.status === 'done') {
        toast(`Script finished — ${status.cards_advanced} card${status.cards_advanced !== 1 ? 's' : ''} advanced`, 'success')
      } else if (status.status === 'failed') {
        toast(`Script failed: ${status.error || 'unknown error'}`, 'error')
      }
    }
  }, [load])

  const startPolling = useCallback(() => {
    if (pollingRef.current) return
    pollingRef.current = true
    pollOnce()
  }, [pollOnce])

  // Resume polling if a run is already in flight
  useEffect(() => {
    getVolumeRunStatus()
      .then((s) => { if (s.active) startPolling() })
      .catch(() => {})
  }, [startPolling])

  async function handleVolumeRun(kind: VolumeRunKind) {
    try {
      const r = await startVolumeRun(kind)
      toast(`Started ${kind.replace('_', '-')} on ${r.count ?? 0} card${r.count === 1 ? '' : 's'}…`, 'info')
      startPolling()
    } catch (e: unknown) {
      toast((e as Error).message, 'error')
    }
  }

  async function handleScanPly() {
    setScanning(true)
    try {
      const result = await provisionFromPly()
      if (result.created.length > 0) {
        toast(`Created ${result.created.length} volume card${result.created.length !== 1 ? 's' : ''} from ${result.ply_count} PLY file${result.ply_count !== 1 ? 's' : ''}`, 'success')
        await load()
      } else if (result.ply_count === 0) {
        toast('No PLY files found in output directory', 'error')
      } else {
        toast(`${result.ply_count} PLY file${result.ply_count !== 1 ? 's' : ''} scanned — all SUs already have cards`, 'success')
      }
    } catch (err: unknown) {
      toast((err as Error).message || 'PLY scan failed', 'error')
    } finally {
      setScanning(false)
    }
  }

  const trenches = [...new Set(entries.map(e => e.trench).filter(Boolean))].sort()
  const readyCount = entries.filter((e) => e.ready).length

  const filtered = entries.filter((e) => {
    if (trenchFilter !== 'All Trenches' && e.trench !== trenchFilter) return false
    if (readyFilter === 'ready' && !e.ready) return false
    if (readyFilter === 'not_ready' && e.ready) return false
    return true
  })

  const byStage = (stageKey: string) =>
    filtered.filter((e) => e.stage === stageKey)

  function handleDragStart(event: DragStartEvent) {
    const entry = entries.find((e) => e.su_id === event.active.id)
    if (entry) setDraggingEntry(entry)
  }

  async function handleDragEnd(event: DragEndEvent) {
    setDraggingEntry(null)
    const { active, over } = event
    if (!over) return

    const suId = String(active.id)
    const overId = String(over.id)

    const stageKeys = new Set(SU_STAGES.map((s) => s.key))
    const targetStage = stageKeys.has(overId)
      ? overId
      : entries.find((e) => e.su_id === overId)?.stage ?? overId

    const entry = entries.find((e) => e.su_id === suId)
    if (!entry || entry.stage === targetStage) return

    if (!isValidSUDrop(entry, targetStage)) {
      if (entry.stage === 'not_started' && targetStage === 'to_be_pre_snipped' && !entry.ready) {
        toast('Not ready: both top & bottom PLYs must be processed before queuing for pre-snip', 'error')
      } else if (entry.stage === 'not_started' && targetStage === 'volumetrics_created') {
        toast('Use the snip pipeline — drag to To Be Pre-Snipped first', 'error')
      } else {
        toast('Move one step at a time', 'error')
      }
      return
    }

    await requestMove(suId, targetStage, entry)
  }

  async function requestMove(suId: string, targetStage: string, entry?: SUEntry) {
    const e = entry ?? entries.find((en) => en.su_id === suId)
    if (!e) return

    // Check if this transition requires confirmation (e.g. manual snip drag)
    const result = await updateStage(suId, targetStage, false)
    if (result.requires_confirmation && result.message) {
      setConfirmState({ message: result.message, suId, targetStage })
      return
    }

    applyMove(suId, targetStage)
  }

  async function handleConfirm() {
    if (!confirmState) return
    const { suId, targetStage } = confirmState
    setConfirmState(null)
    try {
      await updateStage(suId, targetStage, true)
      applyMove(suId, targetStage)
      toast('Stage updated', 'success')
    } catch (err: unknown) {
      toast((err as Error).message || 'Failed to update stage', 'error')
    }
  }

  function applyMove(suId: string, targetStage: string) {
    setEntries((prev) =>
      prev.map((e) => e.su_id === suId ? { ...e, stage: targetStage } : e)
    )
  }

  async function handleChainRun() {
    try {
      const r = await startChainRun()
      toast(`Started full pipeline chain on ${r.count ?? 0} card stage(s)…`, 'info')
      startPolling()
    } catch (e: unknown) {
      toast((e as Error).message, 'error')
    }
  }

  async function handleBatchMoveToPreSnip() {
    const readyCount = byStage('not_started').filter((e) => e.ready).length
    setBatchMoveState({ loading: true })
    toast(`Moving ${readyCount} ready card${readyCount !== 1 ? 's' : ''} to To Be Pre-Snipped…`, 'info')
    try {
      const r = await batchMoveToPreSnip()
      if (r.moved === 0) {
        toast(r.detail ?? 'No ready cards in Not Started to move', 'error')
      } else {
        toast(`Moved ${r.moved} ready card${r.moved !== 1 ? 's' : ''} to To Be Pre-Snipped${r.skipped ? ` (${r.skipped} failed)` : ''}`, 'success')
        await load()
      }
    } catch (err: unknown) {
      toast((err as Error).message || 'Batch move failed', 'error')
    } finally {
      setBatchMoveState({ loading: false })
    }
  }

  function nextSUStage(stage: string): string | null {
    const idx = SU_ORDER.indexOf(stage)
    if (idx < 0 || idx >= SU_ORDER.length - 1) return null
    return SU_ORDER[idx + 1]
  }

  function stageLabel(key: string): string {
    return SU_STAGES.find((s) => s.key === key)?.label ?? key
  }

  const runActive = volRun?.active ?? false

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20, flexWrap: 'wrap' }}>
        <select
          value={trenchFilter}
          onChange={(e) => setTrenchFilter(e.target.value)}
          style={selectStyle}
        >
          <option>All Trenches</option>
          {trenches.map((t) => <option key={t}>{t}</option>)}
        </select>
        {trenchFilter !== 'All Trenches' && (
          <span style={filterChip}>
            {trenchFilter}
            <button onClick={() => setTrenchFilter('All Trenches')} style={chipClear} title="Clear filter">✕</button>
          </span>
        )}
        <select
          value={readyFilter}
          onChange={(e) => setReadyFilter(e.target.value as typeof readyFilter)}
          style={selectStyle}
          title="Filter by whether the volume is ready to be extracted"
        >
          <option value="all">All readiness</option>
          <option value="ready">Ready to extract</option>
          <option value="not_ready">Not ready</option>
        </select>
        {readyFilter !== 'all' && (
          <span style={filterChip}>
            {readyFilter === 'ready' ? '✓ Ready' : 'Not ready'}
            <button onClick={() => setReadyFilter('all')} style={chipClear} title="Clear filter">✕</button>
          </span>
        )}
        <span style={{ fontSize: 13, color: T.textMuted }}>
          {filtered.length} entr{filtered.length !== 1 ? 'ies' : 'y'}
          {(trenchFilter !== 'All Trenches' || readyFilter !== 'all') && ` of ${entries.length}`}
          {` · ${readyCount} ready`}
        </span>
        <button onClick={load} style={refreshBtn} title="Refresh">↻ Refresh</button>
        <button onClick={handleScanPly} disabled={scanning} style={scanBtn} title="Scan PLY directory and auto-create volume cards">
          {scanning ? 'Scanning…' : '⬡ Scan PLY'}
        </button>
        <button onClick={() => setShowCreate(true)} style={addBtn}>+ New SU Entry</button>
      </div>

      {volRun && volRun.status !== 'idle' && (
        <VolumeRunBanner run={volRun} onDismiss={() => setVolRun(null)} />
      )}

      {loading ? (
        <div style={{ textAlign: 'center', padding: 48, color: T.textSub }}>Loading SU entries…</div>
      ) : (
        <DndContext sensors={sensors} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
          {/* Top scrollbar — synced with content below */}
          <style>{`
            .su-top-scroll::-webkit-scrollbar { height: 10px; }
            .su-top-scroll::-webkit-scrollbar-track { background: transparent; }
            .su-top-scroll::-webkit-scrollbar-thumb { background: #475569; border-radius: 5px; }
            .su-top-scroll::-webkit-scrollbar-thumb:hover { background: #64748b; }
          `}</style>
          <div
            ref={topScrollRef}
            className="su-top-scroll"
            onScroll={handleTopScroll}
            style={{ overflowX: 'auto', overflowY: 'hidden', height: 14, marginBottom: 4 }}
          >
            <div ref={phantomRef} style={{ height: 1 }} />
          </div>
          <div
            ref={contentScrollRef}
            onScroll={handleContentScroll}
            style={{ display: 'flex', gap: 8, overflowX: 'auto', paddingBottom: 12, alignItems: 'flex-start' }}
          >
            {SU_STAGES.map(({ key, label }) => (
              <Fragment key={key}>
                <KanbanColumn
                  id={key}
                  title={label}
                  items={byStage(key)}
                  count={byStage(key).length}
                  color={STAGE_COLORS[key]}
                  isValidTarget={draggingEntry ? (draggingEntry.stage === key ? 'source' : isValidSUDrop(draggingEntry, key)) : true}
                  renderCard={(entry) => {
                    const next = nextSUStage(entry.stage)
                    return (
                      <SUCard
                        key={entry.su_id}
                        entry={entry}
                        onClick={() => setDetailEntry(entry)}
                        onUpdated={(updated) =>
                          setEntries((prev) => prev.map((e) => e.su_id === updated.su_id ? updated : e))
                        }
                        onAdvance={next ? () => requestMove(entry.su_id, next, entry) : undefined}
                        nextStageLabel={next ? `Move to ${stageLabel(next)}` : undefined}
                      />
                    )
                  }}
                />

                {/* Gutter buttons between columns */}
                {key === 'not_started' && (
                  <ActionGutter>
                    <GutterButton
                      label="Move Ready" sub="→ Pre-Snip" color="#94a3b8"
                      loading={batchMoveState.loading}
                      loadingLabel="Moving…"
                      disabled={batchMoveState.loading || runActive}
                      count={byStage('not_started').filter((e) => e.ready).length}
                      title={`Move all ${byStage('not_started').filter((e) => e.ready).length} ready card(s) from Not Started to To Be Pre-Snipped`}
                      onClick={handleBatchMoveToPreSnip}
                    />
                    <GutterButton
                      label="Run All" sub="Pipeline" color="#6366f1"
                      icon="▶▶"
                      disabled
                      title="Pipeline run is disabled for now — it relies on auto-snip, which isn't reliable yet. Run each stage manually and snip in CloudCompare."
                      onClick={handleChainRun}
                    />
                  </ActionGutter>
                )}
                {key === 'to_be_pre_snipped' && (
                  <ActionGutter>
                    <GutterButton
                      label="Pre-Snip" sub="Script" color="#f97316"
                      disabled={runActive}
                      count={byStage('to_be_pre_snipped').length}
                      title={`Run pre_snip_script.py on ${byStage('to_be_pre_snipped').length} card(s) in To Be Pre-Snipped`}
                      onClick={() => handleVolumeRun('pre_snip')}
                    />
                  </ActionGutter>
                )}
                {key === 'to_be_snipped' && (
                  <ActionGutter>
                    <GutterButton
                      label="Auto-Snip" sub="Script" color="#8b5cf6"
                      disabled
                      count={byStage('to_be_snipped').length}
                      title="Auto-snip is disabled for now — the auto_snip_script.py isn't reliable yet. Manually snip in CloudCompare and drag the card to the next stage."
                      onClick={() => handleVolumeRun('auto_snip')}
                    />
                  </ActionGutter>
                )}
                {key === 'to_be_post_snipped' && (
                  <ActionGutter>
                    <GutterButton
                      label="Post-Snip" sub="Script" color="#ec4899"
                      disabled={runActive}
                      count={byStage('to_be_post_snipped').length}
                      title={`Run post_snip_script.py on ${byStage('to_be_post_snipped').length} card(s) in To Be Post-Snipped — requires manually-snipped bins (open pre-snip pair in CC, crop, Save As with _snipped suffix)`}
                      onClick={() => handleVolumeRun('post_snip')}
                    />
                  </ActionGutter>
                )}
                {key === 'volumetrics_created' && (
                  <ActionGutter>
                    <GutterButton label="Create" sub="SU Sheet" color="#22c55e"
                      disabled={runActive}
                      count={byStage('volumetrics_created').length}
                      title={`Run create_su_sheet_script.py on ${byStage('volumetrics_created').length} Volume Created card(s) then move to SU Sheet Created`}
                      onClick={() => handleVolumeRun('create_su_sheet')}
                    />
                  </ActionGutter>
                )}
              </Fragment>
            ))}
          </div>

          <DragOverlay>
            {draggingEntry && (
              <div style={{
                background: T.surface, borderRadius: 8, padding: '12px 14px',
                boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
                border: `1px solid ${T.border}`, width: 240,
              }}>
                <div style={{ fontWeight: 700, fontSize: 14, color: T.text }}>{draggingEntry.su_id}</div>
                {(draggingEntry.top_pgram || draggingEntry.bot_pgram) && (
                  <div style={{ fontSize: 12, color: T.textSub }}>
                    {[draggingEntry.top_pgram, draggingEntry.bot_pgram].filter(Boolean).join(' / ')}
                  </div>
                )}
              </div>
            )}
          </DragOverlay>
        </DndContext>
      )}

      {detailEntry && (
        <SUDetailModal
          entry={detailEntry}
          onClose={() => setDetailEntry(null)}
          onUpdated={(updated) => {
            setEntries((prev) => prev.map((e) => e.su_id === updated.su_id ? updated : e))
            setDetailEntry(updated)
          }}
        />
      )}

      {showCreate && (
        <CreateSUModal
          onClose={() => setShowCreate(false)}
          onCreated={(entry) => setEntries((prev) => [entry, ...prev])}
        />
      )}

      {confirmState && (
        <ConfirmationModal
          message={confirmState.message}
          onConfirm={handleConfirm}
          onCancel={() => setConfirmState(null)}
        />
      )}
    </div>
  )
}

function ActionGutter({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 8,
      flexShrink: 0, padding: '0 2px',
    }}>
      {children}
    </div>
  )
}

function GutterButton({ label, sub, color, onClick, disabled, title, count, icon = '▶', loading = false, loadingLabel }: {
  label: string; sub: string; color: string; onClick: () => void
  disabled?: boolean; title?: string; count?: number; icon?: string
  loading?: boolean; loadingLabel?: string
}) {
  const isDisabled = disabled || loading
  return (
    <button
      onClick={onClick}
      disabled={isDisabled}
      title={title}
      style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
        padding: '8px 10px', borderRadius: 6,
        cursor: isDisabled ? (loading ? 'progress' : 'not-allowed') : 'pointer',
        border: `1px dashed ${color}88`,
        background: isDisabled ? `${color}0a` : `${color}12`,
        color, fontWeight: 600, fontSize: 11, lineHeight: 1.3,
        opacity: isDisabled ? (loading ? 0.8 : 0.45) : 1, whiteSpace: 'nowrap',
        transition: 'background 0.15s',
      }}
    >
      <span style={{ fontSize: 14, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {loading ? <span style={gutterSpinnerStyle} /> : icon}
      </span>
      <span>{loading ? (loadingLabel ?? label) : label}</span>
      <span style={{ fontSize: 10, fontWeight: 600, opacity: 0.9 }}>{sub}</span>
      {loading ? (
        <span style={{ width: '100%', height: 4, borderRadius: 2, background: `${color}22`, overflow: 'hidden', position: 'relative', marginTop: 2 }}>
          <span style={{ ...indeterminateBarStyle, background: color, width: '40%' }} />
        </span>
      ) : count !== undefined && count > 0 && (
        <span style={{ fontSize: 10, fontWeight: 400, color: `${color}bb` }}>({count})</span>
      )}
      <style>{`
        @keyframes suSpin { to { transform: rotate(360deg); } }
        @keyframes suSlide { 0% { left: -40%; } 100% { left: 100%; } }
      `}</style>
    </button>
  )
}

function VolumeRunBanner({ run, onDismiss }: { run: VolumeRunStatus; onDismiss: () => void }) {
  const kindLabels: Record<string, string> = {
    chain: 'Full pipeline chain',
    create_su_sheet: 'Create SU Sheet',
    pre_snip: 'Pre-Snip',
    auto_snip: 'Auto-Snip',
    post_snip: 'Post-Snip',
  }
  const kindLabel = run.kind ? (kindLabels[run.kind] ?? run.kind) : ''
  const isActive = run.active
  // The script reports per-SU counts via progress.json; until the first report
  // total is 0 and we fall back to the indeterminate bar.
  const hasCounts = isActive && run.total > 0
  const remaining = Math.max(0, run.total - run.processed)
  const pct = hasCounts ? Math.min(100, Math.round((run.processed / run.total) * 100)) : 0

  return (
    <div style={runBannerStyle}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: T.text, marginBottom: 6, display: 'flex', alignItems: 'center', gap: 8 }}>
          {isActive && <span style={spinnerStyle} />}
          {isActive
            ? `Running ${run.step_label ?? kindLabel}…`
            : run.status === 'done'
              ? `${kindLabel} finished — ${run.cards_advanced} card${run.cards_advanced !== 1 ? 's' : ''} advanced`
              : `${kindLabel} failed`}
        </div>
        {hasCounts && (
          <div style={{ fontSize: 12, color: T.textSub, marginBottom: 4 }}>
            {run.processed} / {run.total} SU{run.total !== 1 ? 's' : ''} processed · {remaining} left
          </div>
        )}
        {run.status === 'failed' && run.error && (
          <div style={{ fontSize: 12, color: '#f87171', fontFamily: 'monospace', whiteSpace: 'pre-wrap', maxHeight: 100, overflowY: 'auto' }}>
            {run.error}
          </div>
        )}
        {isActive && (
          <div style={{ height: 6, borderRadius: 3, background: T.badgeBg, overflow: 'hidden', position: 'relative', marginTop: 4 }}>
            {hasCounts
              ? <div style={{ height: '100%', width: `${pct}%`, background: '#8b5cf6', borderRadius: 3, transition: 'width 0.3s ease' }} />
              : <div style={indeterminateBarStyle} />}
          </div>
        )}
      </div>
      {!isActive && (
        <button onClick={onDismiss} style={runBannerBtn} title="Dismiss">✕</button>
      )}
      <style>{`
        @keyframes suSpin { to { transform: rotate(360deg); } }
        @keyframes suSlide { 0% { left: -40%; } 100% { left: 100%; } }
      `}</style>
    </div>
  )
}

const selectStyle: React.CSSProperties = {
  padding: '7px 12px', borderRadius: 6, border: `1px solid ${T.inputBorder}`,
  fontSize: 14, background: T.inputBg, color: T.text, cursor: 'pointer', outline: 'none',
}
const filterChip: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 6,
  background: T.chipBg, color: T.chipText, borderRadius: 20,
  padding: '3px 10px 3px 12px', fontSize: 13, fontWeight: 600,
}
const chipClear: React.CSSProperties = {
  background: 'none', border: 'none', cursor: 'pointer',
  color: T.chipText, padding: 0, fontSize: 12, lineHeight: 1,
  display: 'flex', alignItems: 'center',
}
const refreshBtn: React.CSSProperties = {
  padding: '7px 14px', borderRadius: 6, border: `1px solid ${T.border}`,
  background: T.surface, cursor: 'pointer', fontSize: 14, color: T.textSub,
}
const scanBtn: React.CSSProperties = {
  padding: '7px 14px', borderRadius: 6, border: `1px solid ${T.border}`,
  background: T.surface, cursor: 'pointer', fontSize: 14, color: T.textSub,
}
const addBtn: React.CSSProperties = {
  padding: '7px 14px', borderRadius: 6, border: 'none',
  background: T.accent, color: '#fff', fontWeight: 600, cursor: 'pointer', fontSize: 14,
}
const runBannerStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'flex-start', gap: 16,
  marginBottom: 16, padding: '12px 16px',
  background: T.surface, border: `1px solid ${T.border}`, borderRadius: 8,
}
const gutterSpinnerStyle: React.CSSProperties = {
  width: 14, height: 14, borderRadius: '50%', flexShrink: 0,
  border: '2px solid currentColor', borderTopColor: 'transparent',
  display: 'inline-block', animation: 'suSpin 0.7s linear infinite', opacity: 0.9,
}
const spinnerStyle: React.CSSProperties = {
  width: 14, height: 14, borderRadius: '50%', flexShrink: 0,
  border: `2px solid ${T.border}`, borderTopColor: '#8b5cf6',
  display: 'inline-block', animation: 'suSpin 0.7s linear infinite',
}
const indeterminateBarStyle: React.CSSProperties = {
  position: 'absolute', top: 0, bottom: 0, width: '40%',
  background: '#8b5cf6', borderRadius: 3,
  animation: 'suSlide 1.1s ease-in-out infinite',
}
const runBannerBtn: React.CSSProperties = {
  padding: '7px 14px', borderRadius: 6, border: `1px solid ${T.border}`,
  background: T.surface, cursor: 'pointer', fontSize: 13, color: T.textSub,
  fontWeight: 600, flexShrink: 0,
}
