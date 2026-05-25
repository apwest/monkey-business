"""Static site generator. Reads data/clips.jsonl, writes dist/ ready for GitHub Pages.

URL structure: each clip lives at /<id>/ (file: dist/<id>/index.html).
GH Pages 301-redirects /<id> -> /<id>/, preserving old App Engine links.
"""

import json
import shutil
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).parent
DATA_PATH = ROOT / "data" / "clips.jsonl"
STATIC_SRC = ROOT / "static"
TEMPLATES_DIR = ROOT / "site_templates"
DIST = ROOT / "dist"

# v2 originals are 404'd at the CDN with no Wayback snapshot — fall back to v2-alt,
# which is literally the .2.png refresh of the same era image.
STYLE_IMAGES = {
    "v1":     ("mortimer-v1.png",     "monte-v1.png"),
    "v2":     ("mortimer-v2-alt.png", "monte-v2-alt.png"),
    "v2-alt": ("mortimer-v2-alt.png", "monte-v2-alt.png"),
    "v3":     ("mortimer-v3.png",     "monte-v3.png"),
}
DEFAULT_STYLE = "v3"


def load_clips():
    clips = []
    with open(DATA_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                clips.append(json.loads(line))
    clips.sort(key=lambda c: c["id"])
    return clips


def display_date(iso: str) -> str:
    """ISO YYYY-MM-DD -> 'July 4, 2011'. Pass through if not ISO."""
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%B %-d, %Y")
    except (ValueError, TypeError):
        return iso or ""


def build():
    clips = load_clips()
    if not clips:
        raise SystemExit("No clips found in data/clips.jsonl — run migrate.py first.")

    ids = [c["id"] for c in clips]
    first_id, last_id = ids[0], ids[-1]
    id_index = {cid: i for i, cid in enumerate(ids)}

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    clip_tpl = env.get_template("clip.html")
    search_tpl = env.get_template("search.html")
    random_tpl = env.get_template("random.html")

    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    shutil.copytree(STATIC_SRC, DIST / "static")

    # GH Pages: skip Jekyll processing.
    (DIST / ".nojekyll").touch()

    index_entries = [
        {
            "id": c["id"],
            "date": c.get("date", ""),
            "text": " ".join(line["text"] for line in c["lines"]),
        }
        for c in clips
    ]
    (DIST / "clips_index.json").write_text(
        json.dumps(index_entries, separators=(",", ":"), ensure_ascii=False),
        encoding="utf-8",
    )

    for name, tpl in (("search", search_tpl), ("random", random_tpl)):
        page_dir = DIST / name
        page_dir.mkdir()
        (page_dir / "index.html").write_text(tpl.render(), encoding="utf-8")

    for clip in clips:
        clip["date_display"] = display_date(clip["date"])
        i = id_index[clip["id"]]
        prev_id = ids[i - 1] if i > 0 else clip["id"]
        next_id = ids[i + 1] if i < len(ids) - 1 else clip["id"]
        mortimer_img, monte_img = STYLE_IMAGES.get(clip["style"], STYLE_IMAGES[DEFAULT_STYLE])

        html = clip_tpl.render(
            clip=clip,
            first=first_id,
            prev=prev_id,
            next=next_id,
            last=last_id,
            mortimer_img=mortimer_img,
            monte_img=monte_img,
        )
        page_dir = DIST / str(clip["id"])
        page_dir.mkdir()
        (page_dir / "index.html").write_text(html, encoding="utf-8")

    # Homepage = most recent clip.
    latest_html = (DIST / str(last_id) / "index.html").read_text(encoding="utf-8")
    (DIST / "index.html").write_text(latest_html, encoding="utf-8")

    print(f"Built {len(clips)} clip pages -> {DIST}")
    print(f"Latest clip: #{last_id} ({clips[-1].get('date_display', '?')})")


if __name__ == "__main__":
    build()
