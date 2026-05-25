"""Daily Gmail-to-clips.jsonl pipeline.

Reads unread messages from the Gmail label `woot`, extracts Monte & Mortimer
dialogue, appends new clip records to data/clips.jsonl, and marks each
processed message as read so the next run only sees new mail.

Designed to run headless from GitHub Actions. Credentials come from env vars:

    GOOGLE_OAUTH_CLIENT_ID
    GOOGLE_OAUTH_CLIENT_SECRET
    GOOGLE_OAUTH_REFRESH_TOKEN

Use bootstrap_refresh_token.py once locally to mint the refresh token.
"""

from __future__ import annotations

import argparse
import base64
import email
import json
import os
import sys
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from clips import TABLE_RE, build_clip_record

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]
TOKEN_URI = "https://oauth2.googleapis.com/token"

ROOT = Path(__file__).parent
JSONL_PATH = ROOT / "data" / "clips.jsonl"

QUERY = "label:woot is:unread"

# Marker strings that indicate an email's HTML contains a Monte/Mortimer dialogue.
# Mirrors the heuristic used by the original update.py / migrate.py parser.
CLIP_MARKERS = ("monkey-", "monkey_", "mortimer-2.png", "monte-2.png")


def authenticate() -> Credentials:
    """Build Credentials from env vars and refresh the access token."""
    missing = [
        name for name in (
            "GOOGLE_OAUTH_CLIENT_ID",
            "GOOGLE_OAUTH_CLIENT_SECRET",
            "GOOGLE_OAUTH_REFRESH_TOKEN",
        ) if not os.environ.get(name)
    ]
    if missing:
        raise SystemExit(f"Missing required env vars: {', '.join(missing)}")

    creds = Credentials(
        token=None,
        refresh_token=os.environ["GOOGLE_OAUTH_REFRESH_TOKEN"],
        token_uri=TOKEN_URI,
        client_id=os.environ["GOOGLE_OAUTH_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_OAUTH_CLIENT_SECRET"],
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return creds


def get_next_clip_id(path: Path) -> int:
    """Return max(id)+1 across clips.jsonl, or 1 if the file is missing/empty."""
    max_id = 0
    if path.exists():
        with path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(rec.get("id"), int):
                    max_id = max(max_id, rec["id"])
    return max_id + 1


def list_unread_woot_messages(service) -> list[dict]:
    """List unread messages matching the woot label, paginating through all results."""
    messages: list[dict] = []
    page_token = None
    while True:
        response = service.users().messages().list(
            userId="me", q=QUERY, pageToken=page_token
        ).execute()
        messages.extend(response.get("messages", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return messages


def get_mime_message(service, msg_id: str):
    """Fetch a Gmail message as a parsed MIME object."""
    raw_msg = service.users().messages().get(
        userId="me", id=msg_id, format="raw"
    ).execute()
    raw_bytes = base64.urlsafe_b64decode(raw_msg["raw"].encode("ASCII"))
    return email.message_from_bytes(raw_bytes)


def mark_as_read(service, msg_id: str) -> None:
    service.users().messages().modify(
        userId="me", id=msg_id, body={"removeLabelIds": ["UNREAD"]}
    ).execute()


def extract_clip_html(mime_msg) -> str | None:
    """Return the concatenated dialogue-table HTML from a Woot email, or None.

    Walks MIME parts, finds the text part containing Monte/Mortimer, then
    pulls out every <table>...</table> block that sits at or before a known
    monkey-image marker, mirroring the heuristic in the legacy update.py.
    """
    for part in mime_msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
        try:
            txt = part.get_payload(decode=True).decode("utf-8")
        except Exception:
            continue
        if not any(name in txt for name in ("Monte", "Mortimer", "monte", "mortimer")):
            continue
        if not any(marker in txt for marker in CLIP_MARKERS):
            continue
        # clips.py's TABLE_RE finds all tables; we filter to those that
        # reference a known monkey marker so layout tables get dropped.
        tables = [
            m.group() for m in TABLE_RE.finditer(txt)
            if any(marker in m.group() for marker in CLIP_MARKERS)
        ]
        if tables:
            return "".join(tables)
    return None


def email_date_iso(mime_msg) -> str | None:
    """Parse the Date header into 'YYYY-MM-DD' (clip-record format)."""
    raw = mime_msg.get("Date")
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    return dt.date().isoformat() if dt else None


def append_records(path: Path, records: list[dict]) -> None:
    if not records:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def main(limit: int | None = None) -> int:
    creds = authenticate()
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)

    messages = list_unread_woot_messages(service)
    # Process oldest first so clip IDs increase monotonically by send date.
    messages.reverse()

    if not messages:
        print("No new messages.")
        return 0

    total = len(messages)
    if limit and limit > 0 and limit < total:
        messages = messages[:limit]
        print(f"Processing {limit} of {total} unread message(s) (limit applied)...")
    else:
        print(f"Processing {total} unread message(s)...")
    next_id = get_next_clip_id(JSONL_PATH)
    new_records: list[dict] = []

    for i, msg in enumerate(messages, 1):
        msg_id = msg["id"]
        try:
            mime = get_mime_message(service, msg_id)
        except HttpError as e:
            print(f"  [{i}] fetch failed for {msg_id}: {e}")
            continue

        clip_html = extract_clip_html(mime)
        if clip_html is None:
            print(f"  [{i}] {msg_id}: no Monte/Mortimer dialogue found; marking read")
            mark_as_read(service, msg_id)
            continue

        date_iso = email_date_iso(mime)
        record = build_clip_record(next_id, clip_html, date_iso)
        if record is None:
            print(f"  [{i}] {msg_id}: tables found but no parseable lines; marking read")
            mark_as_read(service, msg_id)
            continue

        print(f"  [{i}] {msg_id}: extracted clip #{next_id} ({date_iso or 'no date'}, {len(record['lines'])} lines)")
        new_records.append(record)
        next_id += 1
        mark_as_read(service, msg_id)

    append_records(JSONL_PATH, new_records)
    print(f"\nAdded {len(new_records)} new clip(s) to {JSONL_PATH.relative_to(ROOT)}.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape unread Woot mail into data/clips.jsonl.")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of unread messages to process this run. Unset = process all.",
    )
    args = parser.parse_args()
    sys.exit(main(limit=args.limit))
