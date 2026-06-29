# TARP Lab Dashboard — CLAUDE.md

## Project overview
FastAPI + React (Vite + TypeScript) kanban dashboard for the TARP archaeological photogrammetry lab.
Two parallel websites: **tarp-lab** (this repo, dark mode, Windows + Mac) and **tarp-field** (separate repo, light mode, Field Alienware).

## Running locally
```bash
# Backend (from repo root) — handles OAuth, hot-reload, dev_base_path
python3 -m backend.main --dev

# Frontend (separate terminal)
cd frontend && npm run dev
```

## After editing backend Python files
Run the test suite before committing:
```bash
python3 -m pytest tests/ -v
```

## Key architecture notes
- Google Sheets is the sync ledger between Field and Lab machines. Backend reads from the filesystem (stage folders) and merges with Sheets data.
- `cet_now()` in `backend/models.py` — all timestamps use `Europe/Rome` (handles CET/CEST automatically via `zoneinfo`).
- Pgram numbers are stored as **integers** in the sheet (e.g. `696`, not `Pgram_Job_696`). `_rows_to_pgram()` reconstructs the full `job_id` on read.
- `full_sync()` uses staging tabs (`Pgram Jobs_Staging`, `SU Tracking_Staging`) to minimize the window where live data is empty. It also jitters 0–3 s on entry.
- `_MOVED_TO_MSI` suffix is stripped in `_parse_job_dir()` before regex matching so it never corrupts `su_string`.
- `_blank_if_na()` in `backend/services/gsheets.py` normalises NA/n/a/N/A/#N/A and booleans to `""` in `sus_opened`/`sus_closed` from the Field Pgram Tracking sheet. `notes_from_field` is intentionally not normalised.

## Skill routing
When the user's request matches an available skill, invoke it via the Skill tool.

Key routing rules:
- Architecture → invoke /plan-eng-review
- Design system/plan review → invoke /plan-design-review
- Bugs/errors → invoke /investigate
- Code review/diff check → invoke /review
