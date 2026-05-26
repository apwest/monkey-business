"""Shared parsing for Monte & Mortimer Woot dialogues.

Both migrate.py (legacy templates/X/Y.html bulk conversion) and update.py
(daily Gmail scrape) use this module to turn raw HTML into the clip record
shape stored in data/clips.jsonl:

    {"id": N, "date": "YYYY-MM-DD", "style": "v1|v2|v2-alt|v3|unknown",
     "lines": [{"speaker": "monte|mortimer", "text": "..."}]}

The `style` field records which Monte/Mortimer image set the original email
used, so the rebuilt site can preserve era-appropriate images.
"""

from __future__ import annotations

import html
import re
from datetime import datetime

# URL -> (speaker, style) mapping.
# Style keys group equivalent images across http/https/proxy variants.
URL_STYLE_MAP: dict[str, tuple[str, str]] = {
    # Era 1: 2011-era cloudfront
    "https://d2w0pyk7viytzg.cloudfront.net/monkey_left.png":  ("mortimer", "v1"),
    "https://d2w0pyk7viytzg.cloudfront.net/monkey_right.png": ("monte",    "v1"),

    # Era 2: mid cloudfront (no .2 suffix)
    "http://d3rqdbvvokrlbl.cloudfront.net/images/email/monkey-left.png":  ("mortimer", "v2"),
    "http://d3rqdbvvokrlbl.cloudfront.net/images/email/monkey-right.png": ("monte",    "v2"),

    # Era 2-alt: mid cloudfront (.2 suffix — looks like a refresh)
    "http://d3rqdbvvokrlbl.cloudfront.net/images/email/monkey-left.2.png":   ("mortimer", "v2-alt"),
    "http://d3rqdbvvokrlbl.cloudfront.net/images/email/monkey-right.2.png":  ("monte",    "v2-alt"),
    "https://d3rqdbvvokrlbl.cloudfront.net/images/email/monkey-left.2.png":  ("mortimer", "v2-alt"),
    "https://d3rqdbvvokrlbl.cloudfront.net/images/email/monkey-right.2.png": ("monte",    "v2-alt"),

    # Era 3: current Amazon CDN, plus Gmail-proxied versions
    "http://g-ec2.images-amazon.com/images/G/01/woot/emails/acquisition/monte-2.png":    ("monte",    "v3"),
    "http://g-ec2.images-amazon.com/images/G/01/woot/emails/acquisition/mortimer-2.png": ("mortimer", "v3"),
}

# Gmail proxy URLs embed the underlying URL after `#`. Strip the prefix for lookup.
GMAIL_PROXY_RE = re.compile(r"^https://ci\d+\.googleusercontent\.com/proxy/[^#]*#(http.*)$")

# Era 4 (June 2025+): "rebrand" images on m.media-amazon.com. The cache-bust
# `._CB<digits>_.png` suffix changes over time, so match by speaker stem
# instead of exact URL.
V4_MORT_RE = re.compile(r"MortMonkeyChat", re.IGNORECASE)
V4_MONTE_RE = re.compile(r"MonteMonkeyChat", re.IGNORECASE)

LEGACY_DATE_RE = re.compile(r"date:\s*<span>(.*?)</span>", re.IGNORECASE)
TABLE_RE = re.compile(r"<table.*?</table>", re.DOTALL | re.IGNORECASE)
IMG_SRC_RE = re.compile(r'<img[^>]*\bsrc="([^"]+)"', re.IGNORECASE)
P_TEXT_RE = re.compile(r"<p[^>]*>(.*?)</p>", re.DOTALL | re.IGNORECASE)
TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


def normalize_url(url: str) -> str:
    m = GMAIL_PROXY_RE.match(url)
    return m.group(1) if m else url


def clean_text(html_fragment: str) -> str:
    text = TAG_RE.sub("", html_fragment)
    text = html.unescape(text)
    return WS_RE.sub(" ", text).strip()


def parse_release_date_from_legacy_wrapper(raw_html: str) -> str | None:
    """Pull the date out of migrate.py's saved 'Original release date: <span>...</span>' wrapper.

    Only relevant for the legacy templates/X/Y.html files. Returns ISO date
    (YYYY-MM-DD) on success, the raw string if not parseable, or None if no
    date wrapper is present.
    """
    m = LEGACY_DATE_RE.search(raw_html)
    if not m:
        return None
    raw = m.group(1).strip()
    try:
        return datetime.strptime(raw, "%a, %d %b %Y").date().isoformat()
    except ValueError:
        return raw


def parse_clip(raw_html: str) -> tuple[list[dict], set[str]]:
    """Return (lines, image_urls_seen). lines := [{speaker, text}, ...]"""
    lines: list[dict] = []
    urls_seen: set[str] = set()

    for table_match in TABLE_RE.finditer(raw_html):
        table = table_match.group()

        # Identify speaker from the <img> alt/src in this table.
        speaker = None
        for img_match in IMG_SRC_RE.finditer(table):
            url = normalize_url(img_match.group(1))
            urls_seen.add(url)
            mapped = URL_STYLE_MAP.get(url)
            if mapped:
                speaker = mapped[0]
                break
            # v4 (June 2025+): match by speaker stem since URL has a
            # variable cache-bust suffix.
            if V4_MORT_RE.search(url):
                speaker = "mortimer"
                break
            if V4_MONTE_RE.search(url):
                speaker = "monte"
                break
            # Fall back to filename hints for legacy variants not in the map.
            lower = url.lower()
            if "monte" in lower or "right" in lower:
                speaker = "monte"
                break
            if "mortimer" in lower or "left" in lower:
                speaker = "mortimer"
                break

        # No image? Skip this table — it's layout filler, not dialogue.
        if speaker is None:
            continue

        # First <p> inside the table holds the line of dialogue.
        p_match = P_TEXT_RE.search(table)
        if not p_match:
            continue
        text = clean_text(p_match.group(1))
        if not text:
            continue

        lines.append({"speaker": speaker, "text": text})

    return lines, urls_seen


def infer_style(urls_seen: set[str]) -> str:
    styles = {URL_STYLE_MAP[u][1] for u in urls_seen if u in URL_STYLE_MAP}
    # URL_STYLE_MAP doesn't list v4 entries (cache-bust suffixes are variable);
    # detect v4 by stem match against the seen URLs.
    if any(V4_MORT_RE.search(u) or V4_MONTE_RE.search(u) for u in urls_seen):
        styles.add("v4")
    if len(styles) == 1:
        return styles.pop()
    if len(styles) > 1:
        # Mixed within one clip — pick the most "modern" (v4 > v3 > v2-alt > v2 > v1).
        for preferred in ("v4", "v3", "v2-alt", "v2", "v1"):
            if preferred in styles:
                return preferred
    return "unknown"


def build_clip_record(clip_id: int, raw_html: str, date_iso: str | None = None) -> dict | None:
    """Parse raw email HTML into a clip record, or None if no parseable lines.

    Returns the record shape stored in data/clips.jsonl. Used by update.py
    for live Gmail scrapes; migrate.py composes the same shape directly so
    it can also surface diagnostic stats.
    """
    lines, urls_seen = parse_clip(raw_html)
    if not lines:
        return None
    return {
        "id": clip_id,
        "date": date_iso or "",
        "style": infer_style(urls_seen),
        "lines": lines,
    }
