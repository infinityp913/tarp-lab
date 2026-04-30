# Photogrammetry Folder Structure — UI Design Reference

Scan of `C:\Users\Photogrammetry\` — 282,638 files across 30,544 directories, \~1.19 TB total.

## At a glance

The machine is actively used for two overlapping workflows:

1. **Trench-based archaeological photogrammetry** (the `Pgram_Job_###_SU####` projects). This is the dominant workflow by volume and is organized as a pipeline with explicit stage folders.  
2. **GIS / site-scale products** (DEMs, orthos, shapefiles, PLYs) that consume the photogrammetry outputs and produce derived deliverables.

A third, secondary workflow handles **drone/GCP aerial capture** (`TARP 2025 Photogrammetry`, `TARP 2024 Photogrammetry -- Backlog`).

---

## The pipeline (most important for UI)

The top-level folder names reveal an explicit processing pipeline. Jobs move physically between these folders as they progress:

To Be Processed  →  To Be Aligned  →  To Overnight  →  Processed  →  To be Uploaded to AIR  →  Uploaded to AIR

                                                          ↓

                                                       Working  (active edits / reprocessing)

- Each stage folder is subdivided into **Trench 11000 through Trench 19000** (nine trenches).  
- Individual jobs inside each trench use a consistent naming convention: `Pgram_Job_###_SU####` or `Pgram_Job_###_SU####-####` for multi-SU jobs (SU \= stratigraphic unit).  
- At scan time the `Processed` folder held \~104 `Pgram_Job` folders (most in Trench 18000 and 19000 — those appear to be the active season). The "To Be" stages were empty of jobs at the time of the snapshot, suggesting the queue had been cleared.  
- `Working` contained 6 jobs, including one with a `- Copy` suffix — suggesting ad-hoc versioning when operators branch off a project.

**Implication for UI:** a kanban-style board with these pipeline stages as columns, trenches as swimlanes or a filter, and Pgram\_Job cards moving through, is the most natural representation. The folder moves are literally the state transitions.

## Project-level structure (what's inside a Pgram\_Job)

A typical processed project (example: `Processed\Trench 16000\Pgram_Job_694_SU16014-16015`) contains around 240+ items:

- A `<JobName>.files\` subdirectory — this is a Metashape project cache.  
- 100–200 source images (`.jpg`, `.tif`, and `.arw` raw files).  
- A `.psx` Metashape project file.  
- Possibly `.zip` archives of intermediate state.

Across all Pgram\_Job projects in `Processed`:

- 19,663 `.jpg` files  
- 8,795 `.tif` files  
- 2,014 `.zip` files  
- 813 `.arw` raw files  
- 63 `.psx` Metashape project files

## The "Trash Trench Data" and "Backup Trench Data" folders

- `Trash Trench Data` (85 GB) — contains items like `PreSU17001-Displaced`, `DebuggedScript1_withoutScaleBarTargets`, `Trench 14000 Reprocess`. Reads as a holding area for problematic/rejected/debug runs.  
- `Backup Trench Data` (23 GB) — presumably snapshots before destructive operations.

**Implication for UI:** there's a clear need for "discard/restore" and "version/snapshot" semantics. These shouldn't be hidden folders users navigate to manually — they should be surfaced as first-class undo/recovery features.

---

## Top folders by size (workflow-relevant only)

| Folder | Size (GB) | Files | Role |
| :---- | ----: | ----: | :---- |
| Processed | 527.6 | 31,357 | Completed photogrammetry projects, by trench |
| GIS\_2025 | 159.5 | 5,425 | Current-season GIS deliverables |
| GIS\_2024 | 133.6 | 1,751 | Prior-season GIS archive |
| Trash Trench Data | 84.8 | 4,328 | Rejected / debug runs |
| TARP 2025 Photogrammetry | 52.2 | 1,137 | Drone/GCP capture, current season |
| AutomateRockMask | 49.0 | 9,573 | Automation code \+ its data (git repo) |
| Working | 36.5 | 1,262 | Active/in-progress jobs |
| TARP 2024 Photogrammetry \-- Backlog | 32.2 | 1,743 | Drone/GCP, prior season |
| Backup Trench Data | 23.4 | 2,326 | Safety copies |
| GetElevations | 14.2 | 854 | DEM extraction utility \+ outputs |
| GIS\_2023 | 5.8 | 1,630 | Older GIS archive |
| Volumetrics\_2025 | 2.9 | 99 | Volume calculation outputs |
| AIR | 0.8 | 2,180 | Code repo for AIR system (git) |
| PGStatus | 0.05 | 6,783 | Pipeline status tracker (git repo) |

## GIS folder structure

`GIS_2025` mirrors a standard archaeological-GIS layout:

- `3D_SU_Shapefiles\`, `DEM\`, `Orthos\`, `PLY\`, `Re-referenced PLYs for AIR\`  
- `SU DEMs\`, `SU_contours\`, `SU_Sheets\`, `SU_Layout_Templates\`  
- `Styles\` (QGIS `.qml` files)  
- `.git\` — version controlled  
- `virtualenv\` — bundled Python env  
- Shapefile triplets (`.shp` / `.shx` / `.dbf` / `.prj` / `.cpg` / `.qmd`) at the root, e.g. `Architecture_2025.*`

## Notable infrastructure folders

- **`PGStatus`** — a git repo that mirrors the pipeline folder names (`Processed`, `To Be Aligned`, `To Be Processed`, `To Overnight`, `Uploaded to AIR`, `Utils`). This appears to be a tracking/status system, possibly a lightweight manifest of what's where. Worth inspecting its git history for workflow history.  
- **`AIR`** — another git repo with its own `virtualenv` and `NXS_conversion` subfolder. Likely the upload/publishing target for finished products. Pipeline ends at "Uploaded to AIR".  
- **`AutomateRockMask`** — git repo with DEMs, orthos, PLYs, shapefiles, templates, plus a `processing/` folder. Automation around rock-mask generation, one of the heavier compute steps.  
- **`GetElevations`**, **`NXS_conversion`**, **`Volumetrics_2025`** — focused utility workflows, each with their own folder.  
- **`SU_tool`**, **`PhotogrammetryUtils`**, **`Utils`** — shared tooling.

## File types by volume

| Extension | Count | Size (GB) | Notes |
| :---- | ----: | ----: | :---- |
| `.jpg` | 28,172 | 222.5 | Primary source photos |
| `.tif` | 12,170 | 383.2 | Orthos, DEMs, processed rasters |
| `.zip` | 3,008 | 451.2 | Archived project state (huge) |
| `.arw` | 815 | 20.7 | Sony raw files |
| `.ply` | 367 | 37.8 | Point clouds / meshes |
| `.png` | 1,155 | 4.5 | Visualizations, masks |
| `.psx` | \~63 | — | Metashape projects |
| `.shp` \+ friends | 586+ | 0.1 | Shapefile sets |
| `.qml`, `.qmd`, `.qgz` | 2,700+ | — | QGIS config / project files |

Plus a large `.py` / `.pyc` footprint (\~14k files combined) from the bundled Python environments and automation scripts.

---

## Naming conventions worth enforcing in the UI

- **Trenches:** `Trench #####` (e.g., `Trench 18000`). Five-digit trench IDs, always zero-padded the same way.  
- **Jobs:** `Pgram_Job_###_SU####` (single SU) or `Pgram_Job_###_SU####-####` (range) or `Pgram_Job_###_SU####, ####, ####` (non-contiguous). *The non-contiguous form uses comma-space.* Inconsistent spacing (`SU190062-63, 19065-66` appears in one name) suggests the UI should generate these canonical strings so operators don't have to.  
- **Drone flights:** `GCP-Drone-Flight-#` under a season-specific TARP folder.  
- **Seasons:** year-suffixed (`GIS_2025`, `Volumetrics_2025`, `TARP 2025 Photogrammetry`, `2025 Bounding Regions`). A season concept is clearly load-bearing.

---

## Recommendations for the UI build

Not prescriptive — just what the folder shape suggests:

1. **Treat "job" as the primary entity.** A job has an ID, an SU list, a trench, a current pipeline stage, a set of source images, a Metashape project file, and a set of outputs. Every view probably drills from "show me jobs" to "show me this job."  
     
2. **Pipeline stages are the dominant state dimension.** The existing folder moves are the state machine. A UI that surfaces stage transitions as buttons/drag actions (and does the folder moves under the hood) would replace a lot of manual file shuffling.  
     
3. **Keep the season as a top-level filter.** GIS, TARP, Bounding Regions, and Volumetrics are all split by year. Season-switching needs to be one click.  
     
4. **Surface the "reprocess / trash / backup" operations explicitly.** Right now they're ad-hoc folder moves (`- Copy` suffixes, `Trash Trench Data` dumping ground). A proper snapshot \+ restore model would prevent the drift.  
     
5. **Read-only views on GIS outputs.** GIS data is derived from photogrammetry outputs — the UI probably shouldn't let users edit shapefiles directly, but should show what was produced downstream from each job.  
     
6. **Don't hide the Metashape `.psx` file.** It's the source of truth for a job. A "Open in Metashape" button on each job card is likely valuable.  
     
7. **PGStatus is probably your starting point, not your replacement target.** It already tracks the workflow in git. The new UI can either read it or supersede it, but understanding what it does first will save duplication.  
     
8. **Expect large-folder performance issues.** Some Pgram\_Job folders have 200+ images; trench folders aggregate dozens of those. File browsers will be slow without virtualized lists.

