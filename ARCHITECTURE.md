# TARP Lab — Architecture

## Stack

| Layer | Technology |
|---|---|
| Backend | Python, FastAPI, uvicorn |
| Frontend | React 18, TypeScript, Vite, dnd-kit |
| Persistence | Filesystem (stage folders) + Google Sheets |
| Packaging | Single process — FastAPI serves both API and built frontend |

---

## How one port serves everything (production)

In production, there is only **one process on port 8000**.

FastAPI handles every incoming request by matching its URL:

- `/api/*` → Python route handlers (business logic, filesystem ops, Sheets writes)
- Anything else → serves `backend/static/index.html`

`backend/static/` is the output of `npm run build`. Vite compiles all the React source into a handful of plain HTML/JS/CSS files and drops them there. FastAPI treats them like any other static file — it just sends bytes to the browser.

The browser loads `index.html`, which loads the compiled JS bundle, which boots React. When React needs data it makes fetch calls to `/api/*` — same host, same port, no cross-origin issues.

```
Browser
  │
  └─► FastAPI :8000
          ├─ /api/pgram/jobs    → filesystem scan + Sheets merge
          ├─ /api/su/entries    → Sheets read
          ├─ /api/sheets/sync   → full_sync()
          └─ /*                 → backend/static/index.html (React app)
```

---

## Why there are two ports in development

`npm run build` is slow and produces a non-debuggable minified bundle — you don't want to run it after every edit.

**Vite** is a development-only tool that solves this. It runs a second server on **port 5173** that:

1. Serves your React source files directly with **hot module replacement** — edit a `.tsx` file and the browser updates in under a second, no full page reload
2. **Proxies `/api/*` to port 8000** — so the React app at 5173 can reach FastAPI transparently, as if they were the same server

You open **5173** in the browser during development. Port 8000 still needs to be running (it's the API), but you never open it directly.

```
Development

Browser :5173
  │
  └─► Vite dev server :5173
          ├─ *.tsx, *.ts, *.css  → served from source with hot reload
          └─ /api/*              → proxied to FastAPI :8000
                                        │
                                        └─► FastAPI :8000 (API only)
```

In production there is no Vite process — the browser talks directly to FastAPI on 8000 for everything.

---

## Development vs production summary

| | Development | Production (Windows) |
|---|---|---|
| Start command | `python3 -m backend.main --dev` + `npm run dev` | `start.bat` (`python -m backend.main`) |
| Backend port | 8000 | 8000 |
| Frontend served by | Vite :5173 | FastAPI :8000 (built bundle) |
| Open in browser | http://127.0.0.1:5173 | http://127.0.0.1:8000 |
| Hot reload | Yes (Vite) | No |
| Rebuild needed | No | Yes — `npm run build` after frontend changes |

---

## Filesystem model

Jobs live as folders on disk inside stage directories:

```
base_path/
├── To Be Processed/
│   └── Pgram_Job_696_SU16014/
├── To Be Aligned/
├── To Overnight/
├── Processed/
└── Uploaded to AIR/
```

Dragging a card to a new column **physically moves the folder** on disk. The board is reconstructed by scanning the filesystem on every `/api/pgram/jobs` request — the filesystem is the source of truth for stage.

`dev_base_path` in `config.yaml` points to a local test folder on Mac; `base_path` is the Windows path used in production.

### Folder naming

Folders must match `Pgram_Job_###` or `Pgram_Job_###_<anything>`. The `_MOVED_TO_MSI` suffix (added by the Field machine) is stripped before parsing so it never corrupts the SU string.

---

## Google Sheets model

Sheets is the **sync ledger** between the Lab machine and the Field machine. It is not the primary database — the filesystem is.

### Lab → Sheets (`full_sync`)

Triggered manually (Sync button) or automatically every 5 minutes.

1. Sleeps a random 0–3 s jitter to reduce the chance of a simultaneous Field sync collision
2. Writes the full current state to `Pgram Jobs_Staging` and `SU Tracking_Staging` tabs
3. Clears the live tabs and does a single `batchUpdate copyPaste` from staging to live

The staging pattern minimises the window where the live tab is empty to roughly one API round-trip.

### Field → Sheets (targeted upsert)

The Field machine uses `upsert_pgram()` per job — a targeted row write. It never calls `full_sync` because it does not have SU data; a full sync would blank the SU Tracking sheet.

### Read cache

Sheets reads are cached in-process for 30 seconds. On any read failure, the stale cache is returned and a warning is logged — the UI never blanks out because of a Sheets timeout.

### Race condition

Two machines can call `full_sync` within the same minute. Jitter reduces but does not eliminate overlap. If overlap occurs, the second writer wins. This is acceptable: both machines derive state from their local filesystem; the only manually-entered field is `SUs Closed`, which is preserved by read-before-write.

---

## Request flow — drag a card

```
User drags Pgram_Job_696 from "To Be Aligned" to "To Overnight"
  │
  ├─ React: optimistic UI update (card moves instantly)
  │
  └─► PUT /api/pgram/jobs/Pgram_Job_696/stage  { target_stage: "to_overnight" }
          │
          ├─ Confirmation dialog check (TRANSITION_DIALOGS)
          ├─ filesystem.move_job()  → renames folder on disk
          ├─ gsheets.upsert_pgram() → updates row in Sheets
          └─ Returns updated PgramJob
                │
                └─ React: replaces optimistic state with server response
```

---

## Key files

| File | Purpose |
|---|---|
| `backend/main.py` | FastAPI app, static file serving, startup hooks |
| `backend/config.py` | Reads `config.yaml`, resolves paths |
| `backend/models.py` | Pydantic models, `cet_now()`, stage constants |
| `backend/services/filesystem.py` | Scan, move, create job folders |
| `backend/services/gsheets.py` | Auth, read/write, cache, `full_sync` |
| `backend/routers/pgram.py` | Pgram job endpoints |
| `backend/routers/su.py` | SU entry endpoints |
| `backend/routers/sheets.py` | Manual sync endpoint |
| `frontend/src/tokens.ts` | Dark mode colour palette |
| `frontend/src/App.tsx` | Root component, tabs, auto-sync pill |
| `frontend/vite.config.ts` | Dev proxy (:5173 → :8000), build output path |
| `config.yaml` | Base paths, stage folder names, Sheets ID, host/port |
