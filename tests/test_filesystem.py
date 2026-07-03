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
    fix_su_folder_names,
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
    cfg.current_year_trenches = (20000, 23000)
    cfg.gsheets_spreadsheet_id = ""
    cfg.host = "127.0.0.1"
    cfg.port = 8000
    import backend.config as cfg_mod
    monkeypatch.setattr(cfg_mod, "_instance", cfg)
    return tmp_path


# ─── _parse_job_dir ──────────────────────────────────────────────────────────

def test_parse_normal_job(tmp_path):
    d = tmp_path / "Pgram_Job_696_SU16001"
    d.mkdir()
    job = _parse_job_dir(d, "processed")
    assert job is not None
    assert job.job_id == "Pgram_Job_696"
    assert job.su_string == "SU16001"
    assert job.stage == "processed"
    assert job.trench == "Trench 16000"


def test_parse_no_su_string(tmp_path):
    d = tmp_path / "Pgram_Job_100"
    d.mkdir()
    job = _parse_job_dir(d, "to_be_processed")
    assert job is not None
    assert job.job_id == "Pgram_Job_100"
    assert job.su_string == ""


def test_parse_strips_msi_suffix(tmp_path):
    d = tmp_path / f"Pgram_Job_697_SU16002{_MSI_SUFFIX}"
    d.mkdir()
    job = _parse_job_dir(d, "processed")
    assert job is not None
    assert job.job_id == "Pgram_Job_697"
    assert job.su_string == "SU16002", f"su_string should be 'SU16002', got '{job.su_string}'"


def test_parse_msi_suffix_case_insensitive(tmp_path):
    d = tmp_path / "Pgram_Job_698_SU16003_moved_to_msi"
    d.mkdir()
    job = _parse_job_dir(d, "processed")
    assert job is not None
    assert job.su_string == "SU16003"


def test_parse_invalid_name_returns_none(tmp_path):
    d = tmp_path / "NotAJob"
    d.mkdir()
    assert _parse_job_dir(d, "processed") is None


# ─── scan_filesystem ─────────────────────────────────────────────────────────

def _mk_stage(tmp_path, stage_folder, trench, job_name):
    p = tmp_path / stage_folder / trench / job_name
    p.mkdir(parents=True)
    return p


def test_scan_finds_jobs(tmp_path, use_tmp_base):
    _mk_stage(tmp_path, "To Be Processed", "Trench 20000", "Pgram_Job_001_SU010")
    _mk_stage(tmp_path, "Processed", "Trench 21000", "Pgram_Job_002")
    jobs = scan_filesystem()
    ids = {j.job_id for j in jobs}
    assert "Pgram_Job_001" in ids
    assert "Pgram_Job_002" in ids


def test_scan_ignores_pre_2026_trenches(tmp_path, use_tmp_base):
    # Jobs in out-of-range (pre-2026) trenches are not scanned at all.
    _mk_stage(tmp_path, "To Be Processed", "Trench 19000", "Pgram_Job_900_SU19001")
    _mk_stage(tmp_path, "Processed", "Trench 16000", "Pgram_Job_901")
    assert scan_filesystem() == []


def test_scan_ignores_msi_suffix_in_su_string(tmp_path, use_tmp_base):
    _mk_stage(tmp_path, "Processed", "Trench 20000", f"Pgram_Job_010_SU099{_MSI_SUFFIX}")
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
    (tmp_path / "To Be Processed" / "Trench 20000" / "Pgram_Job_003").mkdir(parents=True)
    assert scan_ignored_folders() == []


def test_scan_ignored_trench_container_misnamed_child_flagged(tmp_path, use_tmp_base):
    (tmp_path / "To Be Processed" / "Trench 20000" / "PreSU20001").mkdir(parents=True)
    result = scan_ignored_folders()
    assert len(result) == 1
    assert result[0].name == "PreSU20001"
    assert result[0].stage == "to_be_processed"
    assert result[0].parent == "Trench 20000"


def test_scan_ignored_out_of_range_trench_not_flagged(tmp_path, use_tmp_base):
    # A trench outside the current-year range (20000–23000) is ignored entirely,
    # including its misnamed children.
    (tmp_path / "To Be Aligned" / "Trench 19000" / "Trench_19000_Final").mkdir(parents=True)
    assert scan_ignored_folders() == []


def test_scan_ignored_loose_stage_root_folders_not_flagged(tmp_path, use_tmp_base):
    # Loose folders at the stage-root / trench level (not "Trench NNNNN") are ignored.
    (tmp_path / "To Be Processed" / "__pycache__").mkdir(parents=True)
    (tmp_path / "To Be Processed" / "Pre-2026").mkdir(parents=True)
    (tmp_path / "Processed" / "Pre-2026").mkdir(parents=True)
    assert scan_ignored_folders() == []


def test_scan_ignored_hidden_folders_skipped(tmp_path, use_tmp_base):
    stage = tmp_path / "To Be Processed"
    (stage / "Trench 20000" / ".DS_Store_folder").mkdir(parents=True)
    assert scan_ignored_folders() == []


def test_scan_ignored_returns_ignored_folder_model(tmp_path, use_tmp_base):
    from backend.models import IgnoredFolder
    (tmp_path / "To Be Processed" / "Trench 20000" / "BadName").mkdir(parents=True)
    result = scan_ignored_folders()
    assert len(result) == 1
    assert isinstance(result[0], IgnoredFolder)
    assert result[0].name == "BadName"
    assert result[0].stage == "to_be_processed"
    assert result[0].parent == "Trench 20000"


# ─── fix_su_folder_names ─────────────────────────────────────────────────────

def test_fix_bare_number_suffix_gets_su_tag(tmp_path, use_tmp_base):
    # Case A: bare SU number suffix → SU#### (no sheet lookup needed)
    _mk_stage(tmp_path, "To Be Processed", "Trench 21000", "Pgram_Job_696_21015")
    result = fix_su_folder_names({})
    assert result["renamed"] == [
        {"from": "Pgram_Job_696_21015", "to": "Pgram_Job_696_SU21015", "pgram": 696, "source": "suffix"}
    ]
    assert (tmp_path / "To Be Processed" / "Trench 21000" / "Pgram_Job_696_SU21015").exists()


def test_fix_bare_compact_range_suffix(tmp_path, use_tmp_base):
    _mk_stage(tmp_path, "To Be Processed", "Trench 21000", "Pgram_Job_700_21015-17")
    result = fix_su_folder_names({})
    assert result["renamed"][0]["to"] == "Pgram_Job_700_SU21015-17"


def test_fix_no_suffix_uses_field_sheet(tmp_path, use_tmp_base):
    # Case B: no SU suffix → look up sus_opened in the field map and append it
    _mk_stage(tmp_path, "To Be Processed", "Trench 21000", "Pgram_Job_696")
    field_map = {"696": {"sus_opened": "21015-17"}}
    result = fix_su_folder_names(field_map)
    assert result["renamed"][0]["to"] == "Pgram_Job_696_SU21015-17"
    assert result["renamed"][0]["source"] == "field_sheet"
    assert (tmp_path / "To Be Processed" / "Trench 21000" / "Pgram_Job_696_SU21015-17").exists()


def test_fix_no_suffix_field_list_sanitized(tmp_path, use_tmp_base):
    # Comma/space separators collapse to underscores for a clean folder token
    _mk_stage(tmp_path, "To Be Processed", "Trench 21000", "Pgram_Job_696")
    result = fix_su_folder_names({"696": {"sus_opened": "21015, 21016"}})
    assert result["renamed"][0]["to"] == "Pgram_Job_696_SU21015_21016"


def test_fix_no_suffix_no_field_entry_skipped(tmp_path, use_tmp_base):
    _mk_stage(tmp_path, "To Be Processed", "Trench 21000", "Pgram_Job_696")
    result = fix_su_folder_names({})
    assert result["renamed"] == []
    assert len(result["skipped"]) == 1
    assert result["skipped"][0]["name"] == "Pgram_Job_696"
    # Folder is left untouched
    assert (tmp_path / "To Be Processed" / "Trench 21000" / "Pgram_Job_696").exists()


def test_fix_already_tagged_left_untouched(tmp_path, use_tmp_base):
    _mk_stage(tmp_path, "To Be Processed", "Trench 21000", "Pgram_Job_696_SU21015")
    result = fix_su_folder_names({"696": {"sus_opened": "99999"}})
    assert result == {"renamed": [], "organized": [], "skipped": []}
    assert (tmp_path / "To Be Processed" / "Trench 21000" / "Pgram_Job_696_SU21015").exists()


def test_fix_unrecognized_suffix_left_untouched(tmp_path, use_tmp_base):
    # A non-numeric, non-SU suffix is not a bare SU number → leave it alone, no skip noise
    _mk_stage(tmp_path, "To Be Processed", "Trench 21000", "Pgram_Job_696_redo")
    result = fix_su_folder_names({})
    assert result == {"renamed": [], "organized": [], "skipped": []}
    assert (tmp_path / "To Be Processed" / "Trench 21000" / "Pgram_Job_696_redo").exists()


def test_fix_flat_layout_renames_and_organizes(tmp_path, use_tmp_base):
    # Flat layout: job folder directly under the stage root → renamed AND filed under its trench
    (tmp_path / "To Be Processed" / "Pgram_Job_800_22001").mkdir(parents=True)
    result = fix_su_folder_names({})
    assert result["renamed"][0]["to"] == "Pgram_Job_800_SU22001"
    assert result["organized"] == [{"name": "Pgram_Job_800_SU22001", "trench": "Trench 22000"}]
    # Moved out of the flat root into the (newly created) trench subfolder
    assert not (tmp_path / "To Be Processed" / "Pgram_Job_800_SU22001").exists()
    assert (tmp_path / "To Be Processed" / "Trench 22000" / "Pgram_Job_800_SU22001").exists()


def test_fix_organizes_already_tagged_flat_folder(tmp_path, use_tmp_base):
    # Correctly named but loose under the stage root → organized only (no rename)
    (tmp_path / "To Be Processed" / "Pgram_Job_810_SU23005").mkdir(parents=True)
    result = fix_su_folder_names({})
    assert result["renamed"] == []
    assert result["organized"] == [{"name": "Pgram_Job_810_SU23005", "trench": "Trench 23000"}]
    assert (tmp_path / "To Be Processed" / "Trench 23000" / "Pgram_Job_810_SU23005").exists()


def test_fix_organizes_into_existing_trench(tmp_path, use_tmp_base):
    # Trench subfolder already exists (holding another job) — flat job is moved in beside it
    _mk_stage(tmp_path, "To Be Processed", "Trench 21000", "Pgram_Job_700_SU21001")
    (tmp_path / "To Be Processed" / "Pgram_Job_701_SU21002").mkdir(parents=True)
    result = fix_su_folder_names({})
    assert result["organized"] == [{"name": "Pgram_Job_701_SU21002", "trench": "Trench 21000"}]
    assert (tmp_path / "To Be Processed" / "Trench 21000" / "Pgram_Job_701_SU21002").exists()


def test_fix_organize_collision_skipped(tmp_path, use_tmp_base):
    # A same-named folder already nested under the target trench → skip, leave the flat one
    _mk_stage(tmp_path, "To Be Processed", "Trench 21000", "Pgram_Job_705_SU21010")
    (tmp_path / "To Be Processed" / "Pgram_Job_705_SU21010").mkdir(parents=True)
    result = fix_su_folder_names({})
    assert result["organized"] == []
    assert len(result["skipped"]) == 1
    assert "already exists under Trench 21000" in result["skipped"][0]["reason"]
    assert (tmp_path / "To Be Processed" / "Pgram_Job_705_SU21010").exists()


def test_fix_flat_out_of_range_trench_not_organized(tmp_path, use_tmp_base):
    # Flat folder whose SU infers an out-of-range trench (24000 > max 23000) stays flat
    (tmp_path / "To Be Processed" / "Pgram_Job_820_24001").mkdir(parents=True)
    result = fix_su_folder_names({})
    # Still SU-tagged, but not moved (no valid current-year trench)
    assert result["renamed"][0]["to"] == "Pgram_Job_820_SU24001"
    assert result["organized"] == []
    assert (tmp_path / "To Be Processed" / "Pgram_Job_820_SU24001").exists()


def test_fix_target_collision_skipped(tmp_path, use_tmp_base):
    _mk_stage(tmp_path, "To Be Processed", "Trench 21000", "Pgram_Job_696_21015")
    _mk_stage(tmp_path, "To Be Processed", "Trench 21000", "Pgram_Job_696_SU21015")
    result = fix_su_folder_names({})
    assert result["renamed"] == []
    assert len(result["skipped"]) == 1
    assert "already exists" in result["skipped"][0]["reason"]
    # Original is preserved (not clobbered)
    assert (tmp_path / "To Be Processed" / "Trench 21000" / "Pgram_Job_696_21015").exists()


def test_fix_spans_all_stages(tmp_path, use_tmp_base):
    # Loose/untagged folders are fixed in any stage, not just To Be Processed.
    _mk_stage(tmp_path, "To Be Aligned", "Trench 21000", "Pgram_Job_900_21015")
    result = fix_su_folder_names({})
    assert result["renamed"][0]["to"] == "Pgram_Job_900_SU21015"
    assert (tmp_path / "To Be Aligned" / "Trench 21000" / "Pgram_Job_900_SU21015").exists()


def test_fix_organizes_flat_folder_in_other_stage(tmp_path, use_tmp_base):
    # Real-world case: flat untagged folder in To Be Aligned → tagged via field sheet + organized
    (tmp_path / "To Be Aligned" / "Pgram_Job_830").mkdir(parents=True)
    result = fix_su_folder_names({"830": {"sus_opened": "21030"}})
    assert result["renamed"][0]["to"] == "Pgram_Job_830_SU21030"
    assert result["organized"] == [{"name": "Pgram_Job_830_SU21030", "trench": "Trench 21000"}]
    assert (tmp_path / "To Be Aligned" / "Trench 21000" / "Pgram_Job_830_SU21030").exists()


def test_fix_ignores_out_of_range_trench(tmp_path, use_tmp_base):
    # Nested jobs under an out-of-range trench are not scanned (matches scan_filesystem)
    _mk_stage(tmp_path, "To Be Processed", "Trench 19000", "Pgram_Job_950_19001")
    result = fix_su_folder_names({})
    assert result == {"renamed": [], "organized": [], "skipped": []}


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


# ─── scan_ignored_folders ────────────────────────────────────────────────────

def test_ignored_top_level_not_flagged(tmp_path, use_tmp_base):
    # A misnamed folder at stage root (not inside a trench) is ignored
    (tmp_path / "To Be Processed" / "PreSU20001").mkdir(parents=True)
    assert scan_ignored_folders() == []


def test_ignored_nested_in_trench(tmp_path, use_tmp_base):
    # Misnamed folder inside a current-year Trench container → flagged with parent set
    (tmp_path / "To Be Processed" / "Trench 21000" / "bad_name").mkdir(parents=True)
    result = scan_ignored_folders()
    assert any(f.name == "bad_name" and f.stage == "to_be_processed" and f.parent == "Trench 21000" for f in result)


def test_valid_job_not_flagged(tmp_path, use_tmp_base):
    # A valid Pgram_Job_### folder is never in the ignored list
    (tmp_path / "To Be Processed" / "Trench 20000" / "Pgram_Job_001_SU20001").mkdir(parents=True)
    result = scan_ignored_folders()
    assert not any(f.name.startswith("Pgram_Job_") for f in result)


def test_trench_container_with_valid_children_not_flagged(tmp_path, use_tmp_base):
    # A Trench folder itself is never flagged, only its misnamed children are
    (tmp_path / "To Be Processed" / "Trench 20000" / "Pgram_Job_002_SU20002").mkdir(parents=True)
    result = scan_ignored_folders()
    assert not any(f.name == "Trench 20000" for f in result)


def test_boundary_trenches_included(tmp_path, use_tmp_base):
    # The range is inclusive on both ends (20000 and 23000).
    (tmp_path / "To Be Processed" / "Trench 20000" / "bad_lo").mkdir(parents=True)
    (tmp_path / "To Be Processed" / "Trench 23000" / "bad_hi").mkdir(parents=True)
    (tmp_path / "To Be Processed" / "Trench 24000" / "bad_over").mkdir(parents=True)
    names = {f.name for f in scan_ignored_folders()}
    assert names == {"bad_lo", "bad_hi"}


def test_hidden_folders_not_flagged(tmp_path, use_tmp_base):
    # Hidden folders (.DS_Store, .Trashes) inside a trench are silently skipped
    (tmp_path / "To Be Processed" / "Trench 20000" / ".DS_Store_folder").mkdir(parents=True)
    result = scan_ignored_folders()
    assert not any(f.name.startswith(".") for f in result)


def test_ignored_folders_empty_when_all_valid(tmp_path, use_tmp_base):
    (tmp_path / "To Be Processed" / "Trench 20000" / "Pgram_Job_100_SU20100").mkdir(parents=True)
    assert scan_ignored_folders() == []


def test_ignored_folders_multiple_stages(tmp_path, use_tmp_base):
    (tmp_path / "To Be Processed" / "Trench 20000" / "bad_a").mkdir(parents=True)
    (tmp_path / "Processed" / "Trench 21000" / "bad_b").mkdir(parents=True)
    result = scan_ignored_folders()
    names = {f.name for f in result}
    assert "bad_a" in names
    assert "bad_b" in names


# ─── find_debug_image_for_su ─────────────────────────────────────────────────

def _make_debug_dir(tmp_path):
    """Point volume_script_dir at tmp_path and create the Data/input snip folder."""
    filesystem.get_config().volume_script_dir = str(tmp_path)
    d = tmp_path / "Data" / "input"
    d.mkdir(parents=True)
    return d


def test_find_debug_image_exact_su(tmp_path, use_tmp_base):
    d = _make_debug_dir(tmp_path)
    f = d / "debug_SU20005_snip_reference.png"
    f.write_bytes(b"x")
    assert filesystem.find_debug_image_for_su("20005") == f


def test_find_debug_image_matches_su_in_range(tmp_path, use_tmp_base):
    # A single USDZ covering several SUs names its snip reference with the whole
    # range; each member SU must still find it.
    d = _make_debug_dir(tmp_path)
    f = d / "debug_SU22044-22048_snip_reference.png"
    f.write_bytes(b"x")
    assert filesystem.find_debug_image_for_su("22044") == f
    assert filesystem.find_debug_image_for_su("22048") == f


def test_find_debug_image_matches_nondigit_separated_name(tmp_path, use_tmp_base):
    # Some USDZ scans yield an SU name with odd separators (prim '_20038__20050' →
    # 'debug_SU20038;_20050_...'); each numeric token must still match.
    d = _make_debug_dir(tmp_path)
    f = d / "debug_SU20038;_20050_snip_reference.png"
    f.write_bytes(b"x")
    assert filesystem.find_debug_image_for_su("20038") == f
    assert filesystem.find_debug_image_for_su("20050") == f


def test_find_debug_image_none_when_su_absent(tmp_path, use_tmp_base):
    d = _make_debug_dir(tmp_path)
    (d / "debug_SU22044-22048_snip_reference.png").write_bytes(b"x")
    assert filesystem.find_debug_image_for_su("99999") is None


def test_find_debug_image_none_when_no_data_dir(tmp_path, use_tmp_base):
    filesystem.get_config().volume_script_dir = str(tmp_path)  # no Data/ created
    assert filesystem.find_debug_image_for_su("20005") is None
