import { useCallback, useEffect, useState } from 'react'
import {
  DndContext, DragEndEvent, DragOverEvent, DragOverlay, DragStartEvent,
  PointerSensor, useSensor, useSensors,
} from '@dnd-kit/core'
import { fetchJobs, fetchIgnoredFolders, updateStage } from '../api/pgram'
import type { IgnoredFolder } from '../api/pgram'
import type { PgramJob } from '../types'
import { PGRAM_STAGES } from '../types'
import { KanbanColumn } from './KanbanColumn'
import { JobCard } from './JobCard'
import { JobDetailModal } from './JobDetailModal'
import { ConfirmationModal } from './ConfirmationModal'
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
  const [detailJob, setDetailJob] = useState<PgramJob | null>(null)
  const [draggingJob, setDraggingJob] = useState<PgramJob | null>(null)
  const [confirmState, setConfirmState] = useState<{
    message: string; jobId: string; targetStage: string
  } | null>(null)
  const [ignoredFolders, setIgnoredFolders] = useState<IgnoredFolder[]>([])
  const [ignoredDismissed, setIgnoredDismissed] = useState(false)

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

  const trenches = [...new Set(jobs.map(j => j.trench).filter(Boolean))].sort()

  const filtered = trenchFilter === 'All Trenches'
    ? jobs
    : jobs.filter((j) => j.trench === trenchFilter)

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

  async function handleDragEnd(event: DragEndEvent) {
    setDraggingJob(null)
    const { active, over } = event
    if (!over) return

    const jobId = String(active.id)
    const targetStage = resolveStage(String(over.id))

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
        <span style={{ fontSize: 13, color: T.textMuted }}>
          {filtered.length} job{filtered.length !== 1 ? 's' : ''}
          {trenchFilter !== 'All Trenches' && ` of ${jobs.length}`}
        </span>
        <button onClick={load} style={refreshBtn} title="Refresh">↻ Refresh</button>
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

      {loading ? (
        <div style={{ textAlign: 'center', padding: 48, color: T.textSub }}>Loading jobs…</div>
      ) : (
        <DndContext sensors={sensors} onDragStart={handleDragStart} onDragOver={handleDragOver} onDragEnd={handleDragEnd}>
          <div style={{ display: 'flex', gap: 12, overflowX: 'auto', paddingBottom: 12 }}>
            {PGRAM_STAGES.map(({ key, label }) => (
              <KanbanColumn
                key={key}
                id={key}
                title={label}
                items={byStage(key)}
                count={byStage(key).length}
                color={STAGE_COLORS[key]}
                isValidTarget={draggingJob ? (draggingJob.stage === key ? 'source' : isValidPgramMove(draggingJob.stage, key)) : true}
                renderCard={(job) => (
                  <JobCard
                    key={job.job_id}
                    job={job}
                    onClick={() => setDetailJob(job)}
                  />
                )}
              />
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
