# TARP Lab Dashboard (`tarp-lab`)

Localhost kanban dashboard for the TARP photogrammetry lab — tracks Pgram jobs through the processing pipeline and SU volumetrics. Dark-mode UI, Google Sheets sync.

See also: `tarp-field` repo (separate) — light-mode Field website for archaeologists.

## Tabs

- **Model Production**: Kanban board for `Pgram_Job_###` folders. Moving a card physically moves the folder on disk. Buttons launch Metashape, CloudCompare, and QGIS.
- **SU Volumes**: Tracks stratigraphic units through volumetrics → SU sheet → AIR upload. SU cards have inline Top/Bottom Pgram number fields that save on blur.

## Google Sheets schema

### Pgram Jobs (10 columns A–J)
`Pgram Number` · `Trench` · `SUs Open` · `SUs Closed` · `Photos—No Alignment` · `Alignment+Manual Check` · `Overnight Completed` · `Uploaded to AIR` · `Notes` · `Last Updated (CET)`

> Pgram Number is stored as an **integer** (e.g. `696`, not `Pgram_Job_696`).

### SU Tracking (9 columns A–I)
`SU ID` · `Top Pgram` · `Bottom Pgram` · `Trench` · `Volumetrics Created` · `SU Sheet Created` · `Uploaded to AIR` · `Notes` · `Last Updated (CET)`

### Staging tabs
`full_sync` writes to `Pgram Jobs_Staging` and `SU Tracking_Staging` first, then does a single `batchUpdate copyPaste` to the live tabs. This minimises the window where live data is empty. A random 0–3 s jitter at sync start reduces the chance of Lab + Field sync calls colliding.

## Setup

### 1. `config.yaml`

```yaml
base_path: "C:\\Users\\Photogrammetry"   # Windows stage-folder root
dev_base_path: "/Users/you/tarp-test"     # Mac dev path (auto-used on non-Windows)

stage_folders:
  to_be_processed: To Be Processed
  to_be_aligned:   To Be Aligned
  to_overnight:    To Overnight
  processed:       Processed
  uploaded_air:    Uploaded to AIR

app_paths:
  metashape:    ""   # full path or leave blank
  cloudcompare: ""
  qgis:        ""   # auto-discovered on Windows

gsheets_spreadsheet_id: ""   # from the spreadsheet URL
host: 127.0.0.1
port: 8000
```

### 2. Google Sheets (optional but recommended)

1. Enable **Google Sheets API** in Google Cloud Console.
2. Create an **OAuth 2.0 Desktop App** credential → download `credentials.json` → place in repo root.
3. Run auth flow once:
   ```bash
   python3 -c "from backend.services.gsheets import run_auth_flow; run_auth_flow()"
   ```
4. Token saved to `%APPDATA%\tarp-dashboard\token.json` (Windows) or `~/AppData/Roaming/tarp-dashboard/token.json`.

### 3. Run

```bash
# Install dependencies (first time)
pip install -r requirements.txt

# Start server (opens browser automatically)
python3 -m backend.main

# Open browser at http://127.0.0.1:8000
```

## Development

```bash
# Backend with hot-reload (reads dev_base_path from config.yaml, handles OAuth)
python3 -m backend.main --dev

# Frontend dev server (hot-reload, proxies API to :8000)
cd frontend && npm run dev

# Rebuild frontend bundle (served by FastAPI in production)
cd frontend && npm run build

# Tests
python3 -m pytest tests/ -v
```

## Folder naming

Job folders must match `Pgram_Job_###` or `Pgram_Job_###_anything`:

```
Pgram_Job_696
Pgram_Job_697_SU16014-16015
Pgram_Job_698_SU016_MOVED_TO_MSI   ← scanned correctly; _MOVED_TO_MSI stripped before parse
```

## Guarded stage transitions

| From | To | Dialog |
|---|---|---|
| To Be Aligned | To Overnight | Did the alignment script run successfully? |
| To Overnight | Processed | Did the overnight script run succeed? |

## Timestamps

All timestamps use `Europe/Rome` via Python `zoneinfo` — correctly handles both CET (UTC+1, winter) and CEST (UTC+2, summer) automatically.

## User guides
- `LAB_HOWTO.md` — for lab technicians
- `FIELD_HOWTO.md` — in the `tarp-field` repo
