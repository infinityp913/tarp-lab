import logging
import re
import shutil
from pathlib import Path
from typing import Optional

from backend.config import LOG_PATH, get_config
from backend.models import FILESYSTEM_STAGES, IgnoredFolder, PgramJob, cet_now

logger = logging.getLogger(__name__)

# Folder must be Pgram_Job_### or Pgram_Job_###_anything
JOB_PATTERN = re.compile(r"^Pgram_Job_(\d+)(?:_(.+))?$", re.IGNORECASE)
_MSI_SUFFIX = "_MOVED_TO_MSI"


def _log_skip(folder: Path, reason: str):
    msg = f"SKIP folder '{folder.name}': {reason}"
    logger.warning(msg)
    try:
        with open(LOG_PATH, "a") as f:
            f.write(msg + "\n")
    except OSError:
        pass


def _parse_job_dir(job_dir: Path, stage_key: str) -> Optional[PgramJob]:
    """
    Parse a job folder name into a PgramJob object. Returns None if the name doesn't match the expected pattern.

    Args:
        job_dir (Path): Path object representing the job directory
        stage_key (str): One of the FILESYSTEM_STAGES keys indicating the stage this job is in

    Returns:
        Optional[PgramJob]: A PgramJob object if parsing is successful, or None if the folder name doesn't match the expected pattern
    """
    # Strip _MOVED_TO_MSI suffix before matching so it doesn't corrupt su_string
    name = job_dir.name
    if name.upper().endswith(_MSI_SUFFIX.upper()):
        name = name[: -len(_MSI_SUFFIX)]
    m = JOB_PATTERN.match(name)
    if not m:
        return None
    su_string = m.group(2) or ""
    # Infer trench from SU number (e.g. SU17001 → Trench 17000), matching field logic.
    # scan_filesystem overrides this with the authoritative filesystem directory name.
    trench = ""
    su_m = re.search(r"SU\s*(\d+)", su_string, re.IGNORECASE)
    if su_m:
        trench = f"Trench {(int(su_m.group(1)) // 1000) * 1000}"
    return PgramJob(
        job_id=f"Pgram_Job_{m.group(1)}",
        su_string=su_string,
        trench=trench,
        stage=stage_key,
        last_updated=cet_now(),
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
                job = _parse_job_dir(entry, stage_key)
                if job:
                    job.trench = ""  # flat layout — no trench directory
                    jobs.append(job)
            else:
                trench = entry.name
                for job_dir in entry.iterdir():
                    if not job_dir.is_dir():
                        continue
                    job = _parse_job_dir(job_dir, stage_key)
                    if job:
                        job.trench = trench  # authoritative: from filesystem dir name
                        jobs.append(job)
                    else:
                        _log_skip(job_dir, "folder name does not match Pgram_Job_### pattern")

    return sorted(jobs, key=lambda j: j.numeric_id, reverse=True)


def scan_ignored_folders() -> list[IgnoredFolder]:
    """Walk every scanned stage directory and collect sub-folders whose names do NOT match
    Pgram_Job_###. These are silently skipped by scan_filesystem(); surfacing them here lets
    the UI warn users about misnamed folders (e.g. 'PreSU17001' instead of 'Pgram_Job_123_SU17001').

    Folders that contain valid job children are treated as containers; only their misnamed
    children are flagged. Empty non-matching folders and known Trench containers are handled
    consistently with scan_filesystem's layout detection.
    """
    cfg = get_config()
    ignored: list[IgnoredFolder] = []

    for stage_key in ("to_be_processed", "to_be_aligned", "to_overnight", "processed"):
        folder_name = cfg.stage_folders[stage_key]
        stage_root = Path(cfg.base_path) / folder_name
        if not stage_root.exists():
            continue

        for entry in sorted(stage_root.iterdir()):
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            if _parse_job_dir(entry, stage_key) is not None:
                continue
            subdirs = [s for s in entry.iterdir() if s.is_dir() and not s.name.startswith(".")]
            has_job_children = any(_parse_job_dir(s, stage_key) is not None for s in subdirs)
            if has_job_children or entry.name.startswith("Trench "):
                for sub in sorted(subdirs):
                    if _parse_job_dir(sub, stage_key) is not None:
                        continue
                    ignored.append(IgnoredFolder(name=sub.name, stage=stage_key, parent=entry.name))
            else:
                ignored.append(IgnoredFolder(name=entry.name, stage=stage_key))

    return ignored


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


def move_to_msi(job: PgramJob) -> Path:
    """Rename the job folder with _MOVED_TO_MSI suffix and move it to a 'Moved to MSI' folder."""
    cfg = get_config()
    src = get_job_folder(job)
    if src is None or not src.exists():
        raise FileNotFoundError(f"Source folder not found: {src}")

    base = Path(cfg.base_path)
    msi_root = base / "Moved to MSI"
    suffix = f"_{job.su_string}" if job.su_string else ""
    dest_name = f"{job.job_id}{suffix}{_MSI_SUFFIX}"
    dest = msi_root / job.trench / dest_name if job.trench else msi_root / dest_name
    _assert_within_base(dest, base)

    if dest.exists():
        raise FileExistsError(f"A folder named '{dest_name}' already exists in Moved to MSI.")

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dest))
    return dest


def scan_subfolders(parent_path: Optional[str] = None) -> list[str]:
    """Return trench subfolder names within base_path (for the Create Job picker)."""
    cfg = get_config()
    base = Path(parent_path) if parent_path else Path(cfg.base_path)
    _assert_within_base(base, Path(cfg.base_path))
    if not base.exists():
        return []
    return sorted(
        entry.name for entry in base.iterdir()
        if entry.is_dir() and not JOB_PATTERN.match(entry.name)
    )
