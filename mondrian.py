#!/usr/bin/env python3
"""mondrian_noun.py — render a Nock noun as a Mondrian dyadic subdivision (SVG).

A cell splits its rectangle in two (alternating vertical/horizontal by depth:
even depth splits vertically, head left / tail right; odd depth splits
horizontally, head top / tail bottom). An atom is a leaf tile. Axis addressing
is geometric: read the axis's binary expansion after the leading 1; each 0-bit
descends into the head sub-rectangle, each 1-bit into the tail.

Sizing is driven by --min-leaf M: every leaf tile is at least M x M pixels and
the canvas grows to accommodate the noun. Two layout modes:

  compact (default)  bottom-up required-size layout. Leaf needs (M, M); a cell
                     needs the sum of its children's sizes along the split axis
                     and the max across it. Canvas = root requirement. Every
                     leaf is >= M x M; deeper/larger nouns produce larger
                     canvases linearly in leaf count. Sacrifices congruence of
                     equal-depth tiles.

  dyadic             strict halving. Exact subdivision semantics: equal nouns
                     at equal depth are congruent tiles, area = 2^-depth.
                     Canvas = M * 2^ceil(dmax/2) x M * 2^floor(dmax/2), which
                     is exponential in depth — guarded by --max-dim.

Usage:
  python3 mondrian_noun.py '[8 [1 0] 9 2 0 1]'
  python3 mondrian_noun.py @formula.txt --mode dyadic --axes -o out.svg
  echo '[42 [1 2] 3]' | python3 mondrian_noun.py - --highlight 6 --highlight 14
"""
import argparse
import hashlib
import html
import sys

sys.setrecursionlimit(1_000_000)

from pinochle import parse, to_noun, deep, head, tail

# ---------------------------------------------------------------- palette
PALETTE = ["#76003B", "#BB0F3D", "#EF4F34", "#4E3C00", "#6E6806",
           "#7F9B19", "#004A40", "#087475", "#179FB5", "#2000B9",
           "#6627F2", "#A863F9"]
HIGHLIGHT = "#ffd700"
GRID = "#222222"


def atom_color(a: int) -> str:
    if a < len(PALETTE):
        return PALETTE[a]
    h = hashlib.blake2b(a.to_bytes((a.bit_length() + 7) // 8 or 1, "little"),
                        digest_size=3).digest()
    # keep it dark enough for white text
    r, g, b = (min(c, 0xb0) for c in h)
    return f"#{r:02x}{g:02x}{b:02x}"


def atom_label(a: int, max_chars: int) -> str:
    s = str(a)
    if len(s) <= max_chars:
        return s
    if max_chars < 4:
        return ""
    return s[: max_chars - 1] + "\u2026"


# ---------------------------------------------------------------- layout
def required_size(n, depth: int, m: float):
    """Compact mode: minimum (w, h) to render noun n starting at this depth."""
    n = to_noun(n)
    if not deep(n):
        return (m, m)
    hw, hh = required_size(head(n), depth + 1, m)
    tw, th = required_size(tail(n), depth + 1, m)
    if depth % 2 == 0:   # vertical split: widths add, heights max
        return (hw + tw, max(hh, th))
    else:                # horizontal split: heights add, widths max
        return (max(hw, tw), hh + th)


def max_depth(n, depth: int = 0) -> int:
    n = to_noun(n)
    if not deep(n):
        return depth
    return max(max_depth(head(n), depth + 1), max_depth(tail(n), depth + 1))


def count_leaves(n) -> int:
    n = to_noun(n)
    if not deep(n):
        return 1
    return count_leaves(head(n)) + count_leaves(tail(n))


# ---------------------------------------------------------------- render
class Renderer:
    def __init__(self, mode: str, min_leaf: float, highlights: set,
                 show_axes: bool):
        self.mode = mode
        self.m = min_leaf
        self.highlights = highlights
        self.show_axes = show_axes
        self.tiles = []      # svg fragments, base layer
        self.overlay = []    # svg fragments, highlight layer (drawn on top)

    def emit_leaf(self, a: int, x, y, w, h, axis: int):
        hl = axis in self.highlights
        rect = (f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" '
                f'height="{h:.2f}" fill="{atom_color(a)}" '
                f'stroke="{GRID}" stroke-width="0.5"/>')
        self.tiles.append(rect)
        if hl:
            self.overlay.append(
                f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" '
                f'height="{h:.2f}" fill="none" stroke="{HIGHLIGHT}" '
                f'stroke-width="3"/>')
        # value label
        max_chars = int(w // 7)
        if h >= 12 and max_chars >= 1:
            lbl = atom_label(a, max_chars)
            if lbl:
                self.tiles.append(
                    f'<text x="{x + w / 2:.1f}" y="{y + h / 2 + 4:.1f}" '
                    f'font-size="11" fill="#ffffff" text-anchor="middle" '
                    f'font-family="monospace">{html.escape(lbl)}</text>')
        # axis annotation
        if self.show_axes and h >= 26 and w >= 22:
            self.tiles.append(
                f'<text x="{x + 3:.1f}" y="{y + 11:.1f}" font-size="8" '
                f'fill="#aaaaaa" font-family="monospace">/{axis}</text>')

    def render(self, n, x, y, w, h, depth: int, axis: int):
        n = to_noun(n)
        if not deep(n):
            self.emit_leaf(int(n), x, y, w, h, axis)
            return
        hd, tl = head(n), tail(n)
        if self.mode == "dyadic":
            if depth % 2 == 0:
                self.render(hd, x, y, w / 2, h, depth + 1, axis * 2)
                self.render(tl, x + w / 2, y, w / 2, h, depth + 1, axis * 2 + 1)
            else:
                self.render(hd, x, y, w, h / 2, depth + 1, axis * 2)
                self.render(tl, x, y + h / 2, w, h / 2, depth + 1, axis * 2 + 1)
        else:  # compact: allocate proportional to required size along split axis
            hw, hh = required_size(hd, depth + 1, self.m)
            tw, th = required_size(tl, depth + 1, self.m)
            if depth % 2 == 0:
                fw = w * hw / (hw + tw)
                self.render(hd, x, y, fw, h, depth + 1, axis * 2)
                self.render(tl, x + fw, y, w - fw, h, depth + 1, axis * 2 + 1)
            else:
                fh = h * hh / (hh + th)
                self.render(hd, x, y, w, fh, depth + 1, axis * 2)
                self.render(tl, x, y + fh, w, h - fh, depth + 1, axis * 2 + 1)


def render_svg(n, mode="compact", min_leaf=14.0, highlights=None,
               show_axes=False, label="", max_dim=16384):
    highlights = set(highlights or [])
    n = to_noun(n)
    if mode == "dyadic":
        d = max_depth(n)
        W = min_leaf * (2 ** ((d + 1) // 2))
        H = min_leaf * (2 ** (d // 2))
        if max(W, H) > max_dim:
            raise SystemExit(
                f"dyadic canvas {W:.0f}x{H:.0f} exceeds --max-dim {max_dim} "
                f"(noun depth {d}). Use --mode compact or raise --max-dim.")
    else:
        W, H = required_size(n, 0, min_leaf)

    pad, label_h = 10, (22 if label else 0)
    r = Renderer(mode, min_leaf, highlights, show_axes)
    r.render(n, pad, pad + label_h, W, H, 0, 1)

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" '
             f'width="{W + 2 * pad:.0f}" height="{H + 2 * pad + label_h:.0f}" '
             f'style="background:#ffffff">']
    if label:
        parts.append(f'<text x="{pad}" y="{pad + 12}" font-size="13" '
                     f'font-family="monospace" font-weight="bold">'
                     f'{html.escape(label)}</text>')
    parts.extend(r.tiles)
    parts.extend(r.overlay)
    parts.append("</svg>")
    return "\n".join(parts), (W, H)


# ---------------------------------------------------------------- cli
def read_input(src: str) -> str:
    if src == "-":
        return sys.stdin.read()
    if src.startswith("@"):
        with open(src[1:]) as f:
            return f.read()
    return src


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("noun", help="noun text, @file, or - for stdin")
    ap.add_argument("--mode", choices=["compact", "dyadic"], default="compact")
    ap.add_argument("--min-leaf", type=float, default=14.0,
                    help="minimum leaf tile size in px (default 14)")
    ap.add_argument("--highlight", type=int, action="append", default=[],
                    metavar="AXIS", help="outline the tile at AXIS (repeatable)")
    ap.add_argument("--axes", action="store_true",
                    help="annotate leaf tiles with their axis address")
    ap.add_argument("--label", default="", help="title text")
    ap.add_argument("--max-dim", type=int, default=16384,
                    help="refuse dyadic canvases larger than this (px)")
    ap.add_argument("-o", "--out", default="mondrian.svg")
    args = ap.parse_args()

    noun = parse(read_input(args.noun).strip())
    svg, (W, H) = render_svg(noun, args.mode, args.min_leaf,
                             args.highlight, args.axes, args.label,
                             args.max_dim)
    with open(args.out, "w") as f:
        f.write(svg)
    print(f"{args.out}: {W:.0f}x{H:.0f}px canvas, "
          f"{count_leaves(noun)} leaves, depth {max_depth(noun)}, "
          f"mode={args.mode}, min-leaf={args.min_leaf}")


if __name__ == "__main__":
    main()
