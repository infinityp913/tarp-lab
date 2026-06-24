import logging
import subprocess
import sys
from pathlib import Path
from typing import Optional

from backend.config import LOG_PATH, get_config
from backend.models import PgramJob
from backend.services.filesystem import find_psx_file

logger = logging.getLogger(__name__)


def _log_error(msg: str):
    logger.error(msg)
    try:
        with open(LOG_PATH, "a") as f:
            f.write(f"ERROR {msg}\n")
    except OSError:
        pass


def _open(executable: str, args: list[str] = None) -> dict:
    if not executable or not Path(executable).exists():
        return {"launched": False, "error": f"Application not found at '{executable}'"}
    try:
        cmd = [executable] + (args or [])
        if sys.platform == "darwin":
            subprocess.Popen(["open", "-a", executable] + (args or []))
        else:
            subprocess.Popen(cmd)
        return {"launched": True}
    except Exception as e:
        _log_error(f"Failed to launch '{executable}': {e}")
        return {"launched": False, "error": str(e)}


def launch_metashape(job: PgramJob) -> dict:
    cfg = get_config()
    psx = find_psx_file(job)
    if psx:
        return _open(cfg.metashape_path, [str(psx)])
    return _open(cfg.metashape_path)


def launch_cloudcompare(job: Optional[PgramJob] = None) -> dict:
    cfg = get_config()
    return _open(cfg.cloudcompare_path)


def launch_cloudcompare_with_ply(ply_path: Path) -> dict:
    cfg = get_config()
    return _open(cfg.cloudcompare_path, [str(ply_path)])


def launch_cloudcompare_with_plys(ply_paths: list[Path]) -> dict:
    cfg = get_config()
    # CloudCompare only reliably loads a single bare path argument; multiple files
    # must be passed via the "-O" (open) command, once per file.
    args: list[str] = []
    for p in ply_paths:
        args += ["-O", str(p)]
    return _open(cfg.cloudcompare_path, args)


def launch_meshlab_with_ply(ply_path: Path) -> dict:
    cfg = get_config()
    if not cfg.meshlab_path:
        return {
            "launched": False,
            "error": "MeshLab not found. Set app_paths.meshlab in config.yaml.",
        }
    return _open(cfg.meshlab_path, [str(ply_path)])


def launch_qgis(job: Optional[PgramJob] = None) -> dict:
    cfg = get_config()
    if not cfg.qgis_path:
        return {
            "launched": False,
            "error": "QGIS not found. Set the path in config.yaml.",
        }
    return _open(cfg.qgis_path)
