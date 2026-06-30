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
    """Return the su_id list for cards currently in the to_be_snipped stage."""
    try:
        with urlopen(api_url, timeout=20) as resp:
            rows = json.load(resp)
    except Exception as e:  # noqa: BLE001 - surface a clear, actionable message
        raise SystemExit(
            f"ERROR: could not reach the dashboard API at {api_url}\n"
            f"       ({e})\n"
            f"       Start the backend (python -m backend.main) and try again."
        )
    return [r["su_id"] for r in rows if r.get("stage") == TARGET_STAGE]


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
            "Which slice of the (sorted) to_be_snipped SUs to copy. "
            "Use 'first-half' for the drive and 'second-half' for the SUs being "
            "snipped on this machine (the split is deterministic). Default: all."
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
        print("No SUs are currently in the 'To Be Snipped' stage. Nothing to copy.")
        return 0

    # Deterministic split so the two machines never pick the same SU.
    ordered = sorted(all_su_ids)
    mid = (len(ordered) + 1) // 2  # first-half gets the larger slice on odd counts
    if args.portion == "first-half":
        su_ids = ordered[:mid]
        other = ordered[mid:]
    elif args.portion == "second-half":
        su_ids = ordered[mid:]
        other = ordered[:mid]
    else:
        su_ids, other = ordered, []

    print(f"{len(all_su_ids)} SU(s) in 'To Be Snipped'; copying portion='{args.portion}' ({len(su_ids)}).")
    if other:
        print(f"  (other half, NOT copied here: {', '.join('SU' + s for s in other)})")
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

    print()
    verb = "Would copy" if args.dry_run else "Copied"
    print(f"{verb} {len(copied)} SU folder(s) to {dest_root}")
    if not args.no_usdz:
        print(f"{verb} {usdz_copied} USDZ LiDAR scan(s) into the SU folders.")
        if usdz_missing:
            print(f"  ({len(usdz_missing)} SU(s) had no USDZ scan: {', '.join('SU' + s for s in usdz_missing)})")
    if missing:
        print(f"WARNING: {len(missing)} SU(s) had no source folder: {', '.join(missing)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
