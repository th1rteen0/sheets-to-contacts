"""
Google Form → Google Contacts Sync Script
==========================================
- Reads new responses from a Google Sheet
- Creates contacts via the Google People API
- Appends new contacts to the existing VCF file → all_contacts.vcf
- Exports new contacts only → Schumann Probies.vcf

Requires viewer access to the sheet only.
Tracks synced rows locally in synced_rows.json.

Setup: See README_SETUP.md
"""

import os
import json
import re
import gspread
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# ─────────────────────────────────────────────
# CONFIGURATION — edit these to match the setup
# ─────────────────────────────────────────────

SPREADSHEET_ID = "1V3rasAeC7cDzFmxybdLT3rwf6wgNQljfopkT1hGmWcM"
# Find this in the Google Sheet URL:
# https://docs.google.com/spreadsheets/d/THIS_PART_HERE/edit
# example: https://docs.google.com/spreadsheets/d/1V3rasAeC7cDzFmxybdLT3rwf6wgNQljfopkT1hGmWcM/edit?gid=1191427220#gid=1191427220

SHEET_NAME = "Form Responses 1"
# The tab name at the bottom of the spreadsheet

# Map the exact column headers (from row 1 of the sheet) to contact fields.
# Set "email" to None to skip it.
COLUMN_MAP = {
    "name":  "Name",           # → the sheet's name column header
    "phone": "Phone Number",   # → the sheet's phone column header
    "email": "UVA Email",             # → e.g. "Email Address", or None to skip
}

# Path to the existing VCF file (the one with the old contacts).
# Place it in the same folder as this script.
EXISTING_VCF_FILE = "vgs_spring26_contacts.vcf"

# Output VCF files (will be created/overwritten in the same folder)
ALL_CONTACTS_VCF   = "all_contacts_spring26.vcf"
NEW_CONTACTS_VCF   = "schumann_probies.vcf"

# Local file that tracks which rows have already been synced
SYNCED_LOG_FILE    = "synced_rows.json"

# Google API files
CREDENTIALS_FILE   = "credentials.json"
TOKEN_FILE         = "token.json"

# ─────────────────────────────────────────────
# SCOPES
# ─────────────────────────────────────────────

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/contacts",
]


# ─────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────

def get_credentials():
    """Handles OAuth2 login. Opens browser on first run, reuses token after."""
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())
    return creds


# ─────────────────────────────────────────────
# LOCAL SYNC LOG
# ─────────────────────────────────────────────

def load_synced_rows():
    if not os.path.exists(SYNCED_LOG_FILE):
        return set()
    with open(SYNCED_LOG_FILE, "r") as f:
        return set(json.load(f))


def save_synced_rows(synced):
    with open(SYNCED_LOG_FILE, "w") as f:
        json.dump(list(synced), f, indent=2)


def row_fingerprint(row):
    name  = str(row.get(COLUMN_MAP.get("name", ""), "")).strip()
    phone = str(row.get(COLUMN_MAP.get("phone", ""), "")).strip()
    return f"{name}|{phone}"


# ─────────────────────────────────────────────
# GOOGLE SHEETS
# ─────────────────────────────────────────────

def get_sheet_data(creds):
    gc = gspread.Client(auth=creds)
    spreadsheet = gc.open_by_key(SPREADSHEET_ID)
    worksheet = spreadsheet.worksheet(SHEET_NAME)
    return worksheet.get_all_records()


# ─────────────────────────────────────────────
# VCF HELPERS
# ─────────────────────────────────────────────

def load_existing_vcf():
    """
    Reads the existing VCF file and returns a list of raw vCard strings.
    Returns an empty list if the file doesn't exist.
    """
    if not os.path.exists(EXISTING_VCF_FILE):
        print(f"  ⚠️  No existing VCF file found at '{EXISTING_VCF_FILE}' — starting fresh.")
        return []

    with open(EXISTING_VCF_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    # Split into individual vCards
    cards = re.findall(r"BEGIN:VCARD.*?END:VCARD", content, re.DOTALL)
    print(f"  📂 Loaded {len(cards)} existing contact(s) from '{EXISTING_VCF_FILE}'.")
    return cards


def build_vcard(first, last, phone, email=None):
    """Builds a vCard 3.0 string for a single contact."""
    full_name = f"{first} {last}".strip()
    lines = [
        "BEGIN:VCARD",
        "VERSION:3.0",
        f"FN:{full_name}",
        f"N:{last};{first};;;",
    ]
    if phone:
        lines.append(f"TEL;TYPE=CELL:{phone}")
    if email:
        lines.append(f"EMAIL;TYPE=WORK:{email}")
    lines.append("END:VCARD")
    return "\n".join(lines)


def write_vcf(filepath, vcards):
    """Writes a list of vCard strings to a VCF file."""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n\n".join(vcards) + "\n")
    print(f"  💾 Saved {len(vcards)} contact(s) → {filepath}")


# ─────────────────────────────────────────────
# GOOGLE CONTACTS API
# ─────────────────────────────────────────────

def build_contact_body(first, last, phone, email=None):
    """Builds a Google People API contact body."""
    body = {
        "names": [{"givenName": first, "familyName": last}],
    }
    if phone:
        body["phoneNumbers"] = [{"value": phone, "type": "mobile"}]
    if email:
        body["emailAddresses"] = [{"value": email, "type": "work"}]
    return body


def create_api_contact(people_service, first, last, phone, email=None):
    body = build_contact_body(first, last, phone, email)
    result = people_service.people().createContact(body=body).execute()
    return result.get("resourceName", "unknown")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    print("\n🔐 Authenticating with Google...")
    creds = get_credentials()

    print("📋 Reading sheet data...")
    rows = get_sheet_data(creds)

    print("📂 Loading existing VCF...")
    existing_vcards = load_existing_vcf()

    synced = load_synced_rows()
    people_service = build("people", "v1", credentials=creds)

    new_vcards = []
    created = 0
    skipped = 0

    print(f"\n🔍 Found {len(rows)} total rows. Processing unsynced rows...\n")

    for i, row in enumerate(rows):
        row_index = i + 2

        fingerprint = row_fingerprint(row)

        if fingerprint in synced:
            skipped += 1
            continue

        # Parse fields
        name_value = str(row.get(COLUMN_MAP.get("name", ""), "")).strip()
        if not name_value:
            skipped += 1
            continue

        parts = name_value.split(" ", 1)
        first = parts[0]
        last  = parts[1] if len(parts) > 1 else ""

        phone = str(row.get(COLUMN_MAP.get("phone", ""), "")).strip()

        email = None
        email_col = COLUMN_MAP.get("email")
        if email_col:
            email = str(row.get(email_col, "")).strip() or None

        display_name = f"{first} {last}".strip()

        try:
            # 1. Create via People API
            resource_name = create_api_contact(people_service, first, last, phone, email)

            # 2. Build vCard for this contact
            vcard = build_vcard(first, last, phone, email)
            new_vcards.append(vcard)

            # 3. Mark as synced
            synced.add(fingerprint)
            save_synced_rows(synced)

            print(f"  ✅ Created contact: {display_name} ({resource_name})")
            created += 1

        except Exception as e:
            print(f"  ❌ Failed for row {row_index} ({display_name}): {e}")

    # ── Write VCF files ──────────────────────────────
    print(f"\n📝 Writing VCF files...")

    if new_vcards:
        # all_contacts.vcf = existing + new
        write_vcf(ALL_CONTACTS_VCF, existing_vcards + new_vcards)

        # Schumann Probies.vcf = new contacts only
        write_vcf(NEW_CONTACTS_VCF, new_vcards)
    else:
        print("  ℹ️  No new contacts to write — VCF files unchanged.")

    print(f"\n{'─'*50}")
    print(f"✅ Done!  Created: {created}  |  Skipped (already synced): {skipped}")
    if new_vcards:
        print(f"📁 {ALL_CONTACTS_VCF}  → all contacts ({len(existing_vcards) + len(new_vcards)} total)")
        print(f"📁 {NEW_CONTACTS_VCF}  → new contacts only ({len(new_vcards)})")
    print(f"{'─'*50}\n")


if __name__ == "__main__":
    main()
