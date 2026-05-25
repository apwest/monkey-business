"""One-shot: convert templates/X/Y.html into data/clips.jsonl.

Each clip becomes one JSON line:
    {"id": N, "date": "...", "style": "v1|v2|v2-alt|v3|unknown", "lines": [{"speaker": "monte|mortimer", "text": "..."}]}

The `style` field records which Monte/Mortimer image set the original email used,
so we can preserve era-appropriate images on the rebuilt site.
"""

import html
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime

TEMPLATES_DIR = "templates"
OUT_PATH = "data/clips.jsonl"

# URL -> (speaker, style) mapping.
# Style keys group equivalent images across http/https/proxy variants.
URL_STYLE_MAP = {
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

DATE_RE = re.compile(r"date:\s*<span>(.*?)</span>", re.IGNORECASE)
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


def parse_release_date(raw_html: str) -> str | None:
    """Return ISO date (YYYY-MM-DD) or None if unparseable."""
    m = DATE_RE.search(raw_html)
    if not m:
        return None
    raw = m.group(1).strip()
    try:
        return datetime.strptime(raw, "%a, %d %b %Y").date().isoformat()
    except ValueError:
        return raw  # keep raw form rather than dropping data


def parse_clip(raw_html: str) -> tuple[list[dict], set[str]]:
    """Return (lines, image_urls_seen). lines := [{speaker, text}, ...]"""
    lines: list[dict] = []
    urls_seen: set[str] = set()

    for table_match in TABLE_RE.finditer(raw_html):
        table = table_match.group()

        # Identify speaker from the <img> alt/src in this table.
        speaker = None
        img_url_in_table = None
        for img_match in IMG_SRC_RE.finditer(table):
            url = normalize_url(img_match.group(1))
            img_url_in_table = url
            urls_seen.add(url)
            mapped = URL_STYLE_MAP.get(url)
            if mapped:
                speaker = mapped[0]
                break
            # Fall back to filename hints if URL isn't in the map.
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
    if len(styles) == 1:
        return styles.pop()
    if len(styles) > 1:
        # Mixed within one clip — pick the most "modern" (v3 > v2-alt > v2 > v1).
        for preferred in ("v3", "v2-alt", "v2", "v1"):
            if preferred in styles:
                return preferred
    return "unknown"


def iter_clip_files():
    for sub in sorted(os.listdir(TEMPLATES_DIR), key=lambda s: int(s) if s.isdigit() else 1e9):
        sub_path = os.path.join(TEMPLATES_DIR, sub)
        if not (os.path.isdir(sub_path) and sub.isdigit()):
            continue
        x = int(sub)
        for name in sorted(os.listdir(sub_path), key=lambda s: int(s.split(".")[0]) if s.split(".")[0].isdigit() else 1e9):
            m = re.match(r"(\d+)\.html$", name)
            if not m:
                continue
            y = int(m.group(1))
            clip_id = 1000 * (x - 1) + y
            yield clip_id, os.path.join(sub_path, name)


def main():
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)

    style_counts: Counter[str] = Counter()
    unknown_url_counts: Counter[str] = Counter()
    line_count_distribution: Counter[int] = Counter()
    empty_clips: list[int] = []
    no_date_clips: list[int] = []

    written = 0
    with open(OUT_PATH, "w") as out:
        for clip_id, path in iter_clip_files():
            with open(path) as f:
                raw = f.read()
            if not raw.strip():
                empty_clips.append(clip_id)
                continue

            date = parse_release_date(raw)
            if date is None:
                no_date_clips.append(clip_id)

            lines, urls_seen = parse_clip(raw)
            for url in urls_seen:
                if url not in URL_STYLE_MAP:
                    unknown_url_counts[url] += 1

            style = infer_style(urls_seen)
            style_counts[style] += 1
            line_count_distribution[len(lines)] += 1

            if not lines:
                empty_clips.append(clip_id)
                continue

            record = {
                "id": clip_id,
                "date": date or "",
                "style": style,
                "lines": lines,
            }
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            written += 1

    print(f"Wrote {written} clips to {OUT_PATH}\n")
    print("Style breakdown:")
    for style, count in style_counts.most_common():
        print(f"  {style:10s} {count:5d}")
    print("\nLine count distribution (top 10):")
    for n, count in sorted(line_count_distribution.most_common(10)):
        print(f"  {n:2d} lines  {count:5d}")
    if unknown_url_counts:
        print("\nUnknown image URLs encountered:")
        for url, count in unknown_url_counts.most_common():
            print(f"  ({count:4d}x) {url}")
    if empty_clips:
        print(f"\n{len(empty_clips)} clips skipped (empty or no parseable lines).")
        if len(empty_clips) <= 20:
            print(f"  IDs: {empty_clips}")
    if no_date_clips:
        print(f"\n{len(no_date_clips)} clips had no release date.")
        if len(no_date_clips) <= 20:
            print(f"  IDs: {no_date_clips}")


if __name__ == "__main__":
    sys.exit(main())
