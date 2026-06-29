"""Tests for backend/services/volume_runner.py — per-SU progress overlay.

get_status() merges the live progress.json the snip scripts write into the run
state so the dashboard can render a determinate bar.
"""
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
