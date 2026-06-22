from fastapi import APIRouter, HTTPException

from backend.models import (
    FILESYSTEM_STAGES,
    PGRAM_STAGES,
    TRANSITION_DIALOGS,
    BatchMoveRequest,
    CreatePgramJobRequest,
    PgramJob,
    StageTransitionRequest,
    UpdateNotesRequest,
    cet_now,
)
from backend.services import filesystem, gsheets, launcher, runner

router = APIRouter(prefix="/api/pgram", tags=["pgram"])


def _build_job_list() -> list[PgramJob]:
    fs_jobs = filesystem.scan_filesystem()
    fs_ids = {j.job_id for j in fs_jobs}

    # Pull GSheets rows for AIR stages and notes
    sheet_rows = gsheets.get_pgram_rows()
    sheet_by_id = {r["job_id"]: r for r in sheet_rows if r.get("job_id")}

    # Merge: apply lab notes and field-sourced data from sheet
    merged: list[PgramJob] = []
    for job in fs_jobs:
        row = sheet_by_id.get(job.job_id)
        if row:
            job.notes = row.get("notes", "")
            job.notes_from_field = row.get("notes_from_field", "")
            job.sus_opened = row.get("sus_opened", "")
            job.sus_closed = row.get("sus_closed", "")
            job.last_updated = row.get("last_updated", cet_now())
        merged.append(job)

    return sorted(merged, key=lambda j: j.numeric_id, reverse=True)


@router.get("/jobs")
def list_jobs():
    jobs = _build_job_list()
    return [j.model_dump() for j in jobs]


@router.get("/ignored-folders")
def list_ignored_folders():
    return [f.model_dump() for f in filesystem.scan_ignored_folders()]


@router.post("/jobs", status_code=201)
def create_job(req: CreatePgramJobRequest):
    try:
        filesystem.create_job_folder(req.job_id, req.su_string, req.trench)
    except FileExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    job = PgramJob(
        job_id=req.job_id,
        su_string=req.su_string,
        trench=req.trench,
        stage="to_be_processed",
        last_updated=cet_now(),
    )
    try:
        gsheets.upsert_pgram(job)
    except Exception:
        pass  # GSheets failure doesn't block job creation

    return job.model_dump()


@router.put("/jobs/{job_id}/stage")
def update_stage(job_id: str, req: StageTransitionRequest):
    jobs = _build_job_list()
    job = next((j for j in jobs if j.job_id == job_id), None)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    current = job.stage
    target = req.target_stage

    dialog = TRANSITION_DIALOGS.get((current, target))
    if dialog and not req.confirmed:
        return {"requires_confirmation": True, "message": dialog}

    if target in FILESYSTEM_STAGES:
        try:
            filesystem.move_job(job, target)
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except FileExistsError as e:
            raise HTTPException(status_code=409, detail=str(e))
        except OSError as e:
            raise HTTPException(
                status_code=500,
                detail=f"File system error: {e}. Common causes: file locked by Metashape, or insufficient permissions.",
            )
        # Update stage in sheet (non-blocking)
        try:
            gsheets.update_pgram_stage(job_id, target)
        except Exception:
            pass
    else:
        # AIR stages — GSheets only
        try:
            gsheets.update_pgram_stage(job_id, target)
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Google Sheets unavailable: {e}")

    updated = PgramJob(**{**job.model_dump(), "stage": target, "last_updated": cet_now()})
    return updated.model_dump()


@router.put("/jobs/{job_id}/notes")
def update_notes(job_id: str, req: UpdateNotesRequest):
    try:
        gsheets.update_pgram_notes(job_id, req.notes)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"ok": True}


@router.post("/batch-move")
def batch_move(req: BatchMoveRequest):
    """Move every job in from_stage to to_stage (folder moves only — no scripts).
    Backs the 'Move all → To Be Aligned' button. Only one step forward is allowed."""
    try:
        fi = PGRAM_STAGES.index(req.from_stage)
        ti = PGRAM_STAGES.index(req.to_stage)
    except ValueError:
        raise HTTPException(status_code=400, detail="Unknown stage.")
    if ti != fi + 1:
        raise HTTPException(status_code=400, detail="Batch move must advance exactly one stage.")

    jobs = [j for j in filesystem.scan_filesystem() if j.stage == req.from_stage]
    moved: list[str] = []
    failed: list[dict] = []
    for job in jobs:
        try:
            filesystem.move_job(job, req.to_stage)
            try:
                gsheets.update_pgram_stage(job.job_id, req.to_stage)
            except Exception:
                pass
            moved.append(job.job_id)
        except Exception as e:
            failed.append({"job_id": job.job_id, "error": str(e)})
    return {"moved": moved, "failed": failed}


@router.post("/run/{kind}")
def start_run(kind: str):
    """Start a batched, per-job Metashape run (kind: alignment | overnight | both)."""
    if kind not in ("alignment", "overnight", "both"):
        raise HTTPException(status_code=400, detail=f"Unknown run type: {kind}")
    result = runner.start_run(kind)
    if not result.get("started"):
        # 409 when a run is already active, 400/422-ish otherwise — use 409 for the busy case.
        msg = result.get("error", "Failed to start run")
        status = 409 if "already in progress" in msg else 400
        raise HTTPException(status_code=status, detail=msg)
    return result


@router.get("/run/status")
def run_status():
    return runner.get_status()


@router.post("/run/cancel")
def run_cancel():
    result = runner.cancel()
    if not result.get("cancelled"):
        raise HTTPException(status_code=400, detail=result.get("error", "Nothing to cancel"))
    return result


@router.post("/jobs/{job_id}/open/{app}")
def open_app(job_id: str, app: str):
    jobs = _build_job_list()
    job = next((j for j in jobs if j.job_id == job_id), None)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if app == "metashape":
        result = launcher.launch_metashape(job)
    elif app == "cloudcompare":
        result = launcher.launch_cloudcompare(job)
    elif app == "qgis":
        result = launcher.launch_qgis(job)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown app: {app}")

    if not result.get("launched"):
        raise HTTPException(status_code=400, detail=result.get("error", "Launch failed"))

    return result
