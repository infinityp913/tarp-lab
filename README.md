# TARP Lab Dashboard (`tarp-lab`)

Localhost kanban dashboard built for the **Tharros Archaeological Research Project (TARP)** — and adaptable to any active archaeological excavation. Tracks photogrammetry (Pgram) jobs through the full processing pipeline and Stratigraphic Unit (SU) volume generation processes. Dark-mode UI, Google Sheets sync.

See also: [`tarp-field` repo](https://github.com/infinityp913/tarp-field) (separate) — light-mode Field website for archaeologists.

## Tabs

- **Model Production**: Kanban board for `Pgram_Job_###` folders. Moving a card physically moves the folder on disk. Buttons launch Metashape, CloudCompare, and QGIS.
- **SU Volumes**: Tracks stratigraphic units through the CloudComPy snip pipeline → volume OBJ → SU sheet → AIR upload. Cards move through: Not Started → To Be Pre-Snipped → To Be Snipped → To Be Post-Snipped → Volume Created → SU Sheet Created → Uploaded to AIR. Gutter buttons between columns launch the CloudComPy scripts (pre-snip, auto-snip, post-snip, create SU sheet) and advance the relevant cards automatically on success. SU cards have inline Top/Bottom Pgram number fields that save on blur.

## Google Sheets schema

### Pgram Jobs (10 columns A–J)
`Pgram Number` · `Trench` · `SUs Open` · `SUs Closed` · `Photos—No Alignment` · `Alignment+Manual Check` · `PLY Created (Overnight completed)` · `Uploaded to AIR` · `Notes` · `Last Updated (CET)`

> Pgram Number is stored as an **integer** (e.g. `696`, not `Pgram_Job_696`).

### SU Tracking (10 columns A–J)
`SU ID` · `Top Pgram` · `Bottom Pgram` · `Volume Stage` · `Volume Created` · `SU Sheet Created` · `Uploaded to AIR` · `Notes` · `Last Updated (CET)` · `Snip Method`

- `Volume Stage` (col D) holds the raw stage string. It takes precedence over the checkbox-derived stage so the pre-snip stages (`to_be_pre_snipped`, `to_be_snipped`, `to_be_post_snipped`) are preserved across syncs. Old rows without this column fall back to checkbox logic.
- `Snip Method` (col J) is set to `"auto"` when auto-snip advanced the card, empty otherwise. Controls whether the debug image button is shown on the card.

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

# Current season — update both at the start of each season.
season_year: 2026          # drives the "Season YYYY" label in the header
current_year_trenches:     # inclusive trench range scanned/run for the season
  min: 20000               # 2026 trenches run 20000–23000
  max: 23000

app_paths:
  metashape:    ""   # full path or leave blank
  cloudcompare: ""
  qgis:        ""   # auto-discovered on Windows

scripts:
  alignment: ""
  overnight: ""
  gcp_csv: ""
  overnight_output_assets_root: ""
  # Volume (CloudComPy) pipeline — enables the Pre-Snip / Auto-Snip / Post-Snip buttons.
  # volume_script_dir must contain a Data/ subfolder and example.json.
  # cloudcompy_python: run `conda activate CloudComPy310 && where python` to find it.
  pre_snip: ""
  auto_snip: ""
  post_snip: ""
  create_su_sheet: ""
  volume_script_dir: ""
  cloudcompy_python: ""

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

> **Windows (PowerShell):**
> - Use `python` instead of `python3` (e.g. `python -m backend.main --dev`). On Windows `python3` may resolve to another interpreter (e.g. QGIS's bundled Python) that lacks the backend dependencies.
> - PowerShell doesn't support `&&`. Use `;` instead (e.g. `cd frontend; npm run dev`).

## Folder naming

Job folders must match `Pgram_Job_###` or `Pgram_Job_###_anything`:

```
Pgram_Job_696
Pgram_Job_697_SU16014-16015
Pgram_Job_698_SU016_MOVED_TO_MSI   ← scanned correctly; _MOVED_TO_MSI stripped before parse
```

## Seasonal trench range

Job scanning, the run buttons, and the misnamed-folder warning only operate on trench
subfolders within `current_year_trenches` (set in `config.yaml`). For 2026 the trenches are
`20000–23000`. Folders at the stage-root level (e.g. `__pycache__`, `Pre-2026`) and
out-of-season trenches (e.g. `Trench 19000`) are ignored entirely — they won't show jobs,
won't be run, and won't be flagged as misnamed.

**At the start of each new season, update `season_year` and `current_year_trenches`.** The
header shows *"Season YYYY"* (from `season_year`) next to a *"Trenches X–Y"* badge (from
`current_year_trenches`). The range is inclusive on both ends; only `Trench NNNNN` folders
are matched.

## Guarded stage transitions

| From | To | Dialog |
|---|---|---|
| To Be Aligned | To Overnight | Did the alignment script run successfully? |
| To Overnight | Processed | Did the overnight script run succeed? |
| To Be Pre-Snipped | To Be Snipped | Did not run pre-snip — use the Pre-Snip button. |
| To Be Snipped | To Be Post-Snipped | Did not run auto-snip — use the Auto-Snip button, or confirm if manually snipped in CloudCompare. |
| To Be Post-Snipped | Volume Created | Did not run post-snip — use the Post-Snip button. |

The SU snip transitions gate against accidental drag-and-drop. Cards can still be moved backward freely. The "→" button on each card advances it one step and also triggers the confirmation dialog where required.

## Timestamps

All timestamps use `Europe/Rome` via Python `zoneinfo` — correctly handles both CET (UTC+1, winter) and CEST (UTC+2, summer) automatically.

## User guides
- `LAB_HOWTO.md` — for lab technicians
- `FIELD_HOWTO.md` — in the `tarp-field` repo
