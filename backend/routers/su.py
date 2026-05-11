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
