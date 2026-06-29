"""Volume script runner — pre-snip, auto-snip, post-snip.

Unlike the Metashape runner (which processes one job at a time), each CloudComPy
script runs once over all cards in the source stage in a single subprocess. On
success every card in that stage is advanced to the target stage in Sheets.
Only one volume script run is allowed at a time.
"""

import logging
import os
import subprocess
import threading
from pathlib import Path
from typing import Optional

from backend.config import LOG_PATH, get_config
from backend.services import gsheets

logger = logging.getLogger(__name__)

_STEPS: dict[str, tuple[str, str]] = {
    "pre_snip":       ("to_be_pre_snipped",  "to_be_snipped"),
    "auto_snip":      ("to_be_snipped",       "to_be_post_snipped"),
    "post_snip":      ("to_be_post_snipped",  "volumetrics_created"),
    "create_su_sheet": ("volumetrics_created", "su_sheet_created"),
}

_lock = threading.Lock()
_state: dict = {
    "active": False,
    "kind": None,
    "started_at": None,
    "status": "idle",   # idle | running | done | failed
    "error": None,
    "cards_advanced": 0,
}


def _log(msg: str) -> None:
    logger.info(msg)
    try:
        with open(LOG_PATH, "a") as f:
            f.write(f"VOL {msg}\n")
    except OSError:
        pass


def get_status() -> dict:
    with _lock:
        return dict(_state)


def cancel() -> dict:
    with _lock:
        if not _state["active"]:
            return {"cancelled": False, "error": "No volume run in progress."}
        return {"cancelled": False, "error": "Volume scripts run to completion — cancellation is not supported mid-script."}


def _exists(path: str) -> bool:
    try:
        return Path(path).exists()
    except OSError:
        return False


def _write_input_json(cards: list[dict], script_dir: str) -> int:
    """Write input.json for the volume scripts from the given SU cards.

    Each card must have a digit top_pgram and bot_pgram; cards missing either
    are skipped (logged). Returns the number of pairs written.
    """
    import json

    pairs = []
    for card in cards:
        top = str(card.get("top_pgram", ""))
        bot = str(card.get("bot_pgram", ""))
        if top.isdigit() and bot.isdigit():
            pairs.append({"top": top, "bottom": bot})
        else:
            _log(f"  skip {card.get('su_id', '?')}: missing/invalid pgrams (top={top!r}, bot={bot!r})")

    dest = Path(script_dir) / "input.json"
    dest.write_text(json.dumps(pairs, indent=2))
    _log(f"  wrote {len(pairs)} pair(s) to {dest}")
    return len(pairs)


def _write_su_sheets_input(cards: list[dict], out_dir: str, year: int) -> int:
    """Write su_sheets_input.json for generate_su_sheets.py from the given SU cards.

    Each card contributes {"su": "SU_<su_id>", "job_id": <top_pgram>}. su_id is a bare
    number in the sheet (e.g. "20005") so it's prefixed with "SU_" to match the form the
    QGIS script expects. Cards with a missing su_id or non-digit top_pgram are skipped.
    Returns the number of items written.
    """
    import json

    items = []
    for card in cards:
        su_id = str(card.get("su_id", "")).strip()
        job_id = str(card.get("top_pgram", "")).strip()
        if su_id and job_id.isdigit():
            items.append({"su": f"SU_{su_id}", "job_id": job_id})
        else:
            _log(f"  skip {su_id or '?'}: missing su_id or non-digit top_pgram (top={job_id!r})")

    dest = Path(out_dir) / "su_sheets_input.json"
    dest.write_text(json.dumps({"year": str(year), "items": items}, indent=2))
    _log(f"  wrote {len(items)} SU sheet item(s) to {dest}")
    return len(items)


def _prepare_run(kind: str, script: str, cards: list[dict], cfg) -> tuple[list[str], str, Optional[dict], int]:
    """Write the input file for `kind` and return (cmd, cwd, env, count).

    create_su_sheet is a QGIS script: it runs under QGIS's own Python via the
    python-qgis-ltr.bat launcher (which sets the GDAL/PROJ/Qt env), in its own repo
    dir, reading a batch su_sheets_input.json. The snip scripts run under the
    CloudComPy venv with PYTHONPATH/PATH from cloudcompy_root. count == 0 means there
    was nothing valid to process and the caller should skip the launch.
    """
    if kind == "create_su_sheet":
        count = _write_su_sheets_input(cards, cfg.create_su_sheet_dir, cfg.season_year)
        return [cfg.qgis_launcher, script], cfg.create_su_sheet_dir, None, count
    count = _write_input_json(cards, cfg.volume_script_dir)
    env = _cloudcompy_env(cfg)
    if env is not None and cfg.overnight_output_assets_root:
        # Tell pre_snip/auto_snip where the overnight-exported PLY meshes live, instead
        # of the script's stale ~/Documents/TARP/ply default.
        env["TARP_PLY_DIR"] = str(Path(cfg.overnight_output_assets_root) / "PLY")
    return [cfg.cloudcompy_python, script], cfg.volume_script_dir, env, count


def _validate(kind: str) -> Optional[str]:
    cfg = get_config()
    if kind not in _STEPS:
        return f"Unknown volume run type: {kind}"
    if kind == "create_su_sheet":
        # QGIS script — validated against the QGIS launcher + its own repo dir,
        # not the CloudComPy interpreter/working dir.
        if not cfg.qgis_launcher or not _exists(cfg.qgis_launcher):
            return f"QGIS launcher not found at '{cfg.qgis_launcher}'. Set scripts.qgis_launcher in config.yaml."
        if not cfg.create_su_sheet_dir or not _exists(cfg.create_su_sheet_dir):
            return f"Create-SU-sheet directory not found at '{cfg.create_su_sheet_dir}'. Set scripts.create_su_sheet_dir in config.yaml."
        if not cfg.script_create_su_sheet or not _exists(cfg.script_create_su_sheet):
            return f"Create SU sheet script not found at '{cfg.script_create_su_sheet}'. Set scripts.create_su_sheet in config.yaml."
        return None
    if not cfg.cloudcompy_python or not _exists(cfg.cloudcompy_python):
        return f"CloudComPy Python not found at '{cfg.cloudcompy_python}'. Set scripts.cloudcompy_python in config.yaml."
    if not cfg.volume_script_dir or not _exists(cfg.volume_script_dir):
        return f"Volume script directory not found at '{cfg.volume_script_dir}'. Set scripts.volume_script_dir in config.yaml."
    if kind == "pre_snip":
        if not cfg.script_pre_snip or not _exists(cfg.script_pre_snip):
            return f"Pre-snip script not found at '{cfg.script_pre_snip}'. Set scripts.pre_snip in config.yaml."
    elif kind == "auto_snip":
        if not cfg.script_auto_snip or not _exists(cfg.script_auto_snip):
            return f"Auto-snip script not found at '{cfg.script_auto_snip}'. Set scripts.auto_snip in config.yaml."
    elif kind == "post_snip":
        if not cfg.script_post_snip or not _exists(cfg.script_post_snip):
            return f"Post-snip script not found at '{cfg.script_post_snip}'. Set scripts.post_snip in config.yaml."
    return None


def start_run(kind: str) -> dict:
    with _lock:
        if _state["active"]:
            return {"started": False, "error": "A volume run is already in progress."}

        err = _validate(kind)
        if err:
            return {"started": False, "error": err}

        from_stage, _ = _STEPS[kind]
        su_rows = gsheets.get_su_rows()
        cards = [r for r in su_rows if r.get("stage") == from_stage]
        if not cards:
            from backend.models import SUEntry
            label = SUEntry.stage_label(from_stage)
            return {"started": False, "error": f"No volume cards in '{label}' to process."}

        _state["active"] = True
        _state["kind"] = kind
        _state["started_at"] = _now()
        _state["status"] = "running"
        _state["error"] = None
        _state["cards_advanced"] = 0

    thread = threading.Thread(target=_worker, args=(kind, cards), daemon=True)
    thread.start()
    return {"started": True, "kind": kind, "count": len(cards)}


def _now() -> str:
    from backend.models import cet_now
    return cet_now()


def _cloudcompy_env(cfg) -> Optional[dict]:
    """Subprocess environment for the CloudComPy volume scripts.

    The dashboard launches the venv's python.exe directly (no shell activation), so
    we must reproduce what the package's envCloudComPy.bat sets, or `import cloudComPy`
    fails: CloudCompare on PYTHONPATH (the bindings) and on PATH (the DLLs/plugins).
    Returns None when cloudcompy_root is unset/missing so the child inherits os.environ
    unchanged (preserving prior behaviour and keeping tests independent of the env).
    """
    root = cfg.cloudcompy_root
    if not root or not Path(root).is_dir():
        return None
    cc = os.path.join(root, "CloudCompare")
    pyapi = os.path.join(root, "doc", "PythonAPI_test")
    plugins = os.path.join(cc, "plugins")
    sep = os.pathsep
    env = os.environ.copy()
    env["PYTHONPATH"] = sep.join(p for p in (cc, pyapi, env.get("PYTHONPATH", "")) if p)
    env["PATH"] = sep.join(p for p in (cc, root, plugins, env.get("PATH", "")) if p)
    return env


def _worker(kind: str, cards: list[dict]) -> None:
    from_stage, to_stage = _STEPS[kind]
    _log(f"started '{kind}': {len(cards)} card(s) in '{from_stage}'")
    cfg = get_config()

    script = {
        "pre_snip":        cfg.script_pre_snip,
        "auto_snip":       cfg.script_auto_snip,
        "post_snip":       cfg.script_post_snip,
        "create_su_sheet": cfg.script_create_su_sheet,
    }[kind]

    cmd, cwd, env, count = _prepare_run(kind, script, cards, cfg)
    if count == 0:
        _finish(False, "No valid cards to process (missing pgrams).", 0)
        return

    _log(f"launching: {' '.join(cmd)} (cwd: {cwd})")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, env=env)
    except Exception as e:
        _finish(False, str(e), 0)
        return

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        _finish(False, detail[-800:] if detail else f"Script exited with code {proc.returncode}", 0)
        return

    # Script succeeded — advance all cards from from_stage → to_stage in Sheets
    # auto_snip sets snip_method="auto" so the debug image button appears;
    # pre_snip/post_snip clear it (no debug image produced by those scripts).
    snip = "auto" if kind == "auto_snip" else ""
    advanced = 0
    for card in cards:
        su_id = card["su_id"]
        try:
            gsheets.update_su_stage(su_id, to_stage, snip_method=snip)
            advanced += 1
        except Exception as e:
            _log(f"advance {su_id} to {to_stage} failed: {e}")

    _finish(True, None, advanced)
    _log(f"finished '{kind}': advanced {advanced}/{len(cards)} card(s)")


def _finish(ok: bool, error: Optional[str], advanced: int) -> None:
    with _lock:
        _state["active"] = False
        _state["status"] = "done" if ok else "failed"
        _state["error"] = error
        _state["cards_advanced"] = advanced


def start_chain_run() -> dict:
    """Run pre_snip → auto_snip → post_snip in sequence, then move all resulting
    volumetrics_created cards to su_sheet_created. Starts with any ready not_started
    cards being batch-moved to to_be_pre_snipped first."""
    with _lock:
        if _state["active"]:
            return {"started": False, "error": "A volume run is already in progress."}

        for kind in ("pre_snip", "auto_snip", "post_snip"):
            err = _validate(kind)
            if err:
                return {"started": False, "error": err}

        # Collect cards across all stages the chain will process
        su_rows = gsheets.get_su_rows()
        from backend.services.volume import annotate_readiness
        annotated = annotate_readiness(su_rows)
        ready_not_started = [r for r in annotated if r.get("stage") == "not_started" and r.get("ready")]
        pre_snip_cards = [r for r in su_rows if r.get("stage") == "to_be_pre_snipped"]
        snip_cards = [r for r in su_rows if r.get("stage") == "to_be_snipped"]
        post_snip_cards = [r for r in su_rows if r.get("stage") == "to_be_post_snipped"]
        vol_cards = [r for r in su_rows if r.get("stage") == "volumetrics_created"]

        total = (len(ready_not_started) + len(pre_snip_cards) + len(snip_cards)
                 + len(post_snip_cards) + len(vol_cards))
        if total == 0:
            return {"started": False, "error": "No cards to process in any pipeline stage."}

        _state["active"] = True
        _state["kind"] = "chain"
        _state["started_at"] = _now()
        _state["status"] = "running"
        _state["error"] = None
        _state["cards_advanced"] = 0

    thread = threading.Thread(
        target=_chain_worker,
        args=(ready_not_started, pre_snip_cards, snip_cards, post_snip_cards, vol_cards),
        daemon=True,
    )
    thread.start()
    return {"started": True, "kind": "chain", "count": total}


def _chain_worker(
    ready_not_started: list[dict],
    pre_snip_cards: list[dict],
    snip_cards: list[dict],
    post_snip_cards: list[dict],
    vol_cards: list[dict],
) -> None:
    cfg = get_config()
    total_advanced = 0

    # Step 0: batch-move ready not_started → to_be_pre_snipped
    for card in ready_not_started:
        try:
            gsheets.update_su_stage(card["su_id"], "to_be_pre_snipped")
            total_advanced += 1
        except Exception as e:
            _log(f"batch-move {card['su_id']} failed: {e}")
    if ready_not_started:
        _log(f"chain step 0: moved {len(ready_not_started)} not_started card(s) to to_be_pre_snipped")

    # The scripts process whatever is now in each stage
    steps = [
        ("pre_snip",        cfg.script_pre_snip,        "to_be_pre_snipped",  "to_be_snipped",       None),
        ("auto_snip",       cfg.script_auto_snip,       "to_be_snipped",       "to_be_post_snipped",  "auto"),
        ("post_snip",       cfg.script_post_snip,       "to_be_post_snipped",  "volumetrics_created", ""),
        ("create_su_sheet", cfg.script_create_su_sheet, "volumetrics_created", "su_sheet_created",    None),
    ]

    for step_num, (kind, script, from_stage, to_stage, snip) in enumerate(steps, start=1):
        # Gather current cards in from_stage (includes any just advanced by previous step)
        su_rows = gsheets.get_su_rows()
        cards = [r for r in su_rows if r.get("stage") == from_stage]
        if not cards:
            _log(f"chain step {step_num} ({kind}): no cards in '{from_stage}', skipping script")
            continue

        cmd, cwd, env, count = _prepare_run(kind, script, cards, cfg)
        if count == 0:
            _log(f"chain step {step_num} ({kind}): no valid cards, skipping script")
            continue

        _log(f"chain step {step_num} ({kind}): launching {' '.join(cmd)} on {len(cards)} card(s)")
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, env=env)
        except Exception as e:
            _finish(False, f"Step {step_num} ({kind}) failed to launch: {e}", total_advanced)
            return

        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()
            _finish(False, f"Step {step_num} ({kind}): " + (detail[-800:] if detail else f"exit code {proc.returncode}"), total_advanced)
            return

        for card in cards:
            try:
                gsheets.update_su_stage(card["su_id"], to_stage, snip_method=snip)
                total_advanced += 1
            except Exception as e:
                _log(f"chain step {step_num}: advance {card['su_id']} failed: {e}")

    _finish(True, None, total_advanced)
    _log(f"chain run finished: {total_advanced} card advancement(s) total")
