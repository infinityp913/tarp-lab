# Changelog

All notable changes to TARP Lab Dashboard are documented here.

## [1.0.1.0] - 2026-06-26

### Fixed
- NA, na, N/A, n/a, and #N/A values in the Field Pgram Tracking sheet's "SUs Opened" and "SUs Closed" columns are now treated as blank. Previously these literal strings would appear as SU badges on pgram cards (e.g., "▲ N/A") and in the detail modal. Boolean cell values from column-insertion accidents in the field sheet are also handled correctly.

## [1.0.0.1] - 2026-06-25

### Added
- Two placeholder script buttons in the Volumes (SU) kanban board, positioned between stages: **Create Volumes** (between Not Started and Volumetrics Created) and **Create SU Sheet** (between Volumetrics Created and SU Sheet Created). Each button shows the count of cards in the preceding stage and can be wired to Python scripts.

### Changed
- Volumetrics Created, SU Sheet Created, and Uploaded to Air columns now have a taller default minimum height (300px vs 120px) so the inter-column script buttons read as sitting between substantial columns rather than floating between stubs.
- Kanban column gap restored to 12px, fixing SU Sheet Created and Uploaded to Air columns sticking together.
