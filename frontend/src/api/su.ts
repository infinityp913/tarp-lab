import type { SUEntry } from '../types'

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

export async function updateStage(suId: string, targetStage: string): Promise<void> {
  const res = await fetch(`/api/su/entries/${suId}/stage`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ target_stage: targetStage }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || res.statusText)
  }
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

export async function provisionFromPly(): Promise<{
  created: object[]
  skipped: { su_id?: string; pgram?: number; reason: string }[]
  ply_count: number
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
