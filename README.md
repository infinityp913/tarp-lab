# TARP Photogrammetry & Volumetrics Dashboard

Localhost kanban dashboard for tracking photogrammetry jobs and SU volumetric processing for the Tharros Archaeological Research Project, Season 2026.

## What it does

- **Pgram Tab**: Kanban board for `Pgram_Job_###` folders. Moving a card physically moves the folder on disk. Buttons launch Metashape, CloudCompare, and QGIS for the selected job.
- **SU Tab**: Kanban board for stratigraphic unit tracking (volumetrics + SU sheets + AIR upload). All state in Google Sheets.
- **Sync to Sheet**: Writes all current state to Google Sheets for backup/sharing.

## Prerequisites

- Python 3.11+
- Windows (required for folder moves and app launch paths)
- (Optional) Google Sheets API credentials for notes persistence

## Setup

### 1. Configure `config.yaml`

Edit `config.yaml` in the project root:

```yaml
base_path: "C:\\Users\\YourName\\Photogrammetry"   # Where Pgram job folders live
                                                      # Do NOT put this repo inside base_path

stage_folders:
  to_be_processed: "01_To_Be_Processed"
  to_be_aligned: "02_To_Be_Aligned"
  to_overnight: "03_To_Overnight"
  processed: "04_Processed"

app_paths:
  metashape: "C:\\Program Files\\Agisoft\\Metashape Pro\\metashape.exe"
  cloudcompare: "C:\\Program Files\\CloudCompare\\CloudCompare.exe"
  qgis: ""   # Leave blank for auto-discovery

gsheets_spreadsheet_id: ""   # See below for Google Sheets setup
```

### 2. Google Sheets setup (optional but recommended)

Without credentials, notes will not persist between sessions. AIR upload stage tracking requires Google Sheets.

1. Go to [Google Cloud Console](https://console.cloud.google.com/) and create a project.
2. Enable the **Google Sheets API**.
3. Create an **OAuth 2.0 Desktop App** credential and download `credentials.json`.
4. Place `credentials.json` in the project root (same folder as `config.yaml`).
5. Create a new Google Spreadsheet, copy its ID from the URL (the long string between `/d/` and `/edit`), and paste it into `config.yaml` as `gsheets_spreadsheet_id`.

The first time the server starts with credentials configured, a browser window will open for you to authorise access. The token is saved to `%APPDATA%\tarp-dashboard\token.json` for subsequent runs.

### 3. First run

Double-click `start.bat`. The browser opens automatically at `http://localhost:8000`.

On subsequent runs, just double-click `start.bat` again.

## Development

If you need to modify the frontend:

```bash
cd frontend
npm install
npm run dev        # Dev server at localhost:5173 with hot reload
npm run build      # Compile into backend/static/
```

Run the backend separately during development:

```bash
.venv\Scripts\activate
uvicorn backend.main:app --reload
```

## Folder naming convention

Job folders must be named `Pgram_Job_###` or `Pgram_Job_###_SU_String`:

```
Pgram_Job_001
Pgram_Job_042_1001A_1002B
```

Folders that don't match this pattern are logged and ignored.

## Guarded stage transitions

Two stage moves show a confirmation dialog before the folder is moved:

| From | To | Dialog |
|------|----|--------|
| To Be Aligned | To Overnight | Did the alignment script run successfully? |
| To Overnight | Processed | Did the overnight script run succeed? |
