"""
Google Sheets service — single source of truth for non-filesystem-backed state.

TARP Lab Pgram Tracking columns (0-indexed, lab-owned, written by lab sync):
  0  Pgram Number        ← integer only (e.g. 696)
  1  Trench
  2  Photos—No Alignment ← TRUE when stage >= to_be_aligned
  3  Alignment+Manual    ← TRUE when stage >= to_overnight
  4  Overnight Completed ← TRUE when stage >= processed
  5  Uploaded to AIR     ← TRUE when stage == uploaded_air
  6  Notes               ← lab-entered notes (editable in lab UI)
  7  Last Updated (CET)

TARP Field Pgram Tracking columns (0-indexed, field-owned, read-only from lab):
  0  Pgram Number
  1  SUs Opened          ← from field UI
  2  SUs Closed          ← from field UI
  3  Field Notes         ← from field UI
  4  Field Stage         ← not_started / aligned / move_to_msi
  5  Last Updated (CET)

SU Trench tabs (one per trench: Trench 20000 … Trench 24000) columns (0-indexed):
  0  SU ID
  1  Top Pgram           ← integer pgram number
  2  Bottom Pgram        ← integer pgram number
  3  Volumetrics Created ← TRUE when stage >= volumetrics_created
  4  SU Sheet Created    ← TRUE when stage >= su_sheet_created
  5  Uploaded to AIR     ← TRUE when stage == uploaded_air
  6  Notes
  7  Last Updated (CET)
"""

import logging
import random
import threading
import time
from typing import Optional

from backend.config import CREDENTIALS_PATH, TOKEN_DIR, TOKEN_PATH, LOG_PATH, get_config
from backend.models import PgramJob, SUEntry, PGRAM_STAGES, SU_STAGES, cet_now

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
_CACHE_TTL = 30       # seconds — pgram cache (field data freshness)
_SU_CACHE_TTL = 300   # seconds — SU cache (invalidated on every mutation anyway)

_pgram_cache: list[dict] = []
_su_cache: list[dict] = []
_pgram_cache_time: float = 0
_su_cache_time: float = 0
_cache_lock = threading.Lock()
# httplib2 connection pool is not thread-safe — all .execute() calls must be serialized
_api_lock = threading.Lock()
_gsheets_available = True
_service = None
_creds = None  # Cached credentials — kept to detect mid-session revocation

# Sheet names
_LAB_PGRAM_SHEET = "TARP Lab Pgram Tracking"
_FIELD_PGRAM_SHEET = "TARP Field Pgram Tracking"

# Column indices — TARP Lab Pgram Tracking
PG_NUM = 0
PG_TRENCH = 1
PG_PHOTOS = 2
PG_ALIGN = 3
PG_OVERNIGHT = 4
PG_AIR = 5
PG_NOTES = 6
PG_UPDATED = 7
PG_COLS = 8

# Column indices — TARP Field Pgram Tracking (read-only from lab)
FP_NUM = 0
FP_SUS_OPENED = 1
FP_SUS_CLOSED = 2
FP_NOTES = 3
FP_STAGE = 4
FP_UPDATED = 5
FP_COLS = 6

# Column indices — SU Trench tabs (no Trench column; trench is implicit in the tab)
SU_ID = 0
SU_TOP_PGRAM = 1
SU_BOT_PGRAM = 2
SU_VOL = 3
SU_SHEET = 4
SU_AIR = 5
SU_NOTES = 6
SU_UPDATED = 7
SU_COLS = 8

# The five trench-specific SU tabs
_SU_TRENCH_TABS = [
    "Trench 20000",
    "Trench 21000",
    "Trench 22000",
    "Trench 23000",
    "Trench 24000",
]

_PGRAM_STAGE_ORDER = {s: i for i, s in enumerate(PGRAM_STAGES)}
_SU_STAGE_ORDER = {s: i for i, s in enumerate(SU_STAGES)}

# Dark green header — R:46 G:92 B:40
_HEADER_R = 46 / 255
_HEADER_G = 92 / 255
_HEADER_B = 40 / 255


def _execute(request, num_retries: int = 0):
    """Run a Sheets API request under the serialization lock."""
    with _api_lock:
        return request.execute(num_retries=num_retries)


def _log_error(msg: str):
    logger.error(msg)
    try:
        with open(LOG_PATH, "a") as f:
            f.write(f"ERROR {msg}\n")
    except OSError:
        pass


def _save_token(creds) -> None:
    import os as _os
    fd = _os.open(str(TOKEN_PATH), _os.O_WRONLY | _os.O_CREAT | _os.O_TRUNC, 0o600)
    with _os.fdopen(fd, "w") as token:
        token.write(creds.to_json())


def _get_service():
    global _service, _creds, _gsheets_available

    # Fast path: cached service — check creds are still valid before returning.
    if _service is not None and _creds is not None:
        if _creds.valid:
            return _service
        # Expired but refreshable — try a silent refresh.
        if _creds.expired and _creds.refresh_token:
            try:
                from google.auth.transport.requests import Request
                _creds.refresh(Request())
                _save_token(_creds)
                return _service  # Same service object; creds mutated in-place.
            except Exception as e:
                # Revoked or network error — reset so status endpoint detects it.
                _gsheets_available = False
                _service = None
                _creds = None
                _log_error(f"Token refresh failed (likely revoked): {e}")
                return None
        # No refresh_token and creds not valid — need full re-auth.
        _gsheets_available = False
        _service = None
        _creds = None
        return None

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
            _save_token(creds)

        _creds = creds
        _service = build("sheets", "v4", credentials=creds)
        _gsheets_available = True
        return _service

    except Exception as e:
        _gsheets_available = False
        _service = None
        _creds = None
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


def _trench_tab(trench: str) -> str:
    """Convert trench string to tab name 'Trench 21000'. Accepts '21000' or 'Trench 21000'."""
    t = trench.strip()
    if t.startswith("Trench "):
        return t
    return f"Trench {t}"


def _trench_from_su_id(su_id: str) -> str:
    """Infer trench from SU ID like '21012' → '21000'."""
    try:
        n = int(su_id)
        return str((n // 1000) * 1000)
    except ValueError:
        return ""


def _ensure_sheets() -> tuple[int, dict[str, int]]:
    """Create TARP Lab Pgram Tracking and the 5 SU trench tabs if needed.
    Returns (pg_sheet_id, trench_tab_ids)."""
    svc = _get_service()
    if svc is None:
        return 0, {}
    sid = get_config().gsheets_spreadsheet_id
    try:
        meta = _execute(svc.spreadsheets().get(spreadsheetId=sid))
        existing = {s["properties"]["title"]: s["properties"]["sheetId"]
                    for s in meta.get("sheets", [])}

        required = [_LAB_PGRAM_SHEET] + _SU_TRENCH_TABS
        add_requests = [
            {"addSheet": {"properties": {"title": t}}}
            for t in required if t not in existing
        ]

        if add_requests:
            _execute(svc.spreadsheets().batchUpdate(
                spreadsheetId=sid, body={"requests": add_requests}
            ))
            meta = _execute(svc.spreadsheets().get(spreadsheetId=sid))
            existing = {s["properties"]["title"]: s["properties"]["sheetId"]
                        for s in meta.get("sheets", [])}

        trench_tab_ids = {tab: existing.get(tab, 0) for tab in _SU_TRENCH_TABS}
        return existing.get(_LAB_PGRAM_SHEET, 0), trench_tab_ids

    except Exception as e:
        _log_error(f"_ensure_sheets failed: {e}")
        return 0, {}


def _apply_sheet_style(svc, sid: str, sheet_id: int, num_cols: int, bool_cols: list[int]):
    """Dark green header, frozen row 1, checkbox validation."""
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
                "rule": {"condition": {"type": "BOOLEAN"}, "showCustomUi": True},
            }
        })
    try:
        _execute(svc.spreadsheets().batchUpdate(
            spreadsheetId=sid, body={"requests": fmt_requests}
        ))
    except Exception as e:
        _log_error(f"_apply_sheet_style (format+validation) failed: {e}")

    try:
        _execute(svc.spreadsheets().batchUpdate(
            spreadsheetId=sid,
            body={"requests": [{
                "autoResizeDimensions": {
                    "dimensions": {"sheetId": sheet_id, "dimension": "COLUMNS",
                                   "startIndex": 0, "endIndex": num_cols}
                }
            }]},
        ))
    except Exception as e:
        _log_error(f"_apply_sheet_style (auto-resize) failed (non-fatal): {e}")


def _read_range(range_name: str) -> Optional[list[list]]:
    svc = _get_service()
    if svc is None:
        return None
    sid = get_config().gsheets_spreadsheet_id
    try:
        result = _execute(
            svc.spreadsheets().values().get(spreadsheetId=sid, range=range_name),
            num_retries=2,
        )
        return result.get("values", [])
    except Exception as e:
        _log_error(f"_read_range({range_name}) failed: {e}")
        return None


def _write_range(range_name: str, values: list[list]):
    svc = _get_service()
    if svc is None:
        return
    sid = get_config().gsheets_spreadsheet_id
    try:
        _execute(svc.spreadsheets().values().update(
            spreadsheetId=sid,
            range=range_name,
            valueInputOption="RAW",
            body={"values": values},
        ))
    except Exception as e:
        _log_error(f"_write_range({range_name}) failed: {e}")
        raise


def _append_row(sheet: str, row: list):
    svc = _get_service()
    if svc is None:
        return
    sid = get_config().gsheets_spreadsheet_id
    try:
        _execute(svc.spreadsheets().values().append(
            spreadsheetId=sid,
            range=f"{sheet}!A1",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        ))
    except Exception as e:
        _log_error(f"_append_row({sheet}) failed: {e}")
        raise


def _pg_header() -> list:
    return [
        "Pgram Number", "Trench",
        "Photos—No Alignment", "Alignment+Manual Check",
        "Overnight Completed", "Uploaded to AIR",
        "Notes", "Last Updated (CET)",
    ]


def _su_header() -> list:
    return [
        "SU ID", "Top Pgram", "Bottom Pgram",
        "Volumetrics Created", "SU Sheet Created",
        "Uploaded to AIR",
        "Notes", "Last Updated (CET)",
    ]


def _pg_num_str(job_id: str) -> str:
    """Extract just the digits from a job_id: 'Pgram_Job_696' → '696'."""
    for p in str(job_id).split("_"):
        if p.isdigit():
            return p
    return str(job_id)


def _job_to_row(job: PgramJob) -> list:
    """Row for TARP Lab Pgram Tracking — lab-owned columns only."""
    photos, align, overnight, air = _pgram_checkboxes(job.stage)
    return [
        job.numeric_id,
        job.trench,
        photos,
        align,
        overnight,
        air,
        job.notes,
        cet_now(),
    ]


def _su_to_row(entry: SUEntry) -> list:
    """Row for a trench-specific SU tab — no Trench column."""
    vol, sheet, air = _su_checkboxes(entry.stage)
    top = int(entry.top_pgram) if str(entry.top_pgram).isdigit() else entry.top_pgram
    bot = int(entry.bot_pgram) if str(entry.bot_pgram).isdigit() else entry.bot_pgram
    return [
        entry.su_id,
        top,
        bot,
        vol,
        sheet,
        air,
        entry.notes,
        cet_now(),
    ]


def _rows_to_pgram(rows: list[list]) -> list[dict]:
    """Parse TARP Lab Pgram Tracking rows. Field data (sus_opened, notes_from_field) is merged later."""
    result = []
    for row in rows[1:]:
        if not row:
            continue
        while len(row) < PG_COLS:
            row.append("")
        if not row[PG_NUM]:
            continue
        raw = str(row[PG_NUM])
        job_id = f"Pgram_Job_{raw}" if raw.isdigit() else raw
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
            "job_id": job_id,
            "su_string": "",
            "trench": row[PG_TRENCH],
            "stage": stage,
            "notes": notes,
            "notes_from_field": "",
            "sus_opened": "",
            "sus_closed": "",
            "last_updated": row[PG_UPDATED],
        })
    return result


def _read_field_pgram_map() -> dict[str, dict]:
    """Read TARP Field Pgram Tracking and return dict keyed by pgram number string.
    Returns empty dict if the sheet doesn't exist or can't be read."""
    rows = _read_range(f"{_FIELD_PGRAM_SHEET}!A:F")
    if not rows:
        return {}
    result: dict[str, dict] = {}
    for row in rows[1:]:
        if not row:
            continue
        while len(row) < FP_COLS:
            row.append("")
        if not row[FP_NUM]:
            continue
        num = _pg_num_str(str(row[FP_NUM]))
        result[num] = {
            "sus_opened": str(row[FP_SUS_OPENED]),
            "sus_closed": str(row[FP_SUS_CLOSED]),
            "notes_from_field": str(row[FP_NOTES]),
        }
    return result


def _rows_to_su(rows: list[list], trench: str) -> list[dict]:
    """Parse rows from a trench-specific tab. trench is injected from the tab name."""
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
            "top_pgram": str(row[SU_TOP_PGRAM]),
            "bot_pgram": str(row[SU_BOT_PGRAM]),
            "trench": trench,
            "stage": stage,
            "notes": notes,
            "last_updated": row[SU_UPDATED],
        })
    return result


def get_pgram_rows() -> list[dict]:
    """Read TARP Lab Pgram Tracking and merge field data from TARP Field Pgram Tracking."""
    global _pgram_cache, _pgram_cache_time
    with _cache_lock:
        if time.time() - _pgram_cache_time < _CACHE_TTL:
            return list(_pgram_cache)

    if not is_available():
        return []

    rows = _read_range(f"{_LAB_PGRAM_SHEET}!A:H")
    if rows is None:
        logger.warning("get_pgram_rows: lab sheet read failed — returning stale cache")
        with _cache_lock:
            return list(_pgram_cache)

    data = _rows_to_pgram(rows)

    # Merge field data (best-effort — don't fail if field sheet is absent)
    field_map = _read_field_pgram_map()
    if field_map:
        for row in data:
            num = _pg_num_str(row["job_id"])
            field = field_map.get(num, {})
            row["sus_opened"] = field.get("sus_opened", "")
            row["sus_closed"] = field.get("sus_closed", "")
            row["notes_from_field"] = field.get("notes_from_field", "")

    with _cache_lock:
        _pgram_cache = data
        _pgram_cache_time = time.time()
    return data


def get_su_rows() -> list[dict]:
    """Read all 5 trench tabs and return a combined flat list."""
    global _su_cache, _su_cache_time
    with _cache_lock:
        if time.time() - _su_cache_time < _SU_CACHE_TTL:
            return list(_su_cache)

    if not is_available():
        return []

    combined: list[dict] = []
    failed = False
    for tab in _SU_TRENCH_TABS:
        trench = tab.replace("Trench ", "")
        rows = _read_range(f"{tab}!A:H")
        if rows is None:
            logger.warning(f"get_su_rows: read failed for {tab} — returning stale cache")
            failed = True
            break
        combined.extend(_rows_to_su(rows, trench))

    if failed:
        with _cache_lock:
            return list(_su_cache)

    with _cache_lock:
        _su_cache = combined
        _su_cache_time = time.time()
    return combined


def invalidate_pgram_cache():
    """Public alias — used by the pull endpoint to force a fresh field data read."""
    _invalidate_pgram_cache()


def _invalidate_pgram_cache():
    with _cache_lock:
        global _pgram_cache_time
        _pgram_cache_time = 0


def _invalidate_su_cache():
    with _cache_lock:
        global _su_cache_time
        _su_cache_time = 0


def upsert_pgram(job: PgramJob):
    """Write or update a row in TARP Lab Pgram Tracking (lab columns only)."""
    if not is_available():
        return
    rows = _read_range(f"{_LAB_PGRAM_SHEET}!A:H")
    if rows is None:
        raise RuntimeError("Google Sheets read failed during upsert_pgram")
    data = rows[1:] if len(rows) > 1 else []
    new_row = _job_to_row(job)
    job_num = _pg_num_str(job.job_id)

    for i, row in enumerate(data):
        while len(row) < PG_COLS:
            row.append("")
        if _pg_num_str(str(row[PG_NUM])) == job_num:
            if not job.notes and row[PG_NOTES]:
                new_row[PG_NOTES] = row[PG_NOTES]
            _write_range(f"{_LAB_PGRAM_SHEET}!A{i + 2}:H{i + 2}", [new_row])
            _invalidate_pgram_cache()
            return

    _append_row(_LAB_PGRAM_SHEET, new_row)
    _invalidate_pgram_cache()


def update_pgram_stage(job_id: str, stage: str):
    if not is_available():
        return
    rows = _read_range(f"{_LAB_PGRAM_SHEET}!A:H")
    if rows is None:
        raise RuntimeError("Google Sheets read failed during update_pgram_stage")
    photos, align, overnight, air = _pgram_checkboxes(stage)
    job_num = _pg_num_str(job_id)
    for i, row in enumerate(rows[1:], start=2):
        if row and _pg_num_str(str(row[0])) == job_num:
            while len(row) < PG_COLS:
                row.append("")
            # Columns C-H: photos(C=2), align(D=3), overnight(E=4), air(F=5), notes(G=6), updated(H=7)
            _write_range(
                f"{_LAB_PGRAM_SHEET}!C{i}:H{i}",
                [[photos, align, overnight, air,
                  row[PG_NOTES] if len(row) > PG_NOTES else "", cet_now()]],
            )
            _invalidate_pgram_cache()
            return
    new_row = _job_to_row(PgramJob(job_id=job_id, su_string="", trench="", stage=stage))
    _append_row(_LAB_PGRAM_SHEET, new_row)
    _invalidate_pgram_cache()


def update_pgram_notes(job_id: str, notes: str):
    if not is_available():
        raise RuntimeError("Google Sheets is unavailable")
    rows = _read_range(f"{_LAB_PGRAM_SHEET}!A:H")
    if rows is None:
        raise RuntimeError("Google Sheets read timed out")
    job_num = _pg_num_str(job_id)
    for i, row in enumerate(rows[1:], start=2):
        if row and _pg_num_str(str(row[0])) == job_num:
            # Columns G-H: notes(G=6), updated(H=7)
            _write_range(f"{_LAB_PGRAM_SHEET}!G{i}:H{i}", [[notes, cet_now()]])
            _invalidate_pgram_cache()
            return
    raise ValueError(f"Job {job_id} not found in {_LAB_PGRAM_SHEET}")


def _su_tab_for(su_id: str, trench: str = "") -> str:
    if trench:
        return _trench_tab(trench)
    inferred = _trench_from_su_id(su_id)
    if inferred:
        return _trench_tab(inferred)
    return ""


def upsert_su(entry: SUEntry):
    if not is_available():
        return
    tab = _su_tab_for(entry.su_id, entry.trench)
    if not tab:
        _log_error(f"upsert_su: cannot determine tab for SU {entry.su_id}")
        return
    rows = _read_range(f"{tab}!A:H")
    if rows is None:
        raise RuntimeError(f"Google Sheets read failed during upsert_su ({tab})")
    data = rows[1:] if len(rows) > 1 else []
    new_row = _su_to_row(entry)

    for i, row in enumerate(data):
        while len(row) < SU_COLS:
            row.append("")
        if row[SU_ID] == entry.su_id:
            _write_range(f"{tab}!A{i + 2}:H{i + 2}", [new_row])
            _invalidate_su_cache()
            return

    _append_row(tab, new_row)
    _invalidate_su_cache()


def update_su_stage(su_id: str, stage: str):
    if not is_available():
        raise RuntimeError("Google Sheets is unavailable")
    tab = _su_tab_for(su_id)
    if not tab:
        raise ValueError(f"Cannot determine trench tab for SU {su_id}")
    rows = _read_range(f"{tab}!A:H")
    if rows is None:
        raise RuntimeError("Google Sheets read timed out")
    vol, sheet, air = _su_checkboxes(stage)
    for i, row in enumerate(rows[1:], start=2):
        if row and row[0] == su_id:
            while len(row) < SU_COLS:
                row.append("")
            _write_range(
                f"{tab}!D{i}:H{i}",
                [[vol, sheet, air,
                  row[SU_NOTES] if len(row) > SU_NOTES else "", cet_now()]],
            )
            _invalidate_su_cache()
            return
    raise ValueError(f"SU {su_id} not found in {tab}")


def update_su_pgrams(su_id: str, top_pgram: str, bot_pgram: str):
    if not is_available():
        raise RuntimeError("Google Sheets is unavailable")
    tab = _su_tab_for(su_id)
    if not tab:
        raise ValueError(f"Cannot determine trench tab for SU {su_id}")
    rows = _read_range(f"{tab}!A:H")
    if rows is None:
        raise RuntimeError("Google Sheets read timed out")
    top = int(top_pgram) if str(top_pgram).isdigit() else (top_pgram or "")
    bot = int(bot_pgram) if str(bot_pgram).isdigit() else (bot_pgram or "")
    for i, row in enumerate(rows[1:], start=2):
        if row and row[0] == su_id:
            _write_range(f"{tab}!B{i}:C{i}", [[top, bot]])
            _invalidate_su_cache()
            return
    raise ValueError(f"SU {su_id} not found in {tab}")


def update_su_notes(su_id: str, notes: str):
    if not is_available():
        raise RuntimeError("Google Sheets is unavailable")
    tab = _su_tab_for(su_id)
    if not tab:
        raise ValueError(f"Cannot determine trench tab for SU {su_id}")
    rows = _read_range(f"{tab}!A:H")
    if rows is None:
        raise RuntimeError("Google Sheets read timed out")
    for i, row in enumerate(rows[1:], start=2):
        if row and row[0] == su_id:
            _write_range(f"{tab}!G{i}:H{i}", [[notes, cet_now()]])
            _invalidate_su_cache()
            return
    raise ValueError(f"SU {su_id} not found in {tab}")


def full_sync(pgram_jobs: list[PgramJob], su_entries: list[SUEntry]):
    """Overwrite TARP Lab Pgram Tracking and all SU trench tabs.

    Also reads TARP Field Pgram Tracking to populate field data in the cache.
    Does NOT write to TARP Field Pgram Tracking.

    A random 0–3 s jitter at the start reduces collision risk with concurrent syncs.
    """
    if not is_available():
        raise RuntimeError("Google Sheets is unavailable")

    time.sleep(random.uniform(0, 3))

    pg_sheet_id, trench_tab_ids = _ensure_sheets()

    pgram_rows = [_pg_header()]
    for j in pgram_jobs:
        pgram_rows.append(_job_to_row(j))

    svc = _get_service()
    sid = get_config().gsheets_spreadsheet_id

    # Write lab pgram sheet directly
    _execute(svc.spreadsheets().values().clear(spreadsheetId=sid, range=f"{_LAB_PGRAM_SHEET}!A:H"))
    _write_range(f"{_LAB_PGRAM_SHEET}!A1", pgram_rows)

    if pg_sheet_id:
        _apply_sheet_style(svc, sid, pg_sheet_id, PG_COLS, [PG_PHOTOS, PG_ALIGN, PG_OVERNIGHT, PG_AIR])

    # Write SU trench tabs directly (no staging)
    entries_by_trench: dict[str, list[SUEntry]] = {
        tab.replace("Trench ", ""): [] for tab in _SU_TRENCH_TABS
    }
    for entry in su_entries:
        if entry.trench in entries_by_trench:
            entries_by_trench[entry.trench].append(entry)

    for tab in _SU_TRENCH_TABS:
        trench = tab.replace("Trench ", "")
        entries = entries_by_trench.get(trench, [])
        su_rows = [_su_header()] + [_su_to_row(e) for e in entries]
        _execute(svc.spreadsheets().values().clear(spreadsheetId=sid, range=f"{tab}!A:H"))
        _write_range(f"{tab}!A1", su_rows)
        tab_id = trench_tab_ids.get(tab, 0)
        if tab_id:
            _apply_sheet_style(svc, sid, tab_id, SU_COLS, [SU_VOL, SU_SHEET, SU_AIR])

    _invalidate_pgram_cache()
    _invalidate_su_cache()


def run_auth_flow():
    """Delete stale token and run the OAuth browser flow."""
    global _service, _creds, _gsheets_available
    if not CREDENTIALS_PATH.exists():
        return
    if TOKEN_PATH.exists():
        TOKEN_PATH.unlink()
    _service = None
    _creds = None
    _gsheets_available = True
    _get_service()


def init():
    if is_available():
        try:
            _ensure_sheets()
        except Exception as e:
            _log_error(f"init failed: {e}")


def warm_cache():
    """Pre-populate in-memory caches. Intended to run in a background thread at startup."""
    if not is_available():
        return
    try:
        get_pgram_rows()
    except Exception as e:
        _log_error(f"warm_cache: pgram read failed: {e}")
    try:
        get_su_rows()
    except Exception as e:
        _log_error(f"warm_cache: SU read failed: {e}")
