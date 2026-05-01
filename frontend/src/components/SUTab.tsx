import { useCallback, useEffect, useState } from 'react'
import {
  DndContext, DragEndEvent, DragOverlay, DragStartEvent,
  PointerSensor, useSensor, useSensors,
} from '@dnd-kit/core'
import { fetchEntries, updateStage } from '../api/su'
import type { SUEntry } from '../types'
import { SU_STAGES, TRENCHES } from '../types'
import { KanbanColumn } from './KanbanColumn'
import { SUCard } from './SUCard'
import { SUDetailModal } from './SUDetailModal'
import { CreateSUModal } from './CreateSUModal'
import { toast } from './Toast'

const STAGE_COLORS: Record<string, string> = {
  not_started: '#94a3b8',
  volumetrics_created: '#f59e0b',
  su_sheet_created: '#22c55e',
  uploaded_air: '#0ea5e9',
}

export function SUTab() {
  const [entries, setEntries] = useState<SUEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [trenchFilter, setTrenchFilter] = useState('All Trenches')
  const [detailEntry, setDetailEntry] = useState<SUEntry | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [draggingEntry, setDraggingEntry] = useState<SUEntry | null>(null)

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

  const filtered = trenchFilter === 'All Trenches'
    ? entries
    : entries.filter((e) => e.trench === trenchFilter)

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

    setEntries((prev) =>
      prev.map((e) => e.su_id === suId ? { ...e, stage: targetStage } : e)
    )

    try {
      await updateStage(suId, targetStage)
      toast('Stage updated', 'success')
    } catch (err: unknown) {
      setEntries((prev) =>
        prev.map((e) => e.su_id === suId ? { ...e, stage: entry.stage } : e)
      )
      toast((err as Error).message || 'Failed to update stage', 'error')
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
          {TRENCHES.map((t) => <option key={t}>{t}</option>)}
        </select>
        {trenchFilter !== 'All Trenches' && (
          <span style={filterChip}>
            {trenchFilter}
            <button onClick={() => setTrenchFilter('All Trenches')} style={chipClear} title="Clear filter">✕</button>
          </span>
        )}
        <span style={{ fontSize: 13, color: '#6b7280' }}>
          {filtered.length} entr{filtered.length !== 1 ? 'ies' : 'y'}
          {trenchFilter !== 'All Trenches' && ` of ${entries.length}`}
        </span>
        <button onClick={load} style={refreshBtn} title="Refresh">↻ Refresh</button>
        <button onClick={() => setShowCreate(true)} style={addBtn}>+ New SU</button>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: 48, color: '#94a3b8' }}>Loading SU entries…</div>
      ) : (
        <DndContext sensors={sensors} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
          <div style={{ display: 'flex', gap: 12, overflowX: 'auto', paddingBottom: 12 }}>
            {SU_STAGES.map(({ key, label }) => (
              <KanbanColumn
                key={key}
                id={key}
                title={label}
                items={byStage(key)}
                getId={(e) => e.su_id}
                count={byStage(key).length}
                color={STAGE_COLORS[key]}
                renderCard={(entry) => (
                  <SUCard
                    key={entry.su_id}
                    entry={entry}
                    onClick={() => setDetailEntry(entry)}
                  />
                )}
              />
            ))}
          </div>

          <DragOverlay>
            {draggingEntry && (
              <div style={{
                background: '#fff', borderRadius: 8, padding: '12px 14px',
                boxShadow: '0 8px 24px rgba(0,0,0,0.18)',
                border: '1px solid #e2e8f0', width: 240,
              }}>
                <div style={{ fontWeight: 700, fontSize: 14 }}>{draggingEntry.su_id}</div>
                {draggingEntry.parent_job_id && (
                  <div style={{ fontSize: 12, color: '#475569' }}>↳ {draggingEntry.parent_job_id}</div>
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
    </div>
  )
}

const selectStyle: React.CSSProperties = {
  padding: '7px 12px', borderRadius: 6, border: '1px solid #d1d5db',
  fontSize: 14, background: '#fff', cursor: 'pointer', outline: 'none',
}
const filterChip: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 6,
  background: '#dbeafe', color: '#1d4ed8', borderRadius: 20,
  padding: '3px 10px 3px 12px', fontSize: 13, fontWeight: 600,
}
const chipClear: React.CSSProperties = {
  background: 'none', border: 'none', cursor: 'pointer',
  color: '#1d4ed8', padding: 0, fontSize: 12, lineHeight: 1,
  display: 'flex', alignItems: 'center',
}
const refreshBtn: React.CSSProperties = {
  padding: '7px 14px', borderRadius: 6, border: '1px solid #d1d5db',
  background: '#fff', cursor: 'pointer', fontSize: 14, color: '#374151',
}
const addBtn: React.CSSProperties = {
  padding: '7px 14px', borderRadius: 6, border: 'none',
  background: '#2563eb', color: '#fff', fontWeight: 600, cursor: 'pointer', fontSize: 14,
}
