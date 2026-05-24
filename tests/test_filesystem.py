"""Tests for backend/services/filesystem.py — filesystem scanning and move operations."""
import shutil
from pathlib import Path

import pytest

from backend.config import Config, init_config
from backend.services import filesystem
from backend.services.filesystem import (
    _MSI_SUFFIX,
    _parse_job_dir,
    create_job_folder,
    move_job,
    move_to_msi,
    scan_filesystem,
    scan_ignored_folders,
    scan_subfolders,
)
from backend.models import PgramJob


@pytest.fixture(autouse=True)
def use_tmp_base(tmp_path, monkeypatch):
    """Point the config at a temporary directory so tests never touch real data."""
    cfg = Config.__new__(Config)
    cfg.base_path = str(tmp_path)
    cfg.stage_folders = {
        "to_be_processed": "To Be Processed",
        "to_be_aligned": "To Be Aligned",
        "to_overnight": "To Overnight",
        "processed": "Processed",
        "uploaded_air": "Uploaded to AIR",
    }
    cfg.metashape_path = ""
    cfg.cloudcompare_path = ""
    cfg.qgis_path = ""
    cfg.gsheets_spreadsheet_id = ""
    cfg.host = "127.0.0.1"
    cfg.port = 8000
    import backend.config as cfg_mod
    monkeypatch.setattr(cfg_mod, "_instance", cfg)
    return tmp_path


# ─── _parse_job_dir ──────────────────────────────────────────────────────────

def test_parse_normal_job(tmp_path):
    d = tmp_path / "Pgram_Job_696_SU001"
    d.mkdir()
    job = _parse_job_dir(d, "processed", "Trench 16000")
    assert job is not None
    assert job.job_id == "Pgram_Job_696"
    assert job.su_string == "SU001"
    assert job.stage == "processed"
    assert job.trench == "Trench 16000"


def test_parse_no_su_string(tmp_path):
    d = tmp_path / "Pgram_Job_100"
    d.mkdir()
    job = _parse_job_dir(d, "to_be_processed", "")
    assert job is not None
    assert job.job_id == "Pgram_Job_100"
    assert job.su_string == ""


def test_parse_strips_msi_suffix(tmp_path):
    d = tmp_path / f"Pgram_Job_697_SU002{_MSI_SUFFIX}"
    d.mkdir()
    job = _parse_job_dir(d, "processed", "Trench 16000")
    assert job is not None
    assert job.job_id == "Pgram_Job_697"
    assert job.su_string == "SU002", f"su_string should be 'SU002', got '{job.su_string}'"


def test_parse_msi_suffix_case_insensitive(tmp_path):
    d = tmp_path / "Pgram_Job_698_SU003_moved_to_msi"
    d.mkdir()
    job = _parse_job_dir(d, "processed", "")
    assert job is not None
    assert job.su_string == "SU003"


def test_parse_invalid_name_returns_none(tmp_path):
    d = tmp_path / "NotAJob"
    d.mkdir()
    assert _parse_job_dir(d, "processed", "") is None


# ─── scan_filesystem ─────────────────────────────────────────────────────────

def _mk_stage(tmp_path, stage_folder, trench, job_name):
    p = tmp_path / stage_folder / trench / job_name
    p.mkdir(parents=True)
    return p


def test_scan_finds_jobs(tmp_path, use_tmp_base):
    _mk_stage(tmp_path, "To Be Processed", "Trench 16000", "Pgram_Job_001_SU010")
    _mk_stage(tmp_path, "Processed", "Trench 17000", "Pgram_Job_002")
    jobs = scan_filesystem()
    ids = {j.job_id for j in jobs}
    assert "Pgram_Job_001" in ids
    assert "Pgram_Job_002" in ids


def test_scan_ignores_msi_suffix_in_su_string(tmp_path, use_tmp_base):
    _mk_stage(tmp_path, "Processed", "Trench 16000", f"Pgram_Job_010_SU099{_MSI_SUFFIX}")
    jobs = scan_filesystem()
    assert len(jobs) == 1
    assert jobs[0].su_string == "SU099"


def test_scan_flat_layout(tmp_path, use_tmp_base):
    # Flat: stage_root/Pgram_Job_### (no trench subdir)
    p = tmp_path / "To Be Processed" / "Pgram_Job_200"
    p.mkdir(parents=True)
    jobs = scan_filesystem()
    assert any(j.job_id == "Pgram_Job_200" for j in jobs)


def test_scan_empty(tmp_path, use_tmp_base):
    assert scan_filesystem() == []


# ─── create_job_folder ───────────────────────────────────────────────────────

def test_create_job_folder(tmp_path, use_tmp_base):
    path = create_job_folder("Pgram_Job_500", "SU100", "Trench 11000")
    assert path.exists()
    assert path.name == "Pgram_Job_500_SU100"


def test_create_job_folder_no_su(tmp_path, use_tmp_base):
    path = create_job_folder("Pgram_Job_501", "", "Trench 11000")
    assert path.name == "Pgram_Job_501"


def test_create_job_folder_duplicate_raises(tmp_path, use_tmp_base):
    create_job_folder("Pgram_Job_502", "SU101", "Trench 11000")
    with pytest.raises(FileExistsError):
        create_job_folder("Pgram_Job_502", "SU101", "Trench 11000")


# ─── move_job ────────────────────────────────────────────────────────────────

def _make_job(tmp_path, stage_key, stage_folder, trench, job_id, su_string=""):
    suffix = f"_{su_string}" if su_string else ""
    p = tmp_path / stage_folder / trench / f"{job_id}{suffix}"
    p.mkdir(parents=True)
    return PgramJob(job_id=job_id, su_string=su_string, trench=trench, stage=stage_key)


def test_move_job(tmp_path, use_tmp_base):
    job = _make_job(tmp_path, "to_be_processed", "To Be Processed", "Trench 16000", "Pgram_Job_300", "SU050")
    dest = move_job(job, "to_be_aligned")
    assert dest.exists()
    assert "To Be Aligned" in str(dest)
    assert not (tmp_path / "To Be Processed" / "Trench 16000" / "Pgram_Job_300_SU050").exists()


def test_move_job_missing_source_raises(tmp_path, use_tmp_base):
    job = PgramJob(job_id="Pgram_Job_999", su_string="", trench="Trench 11000", stage="to_be_processed")
    with pytest.raises(FileNotFoundError):
        move_job(job, "to_be_aligned")


# ─── move_to_msi ─────────────────────────────────────────────────────────────

def test_move_to_msi_renames_with_suffix(tmp_path, use_tmp_base):
    job = _make_job(tmp_path, "processed", "Processed", "Trench 16000", "Pgram_Job_400", "SU060")
    dest = move_to_msi(job)
    assert dest.exists()
    assert dest.name == f"Pgram_Job_400_SU060{_MSI_SUFFIX}"
    assert "Moved to MSI" in str(dest)


def test_move_to_msi_no_su_string(tmp_path, use_tmp_base):
    job = _make_job(tmp_path, "processed", "Processed", "", "Pgram_Job_401")
    dest = move_to_msi(job)
    assert dest.name == f"Pgram_Job_401{_MSI_SUFFIX}"


def test_move_to_msi_duplicate_raises(tmp_path, use_tmp_base):
    job = _make_job(tmp_path, "processed", "Processed", "Trench 16000", "Pgram_Job_402", "SU062")
    move_to_msi(job)
    # Recreate source to try again
    src = tmp_path / "Processed" / "Trench 16000" / "Pgram_Job_402_SU062"
    src.mkdir(parents=True)
    job2 = PgramJob(job_id="Pgram_Job_402", su_string="SU062", trench="Trench 16000", stage="processed")
    with pytest.raises(FileExistsError):
        move_to_msi(job2)


# ─── scan_ignored_folders ────────────────────────────────────────────────────

def test_scan_ignored_empty_stages(tmp_path, use_tmp_base):
    # No stage dirs exist → empty list, no crash.
    assert scan_ignored_folders() == []


def test_scan_ignored_valid_jobs_not_flagged(tmp_path, use_tmp_base):
    (tmp_path / "To Be Processed" / "Pgram_Job_001").mkdir(parents=True)
    (tmp_path / "To Be Aligned" / "Pgram_Job_002_SU010").mkdir(parents=True)
    assert scan_ignored_folders() == []


def test_scan_ignored_trench_container_valid_children_not_flagged(tmp_path, use_tmp_base):
    (tmp_path / "To Be Processed" / "Trench 17000" / "Pgram_Job_003").mkdir(parents=True)
    assert scan_ignored_folders() == []


def test_scan_ignored_trench_container_misnamed_child_flagged(tmp_path, use_tmp_base):
    (tmp_path / "To Be Processed" / "Trench 17000" / "PreSU17001").mkdir(parents=True)
    result = scan_ignored_folders()
    assert len(result) == 1
    assert result[0].name == "PreSU17001"
    assert result[0].stage == "to_be_processed"
    assert result[0].parent == "Trench 17000"


def test_scan_ignored_non_trench_with_job_children_treated_as_container(tmp_path, use_tmp_base):
    # A folder that doesn't start with "Trench " but contains a valid job subfolder
    # should be treated as a container (not flagged), and only its misnamed children flagged.
    container = tmp_path / "Processed" / "TR17000"
    (container / "Pgram_Job_010").mkdir(parents=True)
    (container / "BadFolder").mkdir(parents=True)
    result = scan_ignored_folders()
    names = [r.name for r in result]
    assert "TR17000" not in names
    assert "BadFolder" in names
    assert result[0].parent == "TR17000"


def test_scan_ignored_misnamed_top_level_no_job_children(tmp_path, use_tmp_base):
    # A folder that doesn't start with "Trench " and has no job children → flagged itself.
    (tmp_path / "To Be Processed" / "PreSU17001").mkdir(parents=True)
    result = scan_ignored_folders()
    assert len(result) == 1
    assert result[0].name == "PreSU17001"
    assert result[0].parent == ""


def test_scan_ignored_hidden_folders_skipped(tmp_path, use_tmp_base):
    stage = tmp_path / "To Be Processed"
    stage.mkdir()
    (stage / ".DS_Store_folder").mkdir()
    assert scan_ignored_folders() == []


def test_scan_ignored_returns_ignored_folder_model(tmp_path, use_tmp_base):
    from backend.models import IgnoredFolder
    (tmp_path / "To Be Processed" / "BadName").mkdir(parents=True)
    result = scan_ignored_folders()
    assert len(result) == 1
    assert isinstance(result[0], IgnoredFolder)
    assert result[0].name == "BadName"
    assert result[0].stage == "to_be_processed"
    assert result[0].parent == ""


# ─── scan_subfolders ─────────────────────────────────────────────────────────

def test_scan_subfolders(tmp_path, use_tmp_base):
    (tmp_path / "Trench 16000").mkdir()
    (tmp_path / "Trench 17000").mkdir()
    (tmp_path / "To Be Processed").mkdir()
    result = scan_subfolders()
    assert "Trench 16000" in result
    assert "Trench 17000" in result


def test_scan_subfolders_excludes_job_dirs(tmp_path, use_tmp_base):
    (tmp_path / "Pgram_Job_001").mkdir()
    result = scan_subfolders()
    assert "Pgram_Job_001" not in result
