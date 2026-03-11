# Google Form → Google Contacts + VCF Export

## Overview

This script reads new form responses from a Google Sheet and:

1. Creates contacts in Google Contacts via the People API
2. Appends new contacts to the existing VCF file
3. Exports new contacts only

It only needs **viewer access** to the sheet and tracks synced rows locally so repeated runs only process new entries.

---

## Files

```
the-folder-name/
├── sheets_to_contacts.py         ← main sync script
├── delete_synced_contacts.py     ← cleanup: deletes previously created contacts
├── existing_contacts.vcf         ← THE existing contacts file (you provide this)
├── credentials.json              ← downloaded from Google Cloud (keep private)
├── token.json                    ← auto-created after first login (keep private)
├── synced_rows.json              ← auto-created; tracks synced rows locally
├── all_contacts_SEMESTERYEAR.vcf ← output: existing + new contacts
└── NEWCLASSNAME_probies.vcf      ← output: new contacts only
```

> ⚠️ Never share `credentials.json` or `token.json` — they grant access to the Tech Chair Google account.

---

## One-Time Setup

### Step 1 — Set up virtual environment and install libraries

```bash
python3 -m venv venv
source venv/bin/activate
pip install gspread google-auth google-auth-oauthlib google-api-python-client
```

### Step 2 — Create Google Cloud credentials

1. Go to https://console.cloud.google.com/
2. Click **"Select a project"** → **"New Project"** → name it anything (e.g. `contacts-sync`)
3. Go to **APIs & Services → Library** and enable these two APIs:
   - ✅ Google Sheets API
   - ✅ People API
4. Go to **APIs & Services → OAuth consent screen**
   - Choose **External** → click Create
   - Fill in App name and Gmail email → click through all steps
5. On the OAuth consent screen page, click on **Audience** on the sidebar, scroll to **Test users** → **+ Add Users**
   - Add Gmail email here (required or login will fail with access_denied)
6. Go to **APIs & Services → Credentials**
   - Click **"+ Create Credentials"** → **OAuth client ID**
   - Application type: **Desktop app** → name it anything (e.g. `contacts-sync`) → click Create
7. Click **Download JSON**, rename it to `credentials.json`
8. Place `credentials.json` in the same folder as `sheets_to_contacts.py`

### Step 3 — Add the existing contacts file and rename Output VCF files

Place the existing VCF file in the same folder and update EXISTING_VCF_FILE:
```
EXISTING_VCF_FILE = "existing_vcf_file_name"
```

Update ALL_CONTACTS_VCF variable to reflect the current semester:
```
EXISTING_VCF_FILE = "all_contacts_SEMESTERYEAR.vcf"
```

Update NEW_CONTACTS_VCF variable to reflect the new probie class name:
```
EXISTING_VCF_FILE = "NEWCLASSNAME_probies.vcf"
```

If you don't have one yet, the script will create both output files from scratch using only the new contacts.

### Step 4 — Configure the script

Open `sheets_to_contacts.py` and update:

**Spreadsheet ID** — from the Google Sheet URL:
```
https://docs.google.com/spreadsheets/d/COPY_THIS_PART/edit
```
```python
SPREADSHEET_ID = "paste_the_id_here"
```

**Sheet tab name:**
```python
SHEET_NAME = "Form Responses 1"  # check the tab at the bottom of the response sheet
```

**Column headers** — must match Row 1 of the response sheet exactly:
```python
COLUMN_MAP = {
    "name":  "Name",           # the response sheet's name column header
    "phone": "Phone Number",   # the response sheet's phone column header
    "email": None,             # set to the response sheet's email column header to enable, or leave as None
}
```

---

## Running the Script

Activate the virtual environment each time you open a new terminal:
```bash
cd ~/sheets-to-contacts
source venv/bin/activate
```

Run the sync:
```bash
python3 sheets_to_contacts.py
```

On the **first run**, a browser window will open for Google login. Sign in with the account that has access to the sheet and contacts. If you see "Google hasn't verified this app", click **Continue**.

After each run you'll find:
- `all_contacts_SEMESTERYEAR.vcf` — the existing contacts + all new ones combined
- `NEWCLASSNAME_probies.vcf`      — only the contacts added in this run

---

## Running Again Later

Just run the script again — it will only process rows that haven't been synced yet:
```bash
source venv/bin/activate
python3 sheets_to_contacts.py
```

Each run refreshes both VCF files. `all_contacts_SEMESTERYEAR.vcf` always includes everything; `NEWCLASSNAME_probies.vcf` only includes contacts from the most recent run.

---

## Deleting Previously Created Contacts

If you need to undo a sync run:
```bash
python3 delete_synced_contacts.py
```

This deletes all contacts created in the last sync from Google Contacts and clears `synced_rows.json` so you can start fresh.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError` | Activate venv first: `source venv/bin/activate` |
| `Error 403: access_denied` on login | Add your Gmail under Test Users in the OAuth consent screen |
| `SpreadsheetNotFound` (404) | Check `SPREADSHEET_ID` is correct and you're signed in with an account that has access |
| Phone/email missing from contacts | Column header in `COLUMN_MAP` doesn't match your sheet exactly — check spacing and capitalisation |
| `NEWCLASSNAME_probies.vcf` is empty | No new rows were found — all rows were already in `synced_rows.json` |
| Want to re-export all contacts as new | Delete `synced_rows.json` and re-run (will re-create API contacts too) |
