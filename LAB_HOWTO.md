# TARP Lab Dashboard — How-To Guide

*For lab technicians using the MSI machine*

---

## Starting the dashboard

1. Open the `tarp-lab` folder on your Desktop.
2. Double-click **`start.bat`**.
3. A black command window will appear — leave it open. The dashboard will open in your browser automatically at **http://127.0.0.1:8000**.

To close the dashboard, close the black command window.

---

## First-time setup

You only need to do this once.

### Step 0 — Get the code onto this machine

**Install Python** (if not already installed):
1. Go to [python.org/downloads](https://www.python.org/downloads/) and download the latest Python 3 installer.
2. Run the installer. On the first screen, **tick "Add Python to PATH"** before clicking Install Now.

**Download the dashboard:**
1. Go to [github.com/infinityp913/tarp-lab](https://github.com/infinityp913/tarp-lab)
2. Click the green **Code** button → **Download ZIP**
3. Open your Downloads folder, right-click the ZIP → **Extract All…** and extract to your Desktop

**Install dependencies:**
4. Open the extracted folder on your Desktop — it will be called `tarp-lab-main`. Rename it to **`tarp-lab`** (right-click → Rename)
5. Open the `tarp-lab` folder and double-click **`setup.bat`** — a window will appear, wait for **"Setup complete"** then close it

You're ready. Proceed to Step 1.

### Step 1 — Set up the stage folders

The dashboard reads photogrammetry jobs from a fixed folder structure on this machine. You need to create it once.

1. Open **File Explorer** and navigate to `C:\Users\Photogrammetry` — create this folder if it doesn't exist.
2. Inside `C:\Users\Photogrammetry`, create these five subfolders (names must match exactly):
   - `To Be Processed`
   - `To Be Aligned`
   - `To Overnight`
   - `Processed`
   - `Uploaded to AIR`
3. Open `config.yaml` in the `tarp-lab` folder (the same folder as `start.bat`) and check that the `base_path` line points to the folder you just created:
   ```
   base_path: "C:\Users\Photogrammetry"
   ```
   If your folder is in a different location, update this line to match before continuing.

Inside each stage folder, jobs live in **trench subfolders** named after the trench (e.g. `Trench 20000`), and individual job folders follow the pattern `Pgram_Job_###_<SU_string>` (e.g. `Pgram_Job_696_SU20014`). The dashboard creates new job folders for you automatically — you only need the five stage folders to exist.

### Step 1b — Set this season's year and trench numbers

The dashboard only looks at trenches for the **current season**. This keeps old trenches from previous years off the board and out of the scripts.

1. In the same `config.yaml`, find the `season_year` line and the `current_year_trenches` lines:
   ```
   season_year: 2026
   current_year_trenches:
     min: 20000   # 2026 trenches run 20000–23000
     max: 23000
   ```
2. Set `season_year` to the current year, and set `min`/`max` to this season's trench range (inclusive). For **2026**, the values above are correct.
3. Save the file. When the dashboard is running, the header shows **"Season 2026"** next to a **"Trenches 20000–23000"** badge confirming the active range.

> Anything outside this range — folders sitting loose in a stage folder (like `Pre-2026` or `__pycache__`) and old trenches (like `Trench 19000`) — is ignored. It won't appear on the board, won't be run by the scripts, and won't trigger the "misnamed folder" warning.

### Step 2 — Get access to the Google Sheet

Ask **Ananth** to share [the TARP tracking Google Sheet](https://docs.google.com/spreadsheets/d/1r6TMtVEl6wIAAO8FNEXW1qkkFeAxumyyRsFSE4vHIwI/edit?gid=1174152009#gid=1174152009) for the current season with your Google account. You need edit access.

### Step 3 — Get the credentials file

Ask **Ananth** for the `credentials.json` file and place it inside the `tarp-lab` folder (the same folder where `start.bat` is). Do not rename the file.

### Step 4 — Authorise the app

The next time you double-click `start.bat`, a browser window will open asking you to sign in to Google and grant access. Use the Google account that Ananth shared the sheet with, then click **Allow**.

That's it. The authorisation is saved — you won't be asked again on this machine.

---

## Model Production tab

This tab shows all photogrammetry jobs as a kanban board.

**Columns** (left to right):
1. **To Be Processed** — job arrived from the field, waiting to be processed
2. **To Be Aligned** — in the alignment pipeline
3. **To Overnight** — running the overnight script
4. **Processed** — complete
5. **Uploaded to AIR** — delivered to the archive

**Moving a job:** click and drag a card to the next column. You can only move one step forward at a time (or any step backward). Moving to **To Overnight** or **Processed** will ask a quick confirmation first — answer honestly.

**Field notes:** each job card shows notes left by the field team (SUs opened/closed, capture conditions). These are read-only on the lab side.

**Lab notes:** click a card to open it. You can add your own notes — they save automatically.

**Filtering by trench:** use the trench dropdown at the top-left to narrow the board to one trench.

**Current season:** the header shows **"Season YYYY"** next to a **"Trenches X–Y"** badge — which trenches the board is scanning this season. If it's wrong, update `season_year` / `current_year_trenches` in `config.yaml` (see *Starting a new season* below).

**Creating a new job:** click **+ New Job** at the top. Fill in the job number and SU string — the folder will be created automatically on disk.

---

## SU Volumes tab

This tab tracks individual stratigraphic units through the volumetrics pipeline.

**Columns:**
1. **Not Started** — SU registered, no volumes yet
2. **Volume Created** — volumetric model generated
3. **SU Sheet Created** — SU data sheet completed
4. **Uploaded to AIR** — delivered to the archive

**Top and Bottom Pgram:** each card shows two number boxes for the photogrammetry job numbers covering the top and bottom of that SU. Click a box, type the number, then click anywhere else — it saves automatically.

**Notes:** click a card to open it and add notes. They save automatically.

**Creating a new SU:** click **+ New SU**. The trench is filled in automatically if the SU number follows the standard format (e.g. SU 16014 → Trench 16000).

---

## Sync button

The **⇅ Sync now** button in the top-right header performs a two-phase sync:

1. **↓ Pulling…** — reads the latest field data (notes, SUs opened/closed) from Google Sheets
2. **↑ Pushing…** — writes lab job states and SU tracking data back to Google Sheets

After a successful sync the button shows **✓ Synced** and the timestamp updates. If sync fails it shows **✕ Sync failed** in red.

The dashboard auto-syncs every 5 minutes — you rarely need to click it. Use it if you want the Sheet updated immediately after making several changes.

---

## Re-authentication

If a red warning banner appears at the top saying the Google Sheets token was revoked, click **↻ Re-authenticate**. A browser window will open — sign in with the same Google account and click Allow. The connection will restore automatically.

---

## Starting a new season

When a new season begins and you move to a new set of trenches, update the dashboard so it scans the right ones:

1. Close the dashboard (close the black command window).
2. Open `config.yaml` in the `tarp-lab` folder.
3. Change `season_year` to the new year and set `current_year_trenches` `min`/`max` to the new season's trench range (inclusive):
   ```
   season_year: 2027
   current_year_trenches:
     min: 24000
     max: 27000
   ```
4. Save the file and start the dashboard again. The header will show the new **"Season YYYY"** label and **"Trenches X–Y"** badge.

That's the only change needed — the previous season's trenches stay on disk but drop off the board automatically.

---

## Troubleshooting

| Problem | What to check |
|---|---|
| Dashboard doesn't open | Make sure the black command window is still open. Try going to http://127.0.0.1:8000 manually. |
| No jobs showing on the board | The stage folders may not be found. Check that the `tarp-lab` folder is configured correctly (ask Ananth). Also check the **"Working on trenches X–Y"** badge — if this season's trenches aren't in that range, update `current_year_trenches` (see *Starting a new season*). |
| Jobs in an old trench missing | Old trenches outside `current_year_trenches` are hidden on purpose. Widen the range in `config.yaml` if you need them back. |
| Sync failed (red button) | Check that the machine is connected to the internet. It will retry automatically on the next 5-minute cycle. |
| Red auth banner | Click **↻ Re-authenticate** and sign in again. |
| Folder won't move | Close the job in Metashape first — Windows locks the folder while it's open. |

---

## For developers (Mac setup)

```bash
# Clone the repo and navigate to the folder
git clone <repo-url> && cd tarp-lab

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip3 install -r requirements.txt

# Run the backend with hot reload (reads dev_base_path and port from config.yaml,
# handles Google Sheets OAuth automatically on first run)
python3 -m backend.main --dev

# Run the frontend dev server in a second terminal
cd frontend && npm run dev

# Run tests
python3 -m pytest tests/ -v
```

Set `dev_base_path` in `config.yaml` to a local test folder that mirrors the stage-folder structure.
