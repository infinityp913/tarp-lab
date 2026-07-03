import logging

from fastapi import APIRouter, HTTPException

from backend.routers.pgram import _build_job_list
from backend.services import gsheets

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sheets", tags=["sheets"])


@router.post("/sync")
def sync():
    from backend.services.gsheets import get_su_rows
    from backend.models import SUEntry

    if not gsheets.is_available():
        raise HTTPException(status_code=503, detail="Google Sheets is not configured or authentication failed.")

    pgram_jobs = _build_job_list()
    # full_sync CLEARS and rewrites every trench tab from these rows, so a stale or
    # rate-limited (429) read must never drive it — that would overwrite finished
    # cards with an incomplete view. Read strictly (fresh, no stale-cache fallback)
    # and abort the sync on any read failure rather than clobbering good data.
    su_rows = get_su_rows(strict=True)
    if su_rows is None:
        logger.warning("Sync aborted: SU read failed (Sheets unavailable/rate-limited) — not overwriting tabs")
        raise HTTPException(status_code=503, detail="SU read failed — sync skipped to avoid overwriting data")
    su_entries = [
        SUEntry(
            su_id=r["su_id"],
            top_pgram=r.get("top_pgram", ""),
            bot_pgram=r.get("bot_pgram", ""),
            trench=r["trench"],
            stage=r["stage"],
            notes=r.get("notes", ""),
            last_updated=r.get("last_updated", ""),
            # Preserve per-card flags so full_sync round-trips them instead of
            # resetting to defaults (would uncheck "Ready for SU sheet" and clear
            # the auto-snip debug-image flag on every sync).
            snip_method=r.get("snip_method", ""),
            ready_for_sheet=r.get("ready_for_sheet", False),
            flagged=r.get("flagged", False),
        )
        for r in su_rows
        if r.get("su_id")
    ]
    logger.info(f"Sync starting: {len(pgram_jobs)} Pgram jobs, {len(su_entries)} SU entries")
    try:
        gsheets.full_sync(pgram_jobs, su_entries)
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    logger.info("Sync complete — data written to 'Pgram Jobs' and 'SU Tracking' tabs")
    return {"ok": True, "pgram_count": len(pgram_jobs), "su_count": len(su_entries)}


@router.post("/pull")
def pull_field_data():
    """Invalidate the pgram cache and re-read from the Field sheet.
    Returns the number of field records pulled so the frontend can confirm it worked."""
    if not gsheets.is_available():
        raise HTTPException(status_code=503, detail="Google Sheets is not configured or authentication failed.")
    try:
        gsheets.invalidate_pgram_cache()
        rows = gsheets.get_pgram_rows()
        field_count = sum(1 for r in rows if r.get("sus_opened") or r.get("sus_closed") or r.get("notes_from_field"))
        return {"ok": True, "total": len(rows), "with_field_data": field_count}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Pull failed: {e}")


@router.post("/auth")
def reauth():
    """Delete the stale token and re-run the OAuth browser flow on the server machine."""
    from backend.config import CREDENTIALS_PATH
    if not CREDENTIALS_PATH.exists():
        raise HTTPException(status_code=503, detail="credentials.json not found — cannot authenticate.")
    try:
        gsheets.run_auth_flow()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Auth failed: {e}")
    return {"ok": True}


@router.get("/status")
def status():
    from backend.config import CREDENTIALS_PATH, TOKEN_PATH, get_config
    cfg = get_config()
    spreadsheet_id = cfg.gsheets_spreadsheet_id or ""
    sheet_url = (
        f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"
        if spreadsheet_id and spreadsheet_id != "YOUR_SPREADSHEET_ID_HERE"
        else None
    )
    available = gsheets.is_available()
    # Detect expired/revoked token: credentials present but service won't build
    auth_error = CREDENTIALS_PATH.exists() and TOKEN_PATH.exists() and not available
    return {
        "available": available,
        "has_credentials": CREDENTIALS_PATH.exists(),
        "has_token": TOKEN_PATH.exists(),
        "auth_error": auth_error,
        "sheet_url": sheet_url,
    }
