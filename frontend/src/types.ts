export interface PgramJob {
  job_id: string
  su_string: string
  trench: string
  stage: string
  notes: string             // lab-entered notes (editable)
  notes_from_field: string  // from TARP Field sheet (read-only)
  sus_opened: string        // from TARP Field sheet (read-only)
  sus_closed: string        // from TARP Field sheet (read-only)
  last_updated: string
}

export interface SUEntry {
  su_id: string
  top_pgram: string
  bot_pgram: string
  trench: string
  stage: string
  notes: string
  last_updated: string
  /** Computed server-side: both top & bottom pgrams are processed (PLYs exist),
   *  so the volume is ready to be extracted. */
  ready?: boolean
  /** "auto" when auto-snip advanced this card; "" otherwise. Used to show debug image button. */
  snip_method?: string
}

export const PGRAM_STAGES = [
  { key: 'to_be_processed', label: 'To Be Processed' },
  { key: 'to_be_aligned', label: 'To Be Aligned' },
  { key: 'to_overnight', label: 'To Overnight' },
  { key: 'processed', label: 'Processed' },
  { key: 'uploaded_air', label: 'Uploaded to AIR' },
]

export const SU_STAGES = [
  { key: 'not_started', label: 'Not Started' },
  { key: 'to_be_pre_snipped', label: 'To Be Pre-Snipped' },
  { key: 'to_be_snipped', label: 'To Be Snipped' },
  { key: 'to_be_post_snipped', label: 'To Be Post-Snipped' },
  { key: 'volumetrics_created', label: 'Volume Created' },
  { key: 'su_sheet_created', label: 'SU Sheet Created' },
  { key: 'uploaded_air', label: 'Uploaded to AIR' },
]

export type VolumeRunKind = 'pre_snip' | 'auto_snip' | 'post_snip' | 'create_su_sheet' | 'chain'

export interface VolumeRunStatus {
  active: boolean
  kind: VolumeRunKind | null
  started_at: string | null
  status: 'idle' | 'running' | 'done' | 'failed'
  error: string | null
  cards_advanced: number
}

export const FILESYSTEM_STAGES = new Set(['to_be_processed', 'to_be_aligned', 'to_overnight', 'processed', 'uploaded_air'])

/** Infers trench from an SU string like "16,015-16,016" → "Trench 16000" */
export function inferTrench(suString: string): string | null {
  const digits = suString.replace(/,/g, '').match(/\d+/)
  if (!digits) return null
  const num = parseInt(digits[0], 10)
  if (isNaN(num) || num < 1000) return null
  return `Trench ${Math.floor(num / 1000) * 1000}`
}

export const TRENCHES = [
  'Trench 20000', 'Trench 21000', 'Trench 22000', 'Trench 23000', 'Trench 24000',
]
