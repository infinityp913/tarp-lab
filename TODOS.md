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
- [ ] Set `scripts.gcp_csv` in `config.yaml` once the 2026 GCP reference CSV exists — alignment/both buttons are blocked until then
- [ ] Confirm the two headless `.py` paths in `config.yaml` `scripts:` match the lab machine, and that `metashape.exe` path is correct
- [ x ] Build + typecheck the frontend on a machine with node (`cd frontend && npm install && npm run build`) and copy `dist/` into `backend/static`
- [ x ] Run the backend test suite (`python -m pytest tests/ -v`) on a machine with pytest installed
- [ ] End-to-end test on the lab machine: run Overnight on a real `To Overnight` job, confirm it advances to `Processed` and exports land in `GIS_2026/`
- [ x ] 0 `.psx` in job folder is now a hard failure — script pre-flight check returns error before launching Metashape
- [ ] Consider surfacing per-job script stdout/errors in the UI (currently logged to `tarp-dashboard.log` only)
