import glob
import os
import sys
from pathlib import Path
from typing import Optional

import yaml

ROOT_DIR = Path(__file__).parent.parent
CONFIG_PATH = ROOT_DIR / "config.yaml"
CREDENTIALS_PATH = ROOT_DIR / "credentials.json"
TOKEN_DIR = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "tarp-dashboard"
TOKEN_PATH = TOKEN_DIR / "token.json"
LOG_PATH = ROOT_DIR / "tarp-dashboard.log"
STATIC_DIR = ROOT_DIR / "backend" / "static"


def _load_raw() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f) or {}


class Config:
    def __init__(self, dev: bool = False):
        raw = _load_raw()
        # On non-Windows, automatically use dev_base_path when it is set
        if not dev and sys.platform != "win32" and raw.get("dev_base_path", ""):
            dev = True
        default_path = raw.get("dev_base_path", "") if dev else raw.get("base_path", "C:\\Users\\Photogrammetry")
        self.base_path: str = default_path or raw.get("base_path", "C:\\Users\\Photogrammetry")
        stage_cfg = raw.get("stage_folders", {})
        self.stage_folders = {
            "to_be_processed": stage_cfg.get("to_be_processed", "To Be Processed"),
            "to_be_aligned": stage_cfg.get("to_be_aligned", "To Be Aligned"),
            "to_overnight": stage_cfg.get("to_overnight", "To Overnight"),
            "processed": stage_cfg.get("processed", "Processed"),
            "uploaded_air": stage_cfg.get("uploaded_air", "Uploaded to AIR"),
        }
        app_cfg = raw.get("app_paths", {})
        self.metashape_path: str = app_cfg.get("metashape", "")
        self.cloudcompare_path: str = app_cfg.get("cloudcompare", "")
        self.qgis_path: str = self._resolve_qgis(app_cfg.get("qgis", ""))
        scripts_cfg = raw.get("scripts", {})
        self.script_alignment: str = scripts_cfg.get("alignment", "")
        self.script_overnight: str = scripts_cfg.get("overnight", "")
        self.gcp_csv: str = scripts_cfg.get("gcp_csv", "")
        self.output_root: str = scripts_cfg.get("output_root", "C:/Users/Photogrammetry/GIS_2026")
        self.season_year: int = int(raw.get("season_year", 2026))
        trench_cfg = raw.get("current_year_trenches", {}) or {}
        self.current_year_trenches: tuple[int, int] = (
            int(trench_cfg.get("min", 20000)),
            int(trench_cfg.get("max", 23000)),
        )
        self.gsheets_spreadsheet_id: str = raw.get("gsheets_spreadsheet_id", "")
        self.host: str = raw.get("host", "127.0.0.1")
        self.port: int = int(raw.get("port", 8000))

    def _resolve_qgis(self, configured: str) -> str:
        if configured:
            return configured
        # Auto-discover QGIS on Windows
        patterns = [
            "C:\\Program Files\\QGIS*\\bin\\qgis-bin.exe",
            "C:\\Program Files\\QGIS*\\bin\\qgis-ltr-bin.exe",
        ]
        for pattern in patterns:
            matches = sorted(glob.glob(pattern), reverse=True)
            if matches:
                return matches[0]
        return ""

    def stage_folder_path(self, stage_key: str, trench: str) -> Optional[Path]:
        folder_name = self.stage_folders.get(stage_key)
        if not folder_name:
            return None
        return Path(self.base_path) / folder_name / trench

    def has_credentials(self) -> bool:
        return CREDENTIALS_PATH.exists()

    def has_token(self) -> bool:
        return TOKEN_PATH.exists()


_instance: Optional[Config] = None


def init_config(dev: bool = False) -> Config:
    global _instance
    _instance = Config(dev=dev)
    return _instance


def get_config() -> Config:
    global _instance
    if _instance is None:
        _instance = Config()
    return _instance
