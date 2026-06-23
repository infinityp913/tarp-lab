from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo
from pydantic import BaseModel

PGRAM_STAGES = [
    "to_be_processed",
    "to_be_aligned",
    "to_overnight",
    "processed",
    "uploaded_air",
]

SU_STAGES = [
    "not_started",
    "volumetrics_created",
    "su_sheet_created",
    "uploaded_air",
]

FILESYSTEM_STAGES = {"to_be_processed", "to_be_aligned", "to_overnight", "processed", "uploaded_air"}

TRANSITION_DIALOGS: dict[tuple[str, str], str] = {
    ("to_be_aligned", "to_overnight"): "This only moves the job folder to 'To Overnight'. It does NOT run the alignment script — use the 'Run Alignment' button between the columns for that.",
    ("to_overnight", "processed"): "This only moves the job folder to 'Processed'. It does NOT run the overnight script — use the 'Run Overnight' button between the columns for that.",
}


class PgramJob(BaseModel):
    job_id: str
    su_string: str
    trench: str
    stage: str
    notes: str = ""           # lab-entered notes (stored in TARP Lab Pgram Tracking)
    notes_from_field: str = ""  # pulled from TARP Field Pgram Tracking (read-only in lab)
    sus_opened: str = ""      # pulled from TARP Field Pgram Tracking (read-only in lab)
    sus_closed: str = ""      # pulled from TARP Field Pgram Tracking (read-only in lab)
    last_updated: str = ""

    @classmethod
    def stage_label(cls, stage: str) -> str:
        labels = {
            "to_be_processed": "To Be Processed",
            "to_be_aligned": "To Be Aligned",
            "to_overnight": "To Overnight",
            "processed": "Processed",
            "uploaded_air": "Uploaded to AIR",
        }
        return labels.get(stage, stage)

    @property
    def numeric_id(self) -> int:
        parts = self.job_id.split("_")
        for p in parts:
            if p.isdigit():
                return int(p)
        return 0


class SUEntry(BaseModel):
    su_id: str
    top_pgram: str = ""
    bot_pgram: str = ""
    trench: str
    stage: str
    notes: str = ""
    last_updated: str = ""

    @classmethod
    def stage_label(cls, stage: str) -> str:
        labels = {
            "not_started": "Not Started",
            "volumetrics_created": "Volume Created",
            "su_sheet_created": "SU Sheet Created",
            "uploaded_air": "Uploaded to AIR",
        }
        return labels.get(stage, stage)


class StageTransitionRequest(BaseModel):
    target_stage: str
    confirmed: bool = False


class BatchMoveRequest(BaseModel):
    from_stage: str
    to_stage: str


class IgnoredFolder(BaseModel):
    name: str
    stage: str
    parent: str = ""  # empty for top-level; "Trench XXX" if nested


class CreatePgramJobRequest(BaseModel):
    job_id: str
    su_string: str = ""
    trench: str


class UpdateNotesRequest(BaseModel):
    notes: str


class UpdateSUPgramsRequest(BaseModel):
    top_pgram: str = ""
    bot_pgram: str = ""


class CreateSUEntryRequest(BaseModel):
    su_id: str
    top_pgram: str = ""
    bot_pgram: str = ""
    trench: str


def cet_now() -> str:
    dt = datetime.now(ZoneInfo("Europe/Rome"))
    return f"{dt.day} {dt.strftime('%b %Y, %H:%M')}"


def expand_su_range(su_string: str) -> list[str]:
    """Expand SU range strings to a flat list of SU ID strings.

    Handles:
      "21015-17"        → ["21015", "21016", "21017"]  (compact suffix range)
      "21015-21017"     → ["21015", "21016", "21017"]  (full range)
      "21015, 21020"    → ["21015", "21020"]            (comma list)
      "SU21015"         → ["21015"]                    (SU prefix stripped)
      mixed of the above
    """
    results: list[str] = []
    for segment in su_string.replace(";", ",").split(","):
        segment = segment.strip()
        if segment.upper().startswith("SU"):
            segment = segment[2:].strip()
        if not segment:
            continue
        if "-" in segment:
            parts = segment.split("-", 1)
            start_str, end_str = parts[0].strip(), parts[1].strip()
            if start_str.isdigit() and end_str.isdigit():
                start = int(start_str)
                if len(end_str) < len(start_str):
                    # Compact range: "21015-17" → prefix "210", end 17 → 21017
                    prefix = start_str[: len(start_str) - len(end_str)]
                    end = int(prefix + end_str)
                else:
                    end = int(end_str)
                results.extend(str(n) for n in range(start, end + 1))
        elif segment.isdigit():
            results.append(segment)
    return results


def trench_from_su_id(su_id: str) -> str:
    """Infer trench number string from SU ID. '21015' → '21000'."""
    try:
        n = int(su_id)
        return str((n // 1000) * 1000)
    except ValueError:
        return ""


TRENCHES = [
    "Trench 20000",
    "Trench 21000",
    "Trench 22000",
    "Trench 23000",
    "Trench 24000",
]
