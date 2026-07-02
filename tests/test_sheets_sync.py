"""Regression tests for the /api/sheets/sync endpoint.

Guards that full_sync round-trips per-card flags read from the sheet instead of
resetting them to defaults — a dropped field here silently unchecks
"Ready for SU sheet" and clears the auto-snip debug-image flag on every sync.
"""
from unittest.mock import patch

from backend.routers import sheets


def test_sync_preserves_per_card_flags():
    su_rows = [
        {
            "su_id": "20005", "top_pgram": "696", "bot_pgram": "697",
            "trench": "20000", "stage": "volumetrics_created",
            "notes": "keep me", "last_updated": "1 Jul 2026, 10:00",
            "snip_method": "auto", "ready_for_sheet": True,
        },
        {
            "su_id": "20006", "top_pgram": "698", "bot_pgram": "699",
            "trench": "20000", "stage": "volumetrics_created",
            "notes": "", "last_updated": "1 Jul 2026, 10:00",
            "snip_method": "", "ready_for_sheet": False,
        },
    ]
    captured = {}

    def fake_full_sync(pgram_jobs, su_entries):
        captured["entries"] = su_entries

    with patch("backend.services.gsheets.is_available", return_value=True), \
         patch("backend.routers.sheets._build_job_list", return_value=[]), \
         patch("backend.services.gsheets.get_su_rows", return_value=su_rows), \
         patch("backend.services.gsheets.full_sync", side_effect=fake_full_sync):
        result = sheets.sync()

    assert result["ok"] is True
    by_id = {e.su_id: e for e in captured["entries"]}
    assert by_id["20005"].ready_for_sheet is True
    assert by_id["20005"].snip_method == "auto"
    assert by_id["20006"].ready_for_sheet is False
    assert by_id["20006"].snip_method == ""
