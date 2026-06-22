"""Batched, per-job Metashape pipeline runner.

Runs the headless Metashape scripts over every job in a stage, ONE JOB AT A TIME,
and advances each card to the next stage the moment its script succeeds — so a
failure on one job never blocks the others, and the kanban updates live.

Only one run is allowed at a time (single machine, single Metashape / GPU).
The run executes on a daemon thread; the frontend polls get_status() to follow it.
"""

import logging
import subprocess
import threading
from typing import Optional

from backend.config import LOG_PATH, get_config
from backend.models import PgramJob
from backend.services import filesystem, gsheets

logger = logging.getLogger(__name__)

# A "step" applies one script to a job then moves it forward:
#   (script_kind, from_stage, to_stage)
# A run is an ordered list of steps applied per job. "both" chains two steps so a
# single job goes To Be Aligned -> (align) -> To Overnight -> (overnight) -> Processed.
_STEPS: dict[str, list[tuple[str, str, str]]] = {
    "alignment": [("alignment", "to_be_aligned", "to_overnight")],
    "overnight": [("overnight", "to_overnight", "processed")],
    "both": [
        ("alignment", "to_be_aligned", "to_overnight"),
        ("overnight", "to_overnight", "processed"),
    ],
}

_lock = threading.Lock()
# Mutable run state, read by get_status() and mutated by the worker (always under _lock).
_state: dict = {
    "active": False,
    "kind": None,
    "started_at": None,
    "cancel": False,
    "jobs": [],  # list of dicts: job_id, su_string, trench, stage, status, step, error
}


def _log(msg: str) -> None:
    logger.info(msg)
    try:
        with open(LOG_PATH, "a") as f:
            f.write(f"RUN {msg}\n")
    except OSError:
        pass


def get_status() -> dict:
    with _lock:
        return {
            "active": _state["active"],
            "kind": _state["kind"],
            "started_at": _state["started_at"],
            "cancel": _state["cancel"],
            "jobs": [dict(j) for j in _state["jobs"]],
        }


def cancel() -> dict:
    """Request the run to stop after the job currently in progress finishes."""
    with _lock:
        if not _state["active"]:
            return {"cancelled": False, "error": "No run in progress."}
        _state["cancel"] = True
        return {"cancelled": True}


def _validate(kind: str) -> Optional[str]:
    cfg = get_config()
    steps = _STEPS.get(kind)
    if steps is None:
        return f"Unknown run type: {kind}"
    if not cfg.metashape_path or not _exists(cfg.metashape_path):
        return f"Metashape not found at '{cfg.metashape_path}'. Set app_paths.metashape in config.yaml."
    script_kinds = {s[0] for s in steps}
    if "alignment" in script_kinds:
        if not cfg.script_alignment or not _exists(cfg.script_alignment):
            return f"Alignment script not found at '{cfg.script_alignment}'. Set scripts.alignment in config.yaml."
        if not cfg.gcp_csv or "<" in cfg.gcp_csv or not _exists(cfg.gcp_csv):
            return (
                "No GCP CSV configured. Alignment cannot run until the 2026 GCP reference CSV "
                "exists and scripts.gcp_csv is set in config.yaml."
            )
    if "overnight" in script_kinds:
        if not cfg.script_overnight or not _exists(cfg.script_overnight):
            return f"Overnight script not found at '{cfg.script_overnight}'. Set scripts.overnight in config.yaml."
    return None


def _exists(path: str) -> bool:
    from pathlib import Path

    try:
        return Path(path).exists()
    except OSError:
        return False


def start_run(kind: str) -> dict:
    """Validate config, snapshot the jobs in the source stage, and kick off the worker."""
    with _lock:
        if _state["active"]:
            return {"started": False, "error": "A run is already in progress."}

        err = _validate(kind)
        if err:
            return {"started": False, "error": err}

        steps = _STEPS[kind]
        first_from = steps[0][1]
        jobs = [j for j in filesystem.scan_filesystem() if j.stage == first_from]
        if not jobs:
            label = PgramJob.stage_label(first_from)
            return {"started": False, "error": f"No jobs in '{label}' to process."}

        _state["active"] = True
        _state["kind"] = kind
        _state["started_at"] = _now()
        _state["cancel"] = False
        _state["jobs"] = [
            {
                "job_id": j.job_id,
                "su_string": j.su_string,
                "trench": j.trench,
                "stage": j.stage,
                "status": "queued",
                "step": None,
                "error": None,
            }
            for j in jobs
        ]

    thread = threading.Thread(target=_worker, args=(kind, steps, jobs), daemon=True)
    thread.start()
    return {"started": True, "kind": kind, "count": len(jobs)}


def _now() -> str:
    from backend.models import cet_now

    return cet_now()


def _set(job_id: str, **fields) -> None:
    with _lock:
        for j in _state["jobs"]:
            if j["job_id"] == job_id:
                j.update(fields)
                break


def _is_cancelled() -> bool:
    with _lock:
        return _state["cancel"]


def _worker(kind: str, steps: list[tuple[str, str, str]], jobs: list[PgramJob]) -> None:
    _log(f"started '{kind}' over {len(jobs)} job(s)")
    try:
        for job in jobs:
            if _is_cancelled():
                _set(job.job_id, status="cancelled")
                continue

            ok = True
            for (script_kind, from_stage, to_stage) in steps:
                _set(job.job_id, status="running", step=script_kind, stage=from_stage)
                ok, err = _run_script(script_kind, job)
                if not ok:
                    _set(job.job_id, status="failed", error=err)
                    _log(f"{job.job_id} {script_kind} FAILED: {err}")
                    break

                try:
                    filesystem.move_job(job, to_stage)
                except Exception as e:
                    _set(job.job_id, status="failed", error=f"Move to {to_stage} failed: {e}")
                    _log(f"{job.job_id} move to {to_stage} FAILED: {e}")
                    ok = False
                    break

                try:
                    gsheets.update_pgram_stage(job.job_id, to_stage)
                except Exception:
                    pass  # sheet sync is best-effort; the filesystem move is authoritative

                job = PgramJob(**{**job.model_dump(), "stage": to_stage})
                _set(job.job_id, stage=to_stage)

            if ok:
                _set(job.job_id, status="done", step=None)
                _log(f"{job.job_id} done")
    finally:
        with _lock:
            _state["active"] = False
            _state["cancel"] = False
        _log(f"finished '{kind}'")


def _run_script(script_kind: str, job: PgramJob) -> tuple[bool, str]:
    """Invoke Metashape headlessly on this one job's folder. Blocks until it exits."""
    cfg = get_config()
    folder = filesystem.get_job_folder(job)
    if folder is None or not folder.exists():
        return False, "Job folder not found on disk."

    if script_kind == "alignment":
        script = cfg.script_alignment
        args = [str(folder), cfg.gcp_csv]
    else:
        script = cfg.script_overnight
        args = [str(folder), cfg.output_root]

    cmd = [cfg.metashape_path, "-r", script] + args
    _log(f"{job.job_id} launching: {' '.join(cmd)}")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except Exception as e:
        return False, str(e)

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        return False, (detail[-500:] if detail else f"Metashape exited with code {proc.returncode}")
    return True, ""
