from fastapi import APIRouter, HTTPException

from backend.models import (
    CreateSUEntryRequest,
    SUEntry,
    StageTransitionRequest,
    UpdateNotesRequest,
    UpdateSUPgramsRequest,
    cet_now,
)
from backend.services import gsheets
from backend.services.filesystem import find_ply_for_pgram
from backend.services.launcher import (
    launch_cloudcompare_with_plys,
    launch_meshlab_with_ply,
)
from backend.services.volume import provision_from_ply as _provision_from_ply

router = APIRouter(prefix="/api/su", tags=["su"])


@router.get("/entries")
def list_entries():
    rows = gsheets.get_su_rows()
    return rows


@router.post("/entries", status_code=201)
def create_entry(req: CreateSUEntryRequest):
    entry = SUEntry(
        su_id=req.su_id,
        top_pgram=req.top_pgram,
        bot_pgram=req.bot_pgram,
        trench=req.trench,
        stage="not_started",
        last_updated=cet_now(),
    )
    try:
        gsheets.upsert_su(entry)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Google Sheets unavailable: {e}")
    return entry.model_dump()


@router.post("/provision-from-ply")
def provision_from_ply():
    """Scan PLY directory and auto-create volume cards for SUs without one."""
    return _provision_from_ply()


def _resolve_su_ply(su_id: str, pgram_type: str):
    """Return the resolved PLY Path for an SU's top/bot pgram, raising HTTPException on any miss."""
    rows = gsheets.get_su_rows()
    entry_data = next((r for r in rows if r["su_id"] == su_id), None)
    if not entry_data:
        raise HTTPException(status_code=404, detail=f"SU {su_id} not found")

    pgram_val = str(entry_data.get("top_pgram" if pgram_type == "top" else "bot_pgram", ""))
    if not pgram_val.isdigit():
        raise HTTPException(status_code=422, detail=f"No valid {pgram_type} pgram set for this SU")

    ply_path = find_ply_for_pgram(int(pgram_val))
    if not ply_path:
        raise HTTPException(status_code=404, detail=f"No PLY file found for pgram {pgram_val}")
    return ply_path


@router.post("/entries/{su_id}/open-ply/{pgram_type}")
def open_ply(su_id: str, pgram_type: str):
    """Open the PLY file for this SU's top or bottom pgram model in MeshLab.

    pgram_type must be "top" or "bot".
    """
    if pgram_type not in ("top", "bot"):
        raise HTTPException(status_code=422, detail="pgram_type must be 'top' or 'bot'")

    ply_path = _resolve_su_ply(su_id, pgram_type)

    result = launch_meshlab_with_ply(ply_path)
    if not result.get("launched"):
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to open PLY"))
    return result


@router.post("/entries/{su_id}/open-both-ply")
def open_both_ply(su_id: str):
    """Open both the top and bottom PLY files for this SU together in CloudCompare."""
    top_path = _resolve_su_ply(su_id, "top")
    bot_path = _resolve_su_ply(su_id, "bot")

    result = launch_cloudcompare_with_plys([top_path, bot_path])
    if not result.get("launched"):
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to open PLYs"))
    return result


@router.put("/entries/{su_id}/stage")
def update_stage(su_id: str, req: StageTransitionRequest):
    try:
        gsheets.update_su_stage(su_id, req.target_stage)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"ok": True, "su_id": su_id, "stage": req.target_stage}


@router.put("/entries/{su_id}/pgrams")
def update_pgrams(su_id: str, req: UpdateSUPgramsRequest):
    try:
        gsheets.update_su_pgrams(su_id, req.top_pgram, req.bot_pgram)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"ok": True}


@router.put("/entries/{su_id}/notes")
def update_notes(su_id: str, req: UpdateNotesRequest):
    try:
        gsheets.update_su_notes(su_id, req.notes)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"ok": True}
