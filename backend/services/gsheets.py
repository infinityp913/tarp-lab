"""
Google Sheets service — single source of truth for non-filesystem-backed state.

Pgram Jobs sheet columns (0-indexed):
  0  Pgram Number
  1  Trench
  2  SUs Open
  3  SUs Closed          ← manual, preserved across syncs
  4  Photos—No Alignment ← TRUE when stage >= to_be_aligned
  5  Alignment+Manual    ← TRUE when stage >= to_overnight
  6  Overnight Completed ← TRUE when stage >= processed
  7  Uploaded to AIR     ← TRUE when stage == uploaded_air
  8  Notes
  9  Last Updated

SU Tracking sheet columns (0-indexed):
  0  SU ID
  1  Parent Pgram Job
  2  Trench
  3  Volumetrics Created ← TRUE when stage >= volumetrics_created
  4  SU Sheet Created    ← TRUE when stage >= su_sheet_created
  5  Uploaded to AIR     ← TRUE when stage == uploaded_air
  6  Notes
  7  Last Updated
"""

import logging
import threading
import time
from typing import Optional

from backend.config import CREDENTIALS_PATH, TOKEN_DIR, TOKEN_PATH, LOG_PATH, get_config
from backend.models import PgramJob, SUEntry, PGRAM_STAGES, SU_STAGES, utcnow

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
_CACHE_TTL = 30  # seconds

_pgram_cache: list[dict] = []
_su_cache: list[dict] = []
_pgram_cache_time: float = 0
_su_cache_time: float = 0
_cache_lock = threading.Lock()
_gsheets_available = True
_service = None

# Column indices — Pgram Jobs
PG_NUM = 0
PG_TRENCH = 1
PG_SUS_OPEN = 2
PG_SUS_CLOSED = 3
PG_PHOTOS = 4
PG_ALIGN = 5
PG_OVERNIGHT = 6
PG_AIR = 7
PG_NOTES = 8
PG_UPDATED = 9
PG_COLS = 10

# Column indices — SU Tracking
SU_ID = 0
SU_PARENT = 1
SU_TRENCH = 2
SU_VOL = 3
SU_SHEET = 4
SU_AIR = 5
SU_NOTES = 6
SU_UPDATED = 7
SU_COLS = 8

_PGRAM_STAGE_ORDER = {s: i for i, s in enumerate(PGRAM_STAGES)}
_SU_STAGE_ORDER = {s: i for i, s in enumerate(SU_STAGES)}

# Dark green header — R:46 G:92 B:40  → fractions
_HEADER_R = 46 / 255
_HEADER_G = 92 / 255
_HEADER_B = 40 / 255


def _log_error(msg: str):
    logger.error(msg)
    try:
        with open(LOG_PATH, "a") as f:
            f.write(f"ERROR {msg}\n")
    except OSError:
        pass


def _get_service():
    global _service, _gsheets_available
    if _service is not None:
        return _service

    if not CREDENTIALS_PATH.exists():
        _gsheets_available = False
        _log_error("credentials.json not found — Google Sheets disabled")
        return None

    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        creds = None
        TOKEN_DIR.mkdir(parents=True, exist_ok=True)

        if TOKEN_PATH.exists():
            creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), _SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), _SCOPES)
                creds = flow.run_local_server(port=0)
            import os as _os
            fd = _os.open(str(TOKEN_PATH), _os.O_WRONLY | _os.O_CREAT | _os.O_TRUNC, 0o600)
            with _os.fdopen(fd, "w") as token:
                token.write(creds.to_json())

        _service = build("sheets", "v4", credentials=creds)
        _gsheets_available = True
        return _service

    except Exception as e:
        _gsheets_available = False
        _log_error(f"Google Sheets auth failed: {e}")
        return None


def is_available() -> bool:
    return _gsheets_available and get_config().gsheets_spreadsheet_id not in ("", "YOUR_SPREADSHEET_ID_HERE")


def _pgram_checkboxes(stage: str) -> tuple[bool, bool, bool, bool]:
    """Return (photos, alignment, overnight, air) booleans for a stage."""
    idx = _PGRAM_STAGE_ORDER.get(stage, 0)
    photos = idx >= _PGRAM_STAGE_ORDER["to_be_aligned"]
    alignment = idx >= _PGRAM_STAGE_ORDER["to_overnight"]
    overnight = idx >= _PGRAM_STAGE_ORDER["processed"]
    air = stage == "uploaded_air"
    return photos, alignment, overnight, air


def _su_checkboxes(stage: str) -> tuple[bool, bool, bool]:
    """Return (vol, sheet, air) booleans for an SU stage."""
    idx = _SU_STAGE_ORDER.get(stage, 0)
    vol = idx >= _SU_STAGE_ORDER["volumetrics_created"]
    sheet = idx >= _SU_STAGE_ORDER["su_sheet_created"]
    air = stage == "uploaded_air"
    return vol, sheet, air


def _stage_from_pgram_checkboxes(air: bool, overnight: bool, alignment: bool, photos: bool) -> str:
    if air:
        return "uploaded_air"
    if overnight:
        return "processed"
    if alignment:
        return "to_overnight"
    if photos:
        return "to_be_aligned"
    return "to_be_processed"


def _stage_from_su_checkboxes(air: bool, sheet: bool, vol: bool) -> str:
    if air:
        return "uploaded_air"
    if sheet:
        return "su_sheet_created"
    if vol:
        return "volumetrics_created"
    return "not_started"


def _bool(val) -> bool:
    if isinstance(val, bool):
        return val
    return str(val).upper() in ("TRUE", "1", "YES")


def _ensure_sheets() -> tuple[int, int]:
    """Create both sheets if they don't exist. Returns (pg_sheet_id, su_sheet_id)."""
    svc = _get_service()
    if svc is None:
        return 0, 0
    sid = get_config().gsheets_spreadsheet_id
    try:
        meta = svc.spreadsheets().get(spreadsheetId=sid).execute()
        existing = {s["properties"]["title"]: s["properties"]["sheetId"]
                    for s in meta.get("sheets", [])}

        add_requests = []
        if "Pgram Jobs" not in existing:
            add_requests.append({"addSheet": {"properties": {"title": "Pgram Jobs"}}})
        if "SU Tracking" not in existing:
            add_requests.append({"addSheet": {"properties": {"title": "SU Tracking"}}})

        if add_requests:
            svc.spreadsheets().batchUpdate(
                spreadsheetId=sid, body={"requests": add_requests}
            ).execute()
            meta = svc.spreadsheets().get(spreadsheetId=sid).execute()
            existing = {s["properties"]["title"]: s["properties"]["sheetId"]
                        for s in meta.get("sheets", [])}

        return existing.get("Pgram Jobs", 0), existing.get("SU Tracking", 0)

    except Exception as e:
        _log_error(f"_ensure_sheets failed: {e}")
        return 0, 0


def _apply_sheet_style(svc, sid: str, sheet_id: int, num_cols: int):
    """Dark green header, frozen row 1, checkbox validation — two separate batches."""
    if num_cols == PG_COLS:
        bool_cols = [PG_PHOTOS, PG_ALIGN, PG_OVERNIGHT, PG_AIR]
    else:
        bool_cols = [SU_VOL, SU_SHEET, SU_AIR]

    # Batch 1: freeze + header colour + checkbox validation
    fmt_requests = [
        {
            "updateSheetProperties": {
                "properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": 1}},
                "fields": "gridProperties.frozenRowCount",
            }
        },
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1,
                           "startColumnIndex": 0, "endColumnIndex": num_cols},
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": {"red": _HEADER_R, "green": _HEADER_G, "blue": _HEADER_B},
                        "textFormat": {"foregroundColor": {"red": 1, "green": 1, "blue": 1},
                                       "bold": True},
                        "horizontalAlignment": "CENTER",
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
            }
        },
    ]
    for col in bool_cols:
        fmt_requests.append({
            "setDataValidation": {
                "range": {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": 1000,
                          "startColumnIndex": col, "endColumnIndex": col + 1},
                "rule": {
                    "condition": {"type": "BOOLEAN"},
                    "showCustomUi": True,
                },
            }
        })
    try:
        svc.spreadsheets().batchUpdate(
            spreadsheetId=sid, body={"requests": fmt_requests}
        ).execute()
    except Exception as e:
        _log_error(f"_apply_sheet_style (format+validation) failed: {e}")

    # Batch 2: auto-resize — separate so a failure here can't kill the validation above
    try:
        svc.spreadsheets().batchUpdate(
            spreadsheetId=sid,
            body={"requests": [{
                "autoResizeDimensions": {
                    "dimensions": {"sheetId": sheet_id, "dimension": "COLUMNS",
                                   "startIndex": 0, "endIndex": num_cols}
                }
            }]},
        ).execute()
    except Exception as e:
        _log_error(f"_apply_sheet_style (auto-resize) failed (non-fatal): {e}")



def _read_range(range_name: str) -> list[list]:
    svc = _get_service()
    if svc is None:
        return []
    sid = get_config().gsheets_spreadsheet_id
    try:
        result = svc.spreadsheets().values().get(spreadsheetId=sid, range=range_name).execute()
        return result.get("values", [])
    except Exception as e:
        _log_error(f"_read_range({range_name}) failed: {e}")
        return []


def _write_range(range_name: str, values: list[list]):
    svc = _get_service()
    if svc is None:
        return
    sid = get_config().gsheets_spreadsheet_id
    try:
        svc.spreadsheets().values().update(
            spreadsheetId=sid,
            range=range_name,
            valueInputOption="RAW",
            body={"values": values},
        ).execute()
    except Exception as e:
        _log_error(f"_write_range({range_name}) failed: {e}")
        raise


def _append_row(sheet: str, row: list):
    svc = _get_service()
    if svc is None:
        return
    sid = get_config().gsheets_spreadsheet_id
    try:
        svc.spreadsheets().values().append(
            spreadsheetId=sid,
            range=f"{sheet}!A1",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        ).execute()
    except Exception as e:
        _log_error(f"_append_row({sheet}) failed: {e}")
        raise


def _pg_header() -> list:
    return [
        "Pgram Number", "Trench", "SUs Open", "SUs Closed",
        "Photos—No Alignment", "Alignment+Manual Check",
        "Overnight Completed", "Uploaded to AIR",
        "Notes", "Last Updated",
    ]


def _su_header() -> list:
    return [
        "SU ID", "Parent Pgram Job", "Trench",
        "Volumetrics Created", "SU Sheet Created",
        "Uploaded to AIR",
        "Notes", "Last Updated",
    ]


def _job_to_row(job: PgramJob, sus_closed: int = 0, sus_open: int = 0) -> list:
    photos, align, overnight, air = _pgram_checkboxes(job.stage)
    return [
        job.job_id,
        job.trench,
        sus_open,
        sus_closed,
        photos,
        align,
        overnight,
        air,
        job.notes_from_field,
        utcnow(),
    ]


def _su_to_row(entry: SUEntry) -> list:
    vol, sheet, air = _su_checkboxes(entry.stage)
    return [
        entry.su_id,
        entry.parent_job_id,
        entry.trench,
        vol,
        sheet,
        air,
        entry.notes,
        utcnow(),
    ]


def _rows_to_pgram(rows: list[list]) -> list[dict]:
    result = []
    for row in rows[1:]:  # skip header
        if not row:
            continue
        while len(row) < PG_COLS:
            row.append("")
        if not row[PG_NUM]:
            continue
        stage = _stage_from_pgram_checkboxes(
            _bool(row[PG_AIR]),
            _bool(row[PG_OVERNIGHT]),
            _bool(row[PG_ALIGN]),
            _bool(row[PG_PHOTOS]),
        )
        notes = row[PG_NOTES]
        if isinstance(notes, bool) or str(notes).upper() in ("TRUE", "FALSE"):
            notes = ""
        result.append({
            "job_id": row[PG_NUM],
            "su_string": "",
            "trench": row[PG_TRENCH],
            "stage": stage,
            "notes_from_field": notes,
            "last_updated": row[PG_UPDATED],
            "sus_open": row[PG_SUS_OPEN],
            "sus_closed": row[PG_SUS_CLOSED],
        })
    return result


def _rows_to_su(rows: list[list]) -> list[dict]:
    result = []
    for row in rows[1:]:
        if not row:
            continue
        while len(row) < SU_COLS:
            row.append("")
        if not row[SU_ID]:
            continue
        stage = _stage_from_su_checkboxes(
            _bool(row[SU_AIR]),
            _bool(row[SU_SHEET]),
            _bool(row[SU_VOL]),
        )
        notes = row[SU_NOTES]
        if isinstance(notes, bool) or str(notes).upper() in ("TRUE", "FALSE"):
            notes = ""
        result.append({
            "su_id": row[SU_ID],
            "parent_job_id": row[SU_PARENT],
            "trench": row[SU_TRENCH],
            "stage": stage,
            "notes": notes,
            "last_updated": row[SU_UPDATED],
        })
    return result


def get_pgram_rows() -> list[dict]:
    global _pgram_cache, _pgram_cache_time
    with _cache_lock:
        if time.time() - _pgram_cache_time < _CACHE_TTL:
            return list(_pgram_cache)

    if not is_available():
        return []

    rows = _read_range("Pgram Jobs!A:J")
    data = _rows_to_pgram(rows)
    with _cache_lock:
        _pgram_cache = data
        _pgram_cache_time = time.time()
    return data


def get_su_rows() -> list[dict]:
    global _su_cache, _su_cache_time
    with _cache_lock:
        if time.time() - _su_cache_time < _CACHE_TTL:
            return list(_su_cache)

    if not is_available():
        return []

    rows = _read_range("SU Tracking!A:H")
    data = _rows_to_su(rows)
    with _cache_lock:
        _su_cache = data
        _su_cache_time = time.time()
    return data


def _invalidate_pgram_cache():
    with _cache_lock:
        global _pgram_cache_time
        _pgram_cache_time = 0


def _invalidate_su_cache():
    with _cache_lock:
        global _su_cache_time
        _su_cache_time = 0


def upsert_pgram(job: PgramJob):
    if not is_available():
        return
    rows = _read_range("Pgram Jobs!A:J")
    data = rows[1:] if len(rows) > 1 else []
    new_row = _job_to_row(job)

    for i, row in enumerate(data):
        while len(row) < PG_COLS:
            row.append("")
        if row[PG_NUM] == job.job_id:
            # Preserve manual SUs Closed count
            new_row[PG_SUS_CLOSED] = row[PG_SUS_CLOSED]
            # Preserve notes if not passed
            if not job.notes_from_field and row[PG_NOTES]:
                new_row[PG_NOTES] = row[PG_NOTES]
            _write_range(f"Pgram Jobs!A{i + 2}:K{i + 2}", [new_row])
            _invalidate_pgram_cache()
            return

    _append_row("Pgram Jobs", new_row)
    _invalidate_pgram_cache()


def update_pgram_stage(job_id: str, stage: str):
    if not is_available():
        return
    rows = _read_range("Pgram Jobs!A:J")
    photos, align, overnight, air = _pgram_checkboxes(stage)
    for i, row in enumerate(rows[1:], start=2):
        if row and row[0] == job_id:
            while len(row) < PG_COLS:
                row.append("")
            _write_range(
                f"Pgram Jobs!E{i}:J{i}",
                [[photos, align, overnight, air,
                  row[PG_NOTES] if len(row) > PG_NOTES else "", utcnow()]],
            )
            _invalidate_pgram_cache()
            return
    # Not found — append
    new_row = _job_to_row(PgramJob(job_id=job_id, su_string="", trench="", stage=stage))
    _append_row("Pgram Jobs", new_row)
    _invalidate_pgram_cache()


def update_pgram_notes(job_id: str, notes: str):
    if not is_available():
        raise RuntimeError("Google Sheets is unavailable")
    rows = _read_range("Pgram Jobs!A:J")
    for i, row in enumerate(rows[1:], start=2):
        if row and row[0] == job_id:
            _write_range(f"Pgram Jobs!I{i}:J{i}", [[notes, utcnow()]])
            _invalidate_pgram_cache()
            return
    raise ValueError(f"Job {job_id} not found in sheet")


def upsert_su(entry: SUEntry):
    if not is_available():
        return
    rows = _read_range("SU Tracking!A:H")
    data = rows[1:] if len(rows) > 1 else []
    new_row = _su_to_row(entry)

    for i, row in enumerate(data):
        while len(row) < SU_COLS:
            row.append("")
        if row[SU_ID] == entry.su_id:
            _write_range(f"SU Tracking!A{i + 2}:H{i + 2}", [new_row])
            _invalidate_su_cache()
            return

    _append_row("SU Tracking", new_row)
    _invalidate_su_cache()


def update_su_stage(su_id: str, stage: str):
    if not is_available():
        raise RuntimeError("Google Sheets is unavailable")
    rows = _read_range("SU Tracking!A:H")
    vol, sheet, air = _su_checkboxes(stage)
    for i, row in enumerate(rows[1:], start=2):
        if row and row[0] == su_id:
            while len(row) < SU_COLS:
                row.append("")
            _write_range(
                f"SU Tracking!D{i}:H{i}",
                [[vol, sheet, air,
                  row[SU_NOTES] if len(row) > SU_NOTES else "", utcnow()]],
            )
            _invalidate_su_cache()
            return
    raise ValueError(f"SU {su_id} not found in sheet")


def update_su_notes(su_id: str, notes: str):
    if not is_available():
        raise RuntimeError("Google Sheets is unavailable")
    rows = _read_range("SU Tracking!A:H")
    for i, row in enumerate(rows[1:], start=2):
        if row and row[0] == su_id:
            _write_range(f"SU Tracking!G{i}:H{i}", [[notes, utcnow()]])
            _invalidate_su_cache()
            return
    raise ValueError(f"SU {su_id} not found in sheet")


def full_sync(pgram_jobs: list[PgramJob], su_entries: list[SUEntry]):
    """Overwrite both sheets with current state, preserving manual SUs Closed counts."""
    if not is_available():
        raise RuntimeError("Google Sheets is unavailable")

    # Create sheets if missing; styling is applied AFTER the write so auto-resize has content
    pg_sheet_id, su_sheet_id = _ensure_sheets()

    # Read existing SUs Closed counts before clearing
    sus_closed_map: dict[str, int] = {}
    existing_pg = _read_range("Pgram Jobs!A:J")
    for row in existing_pg[1:]:
        while len(row) < PG_COLS:
            row.append("")
        job_id = row[PG_NUM]
        if job_id:
            try:
                sus_closed_map[job_id] = int(row[PG_SUS_CLOSED])
            except (ValueError, TypeError):
                sus_closed_map[job_id] = 0

    # Count SUs Open per job from the SU entries
    sus_open_map: dict[str, int] = {}
    for entry in su_entries:
        if entry.parent_job_id:
            sus_open_map[entry.parent_job_id] = sus_open_map.get(entry.parent_job_id, 0) + 1

    pgram_rows = [_pg_header()]
    for j in pgram_jobs:
        row = _job_to_row(
            j,
            sus_closed=sus_closed_map.get(j.job_id, 0),
            sus_open=sus_open_map.get(j.job_id, 0),
        )
        pgram_rows.append(row)

    su_rows = [_su_header()]
    for e in su_entries:
        su_rows.append(_su_to_row(e))

    svc = _get_service()
    sid = get_config().gsheets_spreadsheet_id
    svc.spreadsheets().values().clear(spreadsheetId=sid, range="Pgram Jobs!A:J").execute()
    svc.spreadsheets().values().clear(spreadsheetId=sid, range="SU Tracking!A:H").execute()
    _write_range("Pgram Jobs!A1", pgram_rows)
    _write_range("SU Tracking!A1", su_rows)

    # Apply formatting + checkboxes AFTER writing — auto-resize requires populated columns
    if pg_sheet_id:
        _apply_sheet_style(svc, sid, pg_sheet_id, PG_COLS)
    if su_sheet_id:
        _apply_sheet_style(svc, sid, su_sheet_id, SU_COLS)

    _invalidate_pgram_cache()
    _invalidate_su_cache()


def run_auth_flow():
    """
    Run the OAuth flow synchronously — call this BEFORE starting uvicorn
    so it doesn't block the event loop.
    """
    if not CREDENTIALS_PATH.exists():
        return
    if TOKEN_PATH.exists():
        return
    _get_service()


def init():
    """Call at startup to ensure sheets exist."""
    if is_available():
        try:
            _ensure_sheets()
        except Exception as e:
            _log_error(f"init failed: {e}")
