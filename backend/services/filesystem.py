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
# Matches a trench container folder, e.g. "Trench 20000".
TRENCH_PATTERN = re.compile(r"^Trench\s+(\d+)$", re.IGNORECASE)
_MSI_SUFFIX = "_MOVED_TO_MSI"

# Filesystem stages scanned for jobs, in board order. Shared by scan_filesystem,
# scan_ignored_folders, and fix_su_folder_names so they stay in lockstep.
_SCAN_STAGES = ("to_be_processed", "to_be_aligned", "to_overnight", "processed", "uploaded_air")


def _trench_number(name: str) -> Optional[int]:
    """Return the numeric trench id for a 'Trench NNNNN' folder, or None if it isn't one."""
    m = TRENCH_PATTERN.match(name.strip())
    return int(m.group(1)) if m else None


def _is_current_year_trench(name: str) -> bool:
    """True if `name` is a 'Trench NNNNN' folder within the configured current-year range.

    Out-of-range (e.g. pre-2026) trenches and non-trench folders return False, so they are
    excluded from job scanning, the run buttons, and the misnamed-folder warning alike.
    """
    num = _trench_number(name)
    if num is None:
        return False
    lo, hi = get_config().current_year_trenches
    return lo <= num <= hi


def _log_skip(folder: Path, reason: str):
    msg = f"SKIP folder '{folder.name}': {reason}"
    logger.warning(msg)
    try:
        with open(LOG_PATH, "a") as f:
            f.write(msg + "\n")
    except OSError:
        pass


def _parse_job_dir(job_dir: Path, stage_key: str) -> Optional[PgramJob]:
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

    for stage_key in _SCAN_STAGES:
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
                # Only scan current-year trench subfolders; ignore pre-2026 / out-of-range
                # trenches and loose non-trench folders entirely.
                if not _is_current_year_trench(trench):
                    continue
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
    """Collect misnamed folders that live INSIDE a current-year trench subfolder.

    Only folders nested within a "Trench NNNNN" container whose number falls in the
    configured current-year range (config.yaml `current_year_trenches`) are checked.
    A child folder is flagged when its name does not match Pgram_Job_### — surfacing
    it lets the UI warn users to rename it (e.g. 'PreSU20001' → 'Pgram_Job_123_SU20001').

    Anything at the stage-root / trench level — loose folders like '__pycache__' or
    'Pre-2026', and out-of-range trenches like 'Trench 19000' — is ignored entirely.
    """
    cfg = get_config()
    ignored: list[IgnoredFolder] = []

    for stage_key in _SCAN_STAGES:
        folder_name = cfg.stage_folders[stage_key]
        stage_root = Path(cfg.base_path) / folder_name
        if not stage_root.exists():
            continue

        for entry in sorted(stage_root.iterdir()):
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            if not _is_current_year_trench(entry.name):
                continue  # not a current-year trench container → ignore this level entirely

            for sub in sorted(entry.iterdir()):
                if not sub.is_dir() or sub.name.startswith("."):
                    continue
                if _parse_job_dir(sub, stage_key) is not None:
                    continue
                ignored.append(IgnoredFolder(name=sub.name, stage=stage_key, parent=entry.name))

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


PLY_JOB_PATTERN = re.compile(r"^Pgram_Job_(\d+)", re.IGNORECASE)


def scan_ply_files() -> list[dict]:
    """Scan {overnight_output_assets_root}/PLY/ for PLY files named Pgram_Job_NNN*.ply.

    Returns list of dicts with keys: pgram_num (int), filename (str), path (str).
    """
    cfg = get_config()
    ply_dir = Path(cfg.overnight_output_assets_root) / "PLY"
    if not ply_dir.exists():
        return []
    results = []
    for f in ply_dir.iterdir():
        if not f.is_file() or f.suffix.lower() != ".ply":
            continue
        m = PLY_JOB_PATTERN.match(f.stem)
        if not m:
            continue
        results.append({"pgram_num": int(m.group(1)), "filename": f.name, "path": str(f)})
    return results


def find_ply_for_pgram(pgram_num: int) -> Optional[Path]:
    """Return the first PLY file in {overnight_output_assets_root}/PLY/ whose name starts with Pgram_Job_{pgram_num}."""
    cfg = get_config()
    ply_dir = Path(cfg.overnight_output_assets_root) / "PLY"
    if not ply_dir.exists():
        return None
    prefix_pattern = re.compile(rf"^Pgram_Job_{pgram_num}", re.IGNORECASE)
    for f in ply_dir.iterdir():
        if f.is_file() and f.suffix.lower() == ".ply" and prefix_pattern.match(f.stem):
            return f
    return None


# A folder suffix that is purely an SU number / range / list (no 'SU' prefix),
# e.g. "21015", "21015-17", "21015, 21016". Underscores or letters → not a bare SU.
_BARE_SU_PATTERN = re.compile(r"^\d[\d\s,\-]*$")
# A suffix that is already SU-tagged, e.g. "SU21015" or "su 21015".
_TAGGED_SU_PATTERN = re.compile(r"^SU\s*\d", re.IGNORECASE)


def _su_suffix(value: str) -> str:
    """Build an 'SU####' folder suffix from a raw SU value.

    Collapses comma/whitespace separators to underscores so the result is a clean,
    filesystem-safe single token: "21015, 21016" → "SU21015_21016", "21015-17" → "SU21015-17".
    """
    cleaned = re.sub(r"[,\s]+", "_", value.strip())
    return f"SU{cleaned}"


def _iter_stage_job_dirs() -> list[tuple[Path, Path]]:
    """Return (job_folder, stage_root) for every Pgram_Job_### folder across all filesystem
    stages (flat + nested layouts). stage_root is carried so callers can tell whether a
    folder is flat (folder.parent == stage_root) or already nested under a trench."""
    cfg = get_config()
    results: list[tuple[Path, Path]] = []
    for stage_key in _SCAN_STAGES:
        stage_root = Path(cfg.base_path) / cfg.stage_folders[stage_key]
        if not stage_root.exists():
            continue
        for entry in stage_root.iterdir():
            if not entry.is_dir():
                continue
            if JOB_PATTERN.match(entry.name):
                results.append((entry, stage_root))  # flat layout
            elif _is_current_year_trench(entry.name):
                for child in entry.iterdir():
                    if child.is_dir() and JOB_PATTERN.match(child.name):
                        results.append((child, stage_root))
    return results


def _organize_into_trench(folder: Path, stage_root: Path, skipped: list[dict]) -> Optional[dict]:
    """Move a flat (un-nested) job folder into its inferred 'Trench NNNNN' subfolder.

    A folder is 'organized' only when it sits directly under `stage_root` (flat layout)
    and its SU number infers a current-year trench. Folders already inside a trench
    subfolder, or whose trench can't be determined / is out of range, are left in place.
    Creates the trench subfolder if it doesn't exist. Returns an entry on move, else None.
    """
    if folder.parent != stage_root:
        return None  # already nested under a trench subfolder
    job = _parse_job_dir(folder, "to_be_processed")  # reuse SU→trench inference
    trench = job.trench if job else ""
    if not trench or not _is_current_year_trench(trench):
        return None  # no determinable current-year trench → leave flat
    dest = stage_root / trench / folder.name
    _assert_within_base(dest, Path(get_config().base_path))
    if dest.exists():
        skipped.append({"name": folder.name, "reason": f"already exists under {trench}"})
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.move(str(folder), str(dest))
    except OSError as e:
        skipped.append({"name": folder.name, "reason": str(e)})
        return None
    return {"name": folder.name, "trench": trench}


def fix_su_folder_names(field_map: dict[str, dict]) -> dict:
    """Normalize Pgram job folders across all stages: SU-tag the name, then file it under
    the right trench subfolder.

    Step 1 — SU-tag the folder name. Two cases are corrected:
      A. Bare SU-number suffix (no 'SU' prefix), e.g. 'Pgram_Job_696_21015'
         → 'Pgram_Job_696_SU21015'  (reformat in place — no sheet lookup)
      B. No SU suffix at all, e.g. 'Pgram_Job_696'
         → look up the pgram in `field_map['696']['sus_opened']` (TARP Field Pgram
           Tracking) and append it, e.g. → 'Pgram_Job_696_SU21015-17'
    Folders already SU-tagged, or with an unrecognized non-numeric suffix (e.g. '..._redo'),
    keep their name.

    Step 2 — organize. Any job folder sitting flat directly under a stage folder (e.g.
    'To Be Aligned/Pgram_Job_696') is moved into its inferred 'Trench NNNNN' subfolder
    (created if missing). Folders already nested under a trench are left where they are.

    Runs over every filesystem stage (To Be Processed, To Be Aligned, To Overnight,
    Processed, Uploaded to AIR) — wherever loose folders happen to be.

    `field_map` is keyed by pgram-number string → {'sus_opened': str, ...}, as returned by
    `gsheets.get_field_pgram_map()`. Pass `{}` to skip case B. Both steps update
    `su_string`/`trench`, so the pgram cards refresh on the next scan.

    Returns {"renamed": [{from, to, pgram, source}], "organized": [{name, trench}],
             "skipped": [{name, reason}]}.
    """
    renamed: list[dict] = []
    organized: list[dict] = []
    skipped: list[dict] = []

    for folder, stage_root in _iter_stage_job_dirs():
        name = folder.name
        m = JOB_PATTERN.match(name)
        if not m:
            continue
        num = m.group(1)
        suffix = (m.group(2) or "").strip()

        # ── Step 1: SU-tag rename ──────────────────────────────────────────────
        new_name = name
        if suffix:
            if not _TAGGED_SU_PATTERN.match(suffix) and _BARE_SU_PATTERN.match(suffix):
                new_name = f"Pgram_Job_{num}_{_su_suffix(suffix)}"  # case A
                source = "suffix"
            # already tagged or unrecognized suffix → name unchanged, may still organize
        else:
            sus_opened = str(field_map.get(num, {}).get("sus_opened", "")).strip()
            if not sus_opened:
                skipped.append({"name": name, "reason": f"no 'SUs Opened' in field tracking for pgram {num}"})
                continue  # no SU → can't tag and can't infer a trench
            new_name = f"Pgram_Job_{num}_{_su_suffix(sus_opened)}"  # case B
            source = "field_sheet"

        if new_name != name:
            target = folder.parent / new_name
            if target.exists():
                skipped.append({"name": name, "reason": f"target '{new_name}' already exists"})
                continue
            try:
                folder.rename(target)
            except OSError as e:
                skipped.append({"name": name, "reason": str(e)})
                continue
            renamed.append({"from": name, "to": new_name, "pgram": int(num), "source": source})
            folder = target

        # ── Step 2: organize flat folders into trench subfolders ───────────────
        entry = _organize_into_trench(folder, stage_root, skipped)
        if entry:
            organized.append(entry)

    if renamed or organized:
        logger.info(f"fix_su_folder_names: renamed {len(renamed)}, organized {len(organized)} folder(s)")
    return {"renamed": renamed, "organized": organized, "skipped": skipped}


def find_volume_bins_for_su(top_pgram: str, su_id: str = "") -> list[Path]:
    """Find the two pre-snip .bin files for this SU.

    Pre-snip writes one pair per SU into Data/SU<su_id>/ as
    *_top_with_dist_*.bin and *_bottom_with_dist_*.bin. When su_id is given we
    look there directly; otherwise (or if that folder is absent — legacy data)
    we fall back to scanning the Data/<Pgram_Job_{top_pgram}*>/ folders.
    """
    cfg = get_config()
    if not cfg.volume_script_dir:
        return []
    data_dir = Path(cfg.volume_script_dir) / "Data"
    if not data_dir.exists():
        return []

    def _dist_bins(folder: Path) -> list[Path]:
        out = []
        for f in folder.glob("*.bin"):
            name_lower = f.name.lower()
            if "_top_with_dist_" in name_lower or "_bottom_with_dist_" in name_lower:
                out.append(f)
        return out

    su = str(su_id).strip()
    if su:
        su_folder = data_dir / f"SU{su}"
        if su_folder.is_dir():
            return _dist_bins(su_folder)

    # Legacy layout: bins live in the top pgram's folder, prefixed SU<su>_.
    prefix = f"pgram_job_{str(top_pgram).strip()}"
    su_marker = f"su{su.lower()}_" if su else ""
    bins: list[Path] = []
    su_bins: list[Path] = []
    for d in data_dir.iterdir():
        if not d.is_dir() or not d.name.lower().startswith(prefix):
            continue
        for f in _dist_bins(d):
            bins.append(f)
            if su_marker and f.name.lower().startswith(su_marker):
                su_bins.append(f)
    return su_bins or bins


def find_post_snip_bin_for_su(su_id: str) -> Optional[Path]:
    """Find the post-snip debug .bin written by post_snip_script.

    post_snip saves a project bin containing the merged cloud/mesh, top/bottom
    clouds and the top mesh (raw + trimmed) to Data/SU<su_id>/<su_id>_post_snip.bin.
    This is the file to open in CloudCompare to debug a finished volume.
    """
    cfg = get_config()
    if not cfg.volume_script_dir:
        return None
    su = str(su_id).strip()
    if not su:
        return None
    bin_path = Path(cfg.volume_script_dir) / "Data" / f"SU{su}" / f"{su}_post_snip.bin"
    return bin_path if bin_path.exists() else None


def find_volume_obj_for_su(su_id: str) -> Optional[Path]:
    """Find the final volume OBJ written by post_snip_script.

    post_snip saves it to this season's Volumetrics folder under the SU's trench:
    <base_path>/Volumetrics_<year>/Trench NNNNN/SU_<su_id>.obj (trench inferred from the
    SU number, e.g. 20001 -> Trench 20000), matching the script's _trench_name().
    """
    cfg = get_config()
    m = re.search(r"\d+", su_id)
    if not cfg.base_path or not m:
        return None
    trench = (int(m.group(0)) // 1000) * 1000
    obj = (
        Path(cfg.base_path)
        / f"Volumetrics_{cfg.season_year}"
        / f"Trench {trench}"
        / f"SU_{su_id}.obj"
    )
    return obj if obj.exists() else None


def find_top_volume_obj_for_su(su_id: str) -> Optional[Path]:
    """Find the SU top OBJ written by post_snip_script.

    post_snip saves the top mesh to this season's Volumetrics folder under a shared
    "SU Top OBJs" subfolder (where the Create-SU-Sheet QGIS script reads it):
    <base_path>/Volumetrics_<year>/SU Top OBJs/SU_<su_id>_top.obj.
    """
    cfg = get_config()
    if not cfg.base_path:
        return None
    obj = (
        Path(cfg.base_path)
        / f"Volumetrics_{cfg.season_year}"
        / "SU Top OBJs"
        / f"SU_{su_id}_top.obj"
    )
    return obj if obj.exists() else None


def find_su_sheet_pdf_for_su(su_id: str) -> Optional[Path]:
    """Find the SU sheet PDF written by generate_su_sheets.py (Create SU Sheet run).

    The QGIS script writes it to this season's Volumetrics folder as
    <base_path>/Volumetrics_<year>/SU_<su_id>.pdf (the su value is prefixed with
    "SU_", matching _write_su_sheets_input()).
    """
    cfg = get_config()
    if not cfg.base_path:
        return None
    pdf = (
        Path(cfg.base_path)
        / f"Volumetrics_{cfg.season_year}"
        / f"SU_{su_id}.pdf"
    )
    return pdf if pdf.exists() else None


def find_debug_image_for_su(su_id: str, top_pgram: str) -> Optional[Path]:
    """Find the debug image written by auto_snip_script.

    Looks for Data/<Pgram_Job_{top_pgram}*>/SU_{su_id}_debug.* (any extension).
    Returns None if no file is found (implies auto-snip has not run for this SU).
    """
    cfg = get_config()
    if not cfg.volume_script_dir:
        return None
    data_dir = Path(cfg.volume_script_dir) / "Data"
    if not data_dir.exists():
        return None
    prefix = f"pgram_job_{str(top_pgram).strip()}"
    stem = f"su_{su_id}_debug"
    for d in data_dir.iterdir():
        if not d.is_dir() or not d.name.lower().startswith(prefix):
            continue
        for f in d.iterdir():
            if f.is_file() and f.stem.lower() == stem:
                return f
    return None


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
