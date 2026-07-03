"""Tests for backend/services/volume_runner.py — per-SU progress overlay and input.json writing."""
import json

import pytest

from backend.services import volume_runner


@pytest.fixture(autouse=True)
def reset_state():
    """Snapshot and restore module globals mutated by these tests."""
    state = dict(volume_runner._state)
    path = volume_runner._progress_path
    yield
    volume_runner._state.clear()
    volume_runner._state.update(state)
    volume_runner._progress_path = path


def _activate(processed=0, total=0):
    volume_runner._state.update(active=True, processed=processed, total=total)


def test_overlay_reads_progress_file(tmp_path):
    pf = tmp_path / "progress.json"
    pf.write_text(json.dumps({"processed": 3, "total": 10}))
    _activate(processed=0, total=10)
    volume_runner._progress_path = pf

    status = volume_runner.get_status()
    assert status["processed"] == 3
    assert status["total"] == 10


def test_overlay_falls_back_when_file_missing(tmp_path):
    _activate(processed=2, total=7)
    volume_runner._progress_path = tmp_path / "progress.json"  # never written

    status = volume_runner.get_status()
    assert status["processed"] == 2
    assert status["total"] == 7


def test_overlay_ignores_partial_or_corrupt_file(tmp_path):
    pf = tmp_path / "progress.json"
    pf.write_text("{not valid json")  # mid-write read
    _activate(processed=4, total=9)
    volume_runner._progress_path = pf

    status = volume_runner.get_status()
    assert status["processed"] == 4
    assert status["total"] == 9


def test_no_overlay_when_idle(tmp_path):
    pf = tmp_path / "progress.json"
    pf.write_text(json.dumps({"processed": 5, "total": 5}))
    volume_runner._state.update(active=False, processed=0, total=0)
    volume_runner._progress_path = pf

    status = volume_runner.get_status()
    assert status["processed"] == 0
    assert status["total"] == 0


# ---------------------------------------------------------------------------
# _write_input_json
# ---------------------------------------------------------------------------

def test_write_input_json_emits_top_bottom_su(tmp_path):
    cards = [{"top_pgram": "123", "bot_pgram": "456", "su_id": "20005"}]
    count = volume_runner._write_input_json(cards, str(tmp_path))
    assert count == 1
    data = json.loads((tmp_path / "input.json").read_text())
    assert data == [{"top": "123", "bottom": "456", "su": "20005"}]


def test_write_input_json_missing_su_id_emits_empty_string(tmp_path):
    cards = [{"top_pgram": "123", "bot_pgram": "456"}]
    volume_runner._write_input_json(cards, str(tmp_path))
    data = json.loads((tmp_path / "input.json").read_text())
    assert data[0]["su"] == ""


def test_write_input_json_skips_invalid_pgrams(tmp_path):
    cards = [
        {"top_pgram": "abc", "bot_pgram": "456", "su_id": "20001"},
        {"top_pgram": "123", "bot_pgram": "456", "su_id": "20002"},
    ]
    count = volume_runner._write_input_json(cards, str(tmp_path))
    assert count == 1
    data = json.loads((tmp_path / "input.json").read_text())
    assert data[0]["su"] == "20002"


def test_write_input_json_su_range_preserved(tmp_path):
    cards = [{"top_pgram": "786", "bot_pgram": "787", "su_id": "22044-22048"}]
    volume_runner._write_input_json(cards, str(tmp_path))
    data = json.loads((tmp_path / "input.json").read_text())
    assert data[0]["su"] == "22044-22048"


def test_write_input_json_dedupes_repeated_pgram_pairs(tmp_path):
    # Several SU cards sharing the same top/bottom pgram pair must collapse to a
    # single compute entry (the scripts key output on the top pgram), while a
    # genuinely different pair stays. The first SU for a pair is the one kept.
    cards = [
        {"top_pgram": "792", "bot_pgram": "835", "su_id": "21002"},
        {"top_pgram": "792", "bot_pgram": "835", "su_id": "21003"},
        {"top_pgram": "792", "bot_pgram": "835", "su_id": "21004"},
        {"top_pgram": "816", "bot_pgram": "819", "su_id": "21010"},
    ]
    count = volume_runner._write_input_json(cards, str(tmp_path))
    assert count == 2
    data = json.loads((tmp_path / "input.json").read_text())
    assert data == [
        {"top": "792", "bottom": "835", "su": "21002"},
        {"top": "816", "bottom": "819", "su": "21010"},
    ]


def test_write_input_json_no_dedupe_keeps_every_su(tmp_path):
    # The snip scripts pass dedupe=False: SUs sharing a pgram pair each keep their
    # own entry so every SU gets its own output (pre_snip a Data/SU<su>/ folder,
    # post_snip a per-SU volume). A genuinely different pair is preserved too.
    cards = [
        {"top_pgram": "792", "bot_pgram": "835", "su_id": "21002"},
        {"top_pgram": "792", "bot_pgram": "835", "su_id": "21003"},
        {"top_pgram": "792", "bot_pgram": "835", "su_id": "21004"},
        {"top_pgram": "816", "bot_pgram": "819", "su_id": "21010"},
    ]
    count = volume_runner._write_input_json(cards, str(tmp_path), dedupe=False)
    assert count == 4
    data = json.loads((tmp_path / "input.json").read_text())
    assert [d["su"] for d in data] == ["21002", "21003", "21004", "21010"]


def test_write_input_json_no_dedupe_still_skips_invalid_pgrams(tmp_path):
    cards = [
        {"top_pgram": "abc", "bot_pgram": "456", "su_id": "20001"},
        {"top_pgram": "792", "bot_pgram": "835", "su_id": "21002"},
        {"top_pgram": "792", "bot_pgram": "835", "su_id": "21003"},
    ]
    count = volume_runner._write_input_json(cards, str(tmp_path), dedupe=False)
    assert count == 2
    data = json.loads((tmp_path / "input.json").read_text())
    assert [d["su"] for d in data] == ["21002", "21003"]


def test_write_input_json_dedupe_is_order_sensitive_on_swapped_pairs(tmp_path):
    # (top, bottom) is directional — a swapped pair is a different computation
    # and must NOT be collapsed.
    cards = [
        {"top_pgram": "800", "bot_pgram": "801", "su_id": "1"},
        {"top_pgram": "801", "bot_pgram": "800", "su_id": "2"},
    ]
    count = volume_runner._write_input_json(cards, str(tmp_path))
    assert count == 2


# ---------------------------------------------------------------------------
# _write_autosnip_input
# ---------------------------------------------------------------------------

def _patch_usdz(monkeypatch, mapping):
    """Stub find_usdz_for_su so _write_autosnip_input maps su_id → USDZ path(s)."""
    from pathlib import Path
    import backend.services.volume as volume

    def fake(su_id):
        return [Path(p) for p in mapping.get(str(su_id), [])]

    monkeypatch.setattr(volume, "find_usdz_for_su", fake)


def test_write_autosnip_input_emits_annotations(tmp_path, monkeypatch):
    _patch_usdz(monkeypatch, {"20005": [r"C:\scans\tarpf1-SU_20005.usdz"]})
    cards = [{"top_pgram": "789", "bot_pgram": "790", "su_id": "20005"}]
    count = volume_runner._write_autosnip_input(cards, str(tmp_path))
    assert count == 1
    data = json.loads((tmp_path / "input.json").read_text())
    assert data == [{
        "top": "789", "bottom": "790", "su": "20005",
        "annotations": [r"C:\scans\tarpf1-SU_20005.usdz"],
    }]


def test_write_autosnip_input_skips_cards_without_usdz(tmp_path, monkeypatch):
    _patch_usdz(monkeypatch, {"20005": [r"C:\scans\a-SU_20005.usdz"]})  # 20006 has none
    cards = [
        {"top_pgram": "789", "bot_pgram": "790", "su_id": "20005"},
        {"top_pgram": "791", "bot_pgram": "792", "su_id": "20006"},
    ]
    count = volume_runner._write_autosnip_input(cards, str(tmp_path))
    assert count == 1
    data = json.loads((tmp_path / "input.json").read_text())
    assert [j["su"] for j in data] == ["20005"]


def test_write_autosnip_input_skips_invalid_pgrams(tmp_path, monkeypatch):
    _patch_usdz(monkeypatch, {"20005": [r"C:\scans\a-SU_20005.usdz"]})
    cards = [{"top_pgram": "abc", "bot_pgram": "790", "su_id": "20005"}]
    count = volume_runner._write_autosnip_input(cards, str(tmp_path))
    assert count == 0


def test_write_autosnip_input_dedupes_by_usdz(tmp_path, monkeypatch):
    # A single USDZ covering several SUs (each card resolves to the same scan) is
    # snipped once, so the shared scan collapses to one job — not one per card.
    shared = r"C:\scans\tarpf9-SU_22044_22045.usdz"
    _patch_usdz(monkeypatch, {"22044": [shared], "22045": [shared]})
    cards = [
        {"top_pgram": "786", "bot_pgram": "787", "su_id": "22044"},
        {"top_pgram": "786", "bot_pgram": "787", "su_id": "22045"},
    ]
    count = volume_runner._write_autosnip_input(cards, str(tmp_path))
    assert count == 1
    data = json.loads((tmp_path / "input.json").read_text())
    assert data[0]["annotations"] == [shared]


# ---------------------------------------------------------------------------
# _stage_autosnip_dems
# ---------------------------------------------------------------------------

def _cfg_for_dems(tmp_path):
    """Assets root with PLY/ + DEM/ subfolders and a separate script working dir."""
    import types

    assets = tmp_path / "assets"
    (assets / "PLY").mkdir(parents=True)
    (assets / "DEM").mkdir(parents=True)
    script = tmp_path / "script"
    script.mkdir()
    return types.SimpleNamespace(
        overnight_output_assets_root=str(assets),
        volume_script_dir=str(script),
    ), assets, script


def test_stage_autosnip_dems_copies_bottom_dem(tmp_path, monkeypatch):
    _patch_usdz(monkeypatch, {"20005": [r"C:\scans\a-SU_20005.usdz"]})
    cfg, assets, script = _cfg_for_dems(tmp_path)
    # DEM is keyed on the BOTTOM pgram (790), named to match the bottom PLY basename.
    (assets / "PLY" / "Pgram_Job_790_SU20005.ply").write_text("ply")
    (assets / "DEM" / "Pgram_Job_790_SU20005_dem.tif").write_bytes(b"demdata")

    cards = [{"top_pgram": "789", "bot_pgram": "790", "su_id": "20005"}]
    staged, missing = volume_runner._stage_autosnip_dems(cards, cfg)

    assert (staged, missing) == (1, [])
    out = script / "Data" / "DEMs" / "Pgram_Job_790_SU20005_dem.tif"
    assert out.read_bytes() == b"demdata"


def test_stage_autosnip_dems_dedupes_by_bottom_pgram(tmp_path, monkeypatch):
    shared = r"C:\scans\s-SU_22044_22045.usdz"
    _patch_usdz(monkeypatch, {"22044": [shared], "22045": [shared]})
    cfg, assets, script = _cfg_for_dems(tmp_path)
    (assets / "PLY" / "Pgram_Job_787_SU22044-22045.ply").write_text("ply")
    (assets / "DEM" / "Pgram_Job_787_SU22044-22045_dem.tif").write_bytes(b"d")

    cards = [
        {"top_pgram": "786", "bot_pgram": "787", "su_id": "22044"},
        {"top_pgram": "786", "bot_pgram": "787", "su_id": "22045"},
    ]
    staged, missing = volume_runner._stage_autosnip_dems(cards, cfg)
    assert (staged, missing) == (1, [])


def test_stage_autosnip_dems_reports_missing_dem(tmp_path, monkeypatch):
    _patch_usdz(monkeypatch, {"20005": [r"C:\scans\a-SU_20005.usdz"]})
    cfg, assets, script = _cfg_for_dems(tmp_path)
    (assets / "PLY" / "Pgram_Job_790_SU20005.ply").write_text("ply")  # PLY but no DEM

    cards = [{"top_pgram": "789", "bot_pgram": "790", "su_id": "20005"}]
    staged, missing = volume_runner._stage_autosnip_dems(cards, cfg)
    assert (staged, missing) == (0, ["790"])


def test_stage_autosnip_dems_skips_cards_without_usdz(tmp_path, monkeypatch):
    _patch_usdz(monkeypatch, {})  # no card has a USDZ → nothing to snip, nothing to stage
    cfg, assets, script = _cfg_for_dems(tmp_path)
    (assets / "PLY" / "Pgram_Job_790_SU20005.ply").write_text("ply")
    (assets / "DEM" / "Pgram_Job_790_SU20005_dem.tif").write_bytes(b"d")

    cards = [{"top_pgram": "789", "bot_pgram": "790", "su_id": "20005"}]
    staged, missing = volume_runner._stage_autosnip_dems(cards, cfg)
    assert (staged, missing) == (0, [])


# ---------------------------------------------------------------------------
# cross-process run lock
# ---------------------------------------------------------------------------

import os  # noqa: E402
import types  # noqa: E402


def _cfg(tmp_path):
    return types.SimpleNamespace(volume_script_dir=str(tmp_path), create_su_sheet_dir=None)


def test_pid_alive_true_for_current_process():
    assert volume_runner._pid_alive(os.getpid()) is True


def test_pid_alive_false_for_zero_or_negative():
    assert volume_runner._pid_alive(0) is False
    assert volume_runner._pid_alive(-1) is False


def test_write_and_clear_lock_roundtrip(tmp_path):
    cfg = _cfg(tmp_path)
    volume_runner._write_lock(cfg, "pre_snip", 4242)
    lock = tmp_path / volume_runner._LOCK_NAME
    assert lock.exists()
    data = json.loads(lock.read_text())
    assert data["pid"] == 4242 and data["kind"] == "pre_snip"
    volume_runner._clear_lock(cfg)
    assert not lock.exists()


def test_clear_lock_is_noop_when_absent(tmp_path):
    volume_runner._clear_lock(_cfg(tmp_path))  # must not raise


def test_active_lock_returns_data_when_pid_alive(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    volume_runner._write_lock(cfg, "auto_snip", 4242)
    monkeypatch.setattr(volume_runner, "_pid_alive", lambda pid: True)
    held = volume_runner._active_lock(cfg)
    assert held is not None and held["kind"] == "auto_snip"
    assert (tmp_path / volume_runner._LOCK_NAME).exists()  # live lock is kept


def test_active_lock_clears_stale_lock_when_pid_dead(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    volume_runner._write_lock(cfg, "pre_snip", 4242)
    monkeypatch.setattr(volume_runner, "_pid_alive", lambda pid: False)
    assert volume_runner._active_lock(cfg) is None
    assert not (tmp_path / volume_runner._LOCK_NAME).exists()  # stale lock removed


def test_active_lock_none_when_no_lockfile(tmp_path):
    assert volume_runner._active_lock(_cfg(tmp_path)) is None


def test_active_lock_clears_corrupt_lockfile(tmp_path):
    (tmp_path / volume_runner._LOCK_NAME).write_text("{not json")
    assert volume_runner._active_lock(_cfg(tmp_path)) is None
    assert not (tmp_path / volume_runner._LOCK_NAME).exists()
