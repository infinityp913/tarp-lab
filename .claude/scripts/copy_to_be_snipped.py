#!/usr/bin/env python3
"""Copy the SU folders currently in the 'To Be Snipped' stage from the
cloudcomparescript ``Data`` directory to a destination drive, ready for an
operator to crop them manually in CloudCompare.

The list of "to be snipped" SUs is read live from the running dashboard API
(``/api/su/entries``), so this always matches what the kanban board shows.

Usage:
    python copy_to_be_snipped.py --dest "D:\\"
    python copy_to_be_snipped.py --dest "D:\\" --dry-run

Notes:
- The dashboard backend must be running (default http://127.0.0.1:8000).
- Destination layout: <dest>\\Temp folder for manual snipping\\SU<su>\\...
  The "Temp folder for manual snipping" folder is created if missing.
- Existing SU folders at the destination are overwritten (merged) so re-running
  picks up any newly-snipped state without manual cleanup.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from urllib.request import urlopen

API_URL = "http://127.0.0.1:8000/api/su/entries"
DEST_SUBFOLDER = "Temp folder for manual snipping"
DEFAULT_DATA_DIR = Path.home() / "cloudcomparescript" / "Data"
TARGET_STAGE = "to_be_snipped"

# LiDAR USDZ scans live here, named like "tarpf24441-SU_21001.usdz". A single
# file may cover several SUs, e.g. "...-SU_22018_22019_22021.usdz".
DEFAULT_USDZ_DIR = Path(r"C:\Users\Public\SynologyDrive\tharros_syn_2")
_USDZ_SU_RE = re.compile(r"-SU_([0-9_]+)\.usdz$", re.IGNORECASE)

# Persistent record of SUs already copied out for manual snipping in past runs,
# so subsequent runs don't hand the same SU to an operator twice. Lives next to
# this script; a JSON list of su_id strings (e.g. ["20013", "21001"]).
DEFAULT_LEDGER = Path(__file__).with_name("copied_sus.json")


def load_ledger(path: Path) -> set[str]:
    """Return the set of su_ids recorded as already copied (empty if none)."""
    try:
        with open(path, encoding="utf-8") as fh:
            return set(json.load(fh))
    except FileNotFoundError:
        return set()
    except (OSError, ValueError) as e:  # noqa: BLE001 - corrupt/unreadable ledger
        raise SystemExit(f"ERROR: could not read ledger {path}: {e}")


def save_ledger(path: Path, su_ids: set[str]) -> None:
    """Write the ledger back as a sorted JSON list."""
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(sorted(su_ids), fh, indent=2)


def usdz_matches(usdz_dir: Path, su_ids: list[str]) -> dict[str, list[Path]]:
    """Map each SU id to the USDZ scan files whose name includes that SU number."""
    targets = set(su_ids)
    matches: dict[str, list[Path]] = {}
    if not usdz_dir.is_dir():
        return matches
    for f in usdz_dir.glob("*.usdz"):
        m = _USDZ_SU_RE.search(f.name)
        if not m:
            continue
        for tok in m.group(1).split("_"):
            if tok in targets:
                matches.setdefault(tok, []).append(f)
    return matches


def get_to_be_snipped(api_url: str) -> list[str]:
    """Return su_ids for 'To Be Snipped' cards that are ready to extract.

    A card is included only when its ``ready`` flag is true (server-computed:
    both top & bottom pgrams are processed and a matching LiDAR scan exists).
    """
    try:
        with urlopen(api_url, timeout=20) as resp:
            rows = json.load(resp)
    except Exception as e:  # noqa: BLE001 - surface a clear, actionable message
        raise SystemExit(
            f"ERROR: could not reach the dashboard API at {api_url}\n"
            f"       ({e})\n"
            f"       Start the backend (python -m backend.main) and try again."
        )
    return [
        r["su_id"]
        for r in rows
        if r.get("stage") == TARGET_STAGE and r.get("ready")
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dest",
        required=True,
        help=r'Destination drive or folder root, e.g. "D:\\" (Seagate 5TB).',
    )
    parser.add_argument(
        "--data-dir",
        default=str(DEFAULT_DATA_DIR),
        help="cloudcomparescript Data directory (default: ~/cloudcomparescript/Data).",
    )
    parser.add_argument(
        "--api-url",
        default=API_URL,
        help="Dashboard SU entries endpoint.",
    )
    parser.add_argument(
        "--portion",
        choices=["all", "first-half", "second-half"],
        default="all",
        help=(
            "How much of the not-yet-copied ready SUs to copy this run: "
            "'first-half' copies 50%% now and leaves the rest for the next run, "
            "'all' copies everything remaining. Default: all."
        ),
    )
    parser.add_argument(
        "--prune",
        action="store_true",
        help=(
            "Before copying, delete any SU folders already at the destination that "
            "are NOT in the selected portion (keeps the drive holding only its half)."
        ),
    )
    parser.add_argument(
        "--usdz-dir",
        default=str(DEFAULT_USDZ_DIR),
        help="Folder of LiDAR USDZ scans to copy alongside each SU (default: Synology tharros_syn_2).",
    )
    parser.add_argument(
        "--no-usdz",
        action="store_true",
        help="Skip copying the corresponding USDZ LiDAR scans into each SU folder.",
    )
    parser.add_argument(
        "--ledger",
        default=str(DEFAULT_LEDGER),
        help="JSON file recording SUs already copied in past runs (skipped this run).",
    )
    parser.add_argument(
        "--no-ledger",
        action="store_true",
        help="Ignore the ledger: don't skip previously-copied SUs and don't record new ones.",
    )
    parser.add_argument(
        "--reset-ledger",
        action="store_true",
        help="Clear the ledger before this run (start tracking copied SUs from scratch).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be copied without copying.",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.is_dir():
        raise SystemExit(f"ERROR: Data directory not found: {data_dir}")

    dest_root = Path(args.dest) / DEST_SUBFOLDER

    all_su_ids = get_to_be_snipped(args.api_url)
    if not all_su_ids:
        print("No ready-to-extract SUs are in the 'To Be Snipped' stage. Nothing to copy.")
        return 0

    ledger_path = Path(args.ledger)
    already = set() if (args.no_ledger or args.reset_ledger) else load_ledger(ledger_path)

    # Work only with SUs not yet copied in a past run.
    candidates = sorted(s for s in all_su_ids if s not in already)
    skipped_prev = sorted(s for s in all_su_ids if s in already)
    if not candidates:
        print(f"All {len(all_su_ids)} ready SU(s) have already been copied in past runs. Nothing new to copy.")
        return 0

    # Copy a portion of the not-yet-copied SUs. 'first-half' takes 50% now and
    # leaves the rest for the next run (nothing is reserved for another machine);
    # 'all' copies everything remaining.
    mid = (len(candidates) + 1) // 2  # first-half gets the larger slice on odd counts
    if args.portion == "first-half":
        su_ids, remainder = candidates[:mid], candidates[mid:]
    elif args.portion == "second-half":
        su_ids, remainder = candidates[mid:], candidates[:mid]
    else:  # all
        su_ids, remainder = candidates, []

    print(f"{len(all_su_ids)} ready-to-extract SU(s) in 'To Be Snipped'; "
          f"{len(candidates)} not yet copied; copying portion='{args.portion}' ({len(su_ids)}).")
    if skipped_prev:
        print(f"  ({len(skipped_prev)} already copied in past runs, skipped)")
    if remainder:
        print(f"  (remaining for a later run: {', '.join('SU' + s for s in remainder)})")
    if not su_ids:
        print("Nothing to copy for this portion.")
        return 0
    print(f"Source: {data_dir}")
    print(f"Dest:   {dest_root}")
    print()

    if not args.dry_run:
        dest_root.mkdir(parents=True, exist_ok=True)

    # Optionally remove SU folders at the destination that belong to the other half,
    # so the drive only ever holds its assigned portion.
    if args.prune and other:
        selected = set(su_ids)
        for existing in sorted(dest_root.glob("SU*")):
            if existing.is_dir() and existing.name[2:] not in selected:
                if args.dry_run:
                    print(f"  WOULD PRUNE  {existing.name}")
                else:
                    shutil.rmtree(existing)
                    print(f"  PRUNED  {existing.name}")
        print()

    usdz_map = {} if args.no_usdz else usdz_matches(Path(args.usdz_dir), su_ids)

    copied, missing = [], []
    usdz_copied, usdz_missing = 0, []
    for su in su_ids:
        src = data_dir / f"SU{su}"
        if not src.is_dir():
            missing.append(su)
            print(f"  MISS  SU{su}  (no source folder at {src})")
            continue
        dst = dest_root / f"SU{su}"
        if args.dry_run:
            print(f"  WOULD COPY  SU{su}  ->  {dst}")
        else:
            shutil.copytree(src, dst, dirs_exist_ok=True)
            print(f"  COPIED  SU{su}  ->  {dst}")
        copied.append(su)

        if not args.no_usdz:
            scans = usdz_map.get(su, [])
            if not scans:
                usdz_missing.append(su)
            for f in scans:
                if args.dry_run:
                    print(f"    WOULD COPY USDZ  {f.name}  ->  SU{su}\\")
                else:
                    shutil.copy2(f, dst / f.name)
                    print(f"    USDZ  {f.name}  ->  SU{su}\\")
                usdz_copied += 1

    # Record the SUs actually copied so future runs skip them.
    if copied and not args.no_ledger and not args.dry_run:
        updated = (set() if args.reset_ledger else already) | set(copied)
        save_ledger(ledger_path, updated)

    print()
    verb = "Would copy" if args.dry_run else "Copied"
    print(f"{verb} {len(copied)} SU folder(s) to {dest_root}")
    if not args.no_usdz:
        print(f"{verb} {usdz_copied} USDZ LiDAR scan(s) into the SU folders.")
        if usdz_missing:
            print(f"  ({len(usdz_missing)} SU(s) had no USDZ scan: {', '.join('SU' + s for s in usdz_missing)})")
    if missing:
        print(f"WARNING: {len(missing)} SU(s) had no source folder: {', '.join(missing)}")
    if copied and not args.no_ledger and not args.dry_run:
        print(f"Ledger updated: {ledger_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
