"""One-time helper: mint a Gmail OAuth refresh token for GitHub Actions.

Run this locally once. It opens a browser for Google OAuth consent, then
prints the three values to paste into GitHub Secrets:

    GOOGLE_OAUTH_CLIENT_ID
    GOOGLE_OAUTH_CLIENT_SECRET
    GOOGLE_OAUTH_REFRESH_TOKEN

Usage:
    venv/bin/python bootstrap_refresh_token.py path/to/client_secret.json

Where client_secret.json is the "Desktop app" OAuth client credentials
downloaded from Google Cloud Console (APIs & Services → Credentials).
Make sure the OAuth client is in "Production" mode (not "Testing") or the
refresh token will expire after 7 days.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2

    client_secrets_path = Path(sys.argv[1])
    if not client_secrets_path.exists():
        print(f"File not found: {client_secrets_path}")
        return 1

    flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets_path), SCOPES)
    # access_type=offline + prompt=consent are required to get a refresh_token back.
    creds = flow.run_local_server(
        port=0,
        access_type="offline",
        prompt="consent",
    )

    if not creds.refresh_token:
        print("ERROR: Google returned no refresh token. "
              "Ensure the OAuth client is a Desktop app and the consent screen is in Production mode.")
        return 1

    with client_secrets_path.open() as f:
        client_info = json.load(f)
    installed = client_info.get("installed") or client_info.get("web") or {}

    print("\nAdd these to your repo as GitHub Actions secrets:\n")
    print(f"  GOOGLE_OAUTH_CLIENT_ID     = {installed.get('client_id', '<missing>')}")
    print(f"  GOOGLE_OAUTH_CLIENT_SECRET = {installed.get('client_secret', '<missing>')}")
    print(f"  GOOGLE_OAUTH_REFRESH_TOKEN = {creds.refresh_token}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
