# Changelog

All notable changes to TARP Lab Dashboard are documented here.

## [1.0.4.0] - 2026-06-30

### Changed
- Post-snip now reads a **single combined bin per SU** instead of the two-file `_top_`/`_bottom_` pair. The operator crops top and bottom in CloudCompare and saves **both** clouds into one project bin named `<su>.bin` (flexible: `<su>.bin`, `SU<su>.bin`, any case) in `Data/SU<su>/`. Post-snip identifies which cloud is top vs bottom by the `Pgram_Job_<n>` number embedded in each cloud's name, matched against `top`/`bottom` in `input.json` (with name-marker and order fallbacks). The two-file detection path is removed; post-snip no longer needs the source PLYs present.

### Fixed
- Post-snip crashed on the lab's CloudComPy 3.12 build: `ccScalarField.toNpArray()` does not exist there — switched the C2C filter and density trim to `toNpArrayCopy()`.
- Post-snip aborted on Windows when log lines contained the `→` character (cp1252 console can't encode it); replaced with `->` and added a stdout/stderr guard so stray Unicode no longer kills a run.
- The merged volume OBJ was never written because `Data/Final_Volumes/` didn't exist and `cc.SaveMesh` fails silently into a missing directory — post-snip now creates output directories first. This is the file the dashboard uses to detect post-snip completion (`Volume ↗`).
- `volume_measures.txt` rows are keyed and matched as `SU<su>` consistently, so re-running an SU updates its row in place instead of appending a duplicate.

## [1.0.3.0] - 2026-06-30

### Changed
- Pre-snip now writes **one `.bin` pair per SU**, in its own `Data/SU<su>/` folder (replacing the per-top-pgram folder), so each SU's working files are isolated and self-describing. Filenames still carry the full top/bottom pgram stems.
- Manual crop no longer needs a `_snipped` rename: open the SU's bins, crop, and **save over the same files**. Post-snip resolves each SU's pair from its `Data/SU<su>/` folder, and the `to_be_post_snipped` stage move is the "snipping done" signal.
- **Open in CC ↗** now opens only the selected SU's two bins (from `Data/SU<su>/`) instead of every dist bin in the top folder.

## [1.0.2.0] - 2026-06-29

### Changed
- Post-Snip script now runs independently without requiring auto-snip. After running Pre-Snip, open the two `.bin` files in CloudCompare via the **Open in CC ↗** button, crop top and bottom to the SU boundary, and Save As each with a `_snipped` suffix in the same folder. Click **Post-Snip** to process all manually-snipped pairs.
- SU ID (`su_id`) is now written into `input.json` alongside the pgram pair numbers. Post-snip uses this to name `SU_<su>_raw.obj` correctly, including SU ranges like `22044-22048`, without fragile stem parsing.
- Post-Snip skips individual un-snipped SUs rather than aborting the whole batch. Only a fully un-snipped batch (no output at all) is treated as a failure.
- Post-Snip button tooltip updated to note that manually-snipped bins are required before running.

### Added
- 4 tests for `_write_input_json` covering the `su` field, missing `su_id` fallback, invalid pgram filtering, and SU range preservation.

## [1.0.1.0] - 2026-06-26

### Fixed
- NA, na, N/A, n/a, and #N/A values in the Field Pgram Tracking sheet's "SUs Opened" and "SUs Closed" columns are now treated as blank. Previously these literal strings would appear as SU badges on pgram cards (e.g., "▲ N/A") and in the detail modal. Boolean cell values from column-insertion accidents in the field sheet are also handled correctly.

## [1.0.0.1] - 2026-06-25

### Added
- Two placeholder script buttons in the Volumes (SU) kanban board, positioned between stages: **Create Volumes** (between Not Started and Volumetrics Created) and **Create SU Sheet** (between Volumetrics Created and SU Sheet Created). Each button shows the count of cards in the preceding stage and can be wired to Python scripts.

### Changed
- Volumetrics Created, SU Sheet Created, and Uploaded to Air columns now have a taller default minimum height (300px vs 120px) so the inter-column script buttons read as sitting between substantial columns rather than floating between stubs.
- Kanban column gap restored to 12px, fixing SU Sheet Created and Uploaded to Air columns sticking together.
