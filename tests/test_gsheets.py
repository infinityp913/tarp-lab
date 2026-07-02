"""Tests for backend/services/gsheets.py — schema, row serialization, cache logic."""
import time
from unittest.mock import MagicMock, patch

import pytest

from backend.models import PgramJob, SUEntry, cet_now
from backend.services.gsheets import (
    PG_COLS, PG_NUM, PG_TRENCH, PG_NOTES, PG_UPDATED,
    SU_COLS, SU_ID, SU_TOP_PGRAM, SU_BOT_PGRAM, SU_VOL, SU_SHEET, SU_AIR, SU_NOTES,
    SU_READY_SHEET,
    _pg_num_str,
    _blank_if_na,
    _job_to_row,
    _su_to_row,
    _rows_to_pgram,
    _rows_to_su,
    _pgram_checkboxes,
    _su_checkboxes,
    _su_header,
    _pg_header,
)


# ─── cet_now ─────────────────────────────────────────────────────────────────

def test_cet_now_format():
    ts = cet_now()
    # "6 May 2026, 07:45" — day, month abbreviation, year, HH:MM
    parts = ts.split()
    assert len(parts) == 4
    assert parts[0].isdigit()
    assert parts[2].rstrip(",").isdigit()


# ─── _pg_num_str ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("job_id,expected", [
    ("Pgram_Job_696", "696"),
    ("696", "696"),
    ("Pgram_Job_1", "1"),
    ("001", "001"),
])
def test_pg_num_str(job_id, expected):
    assert _pg_num_str(job_id) == expected


# ─── column counts ───────────────────────────────────────────────────────────

def test_pg_cols_count():
    assert PG_COLS == 8
    assert len(_pg_header()) == PG_COLS


def test_su_cols_count():
    assert SU_COLS == 11
    assert len(_su_header()) == SU_COLS


# ─── _job_to_row ─────────────────────────────────────────────────────────────

def test_job_to_row_stores_integer():
    job = PgramJob(job_id="Pgram_Job_696", su_string="SU001", trench="Trench 16000", stage="to_be_processed")
    row = _job_to_row(job)
    assert len(row) == PG_COLS
    assert row[PG_NUM] == 696
    assert isinstance(row[PG_NUM], int)
    assert row[PG_TRENCH] == "Trench 16000"


def test_job_to_row_checkboxes_processed():
    job = PgramJob(job_id="Pgram_Job_1", su_string="", trench="", stage="processed")
    row = _job_to_row(job)
    photos, align, overnight, air = _pgram_checkboxes("processed")
    assert row[2] == photos     # PG_PHOTOS = 2
    assert row[3] == align      # PG_ALIGN = 3
    assert row[4] == overnight  # PG_OVERNIGHT = 4
    assert row[5] == air        # PG_AIR = 5


# ─── _su_to_row ──────────────────────────────────────────────────────────────

def test_su_to_row_schema():
    entry = SUEntry(su_id="SU001", top_pgram="696", bot_pgram="697", trench="Trench 16000", stage="not_started")
    row = _su_to_row(entry)
    assert len(row) == SU_COLS
    assert row[SU_ID] == "SU001"
    assert row[SU_TOP_PGRAM] == 696
    assert isinstance(row[SU_TOP_PGRAM], int)
    assert row[SU_BOT_PGRAM] == 697
    assert isinstance(row[SU_BOT_PGRAM], int)
    # Trench is not a column — it's implicit in the tab name


def test_su_to_row_checkboxes_volumetrics_created():
    entry = SUEntry(su_id="SU002", trench="", stage="volumetrics_created")
    row = _su_to_row(entry)
    vol, sheet, air = _su_checkboxes("volumetrics_created")
    assert row[SU_VOL] == vol
    assert row[SU_SHEET] == sheet
    assert row[SU_AIR] == air


def test_su_to_row_empty_pgrams():
    entry = SUEntry(su_id="SU003", top_pgram="", bot_pgram="", trench="Trench 17000", stage="not_started")
    row = _su_to_row(entry)
    assert row[SU_TOP_PGRAM] == ""
    assert row[SU_BOT_PGRAM] == ""


def test_su_to_row_ready_for_sheet():
    default = _su_to_row(SUEntry(su_id="SU004", trench="", stage="volumetrics_created"))
    assert default[SU_READY_SHEET] is False
    checked = _su_to_row(
        SUEntry(su_id="SU005", trench="", stage="volumetrics_created", ready_for_sheet=True)
    )
    assert checked[SU_READY_SHEET] is True


# ─── _rows_to_pgram ──────────────────────────────────────────────────────────

def _pg_fake_rows(*data_rows):
    header = ["Pgram Number", "Trench",
              "Photos—No Alignment", "Alignment+Manual Check",
              "PLY Created (Overnight completed)", "Uploaded to AIR",
              "Notes", "Last Updated (CET)"]
    return [header] + list(data_rows)


def test_rows_to_pgram_reconstructs_job_id():
    rows = _pg_fake_rows([696, "Trench 16000", False, False, False, False, "", ""])
    result = _rows_to_pgram(rows)
    assert len(result) == 1
    assert result[0]["job_id"] == "Pgram_Job_696"


def test_rows_to_pgram_handles_string_number():
    rows = _pg_fake_rows(["697", "Trench 17000", "FALSE", "FALSE", "FALSE", "FALSE", "", ""])
    result = _rows_to_pgram(rows)
    assert result[0]["job_id"] == "Pgram_Job_697"


def test_rows_to_pgram_skips_empty():
    rows = _pg_fake_rows([], [698, "Trench 18000", False, False, False, False, "", ""])
    result = _rows_to_pgram(rows)
    assert len(result) == 1
    assert result[0]["job_id"] == "Pgram_Job_698"


def test_rows_to_pgram_stage_derivation():
    rows = _pg_fake_rows([700, "Trench 11000", True, True, True, True, "", ""])
    result = _rows_to_pgram(rows)
    assert result[0]["stage"] == "uploaded_air"


# ─── _rows_to_su ─────────────────────────────────────────────────────────────

def _su_fake_rows(*data_rows):
    # No Trench column — trench is injected from the tab name
    # Layout: ID, Top, Bot, VolumeStage, VolCreated, ReadyForSheet, SheetCreated,
    #         Air, Notes, Updated, SnipMethod
    header = ["SU ID", "Top Pgram", "Bottom Pgram",
              "Volume Stage",
              "Volume Created", "Ready for SU Sheet", "SU Sheet Created",
              "Uploaded to AIR", "Notes", "Last Updated (CET)", "Snip Method"]
    return [header] + list(data_rows)


def test_rows_to_su_schema():
    # Stage key at index 3; checkboxes at 4 (vol), 5 (ready), 6 (sheet), 7 (air)
    rows = _su_fake_rows(["SU001", 696, 697, "not_started", False, False, False, False, "", "", ""])
    result = _rows_to_su(rows, "16000")  # trench injected from tab name
    assert len(result) == 1
    r = result[0]
    assert r["su_id"] == "SU001"
    assert r["top_pgram"] == "696"
    assert r["bot_pgram"] == "697"
    assert r["trench"] == "16000"
    assert r["stage"] == "not_started"


def test_rows_to_su_stage_volumetrics():
    # Stage key at index 3 takes precedence
    rows = _su_fake_rows(["SU002", 0, 0, "volumetrics_created", True, False, False, False, "", "", ""])
    result = _rows_to_su(rows, "17000")
    assert result[0]["stage"] == "volumetrics_created"


def test_rows_to_su_ready_for_sheet():
    # Col F (index 5) TRUE → ready_for_sheet True; absent/short row → False
    rows = _su_fake_rows(
        ["SU010", 0, 0, "volumetrics_created", True, True, False, False, "", "", ""],
        ["SU011", 0, 0, "volumetrics_created", True, False, False, False, "", "", ""],
        ["SU012", 0, 0, "volumetrics_created", True],  # short row → ready False
    )
    result = {r["su_id"]: r["ready_for_sheet"] for r in _rows_to_su(rows, "17000")}
    assert result == {"SU010": True, "SU011": False, "SU012": False}


def test_rows_to_su_skips_empty_id():
    rows = _su_fake_rows(["", 0, 0, "not_started", False, False, False, False, "", "", ""])
    assert _rows_to_su(rows, "17000") == []


# ─── _migrate_su_columns ─────────────────────────────────────────────────────

_OLD_HEADER = [[
    "SU ID", "Top Pgram", "Bottom Pgram", "Volume Stage",
    "Volume Created", "SU Sheet Created", "Uploaded to AIR",
    "Notes", "Last Updated (CET)", "Snip Method", "Ready for SU Sheet",
]]  # old layout: Ready-for-SU-Sheet at index 10


def _run_migrate(header):
    from backend.services import gsheets
    svc = MagicMock()
    with patch.object(gsheets, "_read_range", return_value=header), \
         patch.object(gsheets, "_execute"), \
         patch.object(gsheets, "_invalidate_su_cache"):
        gsheets._migrate_su_columns(svc, "sid", {"Trench 20000": 111})
    return svc.spreadsheets().batchUpdate


def test_migrate_moves_ready_column_to_target():
    batch = _run_migrate(_OLD_HEADER)
    body = batch.call_args.kwargs["body"]
    move = body["requests"][0]["moveDimension"]
    assert move["source"]["sheetId"] == 111
    assert (move["source"]["startIndex"], move["source"]["endIndex"]) == (10, 11)
    assert move["destinationIndex"] == 5  # between Volume Created (4) and SU Sheet Created


def test_migrate_noop_when_already_at_target():
    batch = _run_migrate([_su_header()])  # current layout — already at index 5
    batch.assert_not_called()


def test_migrate_noop_when_column_absent():
    header = [["SU ID", "Top Pgram", "Bottom Pgram", "Volume Stage", "Volume Created"]]
    batch = _run_migrate(header)
    batch.assert_not_called()


def test_rows_to_su_pads_short_rows():
    rows = [["SU ID", "Top Pgram", "Bottom Pgram", "Vol Stage", "Vol", "Sheet", "AIR", "Notes", "Updated", "Snip"],
            ["SU003"]]  # only 1 column
    result = _rows_to_su(rows, "18000")
    assert len(result) == 1
    assert result[0]["su_id"] == "SU003"


# ─── _blank_if_na ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("val", ["NA", "na", "N/A", "n/a", "Na", "N/a", "#N/A", "#n/a"])
def test_blank_if_na_returns_empty_for_na_variants(val):
    assert _blank_if_na(val) == ""


@pytest.mark.parametrize("val", ["", "  "])
def test_blank_if_na_returns_empty_for_blank_and_whitespace(val):
    assert _blank_if_na(val) == ""


@pytest.mark.parametrize("val", ["  na  ", "  N/A  "])
def test_blank_if_na_returns_empty_for_whitespace_padded_na(val):
    assert _blank_if_na(val) == ""


def test_blank_if_na_returns_empty_for_none():
    assert _blank_if_na(None) == ""


@pytest.mark.parametrize("val", [True, False])
def test_blank_if_na_returns_empty_for_bool(val):
    assert _blank_if_na(val) == ""


@pytest.mark.parametrize("val,expected", [
    ("21015", "21015"),
    ("21015, 21020", "21015, 21020"),
    ("SU21015", "SU21015"),
])
def test_blank_if_na_preserves_real_values(val, expected):
    assert _blank_if_na(val) == expected


def test_field_pgram_map_treats_na_as_blank(monkeypatch):
    import backend.services.gsheets as gs

    fake_rows = [
        ["Pgram", "SUs Opened", "SUs Closed", "Notes", "Stage", "Updated"],
        [696, "N/A", "na", "some note", "", ""],
        [697, "21015", "21020", "", "", ""],
    ]
    monkeypatch.setattr(gs, "_read_range", lambda _: fake_rows)

    result = gs._read_field_pgram_map()
    assert result["696"]["sus_opened"] == ""
    assert result["696"]["sus_closed"] == ""
    assert result["697"]["sus_opened"] == "21015"
    assert result["697"]["sus_closed"] == "21020"


def test_field_pgram_map_returns_empty_when_no_rows(monkeypatch):
    import backend.services.gsheets as gs

    monkeypatch.setattr(gs, "_read_range", lambda _: None)
    assert gs._read_field_pgram_map() == {}

    monkeypatch.setattr(gs, "_read_range", lambda _: [])
    assert gs._read_field_pgram_map() == {}


def test_field_pgram_map_skips_empty_and_no_num_rows(monkeypatch):
    import backend.services.gsheets as gs

    fake_rows = [
        ["Pgram", "SUs Opened", "SUs Closed", "Notes", "Stage", "Updated"],
        [],                                    # empty row
        ["", "21015", "21020", "", "", ""],    # missing pgram number
        [698, "21030", "21031", "", "", ""],   # valid
    ]
    monkeypatch.setattr(gs, "_read_range", lambda _: fake_rows)

    result = gs._read_field_pgram_map()
    assert list(result.keys()) == ["698"]


def test_field_pgram_map_pads_short_rows(monkeypatch):
    import backend.services.gsheets as gs

    fake_rows = [
        ["Pgram", "SUs Opened", "SUs Closed", "Notes", "Stage", "Updated"],
        [699],   # only pgram number, rest missing
    ]
    monkeypatch.setattr(gs, "_read_range", lambda _: fake_rows)

    result = gs._read_field_pgram_map()
    assert result["699"]["sus_opened"] == ""
    assert result["699"]["sus_closed"] == ""


# ─── cache invalidation (unit, no real Sheets API) ───────────────────────────

def test_cache_returns_stale_on_none(monkeypatch):
    """If _batch_read_ranges returns None, get_su_rows should return the cached data."""
    import backend.services.gsheets as gs

    gs._su_cache = [{"su_id": "CACHED", "top_pgram": "", "bot_pgram": "", "trench": "", "stage": "not_started", "notes": "", "last_updated": ""}]
    gs._su_cache_time = 0  # Force TTL expiry

    monkeypatch.setattr(gs, "_batch_read_ranges", lambda _: None)
    monkeypatch.setattr(gs, "is_available", lambda: True)

    result = gs.get_su_rows()
    assert len(result) == 1
    assert result[0]["su_id"] == "CACHED"
