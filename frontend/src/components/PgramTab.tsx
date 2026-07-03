import { Fragment, useCallback, useEffect, useRef, useState } from 'react'
import {
  DndContext, DragEndEvent, DragOverEvent, DragOverlay, DragStartEvent,
  PointerSensor, useSensor, useSensors,
} from '@dnd-kit/core'
import {
  fetchJobs, fetchIgnoredFolders, updateStage,
  startRun, getRunStatus, cancelRun, batchMove, fixSuNames,
} from '../api/pgram'
import type { IgnoredFolder, RunKind, RunStatus, RunJob } from '../api/pgram'
import type { PgramJob } from '../types'
import { PGRAM_STAGES } from '../types'
import { KanbanColumn } from './KanbanColumn'
import { JobCard } from './JobCard'
import { JobDetailModal } from './JobDetailModal'
import { ConfirmationModal } from './ConfirmationModal'
import { ScriptErrorList } from './ScriptErrorList'
import type { ScriptError } from './ScriptErrorList'
import { toast } from './Toast'
import { T } from '../tokens'

const PGRAM_ORDER = ['to_be_processed', 'to_be_aligned', 'to_overnight', 'processed', 'uploaded_air']

function stageLabel(key: string): string {
  return PGRAM_STAGES.find((s) => s.key === key)?.label ?? key
}

const toKey = (f: IgnoredFolder) => `${f.stage}|${f.parent}|${f.name}`

function isValidPgramMove(from: string, to: string): boolean {
  if (from === to) return false
  const fi = PGRAM_ORDER.indexOf(from)
  const ti = PGRAM_ORDER.indexOf(to)
  // backward moves always allowed; forward: exactly one step
  return ti < fi || ti === fi + 1
}

function nextStage(stage: string): string | null {
  const i = PGRAM_ORDER.indexOf(stage)
  return i >= 0 && i < PGRAM_ORDER.length - 1 ? PGRAM_ORDER[i + 1] : null
}

const STAGE_COLORS: Record<string, string> = {
  to_be_processed: '#94a3b8',
  to_be_aligned: '#f59e0b',
  to_overnight: '#8b5cf6',
  processed: '#22c55e',
  uploaded_air: '#0ea5e9',
}

interface Props {
  refreshKey?: number
}

export function PgramTab({ refreshKey }: Props) {
  const [jobs, setJobs] = useState<PgramJob[]>([])
  const [loading, setLoading] = useState(true)
  const [trenchFilter, setTrenchFilter] = useState('All Trenches')
  const [flagFilter, setFlagFilter] = useState<'all' | 'flagged' | 'not_flagged'>('all')
  const [detailJob, setDetailJob] = useState<PgramJob | null>(null)
  const [draggingJob, setDraggingJob] = useState<PgramJob | null>(null)
  const [confirmState, setConfirmState] = useState<{
    message: string; jobId: string; targetStage: string
  } | null>(null)
  const [ignoredFolders, setIgnoredFolders] = useState<IgnoredFolder[]>([])
  const [ignoredDismissed, setIgnoredDismissed] = useState(false)
  const [run, setRun] = useState<RunStatus | null>(null)
  const [batchConfirm, setBatchConfirm] = useState<{ from: string; to: string; count: number } | null>(null)
  const [moving, setMoving] = useState<{ to: string; count: number } | null>(null)
  const [fixingNames, setFixingNames] = useState(false)
  const pollingRef = useRef(false)
  // Track jobs already toasted as failed, scoped to one run (keyed by started_at),
  // so a failure toasts exactly once even though we poll every 2.5s.
  const failedToastedRef = useRef<{ key: string | null; ids: Set<string> }>({ key: null, ids: new Set() })

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } })
  )

  const load = useCallback(async () => {
    try {
      const data = await fetchJobs()
      setJobs(data)
    } catch {
      toast('Failed to load jobs', 'error')
    } finally {
      setLoading(false)
    }
    try {
      const ignored = await fetchIgnoredFolders()
      setIgnoredFolders(prev => {
        const prevKey = prev.map(toKey).sort().join(',')
        const nextKey = ignored.map(toKey).sort().join(',')
        if (prevKey !== nextKey) setIgnoredDismissed(false)
        return ignored
      })
    } catch (e) {
      console.error('Failed to load ignored folders', e)
    }
  }, [])

  useEffect(() => { load() }, [load, refreshKey])

  // --- Batched run polling: follow an active run, refreshing cards as jobs advance live ---
  const pollOnce = useCallback(async () => {
    let status: RunStatus
    try {
      status = await getRunStatus()
    } catch {
      pollingRef.current = false
      return
    }
    setRun(status.jobs.length ? status : null)

    // Toast each newly-failed job once (immediate notice even on another tab/column).
    if (failedToastedRef.current.key !== status.started_at) {
      failedToastedRef.current = { key: status.started_at, ids: new Set() }
    }
    for (const j of status.jobs) {
      if (j.status === 'failed' && !failedToastedRef.current.ids.has(j.job_id)) {
        failedToastedRef.current.ids.add(j.job_id)
        toast(`✗ ${j.job_id}${j.step ? ` — ${j.step}` : ''} failed`, 'error')
      }
    }

    await load()  // reflect folders the backend just moved
    if (status.active) {
      window.setTimeout(() => { pollOnce() }, 2500)
    } else {
      pollingRef.current = false
      const done = status.jobs.filter((j) => j.status === 'done').length
      const failed = status.jobs.filter((j) => j.status === 'failed').length
      if (status.jobs.length) {
        toast(`Run finished — ${done} done${failed ? `, ${failed} failed` : ''}`, failed ? 'error' : 'success')
      }
    }
  }, [load])

  const startPolling = useCallback(() => {
    if (pollingRef.current) return
    pollingRef.current = true
    pollOnce()
  }, [pollOnce])

  // Resume polling if a run is already in flight (e.g. after a page refresh)
  useEffect(() => {
    getRunStatus().then((s) => { if (s.active) startPolling() }).catch(() => {})
  }, [startPolling])

  async function handleRun(kind: RunKind) {
    try {
      const r = await startRun(kind)
      toast(`Started ${kind} on ${r.count ?? 0} job${r.count === 1 ? '' : 's'}…`, 'info')
      startPolling()
    } catch (e: unknown) {
      toast((e as Error).message, 'error')
    }
  }

  async function handleCancelRun() {
    try {
      await cancelRun()
      toast('Stopping after the current job…', 'info')
    } catch (e: unknown) {
      toast((e as Error).message, 'error')
    }
  }

  async function handleFixNames() {
    setFixingNames(true)
    try {
      const r = await fixSuNames()
      const changed = r.renamed.length + r.organized.length
      if (changed === 0 && r.skipped.length === 0) {
        toast('Folders already tagged and organized — nothing to fix', 'info')
      } else {
        const parts: string[] = []
        if (r.renamed.length) parts.push(`Renamed ${r.renamed.length} folder${r.renamed.length === 1 ? '' : 's'}`)
        if (r.organized.length) parts.push(`organized ${r.organized.length} into trench${r.organized.length === 1 ? '' : 'es'}`)
        if (r.skipped.length) parts.push(`${r.skipped.length} need attention`)
        const msg = parts.join(', ').replace(/^./, (c) => c.toUpperCase())
        toast(msg, changed ? 'success' : 'info')
      }
      if (r.skipped.length) {
        console.warn('Fix SU names — skipped:', r.skipped)
      }
      await load()
    } catch (e: unknown) {
      toast((e as Error).message, 'error')
    } finally {
      setFixingNames(false)
    }
  }

  function requestBatchMove(from: string, to: string) {
    const count = jobs.filter((j) => j.stage === from).length
    if (count === 0) { toast('No jobs to move in that column', 'info'); return }
    setBatchConfirm({ from, to, count })
  }

  async function confirmBatchMove() {
    if (!batchConfirm) return
    const { from, to, count } = batchConfirm
    setBatchConfirm(null)
    setMoving({ to, count })
    try {
      const r = await batchMove(from, to)
      toast(
        `Moved ${r.moved.length} job${r.moved.length === 1 ? '' : 's'}${r.failed.length ? `, ${r.failed.length} failed` : ''}`,
        r.failed.length ? 'error' : 'success',
      )
      await load()
    } catch (e: unknown) {
      toast((e as Error).message, 'error')
    } finally {
      setMoving(null)
    }
  }

  const runByJob = new Map<string, RunJob>()
  if (run) for (const j of run.jobs) runByJob.set(j.job_id, j)
  const runActive = run?.active ?? false

  const trenches = [...new Set(jobs.map(j => j.trench).filter(Boolean))].sort()

  const filtered = jobs.filter((j) => {
    if (trenchFilter !== 'All Trenches' && j.trench !== trenchFilter) return false
    if (flagFilter === 'flagged' && !j.flagged) return false
    if (flagFilter === 'not_flagged' && j.flagged) return false
    return true
  })

  const byStage = (stageKey: string) =>
    filtered.filter((j) => j.stage === stageKey)

  function resolveStage(overId: string): string {
    const stageKeys = new Set(PGRAM_STAGES.map((s) => s.key))
    return stageKeys.has(overId) ? overId : (jobs.find((j) => j.job_id === overId)?.stage ?? overId)
  }

  function handleDragStart(event: DragStartEvent) {
    const job = jobs.find((j) => j.job_id === event.active.id)
    if (job) setDraggingJob(job)
  }

  function handleDragOver(event: DragOverEvent) {
    // kept for KanbanColumn isValidTarget computation only; no state needed
    void event
  }

  // Shared by drag-and-drop and the per-card → arrow.
  async function requestMove(jobId: string, targetStage: string) {
    const job = jobs.find((j) => j.job_id === jobId)
    if (!job || job.stage === targetStage) return

    if (!isValidPgramMove(job.stage, targetStage)) {
      toast('Move one step at a time — stage skipping is not allowed', 'error')
      return
    }

    const result = await updateStage(jobId, targetStage, false)

    if (result.requires_confirmation && result.message) {
      setConfirmState({ message: result.message, jobId, targetStage })
      return
    }
    if (result.error) {
      toast(result.error, 'error')
      return
    }
    if (result.job) {
      setJobs((prev) => prev.map((j) => j.job_id === jobId ? result.job! : j))
    }
  }

  async function handleDragEnd(event: DragEndEvent) {
    setDraggingJob(null)
    const { active, over } = event
    if (!over) return
    await requestMove(String(active.id), resolveStage(String(over.id)))
  }

  function renderGutter(afterKey: string) {
    if (afterKey === 'to_be_processed') {
      return (
        <ActionGutter>
          <GutterButton label="Move all" sub="→ To Be Aligned" color="#f59e0b" disabled={runActive || moving !== null}
            title="Move every job in To Be Processed to To Be Aligned (folders only)"
            onClick={() => requestBatchMove('to_be_processed', 'to_be_aligned')} />
        </ActionGutter>
      )
    }
    if (afterKey === 'to_be_aligned') {
      return (
        <ActionGutter>
          <GutterButton label="Run" sub="Alignment" color="#8b5cf6" disabled={runActive}
            title="Align every job in To Be Aligned, advancing each to To Overnight as it succeeds"
            onClick={() => handleRun('alignment')} />
          <GutterButton label="Align +" sub="Overnight" color="#6366f1" disabled={runActive}
            title="Align then overnight each job, advancing it all the way to Processed"
            icon="▶▶"
            onClick={() => handleRun('both')} />
        </ActionGutter>
      )
    }
    if (afterKey === 'to_overnight') {
      return (
        <ActionGutter>
          <GutterButton label="Run" sub="Overnight" color="#22c55e" disabled={runActive}
            title="Run the overnight pipeline on every job in To Overnight, advancing each to Processed"
            onClick={() => handleRun('overnight')} />
        </ActionGutter>
      )
    }
    return null
  }

  async function handleConfirm() {
    if (!confirmState) return
    const { jobId, targetStage } = confirmState
    setConfirmState(null)
    const result = await updateStage(jobId, targetStage, true)
    if (result.error) {
      toast(result.error, 'error')
      return
    }
    if (result.job) {
      setJobs((prev) => prev.map((j) => j.job_id === jobId ? result.job! : j))
      toast('Stage updated', 'success')
    }
  }

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
          value={flagFilter}
          onChange={(e) => setFlagFilter(e.target.value as typeof flagFilter)}
          style={selectStyle}
          title="Filter by flag status"
        >
          <option value="all">All flags</option>
          <option value="flagged">🚩 Flagged</option>
          <option value="not_flagged">Not flagged</option>
        </select>
        {flagFilter !== 'all' && (
          <span style={filterChip}>
            {flagFilter === 'flagged' ? '🚩 Flagged' : 'Not flagged'}
            <button onClick={() => setFlagFilter('all')} style={chipClear} title="Clear filter">✕</button>
          </span>
        )}
        <span style={{ fontSize: 13, color: T.textMuted }}>
          {filtered.length} job{filtered.length !== 1 ? 's' : ''}
          {(trenchFilter !== 'All Trenches' || flagFilter !== 'all') && ` of ${jobs.length}`}
        </span>
        <button onClick={load} style={refreshBtn} title="Refresh">↻ Refresh</button>
        <button
          onClick={handleFixNames}
          disabled={fixingNames}
          style={{ ...refreshBtn, opacity: fixingNames ? 0.5 : 1, cursor: fixingNames ? 'default' : 'pointer' }}
          title="Across all stages: tag job folders with their SU number (SU####), looking up missing SUs in TARP Field Pgram Tracking, then sort each loose folder into its Trench subfolder."
        >
          {fixingNames ? '⚙ Working…' : '⚙ Fix SU names & sort into trenches'}
        </button>
      </div>

      {ignoredFolders.length > 0 && !ignoredDismissed && (
        <div style={ignoredBannerStyle}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#92400e', marginBottom: 4 }}>
              ⚠ {ignoredFolders.length} folder{ignoredFolders.length !== 1 ? 's' : ''} not shown — name does not match <code style={{ background: '#fde68a', padding: '0 4px', borderRadius: 3 }}>Pgram_Job_###</code>
            </div>
            <div style={{ fontSize: 12, color: '#78350f', lineHeight: 1.5 }}>
              {ignoredFolders.slice(0, 8).map((f, i) => (
                <span key={toKey(f)}>
                  <code style={{ background: '#fef3c7', padding: '0 4px', borderRadius: 3 }}>{f.name}</code>
                  <span style={{ opacity: 0.7 }}> in {stageLabel(f.stage)}{f.parent && ` › ${f.parent}`}</span>
                  {i < Math.min(ignoredFolders.length, 8) - 1 ? ', ' : ''}
                </span>
              ))}
              {ignoredFolders.length > 8 && <span> … and {ignoredFolders.length - 8} more</span>}
              <div style={{ marginTop: 4, opacity: 0.85 }}>
                Rename to start with <code style={{ background: '#fef3c7', padding: '0 4px', borderRadius: 3 }}>Pgram_Job_</code> followed by digits (e.g. <code style={{ background: '#fef3c7', padding: '0 4px', borderRadius: 3 }}>Pgram_Job_123_SU17001</code>) and click ↻ Refresh.
              </div>
            </div>
          </div>
          <button onClick={() => setIgnoredDismissed(true)} style={ignoredDismissBtn} title="Hide this warning">✕</button>
        </div>
      )}

      {moving && (
        <MovingBanner count={moving.count} toLabel={stageLabel(moving.to)} />
      )}

      {run && run.jobs.length > 0 && (
        <RunBanner run={run} onCancel={handleCancelRun} onDismiss={() => setRun(null)} />
      )}

      {loading ? (
        <div style={{ textAlign: 'center', padding: 48, color: T.textSub }}>Loading jobs…</div>
      ) : (
        <DndContext sensors={sensors} onDragStart={handleDragStart} onDragOver={handleDragOver} onDragEnd={handleDragEnd}>
          <div style={{ display: 'flex', gap: 8, overflowX: 'auto', paddingBottom: 12, alignItems: 'flex-start' }}>
            {PGRAM_STAGES.map(({ key, label }) => (
              <Fragment key={key}>
                <KanbanColumn
                  id={key}
                  title={label}
                  items={byStage(key)}
                  count={byStage(key).length}
                  color={STAGE_COLORS[key]}
                  isValidTarget={draggingJob ? (draggingJob.stage === key ? 'source' : isValidPgramMove(draggingJob.stage, key)) : true}
                  renderCard={(job) => {
                    const rj = runByJob.get(job.job_id)
                    const next = nextStage(job.stage)
                    return (
                      <JobCard
                        key={job.job_id}
                        job={job}
                        onClick={() => setDetailJob(job)}
                        onUpdated={(updated) =>
                          setJobs((prev) => prev.map((j) => j.job_id === updated.job_id ? updated : j))
                        }
                        onAdvance={next ? () => requestMove(job.job_id, next) : undefined}
                        nextStageLabel={next ? `Move to ${stageLabel(next)}` : undefined}
                        runStatus={rj?.status}
                        runStep={rj?.step}
                        runError={rj?.error}
                      />
                    )
                  }}
                />
                {renderGutter(key)}
              </Fragment>
            ))}
          </div>

          <DragOverlay>
            {draggingJob && (
              <div style={{
                background: T.surface, borderRadius: 8, padding: '12px 14px',
                boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
                border: `1px solid ${T.border}`, width: 240,
              }}>
                <div style={{ fontWeight: 700, fontSize: 14, color: T.text }}>{draggingJob.job_id}</div>
                {draggingJob.su_string && <div style={{ fontSize: 12, color: T.textSub }}>{draggingJob.su_string}</div>}
              </div>
            )}
          </DragOverlay>
        </DndContext>
      )}

      {detailJob && (
        <JobDetailModal
          job={detailJob}
          onClose={() => setDetailJob(null)}
          onUpdated={(updated) => {
            setJobs((prev) => prev.map((j) => j.job_id === updated.job_id ? updated : j))
            setDetailJob(updated)
          }}
        />
      )}

      {confirmState && (
        <ConfirmationModal
          message={confirmState.message}
          onConfirm={handleConfirm}
          onCancel={() => setConfirmState(null)}
        />
      )}

      {batchConfirm && (
        <ConfirmationModal
          message={`Move all ${batchConfirm.count} job${batchConfirm.count === 1 ? '' : 's'} from ${stageLabel(batchConfirm.from)} to ${stageLabel(batchConfirm.to)}? This only moves the folders — it does not run any script.`}
          onConfirm={confirmBatchMove}
          onCancel={() => setBatchConfirm(null)}
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

function GutterButton({ label, sub, color, onClick, disabled, title, icon }: {
  label: string; sub: string; color: string; onClick: () => void; disabled?: boolean; title?: string; icon?: string
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={title}
      style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
        padding: '8px 10px', borderRadius: 6, cursor: disabled ? 'not-allowed' : 'pointer',
        border: `1px dashed ${color}88`, background: disabled ? `${color}0a` : `${color}12`,
        color, fontWeight: 600, fontSize: 11, lineHeight: 1.3,
        opacity: disabled ? 0.45 : 1, whiteSpace: 'nowrap',
        transition: 'background 0.15s',
      }}
    >
      <span style={{ fontSize: 14 }}>{icon ?? '▶'}</span>
      <span>{label}</span>
      <span style={{ fontSize: 10, fontWeight: 600, opacity: 0.9 }}>{sub}</span>
    </button>
  )
}

function MovingBanner({ count, toLabel }: { count: number; toLabel: string }) {
  return (
    <div style={runBannerStyle}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: T.text, marginBottom: 6, display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={spinnerStyle} />
          Moving {count} job{count === 1 ? '' : 's'} to {toLabel}…
          <span style={{ color: T.textSub, fontWeight: 500 }}>this may take a moment for large batches</span>
        </div>
        <div style={{ height: 6, borderRadius: 3, background: T.badgeBg, overflow: 'hidden', position: 'relative' }}>
          <div style={indeterminateBarStyle} />
        </div>
      </div>
      <style>{`
        @keyframes pgramSpin { to { transform: rotate(360deg); } }
        @keyframes pgramSlide { 0% { left: -40%; } 100% { left: 100%; } }
      `}</style>
    </div>
  )
}

function RunBanner({ run, onCancel, onDismiss }: {
  run: RunStatus; onCancel: () => void; onDismiss: () => void
}) {
  const total = run.jobs.length
  const done = run.jobs.filter((j) => j.status === 'done').length
  const failedJobs = run.jobs.filter((j) => j.status === 'failed')
  const failed = failedJobs.length
  const running = run.jobs.find((j) => j.status === 'running')
  const pct = total ? Math.round(((done + failed) / total) * 100) : 0
  const errors: ScriptError[] = failedJobs.map((j) => ({
    label: j.job_id,
    step: j.step,
    error: j.error || 'Failed (no error detail captured — see tarp-dashboard.log).',
  }))

  return (
    <div style={{ ...runBannerStyle, flexDirection: 'column', alignItems: 'stretch' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: T.text, marginBottom: 6 }}>
            {run.active
              ? `Running ${run.kind}${run.cancel ? ' (stopping…)' : ''}`
              : `Finished ${run.kind}`}
            {' · '}{done}/{total} done{failed ? ` · ${failed} failed` : ''}
            {running && <span style={{ color: T.textSub, fontWeight: 500 }}>{`  ·  now: ${running.job_id}${running.step ? ` (${running.step})` : ''}`}</span>}
          </div>
          <div style={{ height: 6, borderRadius: 3, background: T.badgeBg, overflow: 'hidden' }}>
            <div style={{
              width: `${pct}%`, height: '100%',
              background: failed ? '#ef4444' : '#22c55e', transition: 'width 0.4s',
            }} />
          </div>
        </div>
        {run.active ? (
          <button onClick={onCancel} disabled={run.cancel} style={runBannerBtn} title="Stop after the current job">
            ⏹ Stop
          </button>
        ) : (
          <button onClick={onDismiss} style={runBannerBtn} title="Dismiss">✕</button>
        )}
      </div>
      <ScriptErrorList errors={errors} />
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
const ignoredBannerStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'flex-start',
  justifyContent: 'space-between',
  gap: 12,
  marginBottom: 16,
  padding: '12px 16px',
  background: '#fffbeb',
  border: '1px solid #fcd34d',
  borderRadius: 8,
}

const ignoredDismissBtn: React.CSSProperties = {
  background: 'transparent',
  border: 'none',
  color: '#92400e',
  fontSize: 16,
  fontWeight: 700,
  cursor: 'pointer',
  padding: 4,
  lineHeight: 1,
  flexShrink: 0,
}

const refreshBtn: React.CSSProperties = {
  padding: '7px 14px', borderRadius: 6, border: `1px solid ${T.border}`,
  background: T.surface, cursor: 'pointer', fontSize: 14, color: T.textSub,
}

const runBannerStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 16,
  marginBottom: 16, padding: '12px 16px',
  background: T.surface, border: `1px solid ${T.border}`, borderRadius: 8,
}

const spinnerStyle: React.CSSProperties = {
  width: 14, height: 14, borderRadius: '50%', flexShrink: 0,
  border: `2px solid ${T.border}`, borderTopColor: '#f59e0b',
  display: 'inline-block', animation: 'pgramSpin 0.7s linear infinite',
}

const indeterminateBarStyle: React.CSSProperties = {
  position: 'absolute', top: 0, bottom: 0, width: '40%',
  background: '#f59e0b', borderRadius: 3,
  animation: 'pgramSlide 1.1s ease-in-out infinite',
}

const runBannerBtn: React.CSSProperties = {
  padding: '7px 14px', borderRadius: 6, border: `1px solid ${T.border}`,
  background: T.surface, cursor: 'pointer', fontSize: 13, color: T.textSub,
  fontWeight: 600, flexShrink: 0,
}
