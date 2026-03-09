"""
Delete Synced Contacts
======================
Deletes all Google Contacts that were previously created by sheets_to_contacts.py.
Reads synced_rows.json to know which names to delete.

Run ONCE to clean up, then fix the COLUMN_MAP and re-run sheets_to_contacts.py.
"""

import os
import json
import time
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

TOKEN_FILE      = "token.json"
CREDENTIALS_FILE = "credentials.json"
SYNCED_LOG_FILE = "synced_rows.json"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/contacts",
]

def get_credentials():
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

def get_names_to_delete():
    """Reads synced_rows.json and extracts the names that were synced."""
    if not os.path.exists(SYNCED_LOG_FILE):
        print("❌ No synced_rows.json found — nothing to delete.")
        return set()
    with open(SYNCED_LOG_FILE, "r") as f:
        fingerprints = json.load(f)
    # Each fingerprint is "Name|Phone" — extract just the name part
    return {fp.split("|")[0].strip().lower() for fp in fingerprints if fp}

def main():
    print("\n🔐 Authenticating with Google...")
    creds = get_credentials()
    service = build("people", "v1", credentials=creds)

    names_to_delete = get_names_to_delete()
    if not names_to_delete:
        return

    print(f"🗑  Will delete contacts matching these names: {', '.join(names_to_delete)}\n")

    # Fetch all contacts
    print("📋 Fetching all Google Contacts...")
    all_connections = []
    next_page_token = None

    while True:
        params = {
            "resourceName": "people/me",
            "pageSize": 1000,
            "personFields": "names,phoneNumbers",
        }
        if next_page_token:
            params["pageToken"] = next_page_token

        result = service.people().connections().list(**params).execute()
        all_connections.extend(result.get("connections", []))
        next_page_token = result.get("nextPageToken")
        if not next_page_token:
            break

    print(f"   Found {len(all_connections)} total contacts.\n")

    deleted = 0
    for person in all_connections:
        names = person.get("names", [])
        if not names:
            continue

        display_name = names[0].get("displayName", "").strip().lower()
        resource_name = person.get("resourceName")

        if display_name in names_to_delete:
            try:
                service.people().deleteContact(resourceName=resource_name).execute()
                print(f"  🗑  Deleted: {names[0].get('displayName')} ({resource_name})")
                deleted += 1
                time.sleep(0.3)  # avoid rate limiting
            except Exception as e:
                print(f"  ❌ Failed to delete {display_name}: {e}")

    print(f"\n{'─'*50}")
    print(f"✅ Done! Deleted {deleted} contact(s).")
    print(f"{'─'*50}\n")

    if deleted > 0:
        os.remove(SYNCED_LOG_FILE)
        print("🧹 Cleared synced_rows.json — ready to re-run sheets_to_contacts.py\n")

if __name__ == "__main__":
    main()
