# TARP Lab Dashboard — Design System

Decided: 2026-05-05 design + engineering review.

---

## Two websites, two themes

| | tarp-lab | tarp-field |
|---|---|---|
| Audience | Lab technicians (MSI machine) | Field archaeologists (Alienware) |
| Theme | **Dark mode** | **Light mode** |
| Tabs | Model Production · SU Volumes | *(3-column kanban)* |
| Repo | this repo | separate `tarp-field` repo |

---

## Lab — dark mode tokens (`frontend/src/tokens.ts`)

```ts
bg: '#0f172a'       // page background
surface: '#1e293b'  // cards, header, panels
border: '#334155'   // borders, dividers
text: '#f1f5f9'     // primary text
textSub: '#94a3b8'  // secondary text (trench, pgram numbers)
textMuted: '#64748b'// muted / placeholder
accent: '#3b82f6'   // active tab underline, primary buttons
accentText: '#60a5fa'// active tab label
inputBg: '#0f172a'  // input backgrounds
inputBorder: '#475569'
badgeBg: '#334155'  // kanban column count badge
badgeText: '#94a3b8'
colBg: '#141e33'    // kanban column background
colBgOver: '#1a2d50'// kanban column when a card is dragged over
chipBg: '#1e3a8a'   // trench filter chip
chipText: '#93c5fd'
```

## Field — light mode tokens (in `tarp-field` repo)

```ts
bg: '#f8fafc'
surface: '#ffffff'
border: '#e2e8f0'
text: '#1e293b'
textSub: '#475569'
textMuted: '#94a3b8'
accent: '#2563eb'
accentText: '#2563eb'
inputBg: '#ffffff'
inputBorder: '#d1d5db'
badgeBg: '#e2e8f0'
badgeText: '#475569'
colBg: '#f1f5f9'
colBgOver: '#dbeafe'
chipBg: '#dbeafe'
chipText: '#1d4ed8'
```

---

## Sync model

### Lab → Google Sheets (`full_sync`)
- Triggered manually (Sync button) or auto every 60 s
- Writes to `Pgram Jobs_Staging` + `SU Tracking_Staging` first
- Then clears live tabs and does a single `batchUpdate copyPaste` — minimises the read-race window to ~one API round-trip
- **Jitter**: `time.sleep(random.uniform(0, 3))` at entry — prevents Field + Lab from hitting the API simultaneously on the same 60 s tick

### Field → Google Sheets (`field push`)
- Uses `upsert_pgram()` per job only — targeted write, never `full_sync`
- Reason: Field machine doesn't have SU data; calling `full_sync` would blank the SU Tracking sheet

### Both directions
- Reads are cached in-process for 30 s (TTL). On any read failure (`_read_range` returns `None`), the stale cache is returned and a warning is logged — the UI never blanks out due to a Sheets timeout.

### Race condition acknowledgement
Two machines can call `full_sync` within the same minute. Jitter reduces but does not eliminate the chance of overlap. If overlap occurs, the second writer wins. This is acceptable: both machines write the same canonical state derived from the filesystem; the only lossy field is `SUs Closed` (manually entered), which is preserved read-before-write.

---

## Card anatomy

### Model Production (Pgram) card
```
┌──────────────────────────────────┐
│ Pgram_Job_696          Δ  ⠿    │  ← job_id; amber Δ only when notes_from_field non-empty; drag handle
│ SU 16014-16015                   │  ← su_string (if set)
│ Trench 16000                     │  ← trench (muted)
│ [↗ Metashape] [↗ CC] [↗ QGIS]  │  ← app launch buttons
├──────────────────────────────────┤  ← hairline divider; entire strip omitted when no field data
│ ▲ SU 16012, 16014  ▼ SU 16013  │  ← sus_opened (#86efac green) / sus_closed (#fca5a5 red), 11px
└──────────────────────────────────┘
```
Field data strip only renders when `sus_opened` or `sus_closed` is non-empty.
`✉` icon only renders when `notes_from_field` is non-empty.

### SU Volumes card
```
┌──────────────────────────────┐
│ SU001                    ⠿  │  ← su_id, drag handle
│ [top pgram] [bot pgram]      │  ← inline editable number inputs
│ Trench 16000                 │  ← trench (muted)
└──────────────────────────────┘
```
Pgram inputs are always visible and editable directly on the card face.
On `blur`, if the value changed, the backend `/api/su/entries/{id}/pgrams` endpoint is called.
Drag is blocked on the inputs via `onPointerDown stopPropagation`.

---

## Auto-sync header pill (Lab)

Located in the top-right of the header. Doubles as the manual sync trigger.

```
● Synced 2m ago      ← green dot, idle
● Syncing…           ← amber dot
● Sync error 5m ago  ← red dot
```

Auto-fires every 300 s via `setInterval`. The pill label shows time since last sync using a 30 s display tick.

---

## Interaction states

| Action | Behaviour |
|---|---|
| Drag card to column | Optimistic update + API call; reverts on error |
| Move pgram to overnight/processed | Confirmation dialog (TRANSITION_DIALOGS) |
| SU pgram blur | Saves to Sheets if changed; reverts + toast on error |
| Offline (Field) | Red dot in header; writes queued in localStorage; replayed on reconnect |
| Sheets timeout | Stale cache served; warning logged; no UI blankout |

---

## CET timestamps
All timestamps use `Europe/Rome` via Python `zoneinfo.ZoneInfo("Europe/Rome")`.
This automatically handles both CET (UTC+1) and CEST (UTC+2, summer).
Format: `"6 May 2026, 14:22"`
