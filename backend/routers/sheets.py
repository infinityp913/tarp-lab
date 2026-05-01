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
    su_rows = get_su_rows()
    su_entries = [
        SUEntry(
            su_id=r["su_id"],
            parent_job_id=r["parent_job_id"],
            trench=r["trench"],
            stage=r["stage"],
            notes=r.get("notes", ""),
            last_updated=r.get("last_updated", ""),
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
    return {
        "available": gsheets.is_available(),
        "has_credentials": CREDENTIALS_PATH.exists(),
        "has_token": TOKEN_PATH.exists(),
        "sheet_url": sheet_url,
    }
