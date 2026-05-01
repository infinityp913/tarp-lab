import logging
import re
import shutil
from pathlib import Path
from typing import Optional

from backend.config import LOG_PATH, get_config
from backend.models import FILESYSTEM_STAGES, PgramJob, utcnow

logger = logging.getLogger(__name__)

# Folder must be Pgram_Job_### or Pgram_Job_###_anything
JOB_PATTERN = re.compile(r"^Pgram_Job_(\d+)(?:_(.+))?$", re.IGNORECASE)


def _log_skip(folder: Path, reason: str):
    msg = f"SKIP folder '{folder.name}': {reason}"
    logger.warning(msg)
    try:
        with open(LOG_PATH, "a") as f:
            f.write(msg + "\n")
    except OSError:
        pass


def _parse_job_dir(job_dir: Path, stage_key: str, trench: str) -> Optional[PgramJob]:
    m = JOB_PATTERN.match(job_dir.name)
    if not m:
        return None
    return PgramJob(
        job_id=f"Pgram_Job_{m.group(1)}",
        su_string=m.group(2) or "",
        trench=trench,
        stage=stage_key,
        last_updated=utcnow(),
    )


def scan_filesystem() -> list[PgramJob]:
    cfg = get_config()
    jobs: list[PgramJob] = []

    for stage_key in ("to_be_processed", "to_be_aligned", "to_overnight", "processed"):
        folder_name = cfg.stage_folders[stage_key]
        stage_root = Path(cfg.base_path) / folder_name

        if not stage_root.exists():
            continue

        for entry in stage_root.iterdir():
            if not entry.is_dir():
                continue

            # Support both layouts:
            # 1. stage_root/Pgram_Job_###  (flat — no trench subdir)
            # 2. stage_root/TrenchName/Pgram_Job_###  (nested — standard)
            if JOB_PATTERN.match(entry.name):
                job = _parse_job_dir(entry, stage_key, trench="")
                if job:
                    jobs.append(job)
            else:
                trench = entry.name
                for job_dir in entry.iterdir():
                    if not job_dir.is_dir():
                        continue
                    job = _parse_job_dir(job_dir, stage_key, trench)
                    if job:
                        jobs.append(job)
                    else:
                        _log_skip(job_dir, "folder name does not match Pgram_Job_### pattern")

    return sorted(jobs, key=lambda j: j.numeric_id, reverse=True)


def _job_path(base: Path, folder_name: str, trench: str, job_id: str, su_string: str) -> Path:
    suffix = f"_{su_string}" if su_string else ""
    if trench:
        p = base / folder_name / trench / f"{job_id}{suffix}"
    else:
        p = base / folder_name / f"{job_id}{suffix}"
    _assert_within_base(p, base)
    return p


def _assert_within_base(path: Path, base: Path) -> None:
    try:
        path.resolve().relative_to(base.resolve())
    except ValueError:
        raise ValueError(f"Path '{path}' escapes base directory '{base}'")


def get_job_folder(job: PgramJob) -> Optional[Path]:
    cfg = get_config()
    if job.stage not in FILESYSTEM_STAGES:
        return None
    folder_name = cfg.stage_folders[job.stage]
    return _job_path(Path(cfg.base_path), folder_name, job.trench, job.job_id, job.su_string)


def move_job(job: PgramJob, target_stage: str) -> Path:
    cfg = get_config()
    src = get_job_folder(job)
    if src is None or not src.exists():
        raise FileNotFoundError(f"Source folder not found: {src}")

    dest_folder_name = cfg.stage_folders[target_stage]
    dest = _job_path(Path(cfg.base_path), dest_folder_name, job.trench, job.job_id, job.su_string)

    if dest.exists():
        raise FileExistsError(
            f"A folder with this name already exists in the target stage. Check for duplicate job IDs."
        )

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dest))
    return dest


def create_job_folder(job_id: str, su_string: str, trench: str) -> Path:
    cfg = get_config()
    base = Path(cfg.base_path)
    folder_name = cfg.stage_folders["to_be_processed"]
    suffix = f"_{su_string}" if su_string else ""
    dest = base / folder_name / trench / f"{job_id}{suffix}"
    _assert_within_base(dest, base)

    if dest.exists():
        raise FileExistsError(f"A folder named '{dest.name}' already exists in To Be Processed.")

    dest.mkdir(parents=True, exist_ok=True)
    return dest


def find_psx_file(job: PgramJob) -> Optional[Path]:
    folder = get_job_folder(job)
    if folder is None or not folder.exists():
        return None
    for psx in folder.glob("*.psx"):
        return psx
    return None
