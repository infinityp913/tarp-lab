# Changelog

All notable changes to TARP Lab Dashboard are documented here.

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
