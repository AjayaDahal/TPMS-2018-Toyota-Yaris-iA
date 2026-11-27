#!/usr/bin/env python3
"""The carrier's signature for its bottom silkscreen: the AjayaDesign mark and wordmark over the dedication.

    python make_signature_art.py [--preview FILE.png]

Writes signature_art.json: filled polygons (outline + holes) in mm, origin at the block's top-left, y down, as read
from the bottom side (not mirrored). build_carrier.py mirrors the block onto B.SilkS at carrier_layout.SIGNATURE.
Change the words here, run this, then rebuild the carrier: the copper doesn't change.

The mark is the website's favicon (https://ajayadesign.com/favicon.svg): its ink is the red ring, the red "A" and
the blue circuit node; the dark background stays bare board. The words are set in JetBrains Mono Bold, the website's
typeface (SIL Open Font License 1.1), downloaded once into build/fonts/ (git-ignored). Bold's joins, where an arch
meets a stem (r, n, h, a), are 50 font units: 0.185 mm at the dedication's 2.7 mm cap height, which sets that size.
Smaller type would need a heavier weight, and ExtraBold shuts the a's aperture instead.

Checks, for JLCPCB's silkscreen (0.153 mm minimum line): every stroke and every gap at least 0.18 mm, tested by
morphological opening and closing. Needs fontTools and shapely.
"""
import argparse
import json
import os
import sys
import urllib.request

from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont
from shapely import affinity
from shapely.geometry import LineString, MultiPolygon, Point, Polygon, box
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "signature_art.json")
FONT_URL = "https://raw.githubusercontent.com/JetBrains/JetBrainsMono/master/fonts/ttf/JetBrainsMono-{}.ttf"
FONT_DIR = os.path.join(HERE, "build", "fonts")

WORDMARK = "AjayaDesign"
DEDICATION = ("Designed by Ajaya Dahal", "for his Basanti 2018,", "Toyota Yaris iA")
WEIGHT = "Bold"
MARK_MM = 12.5              # the mark's square
WORDMARK_CAP_MM = 4.0       # cap height of the wordmark
TEXT_CAP_MM = 2.7           # cap height of the dedication (see above)
MARK_GAP_MM = 2.5           # mark to wordmark
ROW_GAP_MM = 3.0            # mark row to the first dedication line (cap top)
LINE_PITCH_MM = 4.6         # dedication baseline to baseline
MIN_STROKE_MM = 0.18
MIN_GAP_MM = 0.18
LUMP_MM2 = 0.04             # ink an opening or closing may move at one spot: a rounded corner, not a lost stroke
FLATNESS_MM = 0.01          # curve flattening tolerance


# ---------------------------------------------------------------------- the mark (favicon.svg, 64 x 64 units)
def mark(size):
    """favicon.svg's ink: ring (rounded square, centre line 2..62, r 10, stroke 2.5), the "A" with its counter, and
    the circuit node (dot r 3 at (52, 12), two 1.5-wide round-capped lines). SVG units, y down."""
    centre = box(12, 12, 52, 52).buffer(10, quad_segs=32)              # the rounded square's centre line
    ring = centre.buffer(1.25, quad_segs=32).difference(centre.buffer(-1.25, quad_segs=32))
    a = Polygon([(32, 12), (48, 50), (42, 50), (38.5, 40), (25.5, 40), (22, 50), (16, 50)],
                [[(27.5, 35), (36.5, 35), (32, 22)]])
    node = unary_union([Point(52, 12).buffer(3, quad_segs=24),
                        LineString([(52, 15), (52, 22)]).buffer(0.75, quad_segs=12),
                        LineString([(49, 12), (42, 12)]).buffer(0.75, quad_segs=12)])
    ink = unary_union([ring, a, node])
    return affinity.scale(ink, size / 64.0, size / 64.0, origin=(0, 0))


# ---------------------------------------------------------------------- text from the font's outlines
class _FlatPen(BasePen):
    """Glyph outlines as closed point lists; quadratic and cubic segments flattened to FLATNESS (font units)."""

    def __init__(self, glyphset, flat):
        super().__init__(glyphset)
        self.rings, self.cur, self.flat = [], [], flat

    def _moveTo(self, p):
        self.cur = [p]

    def _lineTo(self, p):
        self.cur.append(p)

    def _steps(self, pts):
        length = sum(((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5 for a, b in zip(pts, pts[1:]))
        return max(2, min(64, int((length / (8 * self.flat)) ** 0.5 * 2) + 2))

    def _qCurveToOne(self, p1, p2):
        p0 = self.cur[-1]
        n = self._steps([p0, p1, p2])
        for i in range(1, n + 1):
            t = i / n
            u = 1 - t
            self.cur.append((u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
                             u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]))

    def _curveToOne(self, p1, p2, p3):
        p0 = self.cur[-1]
        n = self._steps([p0, p1, p2, p3])
        for i in range(1, n + 1):
            t = i / n
            u = 1 - t
            self.cur.append(tuple(u ** 3 * a + 3 * u * u * t * b + 3 * u * t * t * c + t ** 3 * d
                                  for a, b, c, d in zip(p0, p1, p2, p3)))

    def _closePath(self):
        if len(self.cur) > 2:
            self.rings.append(self.cur)
        self.cur = []

    _endPath = _closePath


def _signed_area(ring):
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:] + ring[:1])) / 2


def text_ink(font, s, cap_mm):
    """The string's ink in mm, left edge at x = 0, baseline at y = 0, y down. TrueType fills by non-zero winding:
    contours turning one way are ink and the other way are counters, so ink = union(outer) - union(counters)."""
    scale = cap_mm / font["OS/2"].sCapHeight
    gs, cmap, hmtx = font.getGlyphSet(), font.getBestCmap(), font["hmtx"]
    shapes, x = [], 0.0
    for ch in s:
        name = cmap[ord(ch)]
        pen = _FlatPen(gs, FLATNESS_MM / scale)
        gs[name].draw(pen)
        outer, holes = [], []
        for ring in pen.rings:
            pts = [(x + px * scale, -py * scale) for px, py in ring]     # font y is up
            poly = Polygon(pts).buffer(0)
            # y flipped: the font's clockwise outer contours turn counter-clockwise here (positive area)
            (outer if _signed_area(pts) > 0 else holes).append(poly)
        if outer:
            shapes.append(unary_union(outer).difference(unary_union(holes)) if holes else unary_union(outer))
        x += hmtx[name][0] * scale
    return unary_union(shapes), x


def load_font(weight):
    path = os.path.join(FONT_DIR, f"JetBrainsMono-{weight}.ttf")
    if not os.path.exists(path):
        os.makedirs(FONT_DIR, exist_ok=True)
        print(f"downloading {FONT_URL.format(weight)}")
        urllib.request.urlretrieve(FONT_URL.format(weight), path)
    return TTFont(path)


# ---------------------------------------------------------------------- layout and checks
def compose():
    font = load_font(WEIGHT)
    m = mark(MARK_MM)
    word, word_w = text_ink(font, WORDMARK, WORDMARK_CAP_MM)
    # wordmark's caps centred on the mark
    word = affinity.translate(word, MARK_MM + MARK_GAP_MM, MARK_MM / 2 + WORDMARK_CAP_MM / 2)
    lockup_w = MARK_MM + MARK_GAP_MM + word_w
    lines = [text_ink(font, s, TEXT_CAP_MM) for s in DEDICATION]
    width = max([lockup_w] + [w for _, w in lines])
    parts = [affinity.translate(unary_union([m, word]), (width - lockup_w) / 2, 0)]
    base = MARK_MM + ROW_GAP_MM + TEXT_CAP_MM
    for i, (ink, w) in enumerate(lines):
        parts.append(affinity.translate(ink, (width - w) / 2, base + i * LINE_PITCH_MM))
    art = unary_union(parts)
    x0, y0, x1, y1 = art.bounds
    return affinity.translate(art, -x0, -y0)


def _pieces(geom):
    if geom.is_empty:
        return []
    return [p for p in getattr(geom, "geoms", [geom]) if p.area > 1e-4]


def _topology(geom):
    polys = _pieces(geom)
    return len(polys), sum(1 for p in polys for h in p.interiors if Polygon(h).area > 1e-4)


def print_problems(art):
    """A stroke under MIN_STROKE_MM vanishes in an opening and a gap under MIN_GAP_MM shuts in a closing. Either one
    changes the art's topology (a crossbar gone, a counter shut, two letters touching) or moves a lump of ink out or
    in. Rounding a sharp corner (the A's apex, the crotch of a y) moves only a few hundredths of a mm^2."""
    r, g = MIN_STROKE_MM / 2, MIN_GAP_MM / 2
    opened = art.buffer(-r, quad_segs=16).buffer(r, quad_segs=16)
    closed = art.buffer(g, quad_segs=16).buffer(-g, quad_segs=16)
    probs = []
    for name, limit, test, moved in (("stroke", MIN_STROKE_MM, opened, art.difference(opened)),
                                     ("gap", MIN_GAP_MM, closed, closed.difference(art))):
        if _topology(test) != _topology(art):
            probs.append(f"a {name} under {limit} mm changes the shapes: (polygons, counters) "
                         f"{_topology(art)} -> {_topology(test)}")
        for p in _pieces(moved):
            if p.area > LUMP_MM2:
                c = p.centroid
                probs.append(f"{name} under {limit} mm at ({c.x:.2f}, {c.y:.2f}) mm: {p.area:.3f} mm^2")
    return probs


def polygons(art):
    out = []
    for p in getattr(art, "geoms", [art]):
        p = p.simplify(0.002)
        ring = lambda r: [[round(x, 4), round(y, 4)] for x, y in list(r.coords)[:-1]]
        out.append({"outline": ring(p.exterior), "holes": [ring(h) for h in p.interiors]})
    return out


def preview(art, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import PathPatch
    from matplotlib.path import Path as MPath
    x0, y0, x1, y1 = art.bounds
    fig, ax = plt.subplots(figsize=((x1 - x0 + 4) / 6, (y1 - y0 + 4) / 6), dpi=200)
    ax.set_facecolor("#1d5a32")
    for p in getattr(art, "geoms", [art]):
        verts, codes = [], []
        for r in [p.exterior] + list(p.interiors):
            c = list(r.coords)
            verts += c
            codes += [MPath.MOVETO] + [MPath.LINETO] * (len(c) - 2) + [MPath.CLOSEPOLY]
        ax.add_patch(PathPatch(MPath(verts, codes), facecolor="white", edgecolor="none"))
    ax.set_xlim(x0 - 2, x1 + 2)
    ax.set_ylim(y1 + 2, y0 - 2)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    fig.savefig(path, bbox_inches="tight", facecolor="#1d5a32")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--preview", metavar="PNG", help="also draw the art, white on green")
    a = ap.parse_args()
    art = compose()
    if not isinstance(art, (Polygon, MultiPolygon)) or not art.is_valid:
        print("error: the art isn't a valid polygon set", file=sys.stderr)
        return 2
    probs = print_problems(art)
    w, h = art.bounds[2], art.bounds[3]
    doc = {
        "about": "Bottom silkscreen signature for the v2 carrier. Generated by make_signature_art.py: edit that, not "
                 "this file. Polygons in mm, origin at the block's top-left, y down, as read from the bottom side; "
                 "build_carrier.py mirrors them onto B.SilkS.",
        "words": {"wordmark": WORDMARK, "dedication": list(DEDICATION)},
        "sources": {"mark": "https://ajayadesign.com/favicon.svg",
                    "font": f"JetBrains Mono {WEIGHT}, SIL Open Font License 1.1: " + FONT_URL.format(WEIGHT)},
        "size_mm": [round(w, 3), round(h, 3)],
        "checks": {"min_stroke_mm": MIN_STROKE_MM, "min_gap_mm": MIN_GAP_MM, "problems": probs},
        "polygons": polygons(art),
    }
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, separators=(",", ":"))
        fh.write("\n")
    n = sum(1 + len(p["holes"]) for p in doc["polygons"])
    print(f"{OUT}: {w:.1f} x {h:.1f} mm, {len(doc['polygons'])} polygons ({n} rings), "
          f"{sum(len(p['outline']) + sum(map(len, p['holes'])) for p in doc['polygons'])} points")
    print(f"print check (strokes >= {MIN_STROKE_MM} mm, gaps >= {MIN_GAP_MM} mm): "
          + ("OK" if not probs else f"{len(probs)} problem(s)"))
    for s in probs:
        print("  !! " + s)
    if a.preview:
        preview(art, a.preview)
        print(f"preview: {a.preview}")
    return 2 if probs else 0


if __name__ == "__main__":
    sys.exit(main())
