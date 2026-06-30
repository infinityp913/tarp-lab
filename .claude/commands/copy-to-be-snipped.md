---
description: Copy half of the "To Be Snipped" SU folders to a drive for manual snipping in CloudCompare
argument-hint: "[drive, e.g. D: or 'Seagate 5TB']"
allowed-tools: Bash, AskUserQuestion
---

Copy **half** of the SU folders currently in the **To Be Snipped** stage from
`~/cloudcomparescript/Data` to a destination drive, into a folder named
`Temp folder for manual snipping` (created if it doesn't exist).

Only the first half (a deterministic 50% slice of the sorted SU list) is copied,
via `--portion first-half`.

The corresponding LiDAR **USDZ scans** from
`C:\Users\Public\SynologyDrive\tharros_syn_2` are copied into each SU folder too.
Scans are matched by SU number from the filename (e.g. `tarpf24441-SU_21001.usdz`
→ `SU21001`); one file may cover several SUs. This is on by default — pass
`--no-usdz` to skip it.

The list of "to be snipped" SUs is read live from the dashboard API, so it always
matches the kanban board. The backend must be running.

## Steps

1. Determine the destination drive from `$ARGUMENTS`:
   - If the user named a drive letter (e.g. `D:`), use it.
   - If they named a label (e.g. "Seagate 5TB"), map it to its drive letter by
     running: `powershell.exe -NoProfile -Command "Get-Volume | Select-Object DriveLetter,FileSystemLabel"`.
     The **Seagate 5TB** drive is `D:`.
   - If `$ARGUMENTS` is empty, ask the user which drive with AskUserQuestion
     (list the available drives/labels from the command above).

2. (Optional) Preview first with `--dry-run` if the user wants to check before copying.

3. Run the copy (only the first 50% of the SUs):
   ```bash
   python "C:/Users/Photogrammetry/Desktop/tarp-lab/.claude/scripts/copy_to_be_snipped.py" --dest "<DRIVE>:\\" --portion first-half
   ```
   (e.g. `--dest "D:\\"` for the Seagate 5TB drive.)

4. Report the summary the script prints: how many SU folders were copied (this is
   half of the total in 'To Be Snipped'), how many USDZ LiDAR scans were copied in,
   the destination path, and any SUs that had no source folder or no USDZ scan.
