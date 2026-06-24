import type { PgramJob } from '../types'

export async function fetchJobs(): Promise<PgramJob[]> {
  const res = await fetch('/api/pgram/jobs')
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export interface IgnoredFolder {
  name: string
  stage: string
  parent: string  // empty for top-level; "Trench XXX" if nested
}

export async function fetchIgnoredFolders(): Promise<IgnoredFolder[]> {
  try {
    const res = await fetch('/api/pgram/ignored-folders')
    if (!res.ok) return []
    return await res.json()
  } catch {
    return []
  }
}

export interface FixSuNamesResult {
  renamed: { from: string; to: string; pgram: number; source: 'suffix' | 'field_sheet' }[]
  organized: { name: string; trench: string }[]
  skipped: { name: string; reason: string }[]
}

export async function fixSuNames(): Promise<FixSuNamesResult> {
  const res = await fetch('/api/pgram/fix-su-names', { method: 'POST' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || res.statusText)
  }
  return res.json()
}

export interface Season {
  year: number
  trench_min: number
  trench_max: number
}

export async function fetchSeason(): Promise<Season | null> {
  try {
    const res = await fetch('/api/pgram/season')
    if (!res.ok) return null
    return await res.json()
  } catch {
    return null
  }
}

export async function createJob(data: {
  job_id: string
  su_string: string
  trench: string
}): Promise<PgramJob> {
  const res = await fetch('/api/pgram/jobs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || res.statusText)
  }
  return res.json()
}

export interface StageResult {
  requires_confirmation?: boolean
  message?: string
  job?: PgramJob
  error?: string
}

export async function updateStage(
  jobId: string,
  targetStage: string,
  confirmed = false
): Promise<StageResult> {
  const res = await fetch(`/api/pgram/jobs/${jobId}/stage`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ target_stage: targetStage, confirmed }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    return { error: err.detail || res.statusText }
  }
  const data = await res.json()
  if (data.requires_confirmation) return data
  return { job: data }
}

export async function updateNotes(jobId: string, notes: string): Promise<void> {
  const res = await fetch(`/api/pgram/jobs/${jobId}/notes`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ notes }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || res.statusText)
  }
}

export async function openApp(jobId: string, app: string): Promise<void> {
  const res = await fetch(`/api/pgram/jobs/${jobId}/open/${app}`, { method: 'POST' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || res.statusText)
  }
}

export type RunKind = 'alignment' | 'overnight' | 'both'
export type RunJobStatus = 'queued' | 'running' | 'done' | 'failed' | 'cancelled'

export interface RunJob {
  job_id: string
  su_string: string
  trench: string
  stage: string
  status: RunJobStatus
  step: string | null
  error: string | null
}

export interface RunStatus {
  active: boolean
  kind: RunKind | null
  started_at: string | null
  cancel: boolean
  jobs: RunJob[]
}

export async function startRun(kind: RunKind): Promise<{ started: boolean; count?: number }> {
  const res = await fetch(`/api/pgram/run/${kind}`, { method: 'POST' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || res.statusText)
  }
  return res.json()
}

export async function getRunStatus(): Promise<RunStatus> {
  const res = await fetch('/api/pgram/run/status')
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function cancelRun(): Promise<void> {
  const res = await fetch('/api/pgram/run/cancel', { method: 'POST' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || res.statusText)
  }
}

export interface BatchMoveResult {
  moved: string[]
  failed: { job_id: string; error: string }[]
}

export async function batchMove(fromStage: string, toStage: string): Promise<BatchMoveResult> {
  const res = await fetch('/api/pgram/batch-move', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ from_stage: fromStage, to_stage: toStage }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || res.statusText)
  }
  return res.json()
}
