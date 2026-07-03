import type { SUEntry, VolumeRunKind, VolumeRunStatus } from '../types'

export async function fetchEntries(): Promise<SUEntry[]> {
  const res = await fetch('/api/su/entries')
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function createEntry(data: {
  su_id: string
  top_pgram?: string
  bot_pgram?: string
  trench: string
}): Promise<SUEntry> {
  const res = await fetch('/api/su/entries', {
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

export async function updateStage(
  suId: string,
  targetStage: string,
  confirmed = false,
): Promise<{ requires_confirmation?: boolean; message?: string; ok?: boolean }> {
  const res = await fetch(`/api/su/entries/${suId}/stage`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ target_stage: targetStage, confirmed }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || res.statusText)
  }
  return res.json()
}

export async function updatePgrams(suId: string, topPgram: string, botPgram: string): Promise<void> {
  const res = await fetch(`/api/su/entries/${suId}/pgrams`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ top_pgram: topPgram, bot_pgram: botPgram }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || res.statusText)
  }
}

export async function updateNotes(suId: string, notes: string): Promise<void> {
  const res = await fetch(`/api/su/entries/${suId}/notes`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ notes }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || res.statusText)
  }
}

export async function updateReadyForSheet(suId: string, ready: boolean): Promise<void> {
  const res = await fetch(`/api/su/entries/${suId}/ready-for-sheet`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ready }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || res.statusText)
  }
}

export async function updateFlagged(suId: string, flagged: boolean): Promise<void> {
  const res = await fetch(`/api/su/entries/${suId}/flagged`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ flagged }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || res.statusText)
  }
}

export async function provisionFromPly(): Promise<{
  created: object[]
  skipped: { su_id?: string; pgram?: number; reason: string }[]
  ply_count: number
  removed: { su_id: string; top_pgram: string }[]
  cleared: { su_id: string; bot_pgram: string }[]
}> {
  const res = await fetch('/api/su/provision-from-ply', { method: 'POST' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || res.statusText)
  }
  return res.json()
}

export async function openPly(suId: string, pgramType: 'top' | 'bot'): Promise<void> {
  const res = await fetch(`/api/su/entries/${suId}/open-ply/${pgramType}`, { method: 'POST' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || res.statusText)
  }
}

export async function openBothPly(suId: string): Promise<void> {
  const res = await fetch(`/api/su/entries/${suId}/open-both-ply`, { method: 'POST' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || res.statusText)
  }
}

export async function openBins(suId: string): Promise<void> {
  const res = await fetch(`/api/su/entries/${suId}/open-bins`, { method: 'POST' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || res.statusText)
  }
}

export async function openPostSnipBin(suId: string): Promise<void> {
  const res = await fetch(`/api/su/entries/${suId}/open-post-snip-bin`, { method: 'POST' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || res.statusText)
  }
}

export async function openVolume(suId: string): Promise<void> {
  const res = await fetch(`/api/su/entries/${suId}/open-volume`, { method: 'POST' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || res.statusText)
  }
}

export async function openTopVolume(suId: string): Promise<void> {
  const res = await fetch(`/api/su/entries/${suId}/open-top-volume`, { method: 'POST' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || res.statusText)
  }
}

export async function openSuSheet(suId: string): Promise<void> {
  const res = await fetch(`/api/su/entries/${suId}/open-su-sheet`, { method: 'POST' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || res.statusText)
  }
}

export async function openLidar(suId: string): Promise<void> {
  const res = await fetch(`/api/su/entries/${suId}/open-lidar`, { method: 'POST' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || res.statusText)
  }
}

export async function openDebugImage(suId: string): Promise<void> {
  const res = await fetch(`/api/su/entries/${suId}/open-debug-image`, { method: 'POST' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || res.statusText)
  }
}

export async function startVolumeRun(
  kind: VolumeRunKind,
  suId?: string,
): Promise<{ started: boolean; count?: number }> {
  // Pass su_id to run the script on just one card (single-SU test run).
  const qs = suId ? `?su_id=${encodeURIComponent(suId)}` : ''
  const res = await fetch(`/api/su/run/${kind}${qs}`, { method: 'POST' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || res.statusText)
  }
  return res.json()
}

export async function getVolumeRunStatus(): Promise<VolumeRunStatus> {
  const res = await fetch('/api/su/run/status')
  if (!res.ok) throw new Error(res.statusText)
  return res.json()
}

export async function cancelVolumeRun(): Promise<void> {
  const res = await fetch('/api/su/run/cancel', { method: 'POST' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || res.statusText)
  }
}

export async function pullFieldData(): Promise<{ total: number; with_field_data: number }> {
  const res = await fetch('/api/sheets/pull', { method: 'POST' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || res.statusText)
  }
  return res.json()
}

export async function syncSheets(): Promise<{ pgram_count: number; su_count: number }> {
  const res = await fetch('/api/sheets/sync', { method: 'POST' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || res.statusText)
  }
  return res.json()
}

export async function batchMoveToPreSnip(): Promise<{ moved: number; skipped: number; detail?: string }> {
  const res = await fetch('/api/su/batch-move-to-pre-snip', { method: 'POST' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || res.statusText)
  }
  return res.json()
}

export async function startChainRun(): Promise<{ started: boolean; kind?: string; count?: number; error?: string }> {
  const res = await fetch('/api/su/run/chain', { method: 'POST' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || res.statusText)
  }
  return res.json()
}
