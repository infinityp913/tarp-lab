"""Tests for backend/services/volume.py — volume card provisioning from PLY files."""
import pytest

from backend.models import PgramJob
from backend.services import volume


def _job(num: str, su_string: str, stage: str = "processed") -> PgramJob:
    return PgramJob(
        job_id=f"Pgram_Job_{num}",
        su_string=su_string,
        trench="",
        stage=stage,
        last_updated="",
    )


@pytest.fixture
def patch_sources(monkeypatch):
    """Patch the data sources provision_from_ply reads, capturing upserts in-memory."""
    upserted = []

    def setup(*, ply_files, jobs, su_rows, field_map):
        monkeypatch.setattr(volume, "scan_ply_files", lambda: ply_files)
        monkeypatch.setattr(volume, "scan_filesystem", lambda: jobs)
        monkeypatch.setattr(volume.gsheets, "get_su_rows", lambda: su_rows)
        monkeypatch.setattr(volume.gsheets, "get_field_pgram_map", lambda: field_map)
        monkeypatch.setattr(volume.gsheets, "upsert_su", lambda entry: upserted.append(entry))
        return upserted

    return setup


def test_provisions_from_folder_su_string_when_field_empty(patch_sources):
    """The overnight-failure case: field sus_opened is empty, SUs come from the job folder."""
    upserted = patch_sources(
        ply_files=[{"pgram_num": 830, "filename": "Pgram_Job_830.ply", "path": "x"}],
        jobs=[_job("830", "SU23015-23016")],
        su_rows=[],
        field_map={"830": {"sus_opened": "", "sus_closed": ""}},
    )

    result = volume.provision_from_ply()

    su_ids = sorted(e.su_id for e in upserted)
    assert su_ids == ["23015", "23016"]
    assert all(e.stage == "not_started" for e in upserted)
    assert all(e.top_pgram == "830" for e in upserted)
    assert len(result["created"]) == 2


def test_folder_underscore_separated_sus_expand(patch_sources):
    """Multi-SU folders separate SUs with '_' (SU22003_22090_…)."""
    upserted = patch_sources(
        ply_files=[{"pgram_num": 827, "filename": "Pgram_Job_827.ply", "path": "x"}],
        jobs=[_job("827", "SU22003_22090_22091")],
        su_rows=[],
        field_map={},
    )

    volume.provision_from_ply()

    assert sorted(e.su_id for e in upserted) == ["22003", "22090", "22091"]


def test_skips_su_already_in_sheet(patch_sources):
    upserted = patch_sources(
        ply_files=[{"pgram_num": 828, "filename": "Pgram_Job_828.ply", "path": "x"}],
        jobs=[_job("828", "SU21068")],
        su_rows=[{"su_id": "21068"}],
        field_map={},
    )

    result = volume.provision_from_ply()

    assert upserted == []
    assert result["created"] == []
    assert any(s.get("su_id") == "21068" for s in result["skipped"])


def test_skips_pgram_with_no_su_source(patch_sources):
    upserted = patch_sources(
        ply_files=[{"pgram_num": 999, "filename": "Pgram_Job_999.ply", "path": "x"}],
        jobs=[_job("999", "")],  # in processed, but no SU string to draw from
        su_rows=[],
        field_map={},
    )

    result = volume.provision_from_ply()

    assert upserted == []
    assert result["skipped"][0]["reason"] == "no SUs in job folder or field tracking"


def test_skips_pgram_whose_folder_left_processed(patch_sources):
    """A lingering PLY whose job folder is no longer in processed must not create cards."""
    upserted = patch_sources(
        ply_files=[{"pgram_num": 811, "filename": "Pgram_Job_811.ply", "path": "x"}],
        jobs=[_job("811", "SU20001", stage="to_overnight")],  # moved back out of processed
        su_rows=[],
        field_map={},
    )

    result = volume.provision_from_ply()

    assert upserted == []
    assert result["created"] == []
    assert result["skipped"][0]["reason"] == "job folder not in processed stage"


def test_annotate_readiness(monkeypatch):
    """A card is ready only when BOTH pgrams have a PLY AND the SU has a USDZ scan."""
    monkeypatch.setattr(volume, "scan_ply_files", lambda: [
        {"pgram_num": 100, "filename": "Pgram_Job_100.ply", "path": "x"},
        {"pgram_num": 200, "filename": "Pgram_Job_200.ply", "path": "x"},
    ])
    monkeypatch.setattr(volume, "usdz_su_nums", lambda: {"1", "2", "3", "4", "5"})

    rows = [
        {"su_id": "1", "top_pgram": "100", "bot_pgram": "200"},  # both processed + scan → ready
        {"su_id": "2", "top_pgram": "100", "bot_pgram": "999"},  # bot has no PLY
        {"su_id": "3", "top_pgram": "100", "bot_pgram": ""},     # bot unknown
        {"su_id": "4", "top_pgram": "", "bot_pgram": "200"},     # top unknown
        {"su_id": "5", "top_pgram": "abc", "bot_pgram": "200"},  # top not numeric
    ]

    out = volume.annotate_readiness(rows)

    assert [r["ready"] for r in out] == [True, False, False, False, False]
    # Source rows are not mutated.
    assert "ready" not in rows[0]


def test_annotate_readiness_requires_usdz_scan(monkeypatch):
    """A card with both PLYs but no matching USDZ scan is not ready."""
    monkeypatch.setattr(volume, "scan_ply_files", lambda: [
        {"pgram_num": 100, "filename": "Pgram_Job_100.ply", "path": "x"},
        {"pgram_num": 200, "filename": "Pgram_Job_200.ply", "path": "x"},
    ])
    monkeypatch.setattr(volume, "usdz_su_nums", lambda: {"1"})

    rows = [
        {"su_id": "1", "top_pgram": "100", "bot_pgram": "200"},  # has scan → ready
        {"su_id": "2", "top_pgram": "100", "bot_pgram": "200"},  # no scan → not ready
    ]

    out = volume.annotate_readiness(rows)

    assert [r["ready"] for r in out] == [True, False]
    # has_lidar reflects scan presence independent of PLY/pgram readiness.
    assert [r["has_lidar"] for r in out] == [True, False]


def test_field_and_folder_sources_union(patch_sources):
    """Field sus_opened and folder su_string both contribute, de-duplicated."""
    upserted = patch_sources(
        ply_files=[{"pgram_num": 700, "filename": "Pgram_Job_700.ply", "path": "x"}],
        jobs=[_job("700", "SU20001")],
        su_rows=[],
        field_map={"700": {"sus_opened": "20001, 20002", "sus_closed": ""}},
    )

    volume.provision_from_ply()

    assert sorted(e.su_id for e in upserted) == ["20001", "20002"]


@pytest.fixture
def patch_deprovision(monkeypatch):
    """Patch the sources deprovision_orphaned_cards reads, capturing sheet mutations.

    `processed` is the list of pgram numbers whose job folder is in the processed
    stage on disk; each becomes a scan_filesystem() job at stage 'processed'.
    """
    def setup(*, processed, su_rows, scan_empty=False):
        deleted = []
        cleared = []
        jobs = [] if scan_empty else [_job(str(n), "") for n in processed]
        monkeypatch.setattr(volume, "scan_filesystem", lambda: jobs)
        monkeypatch.setattr(volume.gsheets, "get_su_rows", lambda: su_rows)
        monkeypatch.setattr(
            volume.gsheets, "delete_su",
            lambda su_id, trench="": deleted.append(su_id) or True,
        )
        monkeypatch.setattr(
            volume.gsheets, "update_su_pgrams",
            lambda su_id, top, bot: cleared.append((su_id, top, bot)),
        )
        return deleted, cleared

    return setup


def test_deprovision_removes_card_when_top_pgram_left_processed(patch_deprovision):
    """A card whose top pgram folder left 'processed' is deleted entirely."""
    deleted, cleared = patch_deprovision(
        processed=[700],  # 811 was moved out of processed
        su_rows=[{"su_id": "20001", "top_pgram": "811", "bot_pgram": "700", "trench": "20000"}],
    )

    result = volume.deprovision_orphaned_cards()

    assert deleted == ["20001"]
    assert cleared == []  # top-gone short-circuits before the bottom check
    assert result["removed"] == [{"su_id": "20001", "top_pgram": "811"}]


def test_deprovision_clears_bottom_when_bot_pgram_left_processed(patch_deprovision):
    """A card whose bottom pgram folder left 'processed' keeps the card but clears the bottom."""
    deleted, cleared = patch_deprovision(
        processed=[700],  # 811 was moved out of processed
        su_rows=[{"su_id": "20001", "top_pgram": "700", "bot_pgram": "811", "trench": "20000"}],
    )

    result = volume.deprovision_orphaned_cards()

    assert deleted == []
    assert cleared == [("20001", "700", "")]
    assert result["cleared"] == [{"su_id": "20001", "bot_pgram": "811"}]


def test_deprovision_leaves_healthy_cards_untouched(patch_deprovision):
    """Cards whose top and bottom folders are still in processed are not modified."""
    deleted, cleared = patch_deprovision(
        processed=[700, 811],
        su_rows=[{"su_id": "20001", "top_pgram": "700", "bot_pgram": "811", "trench": "20000"}],
    )

    result = volume.deprovision_orphaned_cards()

    assert deleted == [] and cleared == []
    assert result == {"removed": [], "cleared": []}


def test_deprovision_skips_when_scan_empty(patch_deprovision):
    """A blank filesystem scan (drive offline) must never mass-delete cards."""
    deleted, cleared = patch_deprovision(
        processed=[],
        su_rows=[{"su_id": "20001", "top_pgram": "700", "bot_pgram": "811", "trench": "20000"}],
        scan_empty=True,
    )

    result = volume.deprovision_orphaned_cards()

    assert deleted == [] and cleared == []
    assert result == {"removed": [], "cleared": []}
