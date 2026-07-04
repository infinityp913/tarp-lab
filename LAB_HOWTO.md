# TARP Lab Dashboard — How-To Guide

*For lab technicians using the MSI machine*

---

## Full Pipeline Overview

Every photogrammetry job and SU passes through two sequential pipelines. The dashboard manages both.

![TARP processing pipeline diagram showing photogrammetry and volume production workflows](docs/screenshots/pipeline_diagram.png)

**Outputs at each stage:**

| Stage | Output file |
|---|---|
| Overnight complete | `GIS_YYYY/Trench NNNNN/Pgram_Job_###/model.ply` + ortho + DEM |
| Post-Snip complete | `Volumetrics_YYYY/Trench NNNNN/SU_###_raw.obj` + `volume_measures.txt` |
| SU Sheet complete | `SU_###_sheet.pdf` (georeferenced, ready for AIR upload) |

---

## Starting the dashboard

1. Open the `tarp-lab` folder on your Desktop.
2. Double-click **`start.bat`**.
3. A black command window will appear — leave it open. The dashboard opens in your browser at **http://127.0.0.1:8000**.

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
4. Open the extracted folder — it will be called `tarp-lab-main`. Rename it to **`tarp-lab`** (right-click → Rename)
5. Open the `tarp-lab` folder and double-click **`setup.bat`** — wait for **"Setup complete"** then close it

### Step 1 — Set up the stage folders

1. Open **File Explorer** and navigate to `C:\Users\Photogrammetry` — create this folder if it doesn't exist.
2. Inside `C:\Users\Photogrammetry`, create these five subfolders (names must match exactly):
   - `To Be Processed`
   - `To Be Aligned`
   - `To Overnight`
   - `Processed`
   - `Uploaded to AIR`
3. Open `config.yaml` in the `tarp-lab` folder and check the `base_path` line:
   ```yaml
   base_path: "C:\Users\Photogrammetry"
   ```

Inside each stage folder, jobs live in **trench subfolders** (e.g. `Trench 20000`), and job folders follow `Pgram_Job_###_SU####`. The dashboard creates new job folders automatically — you only need the five stage folders to exist.

### Step 1b — Set this season's year and trench range

```yaml
season_year: 2026
current_year_trenches:
  min: 20000   # 2026 trenches run 20000–23000
  max: 23000
```

The header shows **"Season 2026"** + **"Trenches 20000–23000"** confirming the active range. Trenches outside this range are hidden entirely — they won't appear, won't be run, and won't trigger misnamed-folder warnings.

### Step 1c — Configure the CloudComPy volume pipeline

The Pre-Snip / Auto-Snip / Post-Snip buttons only work if paths are set in `config.yaml`. For 2026 the paths are already filled in — check with Ananth if buttons show an error.

```yaml
scripts:
  alignment:    "C:\\...\\TARP 2026 Alignment Script - Headless.py"
  overnight:    "C:\\...\\TARP 2026 Overnight Script - Headless.py"
  gcp_csv:      "C:\\...\\GCPs 2026 EPSG32632.csv"
  overnight_output_assets_root: "C:\\Users\\Photogrammetry\\GIS_2026"

  pre_snip:         "C:\\...\\cloudcomparescript\\pre_snip_script.py"
  auto_snip:        "C:\\...\\cloudcomparescript\\auto_snip_script.py"
  post_snip:        "C:\\...\\cloudcomparescript\\post_snip_script.py"
  create_su_sheet:  "C:\\...\\AutomateSuSheetCreation\\generate_su_sheets.py"
  volume_script_dir: "C:\\...\\cloudcomparescript"
  cloudcompy_python: "C:\\...\\CloudComPy\\venv312\\Scripts\\python.exe"
  cloudcompy_root:   "C:\\...\\CloudComPy\\CloudComPy312"
  create_su_sheet_dir: "C:\\...\\AutomateSuSheetCreation"
  qgis_launcher:    "C:\\Program Files\\QGIS 3.40.8\\bin\\python-qgis-ltr.bat"
```

### Step 2 — Get access to the Google Sheet

Ask **Ananth** to share the TARP tracking Google Sheet with your Google account (edit access).

### Step 3 — Get the credentials file

Ask **Ananth** for `credentials.json` and place it in the `tarp-lab` folder (same folder as `start.bat`).

### Step 4 — Authorise the app

The first time you start the dashboard a browser window will open — sign in with the shared Google account and click **Allow**. The token is saved; you won't be asked again.

---

## Model Production tab

This tab shows all photogrammetry jobs as a kanban board. Moving a card physically moves the `Pgram_Job_###` folder on disk — no separate file management step.

**Columns (left to right):**

| Column | What it means |
|---|---|
| To Be Processed | Job arrived from field; photos imported into Metashape |
| To Be Aligned | Alignment script has run; awaiting manual check |
| To Overnight | Alignment checked; ready for dense reconstruction |
| Processed | Overnight complete; PLY + ortho exported |
| Uploaded to AIR | Delivered to archive |

### Running the Alignment script

1. Move the job folder into `To Be Processed / Trench NNNNN /` and create it in Metashape (add photos, place GCPs).
2. On the dashboard card, click **Align →**. The headless alignment script runs for that job only.
3. The script requires `gcp_csv` to be set in `config.yaml` — it refuses to run without it.
4. When the script finishes the card moves to **To Be Aligned** automatically.
5. Open the project in Metashape and inspect the sparse cloud. Fix any misaligned cameras before proceeding.
6. Drag the card to **To Overnight** — the dashboard asks: _"Did the alignment script run successfully?"_

### Running the Overnight script

The **Overnight →** button runs all jobs currently in the `To Overnight` column sequentially — it's a column-level button, not per-card. Run it at end of day so machines work overnight unattended.

Progress is streamed live: a banner appears at the top with a spinner and live output. When the script finishes a toast shows how many jobs completed. PLY models and exports are written to `overnight_output_assets_root` (e.g. `GIS_2026`).

When the run succeeds, drag the cards to **Processed**.

### Other card actions

- **↗ Metashape** — opens the job's Metashape project directly from the card
- **↗ CloudCompare** — opens the job folder in CloudCompare (for inspecting PLY output)
- **↗ QGIS** — opens the GIS project (for checking the ortho / DEM export)
- **Filtering** — use the trench dropdown and flag filter at the top to narrow the board
- **New job** — click **+ New Job** at top right; the folder is created on disk automatically

---

## SU Volumes tab

This tab tracks each Stratigraphic Unit through the CloudComPy snip pipeline to a final volume OBJ and SU Sheet.

**Before a card appears here:** go to the card in Not Started, set the **Top Pgram** and **Bottom Pgram** numbers (the Pgram job numbers for the surface above and below this SU). Both PLYs must be in the `Processed` column for the card to turn green and enter the pipeline.

**Columns (left to right):**

| Column | What it means |
|---|---|
| Not Started | SU registered; waiting for both PLYs to be processed |
| To Be Pre-Snipped | Ready for pre-snip — click Pre-Snip on the card |
| To Be Snipped | Pre-snip ran; snipping in progress (auto or manual) |
| To Be Post-Snipped | Snipping done; click Post-Snip on the card |
| Volume Created | Volume OBJ generated — review with Volume ↗ |
| SU Sheet Created | SU Sheet PDF generated |
| Uploaded to AIR | Delivered to archive |

### Step-by-step: Pre-Snip

1. Find the SU card in **Not Started**. Set the **Top Pgram** and **Bottom Pgram** fields (the two Pgram job numbers that bound this SU, top and bottom surface). Click anywhere to save.
2. Once both PLYs are processed, the card turns green with a **→** button.
3. Click **Pre-Snip** on the card (or the gutter **Pre-Snip Script** button to run all ready cards at once).
4. The script loads the top and bottom PLY meshes, samples them to point clouds, and computes bidirectional C2C distances. Output `.bin` files are saved in `cloudcomparescript/Data/Pgram_Job_###/`.
5. Card advances to **To Be Snipped** automatically.

### Step-by-step: Snipping

**Auto-Snip (iPhone LiDAR — preferred when available)**

If the field team painted the SU boundary with yellow spray paint before the LiDAR scan:

1. Card arrives in **To Be Snipped** with an **Auto-Snip** button visible.
2. Click **Auto-Snip** — the script loads the `.usdz` iPhone scan from the path set in `input.json`, detects the yellow-painted region, aligns the LiDAR scan to the photogrammetry world frame using slope-map cross-correlation, and crops both point clouds to the SU boundary.
3. A debug image is saved and linked from the card (**Debug Img ↗**) — inspect it to confirm the boundary was detected correctly.
4. Card advances to **To Be Post-Snipped** automatically.

**Manual Snip in CloudCompare (when no LiDAR annotation is available)**

1. Card arrives in **To Be Snipped** with an **Open in CC ↗** button.
2. Click **Open in CC ↗** — opens the pre-snip `.bin` files for this SU in CloudCompare.
3. In CloudCompare:
   - Use **Segment** (scissors tool) to draw a polygon around the SU boundary on the top cloud. Keep it, delete the rest.
   - Repeat for the bottom cloud.
   - Select **both** cropped clouds in the DB tree, then **File → Save** as `<su>.bin` (e.g. `20001.bin`) inside `cloudcomparescript/Data/SU<su>/`.
4. Back on the dashboard, drag the card from **To Be Snipped** to **To Be Post-Snipped** — the dialog asks you to confirm both clouds are saved before continuing.

### Step-by-step: Post-Snip

1. Click **Post-Snip** on the card (or the gutter button to run all ready cards).
2. The script loads the cropped top and bottom clouds, merges them, runs Poisson surface reconstruction, trims the mesh skirt, and computes 3D and 2.5D volumes.
3. The final `.obj` mesh is written to `Volumetrics_YYYY/Trench NNNNN/SU_###/Final_Volumes/`.
4. Volume measurements are appended to `volume_measures.txt`.
5. Card advances to **Volume Created**.
6. Click **Volume ↗** on the card to open the `.obj` in the default viewer and inspect the mesh.

### Step-by-step: SU Sheet

1. Card is in **Volume Created**. Click **Create SU Sheet** (or gutter button).
2. The script uses QGIS to load the volume OBJ, compute the SU footprint, and export a georeferenced PDF SU sheet.
3. Card advances to **SU Sheet Created**.
4. Review the PDF, then drag the card to **Uploaded to AIR** after uploading.

### Script progress and errors

While any script runs, a banner at the top of the tab shows a spinner, progress bar, and live output. The board auto-refreshes every 2.5 seconds. When the script finishes a toast shows how many cards advanced — or the error if it failed. The last 800 characters of script output are shown in the banner on failure.

---

## Sync button

The **⇅ Sync now** button in the header performs a two-phase sync:

1. **↓ Pulling** — reads the latest field data (SUs opened/closed, notes) from Google Sheets
2. **↑ Pushing** — writes lab job states and SU tracking data back to Google Sheets

The dashboard auto-syncs every 5 minutes. Use the button when you want the Sheet updated immediately after several changes.

After a successful sync the button shows **✓ Synced** with a timestamp. If it fails it shows **✕ Sync failed** in red — it will retry on the next 5-minute cycle.

---

## Re-authentication

If a red warning banner appears saying the Google Sheets token was revoked, click **↻ Re-authenticate**. A browser window opens — sign in with the same Google account and click Allow. The connection restores automatically.

---

## Starting a new season

1. Close the dashboard (close the black command window).
2. Open `config.yaml`.
3. Update `season_year` and `current_year_trenches`:
   ```yaml
   season_year: 2027
   current_year_trenches:
     min: 24000
     max: 27000
   ```
4. Save the file and start the dashboard. The header will show the new season and trench range.

Previous season trenches stay on disk but disappear from the board automatically.

---

## Troubleshooting

| Problem | What to check |
|---|---|
| Dashboard doesn't open | Make sure the black command window is still open. Try http://127.0.0.1:8000 manually. |
| Blank / white page | Frontend wasn't built or build was interrupted. Close the dashboard, double-click **`setup.bat`** again, wait for "Setup complete", then start. |
| No jobs on the board | Check that `base_path` in `config.yaml` points to the correct folder. Check the **"Trenches X–Y"** badge — if this season's trenches aren't in range, update `current_year_trenches`. |
| Jobs from an old trench missing | Trenches outside `current_year_trenches` are hidden intentionally. Widen the range if you need them. |
| Sync failed | Check internet connection. It retries automatically every 5 minutes. |
| Red auth banner | Click **↻ Re-authenticate** and sign in again. |
| Folder won't move | Close the job in Metashape first — Windows locks the folder while it's open. |
| Pre-/Auto-/Post-Snip button errors | Check the `scripts:` section in `config.yaml` — all paths must exist on disk. The error banner shows which path is wrong. |
| Script ran but no cards advanced | Script exited with a non-zero return code. Check the banner output. Verify that `Data/` inside `volume_script_dir` has the expected Pgram job subfolders. |
| "Open in CC ↗" says no .bin files found | Pre-snip hasn't run yet, or `.bin` files are in an unexpected location. Files should be at `Data/SU<su>/` as `*_top_with_dist_*.bin` and `*_bottom_with_dist_*.bin`. |
| "Volume ↗" says no OBJ found | Post-snip hasn't run. The file should be at `Volumetrics_YYYY/Trench NNNNN/SU_<id>.obj` under `base_path`. |
| Auto-snip put the boundary in the wrong place | Click **Debug Img ↗** to inspect the alignment result. If it's off, fall back to manual snip: use **Open in CC ↗**, crop both clouds in CloudCompare, and save as `<su>.bin`. |

---

## For developers (Mac setup)

```bash
# Clone and set up
git clone <repo-url> && cd tarp-lab
python3 -m venv .venv && source .venv/bin/activate
pip3 install -r requirements.txt

# Run backend with hot-reload (reads dev_base_path from config.yaml)
python3 -m backend.main --dev

# Run frontend dev server in a second terminal
cd frontend && npm run dev

# Run tests
python3 -m pytest tests/ -v
```

Set `dev_base_path` in `config.yaml` to a local folder that mirrors the stage-folder structure.
