"""Volume card provisioning service.

Called by the SU router (manual "Scan PLY" button) and the pgram router
(auto-triggered when a job lands in "processed" stage).
"""
import logging
import re
from pathlib import Path

from backend.models import SUEntry, cet_now, expand_su_range, trench_from_su_id
from backend.services import gsheets
from backend.services.filesystem import scan_filesystem, scan_ply_files

logger = logging.getLogger(__name__)

# LiDAR USDZ scans live here, named like "tarpf24441-SU_21001.usdz". A single
# file may cover several SUs, e.g. "...-SU_22018_22019_22021.usdz".
USDZ_DIR = Path(r"C:\Users\Public\SynologyDrive\tharros_syn_2")
_USDZ_SU_RE = re.compile(r"-SU_([0-9_]+)\.usdz$", re.IGNORECASE)


def ready_pgram_nums() -> set[int]:
    """Pgram numbers that have a processed model on disk (a PLY file exists).

    A PLY only appears once a pgram reaches the 'processed' stage, so PLY
    presence is the operative signal that a pgram is processed.
    """
    return {ply["pgram_num"] for ply in scan_ply_files()}


def usdz_su_nums() -> set[str]:
    """SU numbers (as strings) that have a matching LiDAR USDZ scan on disk.

    If the folder is unreachable (e.g. the Synology drive is offline), returns
    an empty set so the SUs count as having no scan and are gated out of
    readiness — a missing drive must not silently pass the LiDAR check.
    """
    nums: set[str] = set()
    try:
        if not USDZ_DIR.is_dir():
            logger.warning(f"usdz_su_nums: scan folder not reachable: {USDZ_DIR}")
            return nums
        for f in USDZ_DIR.glob("*.usdz"):
            m = _USDZ_SU_RE.search(f.name)
            if m:
                nums.update(m.group(1).split("_"))
    except OSError as e:
        logger.warning(f"usdz_su_nums: could not read {USDZ_DIR}: {e}")
    return nums


def find_usdz_for_su(su_id: str) -> list[Path]:
    """LiDAR USDZ scan file(s) whose name includes this SU number.

    One file may cover several SUs, so any file listing this SU number matches.
    Returns an empty list if none match or the folder is unreachable.
    """
    su = str(su_id).strip()
    matches: list[Path] = []
    try:
        if not USDZ_DIR.is_dir():
            logger.warning(f"find_usdz_for_su: scan folder not reachable: {USDZ_DIR}")
            return matches
        for f in sorted(USDZ_DIR.glob("*.usdz")):
            m = _USDZ_SU_RE.search(f.name)
            if m and su in m.group(1).split("_"):
                matches.append(f)
    except OSError as e:
        logger.warning(f"find_usdz_for_su: could not read {USDZ_DIR}: {e}")
    return matches


def is_su_ready(
    top_pgram: str,
    bot_pgram: str,
    su_id: str,
    ready_nums: set[int],
    usdz_nums: set[str],
) -> bool:
    """Whether a volume card is ready for its volume to be extracted.

    Ready means BOTH the top and bottom pgrams are known and processed
    (their PLY files exist) AND the SU has a matching LiDAR USDZ scan on disk.
    Only ready cards can be moved from 'Not Started' into the pre-snip pipeline.
    """
    def known_and_processed(val: str) -> bool:
        val = str(val).strip()
        return val.isdigit() and int(val) in ready_nums

    has_lidar = str(su_id).strip() in usdz_nums
    return known_and_processed(top_pgram) and known_and_processed(bot_pgram) and has_lidar


def annotate_readiness(rows: list[dict]) -> list[dict]:
    """Return copies of SU rows each tagged with computed `ready` and `has_lidar` booleans."""
    ready_nums = ready_pgram_nums()
    usdz_nums = usdz_su_nums()
    return [
        {
            **row,
            "ready": is_su_ready(
                row.get("top_pgram", ""),
                row.get("bot_pgram", ""),
                row.get("su_id", ""),
                ready_nums,
                usdz_nums,
            ),
            "has_lidar": str(row.get("su_id", "")).strip() in usdz_nums,
        }
        for row in rows
    ]


def _pgram_to_su_string() -> dict[str, str]:
    """Map pgram number string → the job folder's su_string (e.g. "830" → "SU23015-23016").

    This is the authoritative SU list the lab already parsed from the job folder name.
    Prefer the processed-stage folder when the same pgram appears in multiple stages.
    """
    result: dict[str, str] = {}
    for job in scan_filesystem():
        if not job.su_string:
            continue
        num = job.job_id.split("_")[-1]
        if num not in result or job.stage == "processed":
            result[num] = job.su_string
    return result


def provision_from_ply() -> dict:
    """Scan {overnight_output_assets_root}/PLY/ and create volume cards for new SUs.

    For each PLY file found:
      - Determines the SUs for that pgram by unioning the job folder's su_string
        (authoritative, always present) with Field Pgram Tracking sus_opened
        (often empty when a job lands in processed overnight)
      - Expands range strings (e.g. 21015-17 → 21015, 21016, 21017)
      - Sets top_pgram from the trigger pgram; bot_pgram from the last pgram
        that lists that SU in sus_closed across all field pgrams
      - Creates a not_started volume card for each SU not already in Sheets

    Returns {"created": [...], "skipped": [...], "ply_count": int}.
    """
    ply_files = scan_ply_files()
    if not ply_files:
        return {"created": [], "skipped": [], "ply_count": 0}

    existing_su_ids: set[str] = {row["su_id"] for row in gsheets.get_su_rows()}
    field_map = gsheets.get_field_pgram_map()
    pgram_su_strings = _pgram_to_su_string()

    # Build reverse index: su_id → highest pgram number seen in sus_closed
    su_to_bot: dict[str, int] = {}
    for pgram_str, data in field_map.items():
        try:
            pgram_int = int(pgram_str)
        except ValueError:
            continue
        for su_id in expand_su_range(data.get("sus_closed", "")):
            if su_id and pgram_int > su_to_bot.get(su_id, -1):
                su_to_bot[su_id] = pgram_int

    created: list[dict] = []
    skipped: list[dict] = []

    for ply in ply_files:
        pgram_num = ply["pgram_num"]
        pgram_str = str(pgram_num)
        # The job folder name uses "_" to separate multiple SUs (SU22003_22090_…);
        # normalise to commas so expand_su_range splits them.
        folder_sus = pgram_su_strings.get(pgram_str, "").replace("_", ",")
        sus_opened_str = field_map.get(pgram_str, {}).get("sus_opened", "")

        # Union both sources, preserving order and de-duplicating.
        su_ids: list[str] = []
        seen: set[str] = set()
        for source in (folder_sus, sus_opened_str):
            for su_id in expand_su_range(source):
                if su_id not in seen:
                    seen.add(su_id)
                    su_ids.append(su_id)

        if not su_ids:
            skipped.append({"pgram": pgram_num, "reason": "no SUs in job folder or field tracking"})
            continue

        for su_id in su_ids:
            if not su_id.isdigit():
                continue
            if su_id in existing_su_ids:
                skipped.append({"su_id": su_id, "reason": "already exists"})
                continue

            trench = trench_from_su_id(su_id)
            if not trench:
                skipped.append({"su_id": su_id, "reason": "cannot determine trench"})
                continue

            bot_int = su_to_bot.get(su_id)
            entry = SUEntry(
                su_id=su_id,
                top_pgram=pgram_str,
                bot_pgram=str(bot_int) if bot_int is not None else "",
                trench=trench,
                stage="not_started",
                last_updated=cet_now(),
            )
            try:
                gsheets.upsert_su(entry)
                existing_su_ids.add(su_id)
                created.append(entry.model_dump())
            except Exception as e:
                skipped.append({"su_id": su_id, "reason": str(e)})

    if created:
        logger.info(f"provision_from_ply: created {len(created)} volume card(s) from {len(ply_files)} PLY file(s)")

    return {"created": created, "skipped": skipped, "ply_count": len(ply_files)}
