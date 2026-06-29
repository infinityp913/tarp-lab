# Plan: Run SU-sheet, pre-snip, and post-snip scripts independently

## Context
The SU volume pipeline runs four scripts, each tied to a kanban stage and triggered by a
gutter button that calls `backend/services/volume_runner.py::start_run(kind)`:

| Script | Stage move | Status |
|---|---|---|
| pre_snip | `to_be_pre_snipped` → `to_be_snipped` | already independent |
| auto_snip | `to_be_snipped` → `to_be_post_snipped` | **disabled** (unreliable) |
| post_snip | `to_be_post_snipped` → `volumetrics_created` | **coupled to auto_snip** |
| create_su_sheet | `volumetrics_created` → `su_sheet_created` | already independent (QGIS) |

With auto_snip disabled, the lab snips manually in CloudCompare. But `post_snip` still
discovers its inputs only from auto_snip's output convention — it looks in
`Data/<json_id>/*_cleaned_su_*.bin` (json_id is always `"input"`) and raises
*"Auto-snip must run successfully before post-snip"* when it finds nothing. So post_snip
cannot run on its own. **`pre_snip` and `create_su_sheet` are already self-contained**
(each reads its own input file and is gated only by its source stage); the work is almost
entirely in decoupling `post_snip`, plus a one-line runner change and docs.

Decisions (confirmed with user): manual cropping in CloudCompare; post_snip processes
**only the SUs in the current run** (the pairs in `input.json`), not everything on disk.

## Manual-snip file contract
After Pre-Snip, the human uses the existing **"Open in CC"** button (opens the pre_snip
`*_with_dist_*.bin` pair from `Data/<top_id>/`, where `<top_id>` is the full
`Pgram_Job_<top>_SU_<su>_...` PLY stem). They crop top & bottom and **Save As back into the
same folder, appending `_snipped`** to each source name:
- Top crop:    `<top_id>_top_with_dist_for_<bottom_id>_snipped.bin`
- Bottom crop: `<bottom_id>_bottom_with_dist_for_<top_id>_snipped.bin`

Rationale: minimal human effort (open the two surfaced bins, crop, Save As + suffix — no
SU/pgram typing); deterministic for post_snip to resolve from `input.json`; the
`_top_with_dist_`/`_bottom_with_dist_` infix already encodes role; aligns with the existing
`Data/<Pgram_Job_top>...` layout and `find_volume_bins_for_su`.

## Changes

### 1. `backend/services/volume_runner.py` — `_write_input_json` (~line 116-137)
Add `su` to each pair: `{"top": top, "bottom": bot, "su": str(card.get("su_id", ""))}`.
This lets post_snip name `SU_<su>_raw.obj` from the run's exact card su_id (matching
`find_volume_obj_for_su` and create_su_sheet), avoiding fragile stem parsing — important
because the SU token can be a range like `22044-22048`. `pre_snip` reads only `top`/`bottom`
and ignores extra keys, so this is backward-compatible (one-line change).

### 2. `cloudcomparescript/post_snip_script.py` — discovery rework (core change)
Rewrite `run_postsnip_pipeline(json_filepath="input.json")` to be input.json-driven:
1. Load the JSON list (same shape pre_snip reads); per entry read `top`, `bottom`, `su`.
2. Resolve `<top_id>`/`<bottom_id>` from the pgram numbers via the existing
   `pre_snip_script.find_mesh_by_pgram_job(...)`; folder = `Data/<top_id>/`.
3. Glob that folder for the manually-cropped pair:
   `*_top_with_dist_*_snipped.bin` and `*_bottom_with_dist_*_snipped.bin`.
   If multiple (re-crops), pick newest by mtime and log the choice.
4. Feed the pair into the **unchanged** `merge_clouds_and_build_mesh(top, bottom)` and
   downstream Poisson/volume logic; output stays `Data/Final_Volumes/SU_<su>_raw.obj` with
   `top_base_name = <top_id>`.
5. `su_number` from JSON `su` (preferred), fallback to the `_SU_<su>_` token in `<top_id>`.
6. Preserve any existing progress output the runner reads (`progress.json` in the script dir),
   if present.

Repurpose `find_top_bottom_cloud_pairs` to return `(top_path, bottom_path, su)` tuples from
the resolved per-pair folders via the `_snipped` glob. The old `Data/<json_id>/` path and the
`get_job_number_from_filename`/`get_su_number_from_filename` helpers become dead for this flow
(only referenced here) — leave or remove.

**Replace every `_cleaned_su_` site** — the cropped filenames no longer contain that token
(they are `*_with_dist_*_snipped.bin`), so the current string-splitting on `_cleaned_su_`
breaks. Affected:
- `merge_clouds_and_build_mesh` (~lines 191-194): derives `top_base_name`/`bottom_base_name`
  and `su_number` by `split("_cleaned_su_")`. Change its signature to accept `su_number` and
  the base names explicitly (passed in from the resolved `<top_id>`/`<bottom_id>` and JSON
  `su`) instead of re-parsing the path.
- `run_postsnip_pipeline` (~lines 498-499): same `_cleaned_su_` split — replace with the
  resolved values.

Net: `su_number`/base names flow from `input.json` + the resolved PLY stems, and no code path
depends on the `_cleaned_su_` substring anymore.

### 3. `cloudcomparescript/post_snip_script.py` — per-SU resilience
- Remove the hard `RuntimeError("...Auto-snip must run successfully...")` (~lines 491-495).
- Wrap per-pair discovery + processing in try/except: on a missing `_snipped` pair or a
  processing error, print a clear message and `continue` (one un-snipped SU never aborts the
  batch).
- Raise (non-zero exit) **only** in the all-empty case — input pairs existed but zero produced
  output — with manual-workflow guidance: *"No manually-snipped clouds found for any SU in this
  run. Open each SU's pre-snip bins (Open in CC), crop top & bottom, and Save As with a
  `_snipped` suffix in the same `Data/<Pgram_Job_...>` folder before running post-snip."* This
  makes a fully un-snipped batch a visible failure in the dashboard banner (the runner keys off
  the subprocess return code at `volume_runner.py:303`).

### 4. Docs / UI
- `cloudcomparescript/CLAUDE.md` — "Data layout" / "Callable API": document the `_snipped`
  contract and that post_snip is input.json-driven (top/bottom/su), not auto_snip-driven.
- `cloudcomparescript/README.md` — replace the auto_snip prerequisite with the manual
  crop + Save-As step.
- `tarp-lab` `README.md` / `LAB_HOWTO.md` — describe the manual snip step between pre-snip
  and post-snip.
- `frontend/src/components/SUTab.tsx:449` — update the Post-Snip button `title` tooltip to note
  it needs manually-snipped bins; (optional) `SUCard.tsx` "Open in CC" copy could hint
  "crop & Save As `_snipped`".

## Edge cases
- **SU range** (`_SU_22044-22048`): use JSON `su`, not stem parse.
- **Re-crops** (multiple `_snipped` bins): newest-by-mtime wins, logged.
- **pgram with no matching PLY stem** (`find_mesh_by_pgram_job` → None): skip + log.
- **Hand-written input.json without `su`**: stem-parse fallback; if that fails, skip + log.
- **One top, multiple bottoms**: the `_for_<bottom_id>` infix disambiguates within the folder.

## Known limitation (flagged — not in scope)
`volume_runner._worker` advances **all** cards in the source stage on a successful run
(`volume_runner.py:311-322`). So a per-SU skip in post_snip would still advance the skipped
card to `volumetrics_created`. If that's undesirable, a follow-up would have the runner advance
only SUs that produced an OBJ (e.g. via a result manifest / progress.json). Out of scope here.

## Verification (manual, end-to-end)
1. Put an SU's cards in `to_be_pre_snipped`; run **Pre-Snip**; confirm two `*_with_dist_*.bin`
   in `Data/<Pgram_Job_<top>_SU_<su>_...>/`.
2. Click **Open in CC**, crop top & bottom, Save As with `_snipped` in the same folder.
3. Drag the card `to_be_snipped → to_be_post_snipped` (confirmation dialog); run **Post-Snip**.
4. Verify `Data/Final_Volumes/SU_<su>_raw.obj` exists and **Open Volume** works; card is now
   `volumetrics_created`.
5. Run **Create SU Sheet** on that card — confirms create_su_sheet runs independently.
6. Negative: in a multi-SU batch leave one SU un-snipped — confirm it skips with a log line,
   others still produce OBJs; an entirely un-snipped batch fails with the guidance message.
7. Backward-compat: confirm Pre-Snip still works with the new `su`-bearing `input.json`.
8. Backend: `python3 -m pytest tests/ -v` (per CLAUDE.md) after the `_write_input_json` change.
