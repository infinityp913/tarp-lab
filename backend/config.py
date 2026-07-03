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
        self.meshlab_path: str = self._resolve_meshlab(app_cfg.get("meshlab", ""))
        scripts_cfg = raw.get("scripts", {})
        self.script_alignment: str = scripts_cfg.get("alignment", "")
        self.script_overnight: str = scripts_cfg.get("overnight", "")
        self.gcp_csv: str = scripts_cfg.get("gcp_csv", "")
        self.overnight_output_assets_root: str = scripts_cfg.get("overnight_output_assets_root", "C:/Users/Photogrammetry/GIS_2026")
        self.script_pre_snip: str = scripts_cfg.get("pre_snip", "")
        self.script_auto_snip: str = scripts_cfg.get("auto_snip", "")
        self.script_post_snip: str = scripts_cfg.get("post_snip", "")
        self.script_create_su_sheet: str = scripts_cfg.get("create_su_sheet", "")
        # create_su_sheet is a QGIS script, not a CloudComPy one: it runs under QGIS's
        # bundled Python via the python-qgis-ltr.bat launcher, in its own repo dir.
        self.create_su_sheet_dir: str = scripts_cfg.get("create_su_sheet_dir", "")
        self.qgis_launcher: str = scripts_cfg.get("qgis_launcher", "")
        # Working directory for CloudComPy volume scripts (contains Data/ subfolder and example.json)
        self.volume_script_dir: str = scripts_cfg.get("volume_script_dir", "")
        # Python interpreter in the CloudComPy venv/conda environment
        self.cloudcompy_python: str = scripts_cfg.get("cloudcompy_python", "")
        # CloudComPy binary install root (the folder containing CloudCompare/ and
        # envCloudComPy.bat). Used to set PYTHONPATH/PATH for the volume scripts so
        # `import cloudComPy` works without shell activation. Leave blank to disable.
        self.cloudcompy_root: str = scripts_cfg.get("cloudcompy_root", "")
        # Conda env root providing usdcat.exe (OpenUSD CLI) for auto_snip's USDZ→USDA
        # step. auto_snip shells out to `usdcat`; its DLLs only resolve with this env's
        # activation dirs on PATH, so _cloudcompy_env appends them. Blank = disabled.
        self.usd_env_root: str = scripts_cfg.get("usd_env_root", "")
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

    def _resolve_meshlab(self, configured: str) -> str:
        if configured:
            return configured
        # Auto-discover MeshLab on Windows
        patterns = [
            "C:\\Program Files\\VCG\\MeshLab*\\meshlab.exe",
            "C:\\Program Files\\MeshLab*\\meshlab.exe",
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
