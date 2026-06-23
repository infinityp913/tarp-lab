# TARP Lab Dashboard — TODOs

## Repo Split
- [ x ] Rename current repo to `tarp-lab` on GitHub (manual step)
- [ x ] Push `tarp-field` repo to GitHub (manual step — repo scaffolded at `/Users/ananth/projects/tarp-field`)

## Script Run Buttons (feat/add-script-run-button)
Done:
- [ x ] Verified headless Metashape scripts are byte-for-byte identical to originals (processing logic) — safe to wire to buttons
- [ x ] Drag dialog now says "move only, does not run script" and uses real folder names ("To Overnight" / "Processed")
- [ x ] Backend runner: batched, per-job sequential Metashape runs with live advancement + failure isolation + cancel
- [ x ] Endpoints: `POST /run/{alignment|overnight|both}`, `GET /run/status`, `POST /run/cancel`, `POST /batch-move`
- [ x ] Between-column action gutters + live progress banner; per-card → arrow + run-status badge

Next steps:
- [ x ] Set `scripts.gcp_csv` in `config.yaml` once the 2026 GCP reference CSV exists — alignment/both buttons are blocked until then
- [ x ] Confirm the two headless `.py` paths in `config.yaml` `scripts:` match the lab machine, and that `metashape.exe` path is correct
- [ x ] Build + typecheck the frontend on a machine with node (`cd frontend && npm install && npm run build`) and copy `dist/` into `backend/static`
- [ x ] Run the backend test suite (`python -m pytest tests/ -v`) on a machine with pytest installed
- [ x ] End-to-end test on the lab machine: run Overnight on a real `To Overnight` job, confirm it advances to `Processed` and exports land in `GIS_2026/`
- [ x ] 0 `.psx` in job folder is now a hard failure — script pre-flight check returns error before launching Metashape
- [ ] Consider surfacing per-job script stdout/errors in the UI (currently logged to `tarp-dashboard.log` only)

## Pgram-to-Volume Card Automation (feat/pgram-to-volume-card-automation)
Done:
- [ x ] `scan_ply_files` / `find_ply_for_pgram` in `filesystem.py` — scans `overnight_output_assets_root/PLY/`
- [ x ] `provision_from_ply` service in `backend/services/volume.py` — idempotent, reads field pgram map, expands SU ranges, sets top/bot pgram
- [ x ] Auto-trigger in `runner._worker` only (after overnight script exits, PLY guaranteed on disk)
- [ x ] Manual "Scan PLY" button in SU tab as fallback / for drag-and-drop promoted cards
- [ x ] "Top PLY" / "Bot PLY" buttons on SUCard and SUDetailModal — open PLY in CloudCompare
- [ x ] `output_root` → `overnight_output_assets_root` renamed in config.yaml + all backend references

Testing needed (on lab machine):
- [ ] Run overnight script on a real job via the Run Overnight button; confirm volume cards are auto-created in "Not Started" after the job lands in Processed
- [ ] Verify `top_pgram` = pgram that opened each SU (from Field Tracking "SUs Opened" column)
- [ ] Verify `bot_pgram` = highest pgram in which each SU appears in any `sus_closed` column across all field pgram rows
- [ ] Verify compact SU range notation (e.g. `21015-17`) expands correctly to individual cards
- [ ] Confirm "Top PLY" button opens the correct PLY file in CloudCompare
- [ ] Confirm "Bot PLY" button opens the correct PLY file in CloudCompare (if a closing pgram exists)
- [ ] Click "Scan PLY" manually on a card already in Processed — confirm it is idempotent (no duplicates created)
- [ ] Confirm `overnight_output_assets_root` path in `config.yaml` matches the lab machine GIS_2026 directory
