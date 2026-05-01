from datetime import datetime, timezone
from typing import Optional
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
    ("to_be_aligned", "to_overnight"): "Did the alignment script run successfully?",
    ("to_overnight", "processed"): "Did the overnight script run succeed?",
}


class PgramJob(BaseModel):
    job_id: str
    su_string: str
    trench: str
    stage: str
    notes_from_field: str = ""
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
    parent_job_id: str
    trench: str
    stage: str
    notes: str = ""
    last_updated: str = ""

    @classmethod
    def stage_label(cls, stage: str) -> str:
        labels = {
            "not_started": "Not Started",
            "volumetrics_created": "Volumetrics Created",
            "su_sheet_created": "SU Sheet Created",
            "uploaded_air": "Uploaded to AIR",
        }
        return labels.get(stage, stage)


class StageTransitionRequest(BaseModel):
    target_stage: str
    confirmed: bool = False


class CreatePgramJobRequest(BaseModel):
    job_id: str
    su_string: str = ""
    trench: str


class UpdateNotesRequest(BaseModel):
    notes: str


class CreateSUEntryRequest(BaseModel):
    su_id: str
    parent_job_id: str
    trench: str


def utcnow() -> str:
    dt = datetime.now(timezone.utc)
    return f"{dt.day} {dt.strftime('%b %Y, %H:%M')}"


TRENCHES = [
    "Trench 11000",
    "Trench 12000",
    "Trench 13000",
    "Trench 14000",
    "Trench 15000",
    "Trench 16000",
    "Trench 17000",
    "Trench 18000",
    "Trench 19000",
]
