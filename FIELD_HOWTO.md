# TARP Field Dashboard — How-To Guide

*For field archaeologists using the Alienware machine*

---

## Starting the dashboard

1. Open the `tarp-field` folder on your Desktop.
2. Double-click **`start.bat`**.
3. A black command window will appear — leave it open. The dashboard will open in your browser automatically at **http://127.0.0.1:8000**.

To close the dashboard, close the black command window.

---

## First-time setup

You only need to do this once.

### Step 1 — Get access to the Google Sheet

Ask **Ananth** to share the TARP tracking Google Sheet for the current season with your Google account. You need edit access.

### Step 2 — Get the credentials file

Ask **Ananth** for the `credentials.json` file and place it inside the `tarp-field` folder (the same folder where `start.bat` is). Do not rename the file.

### Step 3 — Authorise the app

The next time you double-click `start.bat`, a browser window will open asking you to sign in to Google and grant access. Use the Google account that Ananth shared the sheet with, then click **Allow**.

That's it. The authorisation is saved — you won't be asked again on this machine.

---

## The board

The board shows all photogrammetry jobs as cards in three columns:

| Column | Meaning |
|---|---|
| **Not Started** | Job folder created, waiting for field capture |
| **Aligned** | Alignment script has run |
| **Move to MSI** | Ready for the lab — the folder is renamed automatically so the MSI machine picks it up |

**Moving a job:** click and drag a card to the next column.

---

## Adding notes to a job

Click any job card to open it. A notes area will appear — type anything relevant:

- Which SUs are open or closed
- Drone vs. handheld capture
- Anything unusual about the conditions

Click anywhere outside the card when you're done. Notes save automatically and will appear on the Lab dashboard within 60 seconds.

---

## Push button

The **Push** button in the header sends all current job states to Google Sheets immediately, without waiting for the 60-second auto-sync. Use it after making several changes to make sure the lab has the latest data right away.

---

## Offline use

If the Alienware loses WiFi:

- A **red dot** appears in the top-right corner — the app keeps working normally
- Any changes you make are saved locally and queued
- When the connection returns, everything syncs automatically
- You don't need to do anything — just wait for the dot to turn green

---

## Troubleshooting

| Problem | What to check |
|---|---|
| Dashboard doesn't open | Make sure the black command window is still open. Try going to http://127.0.0.1:8000 manually. |
| No jobs showing on the board | The stage folders may not be found. Check that the `tarp-field` folder is configured correctly (ask Ananth). |
| Red dot — offline | Check WiFi; the app will retry automatically. |
| "Authorisation failed" on first run | Make sure `credentials.json` is in the right place and try again. |
| Notes not appearing on Lab | Hit Push, or wait for the next 60 s auto-sync. |
| Move to MSI fails | Check the folder isn't open in another application. |

---

## For developers (Mac setup)

```bash
# Clone the repo and install dependencies
pip install -r requirements.txt

# Run the backend
uvicorn backend.main:app --reload

# Run the frontend dev server (hot reload)
cd frontend && npm run dev
```

Set `dev_base_path` in `config.yaml` to a local test folder that mirrors the stage-folder structure.

For first-time Google Sheets auth on Mac, start with `python3 backend/main.py` instead of `uvicorn` — this triggers the OAuth browser flow before the server starts.
