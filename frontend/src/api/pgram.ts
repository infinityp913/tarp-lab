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
