from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.models import (
    CreateSUEntryRequest,
    SUEntry,
    StageTransitionRequest,
    TRANSITION_DIALOGS,
    UpdateNotesRequest,
    UpdateReadyForSheetRequest,
    UpdateSUPgramsRequest,
    cet_now,
)
from backend.services import gsheets
from backend.services.filesystem import (
    find_ply_for_pgram,
    find_volume_bins_for_su,
    find_post_snip_bin_for_su,
    find_volume_obj_for_su,
    find_top_volume_obj_for_su,
    find_debug_image_for_su,
)
from backend.services.launcher import (
    launch_cloudcompare_with_plys,
    launch_cloudcompare_with_bins,
    launch_meshlab_with_ply,
    open_file_default,
    reveal_in_explorer,
    open_url,
)
from backend.services.volume import annotate_readiness, find_usdz_for_su
from backend.services.volume import provision_from_ply as _provision_from_ply
from backend.services import volume_runner

router = APIRouter(prefix="/api/su", tags=["su"])


@router.get("/entries")
def list_entries():
    rows = gsheets.get_su_rows()
    return annotate_readiness(rows)


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
    """Open the PLY file for this SU's top or bottom pgram model in MeshLab."""
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


@router.post("/entries/{su_id}/open-bins")
def open_bins(su_id: str):
    """Open the two pre-snip .bin files for this SU in CloudCompare (available after pre-snip runs)."""
    rows = gsheets.get_su_rows()
    entry_data = next((r for r in rows if r["su_id"] == su_id), None)
    if not entry_data:
        raise HTTPException(status_code=404, detail=f"SU {su_id} not found")

    top_pgram = str(entry_data.get("top_pgram", ""))
    if not top_pgram.isdigit():
        raise HTTPException(status_code=422, detail="No valid top pgram set for this SU")

    bins = find_volume_bins_for_su(top_pgram, su_id)
    if not bins:
        raise HTTPException(
            status_code=404,
            detail=f"No pre-snip .bin files found for top pgram {top_pgram}. Run pre-snip first.",
        )

    result = launch_cloudcompare_with_bins(bins)
    if not result.get("launched"):
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to open BIN files"))
    return result


@router.post("/entries/{su_id}/open-post-snip-bin")
def open_post_snip_bin(su_id: str):
    """Open the post-snip debug .bin in CloudCompare (available after post-snip runs)."""
    bin_path = find_post_snip_bin_for_su(su_id)
    if not bin_path:
        raise HTTPException(
            status_code=404,
            detail=f"No post-snip .bin found for SU {su_id}. Run post-snip first.",
        )
    result = launch_cloudcompare_with_bins([bin_path])
    if not result.get("launched"):
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to open BIN file"))
    return result


@router.post("/entries/{su_id}/open-volume")
def open_volume(su_id: str):
    """Open the final volume OBJ in the default application (available after post-snip runs)."""
    obj = find_volume_obj_for_su(su_id)
    if not obj:
        raise HTTPException(
            status_code=404,
            detail=f"No volume OBJ found for SU {su_id}. Run post-snip first.",
        )
    result = open_file_default(obj)
    if not result.get("launched"):
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to open volume"))
    return result


@router.post("/entries/{su_id}/open-top-volume")
def open_top_volume(su_id: str):
    """Open the SU top OBJ mesh in the default application (available after post-snip runs)."""
    obj = find_top_volume_obj_for_su(su_id)
    if not obj:
        raise HTTPException(
            status_code=404,
            detail=f"No top OBJ found for SU {su_id}. Run post-snip first.",
        )
    result = open_file_default(obj)
    if not result.get("launched"):
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to open top volume"))
    return result


USDZ_VIEWER_URL = "https://www.usdz-viewer.net/"


@router.post("/entries/{su_id}/open-lidar")
def open_lidar(su_id: str):
    """Reveal the SU's LiDAR USDZ scan in the file browser and open the web viewer.

    Windows has no native .usdz viewer, so we can't open the file directly.
    Instead we highlight it in Explorer (ready to drag into the page) and open
    the usdz-viewer.net viewer the lab uses in the default browser.
    """
    rows = gsheets.get_su_rows()
    if not any(r["su_id"] == su_id for r in rows):
        raise HTTPException(status_code=404, detail=f"SU {su_id} not found")

    scans = find_usdz_for_su(su_id)
    if not scans:
        raise HTTPException(
            status_code=404,
            detail=f"No LiDAR USDZ scan found for SU {su_id} (Synology tharros_syn_2).",
        )

    revealed = reveal_in_explorer(scans[0])
    if not revealed.get("launched"):
        raise HTTPException(status_code=500, detail=revealed.get("error", "Failed to reveal LiDAR scan"))
    open_url(USDZ_VIEWER_URL)  # best-effort; revealing the file is the essential step
    return {"launched": True, "path": str(scans[0]), "count": len(scans), "viewer": USDZ_VIEWER_URL}


@router.get("/entries/{su_id}/debug-image-exists")
def debug_image_exists(su_id: str):
    """Check whether a debug image from auto-snip exists for this SU."""
    rows = gsheets.get_su_rows()
    entry_data = next((r for r in rows if r["su_id"] == su_id), None)
    if not entry_data:
        raise HTTPException(status_code=404, detail=f"SU {su_id} not found")

    top_pgram = str(entry_data.get("top_pgram", ""))
    img = find_debug_image_for_su(su_id, top_pgram) if top_pgram.isdigit() else None
    return {"exists": img is not None, "path": str(img) if img else None}


@router.post("/entries/{su_id}/open-debug-image")
def open_debug_image(su_id: str):
    """Open the auto-snip debug image in the default image viewer."""
    rows = gsheets.get_su_rows()
    entry_data = next((r for r in rows if r["su_id"] == su_id), None)
    if not entry_data:
        raise HTTPException(status_code=404, detail=f"SU {su_id} not found")

    top_pgram = str(entry_data.get("top_pgram", ""))
    img = find_debug_image_for_su(su_id, top_pgram) if top_pgram.isdigit() else None
    if not img:
        raise HTTPException(
            status_code=404,
            detail=f"No debug image found for SU {su_id}. Auto-snip may not have run for this SU.",
        )
    result = open_file_default(img)
    if not result.get("launched"):
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to open debug image"))
    return result


@router.put("/entries/{su_id}/stage")
def update_stage(su_id: str, req: StageTransitionRequest):
    # Check if this transition requires confirmation
    rows = gsheets.get_su_rows()
    entry_data = next((r for r in rows if r["su_id"] == su_id), None)
    if entry_data:
        current = entry_data.get("stage", "")
        dialog = TRANSITION_DIALOGS.get((current, req.target_stage))
        if dialog and not req.confirmed:
            return {"requires_confirmation": True, "message": dialog}

    # Clear snip_method when the card returns to to_be_snipped — signals a new snip cycle
    snip_method = "" if req.target_stage == "to_be_snipped" else None
    try:
        gsheets.update_su_stage(su_id, req.target_stage, snip_method=snip_method)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"ok": True, "su_id": su_id, "stage": req.target_stage}


@router.post("/batch-move-to-pre-snip")
def batch_move_to_pre_snip():
    """Move all ready 'not_started' cards to 'to_be_pre_snipped'."""
    rows = gsheets.get_su_rows()
    annotated = annotate_readiness(rows)
    to_move = [r for r in annotated if r.get("stage") == "not_started" and r.get("ready")]
    if not to_move:
        return {"moved": 0, "skipped": 0, "detail": "No ready cards in 'Not Started'."}
    moved, skipped = 0, 0
    for row in to_move:
        try:
            gsheets.update_su_stage(row["su_id"], "to_be_pre_snipped")
            moved += 1
        except Exception:
            skipped += 1
    return {"moved": moved, "skipped": skipped}




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


@router.put("/entries/{su_id}/ready-for-sheet")
def update_ready_for_sheet(su_id: str, req: UpdateReadyForSheetRequest):
    """Toggle whether this Volume Created card is included in Create SU Sheet runs."""
    try:
        gsheets.update_su_ready_for_sheet(su_id, req.ready)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"ok": True, "ready_for_sheet": req.ready}


# NOTE: static routes (/run/status, /run/cancel, /run/chain) MUST precede dynamic /run/{kind}
@router.get("/run/status")
def volume_run_status():
    return volume_runner.get_status()


@router.post("/run/cancel")
def volume_run_cancel():
    result = volume_runner.cancel()
    if not result.get("cancelled"):
        raise HTTPException(status_code=400, detail=result.get("error", "Cannot cancel"))
    return result


@router.post("/run/chain")
def start_chain_run():
    """Run the full pipeline chain: batch-move ready cards → pre_snip → auto_snip → post_snip → su_sheet_created."""
    result = volume_runner.start_chain_run()
    if not result.get("started"):
        msg = result.get("error", "Failed to start chain run")
        status = 409 if "already in progress" in msg else 400
        raise HTTPException(status_code=status, detail=msg)
    return result


@router.post("/run/{kind}")
def start_volume_run(kind: str, su_id: Optional[str] = None):
    """Start a volume script run (kind: pre_snip | auto_snip | post_snip | create_su_sheet).

    Pass ?su_id=<id> to run the script on just that one card (must be in the
    step's source stage) instead of the whole stage — used to test a single SU.
    """
    if kind not in ("pre_snip", "auto_snip", "post_snip", "create_su_sheet"):
        raise HTTPException(status_code=400, detail=f"Unknown volume run type: {kind}")
    result = volume_runner.start_run(kind, su_id=su_id)
    if not result.get("started"):
        msg = result.get("error", "Failed to start run")
        status = 409 if "already in progress" in msg else 400
        raise HTTPException(status_code=status, detail=msg)
    return result
