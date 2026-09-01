#!/usr/bin/env python3
"""
Slate - CAD icon set
====================

Single source of truth for the icon set. Running this script emits:

    icons/monotone/<name>.svg    20 single-weight line icons (currentColor)
    icons/duotone/<name>.svg     20 two-tone icons (currentColor + tint fill)
    icons/colour/<name>.svg      20 semantic-colour icons
    icons/slate-icons.svg        sprite: <symbol id="slate-<name>-<variant>">
    icons/manifest.json          metadata for tooling / docs
    index.html                   spec + preview page (icons inlined as SVG)

Design rules enforced here
--------------------------
* 24 x 24 grid, 18 x 18 live area (3px optical padding), 1px safe bleed.
* Uniform 1.5px stroke weight in every variant - no mixed weights.
* Round caps + joins, no hairlines, no decoration, no perspective.
* Every icon is built from four semantic ROLES so all three variants are
  generated from one geometry definition:

    primary    the subject - full tone in every variant
    secondary  construction / guide / removed material - soft tone
    accent     the focal detail + the category hue in `colour`
    soft       closed silhouette, filled with the category tint

Usage:  python3 scripts/build_icons.py [--sheet]
"""

from __future__ import annotations

import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICONS_DIR = os.path.join(ROOT, "icons")
GRID = 24
STROKE = 1.5
DOT = 3.0

# --------------------------------------------------------------------------
# palette
# --------------------------------------------------------------------------

INK = "#1e293b"    # slate-800  - primary line work
MIST = "#94a3b8"   # slate-400  - construction / guides

CATEGORIES = {
    "neutral":   {"label": "Interface", "accent": "#475569", "tint": "#e2e8f0"},
    "draw":      {"label": "Draw",      "accent": "#2563eb", "tint": "#dbeafe"},
    "modify":    {"label": "Modify",    "accent": "#d97706", "tint": "#fef3c7"},
    "transform": {"label": "Transform", "accent": "#0d9488", "tint": "#ccfbf1"},
}

VARIANTS = ("monotone", "duotone", "colour")


def style_for(variant: str, category: str) -> dict:
    """Resolve how each role is painted in a given variant."""
    cat = CATEGORIES[category]
    if variant == "monotone":
        paint = "currentColor"
        return {
            "primary":   {"stroke": paint, "opacity": 1.0},
            "secondary": {"stroke": paint, "opacity": 1.0},
            "accent":    {"stroke": paint, "opacity": 1.0},
            "soft":      None,                     # single weight, no fills
        }
    if variant == "duotone":
        paint = "currentColor"
        return {
            "primary":   {"stroke": paint, "opacity": 1.0},
            "secondary": {"stroke": paint, "opacity": 0.38},
            "accent":    {"stroke": paint, "opacity": 1.0},
            "soft":      {"fill": paint, "opacity": 0.16},
        }
    return {
        "primary":   {"stroke": INK, "opacity": 1.0},
        "secondary": {"stroke": MIST, "opacity": 1.0},
        "accent":    {"stroke": cat["accent"], "opacity": 1.0},
        "soft":      {"fill": cat["tint"], "opacity": 1.0},
    }


# --------------------------------------------------------------------------
# geometry helpers
# --------------------------------------------------------------------------

def n(v: float) -> str:
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def dot(x: float, y: float) -> str:
    """A node / endpoint marker: zero-length subpath + round cap."""
    return f"M{n(x)} {n(y)}h.01"


def polar(cx: float, cy: float, r: float, deg: float):
    t = math.radians(deg)
    return (cx + r * math.cos(t), cy + r * math.sin(t))


def arc_seg(cx: float, cy: float, r: float, a0: float, a1: float) -> str:
    """Bare `A` command from angle a0 to a1 (0 = east, positive = clockwise)."""
    large = 1 if abs(a1 - a0) > 180 else 0
    sweep = 1 if a1 > a0 else 0
    x1, y1 = polar(cx, cy, r, a1)
    return f"A{n(r)} {n(r)} 0 {large} {sweep} {n(x1)} {n(y1)}"


def arc(cx: float, cy: float, r: float, a0: float, a1: float) -> str:
    """Standalone arc path."""
    x0, y0 = polar(cx, cy, r, a0)
    return f"M{n(x0)} {n(y0)}" + arc_seg(cx, cy, r, a0, a1)


def circle(cx: float, cy: float, r: float) -> str:
    return (f"M{n(cx - r)} {n(cy)}a{n(r)} {n(r)} 0 1 0 {n(2 * r)} 0"
            f"a{n(r)} {n(r)} 0 1 0 {n(-2 * r)} 0")


def ring(cx: float, cy: float, r_out: float, r_in: float) -> str:
    """Two concentric circle sub-paths (use with fill-rule="evenodd")."""
    return circle(cx, cy, r_out) + circle(cx, cy, r_in)


def rrect(x: float, y: float, w: float, h: float, r: float) -> str:
    return (f"M{n(x + r)} {n(y)}H{n(x + w - r)}A{n(r)} {n(r)} 0 0 1 {n(x + w)} {n(y + r)}"
            f"V{n(y + h - r)}A{n(r)} {n(r)} 0 0 1 {n(x + w - r)} {n(y + h)}"
            f"H{n(x + r)}A{n(r)} {n(r)} 0 0 1 {n(x)} {n(y + h - r)}"
            f"V{n(y + r)}A{n(r)} {n(r)} 0 0 1 {n(x + r)} {n(y)}Z")


def chevron(tip, direction, length: float = 3.0, half: float = 2.1) -> str:
    """Open arrow head: two legs meeting at `tip`, pointing along `direction`."""
    dx, dy = direction
    m = math.hypot(dx, dy) or 1.0
    ux, uy = dx / m, dy / m
    nx, ny = -uy, ux
    bx, by = tip[0] - length * ux, tip[1] - length * uy
    p1 = (bx + half * nx, by + half * ny)
    p2 = (bx - half * nx, by - half * ny)
    return f"M{n(p1[0])} {n(p1[1])}L{n(tip[0])} {n(tip[1])}L{n(p2[0])} {n(p2[1])}"


def shorten(start, end, back: float):
    """Point on segment start->end, `back` units before `end`."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    L = math.hypot(dx, dy) or 1.0
    t = max(0.0, (L - back) / L)
    return (start[0] + dx * t, start[1] + dy * t)


class P:
    """One stroked (or filled) sub-path, tagged with a semantic role."""

    def __init__(self, d, role="primary", w=None, dash=None, fr=None):
        self.d = d
        self.role = role
        self.w = w
        self.dash = dash
        self.fr = fr


# --------------------------------------------------------------------------
# the 20 icons
# --------------------------------------------------------------------------

ICONS: list[dict] = []


def icon(name, label, cat, kw, parts, note=""):
    ICONS.append({
        "name": name, "label": label, "cat": cat, "kw": kw,
        "parts": parts, "note": note,
    })


# -- 01 select --------------------------------------------------------------
# Quadrilateral arrow: tip, foot, notch (reflex), tail. 22.5 deg front and
# back edges - the proportion that reads as a cursor at 16px.
_CURSOR = "M4.5 4L11.5 19.5L13.8 12.4L19.5 10.3Z"
icon("select", "Select", "neutral", ["cursor", "pointer", "pick", "arrow"], [
    P(_CURSOR, "soft"),
    P(_CURSOR, "accent"),
], "Classic pick cursor, 5 points.")

# -- 02 line ----------------------------------------------------------------
icon("line", "Line", "draw", ["segment", "edge", "straight"], [
    P("M4.5 19.5L19.5 4.5", "primary"),
    P(dot(4.5, 19.5), "accent", DOT),
    P(dot(19.5, 4.5), "accent", DOT),
], "Two-point segment with end nodes.")

# -- 03 polyline ------------------------------------------------------------
_PL = [(4.5, 17), (9, 8.5), (14, 15), (19.5, 7)]
icon("polyline", "Polyline", "draw", ["pline", "chain", "vertex"], [
    P("M4.5 17L9 8.5L14 15L19.5 7", "primary"),
    P("".join(dot(x, y) for x, y in _PL), "accent", DOT),
], "Chained segments with vertex nodes.")

# -- 04 rectangle -----------------------------------------------------------
_RECT = rrect(4.5, 6.5, 15, 11, 1.5)
icon("rectangle", "Rectangle", "draw", ["box", "rect", "ortho"], [
    P(_RECT, "soft"),
    P(_RECT, "primary"),
    P(dot(12, 12), "accent", DOT),
], "Axis-aligned box with centre node.")

# -- 05 circle --------------------------------------------------------------
_CIRC = circle(12, 12, 7.5)
icon("circle", "Circle", "draw", ["round", "radius", "centre"], [
    P(_CIRC, "soft"),
    P(_CIRC, "primary"),
    P("M12 10.2V13.8M10.2 12H13.8", "accent"),
], "Centre + radius construction.")

# -- 06 arc -----------------------------------------------------------------
_ARC_A0, _ARC_A1 = 150, 390          # 240 deg sweep, gap at the bottom
icon("arc", "Arc", "draw", ["curve", "sweep", "radius"], [
    P(arc(12, 13.5, 7.5, _ARC_A0, _ARC_A1), "primary"),
    P("".join([dot(*polar(12, 13.5, 7.5, _ARC_A0)),
                dot(*polar(12, 13.5, 7.5, _ARC_A1 % 360))]), "accent", DOT),
], "270 degree sweep with end nodes.")

# -- 07 ellipse -------------------------------------------------------------
_ELL = "M4 12a8 6 0 1 0 16 0a8 6 0 1 0-16 0"
icon("ellipse", "Ellipse", "draw", ["oval", "elliptical"], [
    P(_ELL, "soft"),
    P(_ELL, "primary"),
    P("M12 10.2V13.8M10.2 12H13.8", "accent"),
], "Major / minor axis, centre marked.")

# -- 08 polygon -------------------------------------------------------------
_POLY = "M12 4L18.93 8L18.93 16L12 20L5.07 16L5.07 8Z"
icon("polygon", "Polygon", "draw", ["hexagon", "ngon", "regular"], [
    P(_POLY, "soft"),
    P(_POLY, "primary"),
    P(dot(12, 12), "accent", DOT),
], "Regular hexagon, centre node.")

# -- 09 spline --------------------------------------------------------------
_SPL = "M4.5 15C6 14.5 7 8 9 7.5C11 7 12.5 16.5 14.5 16C16.5 15.5 18 9.5 19.5 8"
icon("spline", "Spline", "draw", ["nurbs", "bezier", "curve", "fit"], [
    P(_SPL, "primary"),
    P("".join([dot(4.5, 15), dot(9, 7.5), dot(14.5, 16), dot(19.5, 8)]), "accent", DOT),
], "Curve through four fit points.")

# -- 10 hatch ---------------------------------------------------------------
_HATCH_BOX = rrect(4.5, 4.5, 15, 15, 1.5)
icon("hatch", "Hatch", "draw", ["fill", "pattern", "section", "po"], [
    P(_HATCH_BOX, "soft"),
    P(_HATCH_BOX, "primary"),
    P("M4.5 13.5L13.5 4.5M4.5 18.5L18.5 4.5M8.5 19.5L19.5 8.5", "secondary"),
], "Boundary with 45 degree section lines.")

# -- 11 trim ----------------------------------------------------------------
_TIP_A, _TIP_B = (17.4, 4.8), (6.6, 4.8)
_RING_A, _RING_B = (7.6, 17.8), (16.4, 17.8)
_R = 2.05
icon("trim", "Trim", "modify", ["cut", "scissors", "clip"], [
    P(circle(*_RING_A, _R), "soft"),
    P(circle(*_RING_B, _R), "soft"),
    P(f"M{n(_TIP_A[0])} {n(_TIP_A[1])}"
      f"L{n(shorten(_TIP_A, _RING_A, _R)[0])} {n(shorten(_TIP_A, _RING_A, _R)[1])}", "primary"),
    P(f"M{n(_TIP_B[0])} {n(_TIP_B[1])}"
      f"L{n(shorten(_TIP_B, _RING_B, _R)[0])} {n(shorten(_TIP_B, _RING_B, _R)[1])}", "primary"),
    P(circle(*_RING_A, _R), "accent"),
    P(circle(*_RING_B, _R), "accent"),
], "Blades cross at the pivot; handles end in rings.")

# -- 12 extend --------------------------------------------------------------
icon("extend", "Extend", "modify", ["lengthen", "boundary", "meet"], [
    P("M19.5 5V19", "secondary"),                        # boundary edge
    P("M3.75 12H9", "primary"),                          # existing segment
    P("M9 12H16", "accent", None, "2.33 2.33"),          # added length
    P(chevron((19.5, 12), (1, 0), 3.5, 2.3), "accent"),
], "Segment lengthened until it meets the boundary edge.")

# -- 13 fillet --------------------------------------------------------------
# Matched pair with chamfer: same corner, same dashed "removed" sharp corner,
# but the two legs are joined by an arc of radius 3.5. That single difference
# is what separates fillet from chamfer at 16px.
icon("fillet", "Fillet", "modify", ["round", "radius", "blend", "corner"], [
    P("M18.5 5.5H10", "primary"),
    P("M5.5 10V18.5", "primary"),
    P("M10 5.5" + arc_seg(10, 10, 4.5, 270, 180), "accent"),
    P("M10 5.5H5.5V10", "secondary", None, "3 3"),
], "Radiused corner; the removed sharp corner is dashed.")

# -- 14 chamfer -------------------------------------------------------------
icon("chamfer", "Chamfer", "modify", ["bevel", "corner", "cut"], [
    P("M18.5 5.5H10", "primary"),
    P("M5.5 10V18.5", "primary"),
    P("M10 5.5L5.5 10", "accent"),
    P("M10 5.5H5.5V10", "secondary", None, "3 3"),
], "Bevelled corner; the removed sharp corner is dashed, as in fillet.")

# -- 15 offset --------------------------------------------------------------
_OFF_A = 225                    # radial tick marks the offset distance
icon("offset", "Offset", "modify", ["parallel", "concentric", "copy"], [
    P(ring(12, 12, 7.5, 4), "soft", fr="evenodd"),
    P(circle(12, 12, 7.5), "primary"),
    P(circle(12, 12, 4), "accent"),
    P("M%s %sL%s %s" % (n(polar(12, 12, 4.4, _OFF_A)[0]), n(polar(12, 12, 4.4, _OFF_A)[1]),
                        n(polar(12, 12, 6.6, _OFF_A)[0]), n(polar(12, 12, 6.6, _OFF_A)[1])),
      "accent"),
], "Parallel copy of a closed contour.")

# -- 16 mirror --------------------------------------------------------------
_LTRI = "M9.5 5L4.5 12L9.5 19Z"
_RTRI = "M14.5 5L19.5 12L14.5 19Z"
icon("mirror", "Mirror", "transform", ["reflect", "symmetry", "flip"], [
    P(_LTRI, "soft"),
    P(_RTRI, "soft"),
    P(_LTRI, "primary"),
    P(_RTRI, "primary"),
    P("M12 4V20", "secondary", None, "4 3"),
], "Paired geometry across a dash-dot axis.")

# -- 17 array ---------------------------------------------------------------
_CELLS = [(x, y) for y in (6, 12, 18) for x in (6, 12, 18)]
icon("array", "Array", "transform", ["pattern", "grid", "rectangular", "repeat"], [
    P(rrect(x - 2, y - 2, 4, 4, 0.9), "primary") for x, y in _CELLS[1:]
] + [
    P(rrect(4, 4, 4, 4, 0.9), "soft"),
    P(rrect(4, 4, 4, 4, 0.9), "accent"),
], "3 x 3 rectangular array, source cell marked.")

# -- 18 move ----------------------------------------------------------------
icon("move", "Move", "transform", ["translate", "pan", "shift"], [
    P("M12 4.5V19.5M4.5 12H19.5", "primary"),
    P(" ".join([
        chevron((12, 4.5), (0, -1), 3.0, 2.2),
        chevron((12, 19.5), (0, 1), 3.0, 2.2),
        chevron((4.5, 12), (-1, 0), 3.0, 2.2),
        chevron((19.5, 12), (1, 0), 3.0, 2.2),
    ]), "accent"),
], "Four-way translation.")

# -- 19 rotate --------------------------------------------------------------
_ROT_A0, _ROT_A1 = -65, 245
icon("rotate", "Rotate", "transform", ["spin", "angle", "turn"], [
    P(arc(12, 12, 7.5, _ROT_A0, _ROT_A1), "primary"),
    P(chevron(polar(12, 12, 7.5, _ROT_A1),
              (-math.sin(math.radians(_ROT_A1)), math.cos(math.radians(_ROT_A1))),
              3.0, 2.1), "accent"),
], "310 degree sweep, rotation arrow at the gap.")

# -- 20 dimension -----------------------------------------------------------
icon("dimension", "Dimension", "transform", ["annotate", "measure", "length", "dim"], [
    P("M5 6.5H19", "secondary"),
    P("M5 6.5V18.5M19 6.5V18.5", "secondary"),
    P("M5 15H10.4M13.6 15H19", "primary"),
    P(" ".join([
        chevron((5, 15), (-1, 0), 2.8, 2.1),
        chevron((19, 15), (1, 0), 2.8, 2.1),
    ]), "accent"),
], "Linear dimension: extension lines, witness line, arrow heads.")


# --------------------------------------------------------------------------
# renderers
# --------------------------------------------------------------------------

def inner_svg(ic: dict, variant: str) -> str:
    st = style_for(variant, ic["cat"])
    out = []
    for part in ic["parts"]:
        paint = st[part.role]
        if paint is None:
            continue
        attrs = []
        if "fill" in paint:
            attrs.append('fill="%s"' % paint["fill"])
            attrs.append('stroke="none"')
        else:
            attrs.append('fill="none"')
            attrs.append('stroke="%s"' % paint["stroke"])
        if part.w:
            attrs.append('stroke-width="%s"' % n(part.w))
        if part.dash:
            attrs.append('stroke-dasharray="%s"' % part.dash)
            attrs.append('stroke-linecap="butt"')
        if part.fr:
            attrs.append('fill-rule="%s"' % part.fr)
        if paint.get("opacity", 1.0) != 1.0:
            attrs.append('opacity="%s"' % n(paint["opacity"]))
        out.append('    <path d="%s" %s/>' % (part.d, " ".join(attrs)))
    return "\n".join(out)


_COMMON = ('xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
           'viewBox="0 0 24 24" fill="none" stroke-width="1.5" '
           'stroke-linecap="round" stroke-linejoin="round"')


def svg_doc(ic: dict, variant: str) -> str:
    a11y = 'role="img" aria-label="%s"' % ic["label"]
    return ('<svg %s %s>\n  <title>%s</title>\n%s\n</svg>\n'
            % (_COMMON, a11y, ic["label"], inner_svg(ic, variant)))


def sprite() -> str:
    out = ['<svg xmlns="http://www.w3.org/2000/svg" style="display:none">']
    for ic in ICONS:
        for v in VARIANTS:
            out.append('  <symbol id="slate-%s-%s" viewBox="0 0 24 24">'
                       % (ic["name"], v))
            out.append(inner_svg(ic, v))
            out.append('  </symbol>')
    out.append('</svg>')
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------
# preview sheet (for visual QA)
# --------------------------------------------------------------------------

def contact_sheet(path: str, variant: str = "duotone", cell: int = 56, cols: int = 10):
    import cairosvg  # noqa: F401  (import check only)
    rows = math.ceil(len(ICONS) / cols)
    w, h = cols * cell, rows * (cell + 18)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
             f'viewBox="0 0 {w} {h}">',
             f'<rect width="{w}" height="{h}" fill="#ffffff"/>']
    for i, ic in enumerate(ICONS):
        cx = (i % cols) * cell
        cy = (i // cols) * (cell + 18)
        body = inner_svg(ic, variant).replace("currentColor", "#0f172a")
        parts.append(f'<g transform="translate({cx + (cell - 44) / 2},{cy + 4}) scale({44 / 24})">'
                     f'{body}</g>')
        parts.append(f'<text x="{cx + cell / 2}" y="{cy + cell + 12}" font-family="sans-serif" '
                     f'font-size="9" text-anchor="middle" fill="#64748b">{ic["name"]}</text>')
    parts.append('</svg>')
    with open(path, "w") as fh:
        fh.write("\n".join(parts))


# --------------------------------------------------------------------------
# index.html
# --------------------------------------------------------------------------

HTML = """<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Slate — CAD Icon Set</title>
<style>
  :root{
    --bg:#f6f7f9; --panel:#ffffff; --ink:#0f172a; --body:#475569; --muted:#8a97a8;
    --line:#e4e8ee; --line-2:#eef1f5; --accent:#2563eb; --tile:#f8fafc;
    --radius:14px;
    --shadow:0 1px 2px rgba(15,23,42,.04), 0 8px 24px -16px rgba(15,23,42,.18);
  }
  [data-theme="dark"]{
    --bg:#0b1017; --panel:#111823; --ink:#e8eef6; --body:#9fb0c4; --muted:#6b7c92;
    --line:#1e2935; --line-2:#18222e; --accent:#60a5fa; --tile:#0f1620;
    --shadow:0 1px 2px rgba(0,0,0,.4), 0 8px 24px -16px rgba(0,0,0,.8);
  }
  *{box-sizing:border-box}
  html,body{margin:0}
  body{
    background:var(--bg); color:var(--ink);
    font:15px/1.5 ui-sans-serif,-apple-system,"Segoe UI",Inter,Roboto,Helvetica,Arial,sans-serif;
    -webkit-font-smoothing:antialiased;
  }
  .wrap{max-width:1180px;margin:0 auto;padding:0 24px}
  a{color:var(--accent)}
  code,.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}

  header.hero{padding:56px 0 28px}
  .eyebrow{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);font-weight:600}
  h1{margin:10px 0 8px;font-size:34px;line-height:1.15;letter-spacing:-.02em;font-weight:650}
  .lede{margin:0;max-width:62ch;color:var(--body);font-size:16px}
  .stats{display:flex;gap:8px;flex-wrap:wrap;margin-top:20px}
  .pill{
    border:1px solid var(--line);background:var(--panel);border-radius:999px;
    padding:5px 12px;font-size:12px;color:var(--body);
  }
  .pill b{color:var(--ink);font-weight:600}

  .bar{
    position:sticky;top:0;z-index:20;background:color-mix(in srgb,var(--bg) 88%,transparent);
    backdrop-filter:blur(10px);border-bottom:1px solid var(--line);
  }
  .bar-in{display:flex;gap:12px;align-items:center;flex-wrap:wrap;padding:12px 0}
  .seg{display:flex;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:3px;gap:2px}
  .seg button{
    border:0;background:transparent;color:var(--body);font:inherit;font-size:13px;
    padding:6px 13px;border-radius:7px;cursor:pointer;
  }
  .seg button[aria-pressed="true"]{background:var(--ink);color:var(--panel);font-weight:550}
  .search{
    flex:1;min-width:170px;background:var(--panel);border:1px solid var(--line);
    border-radius:10px;padding:8px 12px;color:var(--ink);font:inherit;font-size:14px;
  }
  .search::placeholder{color:var(--muted)}
  .grow{flex:1}
  .ctl{display:flex;align-items:center;gap:8px;font-size:12px;color:var(--body)}
  input[type=range]{width:96px;accent-color:var(--accent)}
  .tgl{
    border:1px solid var(--line);background:var(--panel);color:var(--body);
    border-radius:10px;padding:8px 12px;font:inherit;font-size:13px;cursor:pointer;
  }
  .tgl:hover{color:var(--ink)}

  section{padding:44px 0 8px}
  h2{font-size:19px;margin:0 0 4px;letter-spacing:-.01em}
  .sub{margin:0 0 22px;color:var(--body);font-size:14px;max-width:70ch}

  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(148px,1fr));gap:14px}
  .card{
    background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);
    padding:14px;cursor:pointer;transition:transform .12s ease,border-color .12s ease,box-shadow .12s ease;
    position:relative;
  }
  .card:hover{transform:translateY(-2px);border-color:color-mix(in srgb,var(--accent) 45%,var(--line));box-shadow:var(--shadow)}
  .tile{
    background:var(--tile);border-radius:10px;height:104px;display:flex;align-items:center;
    justify-content:center;color:var(--ink);position:relative;overflow:hidden;
  }
  .tile svg{width:var(--size);height:var(--size);display:block}
  .tile.compare{gap:4px;padding:0 4px}
  .tile.compare svg{width:calc(var(--size) * .56);height:calc(var(--size) * .56)}
  .slot{
    flex:1;display:flex;align-items:center;justify-content:center;height:100%;
    border-radius:8px;cursor:pointer;transition:background .12s ease;position:relative;
  }
  .slot:hover{background:color-mix(in srgb,var(--accent) 8%,transparent)}
  .slot::after{
    content:attr(data-v);position:absolute;bottom:4px;left:0;right:0;text-align:center;
    font-size:9px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);
    opacity:0;transition:opacity .12s ease;
  }
  .slot:hover::after{opacity:1}
  .tile .gridlines{position:absolute;inset:0;opacity:.5;pointer-events:none}
  .meta{display:flex;align-items:baseline;justify-content:space-between;gap:8px;margin-top:11px}
  .name{font-size:13px;font-weight:550;letter-spacing:-.005em}
  .cat{font-size:10px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);font-weight:600}
  .chips{display:flex;gap:6px;flex-wrap:wrap;margin-top:22px}
  .chip{border:1px solid var(--line);border-radius:999px;padding:4px 11px;font-size:12px;color:var(--body);background:var(--panel)}
  .dot{width:9px;height:9px;border-radius:50%;display:inline-block;margin-right:6px;vertical-align:-1px}

  .cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px}
  .panel{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:18px}
  .panel h3{margin:0 0 8px;font-size:14px}
  .panel p{margin:0;color:var(--body);font-size:13.5px}
  .swatches{display:flex;gap:6px;margin-top:12px;flex-wrap:wrap}
  .sw{width:34px;height:34px;border-radius:9px;border:1px solid var(--line)}
  pre{
    background:var(--tile);border:1px solid var(--line);border-radius:10px;padding:14px;
    overflow:auto;font-size:12.5px;line-height:1.6;color:var(--body);margin:0
  }
  table{width:100%;border-collapse:collapse;font-size:13.5px}
  th,td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--line-2)}
  th{color:var(--muted);font-weight:600;font-size:11px;letter-spacing:.08em;text-transform:uppercase}
  td:first-child{color:var(--ink);font-weight:550;white-space:nowrap}
  tr:last-child td{border-bottom:0}

  footer{padding:44px 0 64px;color:var(--muted);font-size:13px}

  #toast{
    position:fixed;left:50%;bottom:26px;transform:translate(-50%,20px);
    background:var(--ink);color:var(--bg);padding:10px 16px;border-radius:10px;
    font-size:13px;opacity:0;pointer-events:none;transition:.18s ease;z-index:50;
  }
  #toast.on{opacity:1;transform:translate(-50%,0)}
  @media (max-width:640px){ h1{font-size:27px} header.hero{padding:36px 0 20px} }
</style>
</head>
<body>

<header class="hero">
  <div class="wrap">
    <div class="eyebrow">Slate design system</div>
    <h1>CAD icon set</h1>
    <p class="lede">
      20 drafting primitives drawn on one 24&times;24 grid and published in three
      interchangeable sets — <b>duotone</b>, <b>monotone</b> and <b>colour</b>.
      Uniform 1.5px stroke, round terminals, no decoration. Every glyph is hand-built
      SVG: no auto-traced artwork, no raster fallbacks.
    </p>
    <div class="stats">
      <span class="pill"><b>20</b> icons</span>
      <span class="pill"><b>3</b> sets</span>
      <span class="pill"><b>60</b> SVG files</span>
      <span class="pill">24&times;24 grid · <b>1.5px</b> stroke</span>
      <span class="pill"><b>currentColor</b> ready</span>
    </div>
  </div>
</header>

<div class="bar">
  <div class="wrap bar-in">
    <div class="seg" id="seg">
      <button data-v="monotone" aria-pressed="false">Monotone</button>
      <button data-v="duotone"  aria-pressed="true">Duotone</button>
      <button data-v="colour"   aria-pressed="false">Colour</button>
      <button data-v="compare"  aria-pressed="false">Compare</button>
    </div>
    <input class="search" id="q" type="search" placeholder="Search icons — line, trim, radius…" autocomplete="off">
    <div class="ctl"><span>Size</span><input type="range" id="size" min="16" max="96" value="44"><span id="sizev" class="mono">44</span></div>
    <button class="tgl" id="guides">Grid</button>
    <button class="tgl" id="theme">Dark</button>
  </div>
</div>

<main class="wrap">
  <section>
    <h2 id="count">Icons</h2>
    <p class="sub">Click any icon to copy its SVG. Hover for the category.</p>
    <div class="grid" id="grid"></div>
    <div class="chips" id="chips"></div>
  </section>

  <section>
    <h2>The three sets</h2>
    <p class="sub">One geometry definition per icon, three paint recipes. Roles stay put, so switching sets never reflows the artwork.</p>
    <div class="cols">
      <div class="panel">
        <h3>Monotone</h3>
        <p>Flat <code>currentColor</code>, uniform weight, no fills. For toolbars, ribbons and dense UI at 16–20px.</p>
      </div>
      <div class="panel">
        <h3>Duotone</h3>
        <p>Primary line work at full tone, construction geometry at 38%, silhouette tinted at 16%. Reads depth without colour.</p>
      </div>
      <div class="panel">
        <h3>Colour</h3>
        <p>Semantic hues by tool family — draw, modify, transform — over graphite line work. For empty states and onboarding.</p>
      </div>
    </div>
  </section>

  <section>
    <h2>Geometry</h2>
    <p class="sub">Rules that keep the set optically consistent when icons sit side by side.</p>
    <div class="cols">
      <div class="panel">
        <h3>Grid &amp; safe area</h3>
        <p>24&times;24 viewBox, 18&times;18 live area, 3px padding. Terminals may bleed to 1.5px from the edge so round caps optically align.</p>
      </div>
      <div class="panel">
        <h3>Weight</h3>
        <p>1.5px stroke everywhere — primary, secondary, accent and node dots alike. Node dots are 3px round caps, never scaled circles.</p>
      </div>
      <div class="panel">
        <h3>Terminals</h3>
        <p>Round caps and joins throughout. Dashed construction lines switch to butt caps so the dash rhythm stays even.</p>
      </div>
      <div class="panel">
        <h3>Roles</h3>
        <p><b>primary</b> subject · <b>secondary</b> guides &amp; removed material · <b>accent</b> focal detail · <b>soft</b> silhouette fill.</p>
      </div>
    </div>
  </section>

  <section>
    <h2>Palette</h2>
    <p class="sub">Colour set only. Monotone and duotone inherit <code>currentColor</code> and need no tokens.</p>
    <div class="panel">
      <table>
        <thead><tr><th>Token</th><th>Value</th><th>Role</th><th>Used for</th></tr></thead>
        <tbody id="palette"></tbody>
      </table>
    </div>
  </section>

  <section>
    <h2>Usage</h2>
    <p class="sub">Standalone files, a sprite, or copy straight out of the grid above.</p>
    <div class="cols">
      <div class="panel">
        <h3>Inline</h3>
        <pre>&lt;svg width="24" height="24" viewBox="0 0 24 24"
     fill="none" stroke="currentColor"
     stroke-width="1.5" stroke-linecap="round"
     stroke-linejoin="round"&gt;
  &lt;use href="icons/slate-icons.svg#slate-line-duotone"/&gt;
&lt;/svg&gt;</pre>
      </div>
      <div class="panel">
        <h3>File</h3>
        <pre>icons/duotone/line.svg
icons/monotone/line.svg
icons/colour/line.svg</pre>
        <div class="swatches" id="sw"></div>
      </div>
    </div>
  </section>

  <footer>Generated by <code>scripts/build_icons.py</code> — regenerate after editing geometry.</footer>
</main>

<div id="toast">SVG copied</div>

<script>
const VARIANTS = __VARIANTS__;
const DATA = __DATA__;
const CATS = __CATS__;
const PALETTE = __PALETTE__;

const grid = document.getElementById('grid');
const chips = document.getElementById('chips');
const toast = document.getElementById('toast');
let variant = 'duotone', size = 44, guides = false, query = '';

const GUIDES = `<svg class="gridlines" viewBox="0 0 24 24" preserveAspectRatio="none" aria-hidden="true">
  <g fill="none" stroke="#94a3b8" stroke-width=".15" opacity=".55">
    ${Array.from({length:25},(_,i)=>`<path d="M${i} 0V24"/><path d="M0 ${i}H24"/>`).join('')}
    <path d="M0 0H24V24H0Z"/>
    <rect x="3" y="3" width="18" height="18" stroke="#f43f5e" stroke-width=".25" opacity=".8"/>
  </g></svg>`;

const setOf = v => v === 'compare' ? ['monotone','duotone','colour'] : [v];

function card(ic){
  const el = document.createElement('div');
  el.className = 'card';
  if(variant === 'compare'){
    el.innerHTML = `<div class="tile compare">${guides?GUIDES:''}${
      VARIANTS.map(v => `<span class="slot" data-v="${v}" title="Copy ${ic.label} — ${v}">${DATA[ic.name][v]}</span>`).join('')
    }</div>
    <div class="meta"><span class="name">${ic.label}</span><span class="cat">${CATS[ic.cat].label}</span></div>`;
  } else {
    el.innerHTML = `<div class="tile" data-v="${variant}" title="Copy ${ic.label} — ${variant}">${guides?GUIDES:''}${DATA[ic.name][variant]}</div>
    <div class="meta"><span class="name">${ic.label}</span><span class="cat">${CATS[ic.cat].label}</span></div>`;
  }
  el.querySelectorAll('[data-v]').forEach(t => t.addEventListener('click', () =>
    copy(DATA[ic.name][t.dataset.v], ic, t.dataset.v)));
  return el;
}

function render(){
  const q = query.trim().toLowerCase();
  const list = ICONS.filter(ic => !q || (ic.label+' '+ic.cat+' '+ic.kw.join(' ')).toLowerCase().includes(q));
  grid.innerHTML = '';
  list.forEach(ic => grid.appendChild(card(ic)));
  document.getElementById('count').textContent = `Icons · ${list.length}`;
  document.documentElement.style.setProperty('--size', size + 'px');
  chips.innerHTML = list.map(ic => `<span class="chip"><span class="dot" style="background:${CATS[ic.cat].accent}"></span>${ic.label}</span>`).join('');
}

async function copy(svg, ic, v){
  svg = svg.replace('<svg ', '<svg width="24" height="24" ');
  try { await navigator.clipboard.writeText(svg.trimEnd() + String.fromCharCode(10)); }
  catch(e){
    const t = document.createElement('textarea');
    t.value = svg; document.body.appendChild(t); t.select();
    document.execCommand('copy'); t.remove();
  }
  toast.textContent = ic.label + ' \u00b7 ' + v + ' — SVG copied';
  toast.classList.add('on');
  clearTimeout(copy.t);
  copy.t = setTimeout(()=>toast.classList.remove('on'), 1400);
}

// ---- controls -------------------------------------------------------------
document.getElementById('seg').addEventListener('click', e => {
  const b = e.target.closest('button'); if(!b) return;
  variant = b.dataset.v;
  [...e.currentTarget.children].forEach(x => x.setAttribute('aria-pressed', x === b));
  render();
});
document.getElementById('q').addEventListener('input', e => { query = e.target.value; render(); });
document.getElementById('size').addEventListener('input', e => {
  size = +e.target.value; document.getElementById('sizev').textContent = size; render();
});
document.getElementById('guides').addEventListener('click', e => {
  guides = !guides;
  e.target.textContent = guides ? 'Hide grid' : 'Grid';
  e.target.style.color = guides ? 'var(--accent)' : '';
  render();
});
document.getElementById('theme').addEventListener('click', e => {
  const dark = document.documentElement.dataset.theme === 'dark';
  document.documentElement.dataset.theme = dark ? 'light' : 'dark';
  e.target.textContent = dark ? 'Dark' : 'Light';
});

// ---- static sections ------------------------------------------------------
document.getElementById('palette').innerHTML = PALETTE.map(p =>
  `<tr><td><span class="dot" style="background:${p.value}"></span>${p.token}</td><td class="mono">${p.value}</td><td>${p.role}</td><td>${p.use}</td></tr>`).join('');
document.getElementById('sw').innerHTML = PALETTE.map(p =>
  `<span class="sw" style="background:${p.value}" title="${p.token}"></span>`).join('');

render();
</script>
</body>
</html>
"""

PALETTE_ROWS = [
    {"token": "ink", "value": INK, "role": "Primary", "use": "Subject line work"},
    {"token": "mist", "value": MIST, "role": "Secondary", "use": "Guides, removed material"},
    {"token": "draw", "value": CATEGORIES["draw"]["accent"], "role": "Accent", "use": "Draw tools"},
    {"token": "draw-tint", "value": CATEGORIES["draw"]["tint"], "role": "Soft", "use": "Draw silhouettes"},
    {"token": "modify", "value": CATEGORIES["modify"]["accent"], "role": "Accent", "use": "Modify tools"},
    {"token": "modify-tint", "value": CATEGORIES["modify"]["tint"], "role": "Soft", "use": "Modify silhouettes"},
    {"token": "transform", "value": CATEGORIES["transform"]["accent"], "role": "Accent", "use": "Transform tools"},
    {"token": "transform-tint", "value": CATEGORIES["transform"]["tint"], "role": "Soft", "use": "Transform silhouettes"},
    {"token": "neutral", "value": CATEGORIES["neutral"]["accent"], "role": "Accent", "use": "Interface / cursor"},
]


def build_html() -> str:
    data = {}
    for ic in ICONS:
        data[ic["name"]] = {v: svg_doc(ic, v).replace("\n", "").replace("  ", " ")
                            for v in VARIANTS}
    meta = [{"name": i["name"], "label": i["label"], "cat": i["cat"], "kw": i["kw"]}
            for i in ICONS]
    return (HTML
            .replace("__VARIANTS__", json.dumps(list(VARIANTS)))
            .replace("__DATA__", json.dumps(data, separators=(",", ":")))
            .replace("__CATS__", json.dumps(CATEGORIES, separators=(",", ":")))
            .replace("__PALETTE__", json.dumps(PALETTE_ROWS, separators=(",", ":")))
            .replace("const DATA = ", "const ICONS = " + json.dumps(meta, separators=(",", ":")) + ";\nconst DATA = ")
            )


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main() -> int:
    os.makedirs(ICONS_DIR, exist_ok=True)
    written = 0

    for v in VARIANTS:
        d = os.path.join(ICONS_DIR, v)
        os.makedirs(d, exist_ok=True)
        for ic in ICONS:
            with open(os.path.join(d, ic["name"] + ".svg"), "w") as fh:
                fh.write(svg_doc(ic, v))
            written += 1

    with open(os.path.join(ICONS_DIR, "slate-icons.svg"), "w") as fh:
        fh.write(sprite())
    written += 1

    manifest = {
        "name": "Slate CAD icons",
        "grid": GRID,
        "stroke": STROKE,
        "variants": list(VARIANTS),
        "categories": CATEGORIES,
        "icons": [
            {
                "name": ic["name"], "label": ic["label"], "category": ic["cat"],
                "keywords": ic["kw"], "note": ic["note"],
                "files": {v: f"icons/{v}/{ic['name']}.svg" for v in VARIANTS},
            }
            for ic in ICONS
        ],
    }
    with open(os.path.join(ICONS_DIR, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=2)
        fh.write("\n")

    with open(os.path.join(ROOT, "index.html"), "w") as fh:
        fh.write(build_html())
    written += 1

    print(f"wrote {written} files  ({len(ICONS)} icons x {len(VARIANTS)} variants)")

    if "--sheet" in sys.argv:
        for v in VARIANTS:
            contact_sheet(os.path.join("/tmp", f"sheet-{v}.svg"), v)
        print("sheets -> /tmp/sheet-*.svg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
