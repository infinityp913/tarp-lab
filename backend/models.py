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
    ("to_be_aligned", "to_overnight"): "This will move the job folder to 'to_overnight'. It does not run the alignment script — you will need to run it manually.",
    ("to_overnight", "processed"): "This will move the job folder to 'processed'. It does not run the overnight script — you will need to run it manually.",
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


TRENCHES = [
    "Trench 20000",
    "Trench 21000",
    "Trench 22000",
    "Trench 23000",
    "Trench 24000",
]
