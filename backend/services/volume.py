"""Volume card provisioning service.

Called by the SU router (manual "Scan PLY" button) and the pgram router
(auto-triggered when a job lands in "processed" stage).
"""
import logging

from backend.models import SUEntry, cet_now, expand_su_range, trench_from_su_id
from backend.services import gsheets
from backend.services.filesystem import scan_ply_files

logger = logging.getLogger(__name__)


def provision_from_ply() -> dict:
    """Scan {overnight_output_assets_root}/PLY/ and create volume cards for new SUs.

    For each PLY file found:
      - Looks up that pgram in Field Pgram Tracking to get sus_opened
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
        sus_opened_str = field_map.get(pgram_str, {}).get("sus_opened", "")
        if not sus_opened_str:
            skipped.append({"pgram": pgram_num, "reason": "no sus_opened in field tracking"})
            continue

        for su_id in expand_su_range(sus_opened_str):
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
