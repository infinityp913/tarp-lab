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
  { key: 'volumetrics_created', label: 'Volume Created' },
  { key: 'su_sheet_created', label: 'SU Sheet Created' },
  { key: 'uploaded_air', label: 'Uploaded to AIR' },
]

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
