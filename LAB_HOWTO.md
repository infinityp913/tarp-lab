# TARP Lab Dashboard — How-To Guide

*For lab technicians using the MSI machine*

---

## Starting the dashboard

1. Open the `tarp-lab` folder on your Desktop.
2. Double-click **`start.bat`**.
3. A black command window will appear — leave it open. The dashboard will open in your browser automatically at **http://127.0.0.1:8000**.

To close the dashboard, close the black command window.

---

## First-time setup

You only need to do this once.

### Step 1 — Get access to the Google Sheet

Ask **Ananth** to share the TARP tracking Google Sheet for the current season with your Google account. You need edit access.

### Step 2 — Get the credentials file

Ask **Ananth** for the `credentials.json` file and place it inside the `tarp-lab` folder (the same folder where `start.bat` is). Do not rename the file.

### Step 3 — Authorise the app

The next time you double-click `start.bat`, a browser window will open asking you to sign in to Google and grant access. Use the Google account that Ananth shared the sheet with, then click **Allow**.

That's it. The authorisation is saved — you won't be asked again on this machine.

---

## Model Production tab

This tab shows all photogrammetry jobs as a board of cards.

**Columns** (left to right):
1. **To Be Processed** — job captured in the field, waiting for processing
2. **To Be Aligned** — in the alignment pipeline
3. **To Overnight** — running the overnight script
4. **Processed** — complete
5. **Uploaded to AIR** — delivered

**Moving a job:** click and drag a card to the next column. The folder on disk moves automatically. Two moves (Aligned → Overnight and Overnight → Processed) will ask a quick confirmation question first — answer honestly.

**Opening a project in Metashape / CloudCompare / QGIS:** each card has launch buttons. Click the button and the app will open with the right folder already selected.

**Creating a new job:** click **+ New Job** at the top. Fill in the job number and SU string — the folder will be created automatically.

---

## SU Volumes tab

This tab tracks individual stratigraphic units through the volumetrics pipeline.

**Columns:**
1. **Not Started**
2. **Volumetrics Created**
3. **SU Sheet Created**
4. **Uploaded to AIR**

**Top and Bottom Pgram:** each card shows two small number boxes. Type in the photogrammetry job numbers that cover the top and bottom of that SU. Click anywhere else and the numbers save automatically.

**Creating a new SU:** click **+ New SU**. The trench is filled in automatically if the SU number follows the standard format (e.g. SU 16014 → Trench 16000).

---

## Auto-sync

The dashboard keeps the Google Sheet up to date automatically every 5 minutes. You can see the status in the top-right corner of the header:

- **Green dot · Synced 2m ago** — everything is working
- **Yellow dot · Syncing…** — update in progress
- **Red dot · Sync error** — no internet or Sheets is unavailable; your data is safe and will sync when the connection returns

Click the pill to force an immediate sync at any time.

---

## Troubleshooting

| Problem | What to check |
|---|---|
| Dashboard doesn't open | Make sure the black command window is still open. Try going to http://127.0.0.1:8000 manually. |
| No jobs showing on the board | The stage folders may not be found. Check that the `tarp-lab` folder is configured correctly (ask Ananth). |
| Sync error (red dot) | Check that the machine is connected to the internet. It will retry automatically. |
| "Authorisation failed" on first run | Make sure `credentials.json` is in the right place and try again. |
| Folder won't move | Close the job in Metashape first — Windows locks the folder while it's open. |

---

## For developers (Mac setup)

```bash
# Install dependencies
pip install -r requirements.txt

# Run the backend with hot reload (reads dev_base_path and port from config.yaml,
# handles Google Sheets OAuth automatically on first run)
python3 -m backend.main --dev

# Run the frontend dev server in a second terminal
cd frontend && npm run dev

# Run tests
python3 -m pytest tests/ -v
```

Set `dev_base_path` in `config.yaml` to a local test folder that mirrors the stage-folder structure.
