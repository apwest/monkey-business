"""PNG inspection and manipulation utilities used during the v1/v2-alt monkey
image migration. Kept around in case future image variants need the same
treatment (e.g., new Woot email styles).

Subcommands:
  info         Show dimensions, color type, and whether each PNG has an alpha channel.
  corners      Sample corner + edge-midpoint pixels (useful for spotting an
               opaque background that needs to be made transparent).
  transparify  Flood-fill from each corner and turn the connected background
               region transparent. Modifies files in place.

Examples:
  python png_tools.py info static/img/*.png
  python png_tools.py corners static/img/monte-v1.png
  python png_tools.py transparify static/img/monte-v1.png static/img/mortimer-v1.png
  python png_tools.py transparify --threshold 25 static/img/whatever.png
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from struct import unpack

from PIL import Image, ImageDraw

COLOR_TYPE_NAMES = {
    0: "gray",
    2: "RGB",
    3: "palette",
    4: "gray+alpha",
    6: "RGB+alpha",
}
ALPHA_TYPES = {4, 6}

# Marker color used to tag flood-filled pixels. Picked so no real image pixel
# is likely to match it.
FLOOD_MARKER = (1, 2, 3)


# ---------- info ----------

def read_png_header(path: Path) -> tuple[int, int, int, int]:
    """Return (width, height, bit_depth, color_type) by reading the IHDR chunk."""
    with open(path, "rb") as f:
        f.seek(16)
        width, height = unpack(">II", f.read(8))
        bit_depth, color_type = unpack(">BB", f.read(2))
    return width, height, bit_depth, color_type


def cmd_info(paths: list[Path]) -> int:
    for p in paths:
        if not p.exists():
            print(f"  skip {p}: not found", file=sys.stderr)
            continue
        w, h, depth, ct = read_png_header(p)
        ct_name = COLOR_TYPE_NAMES.get(ct, f"?{ct}")
        has_alpha = ct in ALPHA_TYPES
        aspect = w / h if h else 0
        print(f"  {str(p):40s}  {w}x{h}  aspect={aspect:.3f}  depth={depth}  color={ct_name}  alpha={has_alpha}")
    return 0


# ---------- corners ----------

def cmd_corners(paths: list[Path]) -> int:
    for p in paths:
        if not p.exists():
            print(f"  skip {p}: not found", file=sys.stderr)
            continue
        im = Image.open(p).convert("RGBA")
        w, h = im.size
        samples = [
            ("TL",      (0, 0)),
            ("TR",      (w - 1, 0)),
            ("BL",      (0, h - 1)),
            ("BR",      (w - 1, h - 1)),
            ("T-mid",   (w // 2, 0)),
            ("B-mid",   (w // 2, h - 1)),
        ]
        print(f"  {p}:")
        for label, point in samples:
            r, g, b, a = im.getpixel(point)
            print(f"    {label:5s} {point}: rgb=({r},{g},{b}) alpha={a}")
    return 0


# ---------- transparify ----------

CORNER_NAMES = ("TL", "TR", "BL", "BR")


def corner_point(name: str, w: int, h: int) -> tuple[int, int]:
    return {
        "TL": (0, 0),
        "TR": (w - 1, 0),
        "BL": (0, h - 1),
        "BR": (w - 1, h - 1),
    }[name]


def make_background_transparent(path: Path, threshold: int = 15,
                                corners: tuple[str, ...] = CORNER_NAMES) -> None:
    im = Image.open(path).convert("RGBA")
    w, h = im.size

    rgb = im.convert("RGB")
    for name in corners:
        ImageDraw.floodfill(rgb, corner_point(name, w, h), FLOOD_MARKER, thresh=threshold)

    px = rgb.load()
    alpha = im.getchannel("A").load()
    new_alpha = Image.new("L", (w, h))
    new_alpha.putdata([
        0 if px[x, y] == FLOOD_MARKER else alpha[x, y]
        for y in range(h)
        for x in range(w)
    ])
    im.putalpha(new_alpha)
    im.save(path, optimize=True)


def cmd_transparify(paths: list[Path], threshold: int, corners: tuple[str, ...]) -> int:
    for p in paths:
        if not p.exists():
            print(f"  skip {p}: not found", file=sys.stderr)
            continue
        make_background_transparent(p, threshold, corners)
        print(f"  {p}: background -> transparent (corners={','.join(corners)})")
    return 0


# ---------- CLI ----------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="png_tools", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("info", help="Show dimensions / alpha status per file.")
    sp.add_argument("paths", nargs="+", type=Path)

    sp = sub.add_parser("corners", help="Sample corner + edge-midpoint pixels.")
    sp.add_argument("paths", nargs="+", type=Path)

    sp = sub.add_parser("transparify", help="Flood-fill backgrounds to transparent (in place).")
    sp.add_argument("paths", nargs="+", type=Path)
    sp.add_argument("--threshold", type=int, default=15,
                    help="Flood-fill color tolerance, 0-255 (default 15)")
    sp.add_argument("--corners", default="TL,TR,BL,BR",
                    help="Comma-separated list of corners to flood from. "
                         "Use to skip corners that contain the subject "
                         "(e.g. --corners TL,TR for an image where the subject "
                         "touches the bottom edge). Default: TL,TR,BL,BR.")

    args = ap.parse_args(argv)
    if args.cmd == "info":
        return cmd_info(args.paths)
    if args.cmd == "corners":
        return cmd_corners(args.paths)
    if args.cmd == "transparify":
        corners = tuple(c.strip().upper() for c in args.corners.split(",") if c.strip())
        bad = [c for c in corners if c not in CORNER_NAMES]
        if bad:
            ap.error(f"Invalid corner(s): {bad}. Valid: {', '.join(CORNER_NAMES)}")
        return cmd_transparify(args.paths, args.threshold, corners)
    return 2  # unreachable


if __name__ == "__main__":
    sys.exit(main())
