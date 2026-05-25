"""One-shot: convert templates/X/Y.html into data/clips.jsonl.

Each clip becomes one JSON line:
    {"id": N, "date": "...", "style": "v1|v2|v2-alt|v3|unknown", "lines": [{"speaker": "monte|mortimer", "text": "..."}]}

Parsing lives in clips.py — this script just iterates the legacy template
files, calls into the shared parser, and prints diagnostic stats.
"""

import json
import os
import re
import sys
from collections import Counter

from clips import (
    URL_STYLE_MAP,
    infer_style,
    parse_clip,
    parse_release_date_from_legacy_wrapper,
)

TEMPLATES_DIR = "templates"
OUT_PATH = "data/clips.jsonl"


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

            date = parse_release_date_from_legacy_wrapper(raw)
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
