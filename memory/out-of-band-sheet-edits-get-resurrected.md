---
name: out-of-band-sheet-edits-get-resurrected
description: Why direct Google Sheet row deletes/edits get reverted, and the safe procedure to make them stick
metadata:
  type: project
---

Editing Google Sheet rows directly (outside the app) — e.g. deleting an SU volume card row — gets silently reverted within ~5 minutes.

**Why:** The frontend auto-syncs every 300s (`frontend/src/App.tsx` ~L96-98 → POST `/api/sheets/sync`). That endpoint calls `gsheets.full_sync()`, which rewrites EVERY tab from the running server's in-memory SU/pgram cache (`_SU_CACHE_TTL = 300s`). So a direct sheet delete races the cache: the still-running server holds the old rows in cache and the next auto-sync writes them back to the sheet (visible as a fresh "Last Updated" timestamp on all rows).

**How to apply (safe one-off out-of-band edit):**
1. Stop the backend (`python -m backend.main`, default 127.0.0.1:8000) — POST `/api/shutdown` then confirm port 8000 is down. While down, the browser's auto-sync POST just fails harmlessly and cannot resurrect anything.
2. Make the sheet edit (delete rows via Sheets API `deleteDimension` using the tab's real `sheetId` from `spreadsheets().get`).
3. Start the backend fresh — startup `warm_cache` reads the now-clean sheet into cache, so subsequent auto-syncs write the correct state.
4. Hard-refresh the browser (Ctrl+Shift+R) — the UI only reloads SU entries on mount/refresh.

Do NOT just delete + invalidate cache in a separate script process: that only invalidates the script's cache, not the live server's. There is no server endpoint to flush only the SU cache, and `/api/sheets/sync` would resurrect from stale cache. The robust fix would be a real DELETE endpoint (`gsheets.delete_su()` + cache invalidation in-process). See [[no-su-card-delete-feature]].
