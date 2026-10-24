"""SVG building blocks for the poster: floor plans from the real building model, heat maps, histograms,
matrices, line/bar/tornado charts. Everything returns an SVG string; no external libraries."""
from __future__ import annotations

import json
import math
from pathlib import Path

from .config import ROOT

INK, MUT, FAINT, PAPER = "#1b1b1b", "#5a5750", "#d9d5ca", "#f6f4ee"
CUR, OPT, TEAL, GOLD = "#d4572c", "#1f5fa8", "#2a8f84", "#c99a2e"
SERIF = "Georgia,'Times New Roman',serif"
SANS = "'Segoe UI',Inter,system-ui,sans-serif"

_BM = None


def building():
    global _BM
    if _BM is None:
        _BM = json.loads((ROOT / "data/building/building_model.json").read_text())
    return _BM


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;")


def T(x, y, s, size=20, fill=INK, anchor="start", weight=400, family=SANS, extra=""):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" '
            f'font-weight="{weight}" font-family="{family}" {extra}>{s}</text>')


def svg(w, h, body, cls=""):
    return f'<svg class="{cls}" viewBox="0 0 {w} {h}" width="100%" xmlns="http://www.w3.org/2000/svg">{body}</svg>'


def lerp(c1, c2, t):
    t = max(0.0, min(1.0, t))
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(a[i] + (b[i] - a[i]) * t):02x}" for i in range(3))


def ramp(t, hi):
    return lerp("#efece3", hi, t)


# ------------------------------------------------------------------------------ floor plans --
FLOORS = ["B2", "B1", "1F", "2F", "3F", "4F"]


def plan(floor_id, heat=None, hi=CUR, w=300, closed=(), mark=(), arrows=(), label_min=0.0, show_ids=True,
         dim_others=False, title=None):
    """Real floor plan (metres). heat: {room_id: 0..1}. arrows: [(room_a, room_b, color)] drawn as arcs."""
    bm = building()
    f = next(x for x in bm["floors"] if x["id"] == floor_id)
    sc = w / 41.0
    H = 52.0 * sc + (26 if title else 0)
    oy = 26 if title else 0
    X = lambda x: x * sc + 0.5 * sc
    Y = lambda y: y * sc + oy + 0.5 * sc
    pts = lambda poly: " ".join(f"{X(p[0]):.1f},{Y(p[1]):.1f}" for p in poly)
    b = ""
    if title:
        b += T(2, 18, title, 20, INK, "start", 700, SERIF)
    b += f'<polygon points="{pts(f["footprint"])}" fill="#fff" stroke="{INK}" stroke-width="1.6"/>'
    for bl in f.get("blocked", []):
        b += f'<polygon points="{pts(bl["poly"])}" fill="#e7e3d8" stroke="none"/>'
    anchors = {}
    for r in f["rooms"]:
        anchors[r["id"]] = (X(r["anchor"][0]), Y(r["anchor"][1]))
        v = (heat or {}).get(r["id"])
        fill = "#faf9f5"
        if heat is not None and v is not None:
            fill = ramp(v, hi)
        if r["id"] in closed:
            fill = "#ffffff"
        b += f'<polygon points="{pts(r["polygon"])}" fill="{fill}" stroke="#b9b4a6" stroke-width="0.7"/>'
        if r["id"] in closed:
            b += (f'<polygon points="{pts(r["polygon"])}" fill="url(#hatch)" stroke="{CUR}" stroke-width="2"/>')
        if show_ids and (r["area_m2"] > 14) and (v is None or v >= label_min):
            b += T(anchors[r["id"]][0], anchors[r["id"]][1] + 4, r["id"], max(9, 0.34 * sc * 2), MUT, "middle")
    for wl in f["walls"]:
        b += f'<polygon points="{pts(wl["poly"])}" fill="{INK}" stroke="none"/>'
    for c in bm["connectors"]:
        fl = c["floors"] if isinstance(c["floors"], dict) else {}
        if floor_id in fl:
            x0, y0, x1, y1 = fl[floor_id]["footprint"]
            b += f'<rect x="{X(x0):.1f}" y="{Y(y0):.1f}" width="{(x1 - x0) * sc:.1f}" height="{(y1 - y0) * sc:.1f}" fill="url(#stair)" stroke="{INK}" stroke-width="0.8"/>'
    for a, bb, col in arrows:
        if a in anchors and bb in anchors:
            (x1, y1), (x2, y2) = anchors[a], anchors[bb]
            mx, my = (x1 + x2) / 2 + (y2 - y1) * 0.18, (y1 + y2) / 2 - (x2 - x1) * 0.18
            b += (f'<path d="M{x1:.1f},{y1:.1f} Q{mx:.1f},{my:.1f} {x2:.1f},{y2:.1f}" fill="none" stroke="{col}" stroke-width="2.4" '
                  f'marker-end="url(#ah{col[1:]})" opacity=".9"/>')
    for rid, col, txt in mark:
        if rid in anchors:
            b += f'<circle cx="{anchors[rid][0]:.1f}" cy="{anchors[rid][1]:.1f}" r="{0.9 * sc:.1f}" fill="none" stroke="{col}" stroke-width="2.4"/>'
    defs = (f'<defs><pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
            f'<line x1="0" y1="0" x2="0" y2="6" stroke="{CUR}" stroke-width="2"/></pattern>'
            f'<pattern id="stair" width="4" height="4" patternUnits="userSpaceOnUse"><path d="M0,4 L4,0" stroke="#8d887b" stroke-width="1"/></pattern>'
            + "".join(f'<marker id="ah{c[1:]}" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="{c}"/></marker>'
                      for c in {CUR, OPT, INK, TEAL}) + "</defs>")
    return svg(w, H, defs + b)


def room_floor():
    bm = building()
    return {r["id"]: f["id"] for f in bm["floors"] for r in f["rooms"]}


# ---------------------------------------------------------------------------------- charts ---
def axis_y(L, T_, R, B, lo, hi, n=4, fmt="{:.0f}", w=1000):
    s = ""
    for i in range(n + 1):
        v = lo + (hi - lo) * i / n
        y = B - (v - lo) / ((hi - lo) or 1) * (B - T_)
        s += f'<line x1="{L}" x2="{R}" y1="{y:.1f}" y2="{y:.1f}" stroke="{FAINT}" stroke-width="1"/>'
        s += T(L - 8, y + 6, fmt.format(v), 17, MUT, "end")
    return s


def hist(series, w=700, h=330, bins=24, xlab="", lo=None, hi=None, colors=(CUR, OPT), names=("Current", "Optimized"),
         ylab="share of students (%)", density=True, annotate_mean=True):
    allv = [v for s in series for v in s]
    lo = min(allv) if lo is None else lo
    hi = max(allv) if hi is None else hi
    L, R, T_, B = 66, w - 18, 20, h - 56
    step = (hi - lo) / bins or 1
    cnts = []
    for s in series:
        c = [0] * bins
        for v in s:
            i = min(bins - 1, max(0, int((v - lo) / step)))
            c[i] += 1
        cnts.append([100 * x / len(s) for x in c])
    ymax = max(max(c) for c in cnts) * 1.12
    sx = lambda v: L + (v - lo) / (hi - lo) * (R - L)
    sy = lambda v: B - v / ymax * (B - T_)
    b = axis_y(L, T_, R, B, 0, ymax, 4, "{:.0f}")
    for c, col in zip(cnts, colors):
        pts = [(sx(lo), sy(0))]
        for i, v in enumerate(c):
            pts += [(sx(lo + i * step), sy(v)), (sx(lo + (i + 1) * step), sy(v))]
        pts.append((sx(hi), sy(0)))
        b += f'<polygon points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in pts)}" fill="{col}" fill-opacity=".38" stroke="{col}" stroke-width="2"/>'
    for s, col, nm in zip(series, colors, names):
        m = sum(s) / len(s)
        b += f'<line x1="{sx(m):.1f}" x2="{sx(m):.1f}" y1="{T_}" y2="{B}" stroke="{col}" stroke-width="2.4" stroke-dasharray="6 4"/>'
    b += f'<line x1="{L}" x2="{R}" y1="{B}" y2="{B}" stroke="{INK}"/>'
    for i in range(5):
        v = lo + (hi - lo) * i / 4
        b += T(sx(v), B + 24, f"{v:.0f}" if hi > 20 else f"{v:.1f}", 17, MUT, "middle")
    b += T((L + R) / 2, h - 10, xlab, 18, MUT, "middle")
    b += T(16, (T_ + B) / 2, ylab, 17, MUT, "middle", 400, SANS, f'transform="rotate(-90 16 {(T_ + B) / 2})"')
    lx = R - 200
    for i, (col, nm, s) in enumerate(zip(colors, names, series)):
        b += f'<rect x="{lx}" y="{T_ + 4 + i * 26}" width="18" height="14" fill="{col}" fill-opacity=".5" stroke="{col}"/>'
        b += T(lx + 26, T_ + 17 + i * 26, f"{nm}  (mean {sum(s) / len(s):.0f})" if hi > 20 else f"{nm}  (mean {sum(s) / len(s):.1f})", 17, INK)
    return svg(w, h, b)


def line(pts_series, w=700, h=320, xlab="", ylab="", colors=(OPT,), names=None, bad=None, bad_label="", xfmt="{:.0f}",
         yfmt="{:.0f}", ylo=None, yhi=None, labels=None, marker=True):
    xs = [p[0] for s in pts_series for p in s]
    ys = [p[1] for s in pts_series for p in s]
    xs2 = xs + list(bad or [])
    xmin, xmax = min(xs2), max(xs2)
    ymin = min(ys) if ylo is None else ylo
    ymax = (max(ys) * 1.1 if yhi is None else yhi)
    if ymin == ymax:
        ymax = ymin + 1
    L, R, T_, B = 72, w - 24, 24, h - 62
    sx = lambda v: L + (v - xmin) / ((xmax - xmin) or 1) * (R - L)
    sy = lambda v: B - (v - ymin) / ((ymax - ymin) or 1) * (B - T_)
    b = axis_y(L, T_, R, B, ymin, ymax, 4, yfmt)
    for s, col in zip(pts_series, colors):
        b += f'<polyline fill="none" stroke="{col}" stroke-width="3.2" points="{" ".join(f"{sx(x):.1f},{sy(y):.1f}" for x, y in s)}"/>'
        if marker:
            for i, (x, y) in enumerate(s):
                b += f'<circle cx="{sx(x):.1f}" cy="{sy(y):.1f}" r="6" fill="{col}" stroke="#fff" stroke-width="2"/>'
                if labels and i < len(labels):
                    b += T(sx(x) + 9, sy(y) - 10, labels[i], 16, MUT)
    for x in (bad or []):
        b += f'<line x1="{sx(x):.1f}" x2="{sx(x):.1f}" y1="{T_}" y2="{B}" stroke="{CUR}" stroke-width="2.4" stroke-dasharray="7 5"/>'
        b += T(sx(x) - 6, T_ + 20, bad_label, 17, CUR, "end", 700)
    b += f'<line x1="{L}" x2="{R}" y1="{B}" y2="{B}" stroke="{INK}"/>'
    xt = sorted(set(xs))
    for v in (xt if len(xt) <= 7 else [xmin + (xmax - xmin) * i / 4 for i in range(5)]):
        b += T(sx(v), B + 26, xfmt.format(v), 17, MUT, "middle")
    b += T((L + R) / 2, h - 10, xlab, 18, MUT, "middle")
    b += T(16, (T_ + B) / 2, ylab, 17, MUT, "middle", 400, SANS, f'transform="rotate(-90 16 {(T_ + B) / 2})"')
    if names:
        for i, (nm, col) in enumerate(zip(names, colors)):
            b += f'<rect x="{L + 10}" y="{T_ + 6 + i * 26}" width="26" height="6" fill="{col}"/>' + T(L + 44, T_ + 15 + i * 26, nm, 17, INK)
    return svg(w, h, b)


def tornado(rows, base, w=900, rowh=34, lab_w=300, fmt="{:.0f}", unit="%"):
    """rows: [(name, lo, hi)]."""
    h = 64 + rowh * len(rows)
    vals = [r[1] for r in rows] + [r[2] for r in rows] + [base]
    vmin, vmax = min(vals) - 3, max(vals) + 3
    sx = lambda v: lab_w + (v - vmin) / ((vmax - vmin) or 1) * (w - lab_w - 40)
    b = ""
    for i, (nm, lo, hi) in enumerate(rows):
        y = 44 + i * rowh
        b += T(lab_w - 12, y + 18, nm, 19, INK, "end")
        b += f'<rect x="{sx(lo):.1f}" y="{y}" width="{max(sx(hi) - sx(lo), 3):.1f}" height="{rowh - 12}" fill="{OPT}" opacity=".85"/>'
        b += T(sx(lo) - 6, y + 18, fmt.format(lo), 16, MUT, "end") + T(sx(hi) + 6, y + 18, fmt.format(hi), 16, MUT)
    b += f'<line x1="{sx(base):.1f}" x2="{sx(base):.1f}" y1="30" y2="{h - 6}" stroke="{INK}" stroke-width="2"/>'
    b += T(sx(base), 22, f"baseline {fmt.format(base)}{unit}", 18, INK, "middle", 700)
    return svg(w, h, b)


def hbars(rows, w=800, rowh=34, lab_w=250, signed=True, fmt="{:+.2f}", color_pos=OPT, color_neg=CUR):
    h = 20 + rowh * len(rows)
    mx = max(abs(r[1]) for r in rows) or 1
    half = (w - lab_w - 70) / (2 if signed else 1)
    mid = lab_w + (half if signed else 0)
    b = ""
    for i, (nm, v) in enumerate(rows):
        y = 8 + i * rowh
        bw = abs(v) / mx * half
        x = mid if v >= 0 else mid - bw
        b += T(lab_w - 12, y + 19, nm, 19, INK, "end")
        b += f'<rect x="{x:.1f}" y="{y}" width="{max(bw, 2):.1f}" height="{rowh - 11}" fill="{color_pos if v >= 0 else color_neg}"/>'
        b += T(x + (bw + 7 if v >= 0 else -7), y + 19, fmt.format(v), 16, MUT, "start" if v >= 0 else "end")
    if signed:
        b += f'<line x1="{mid:.1f}" x2="{mid:.1f}" y1="2" y2="{h - 4}" stroke="{INK}" stroke-width="1.5"/>'
    return svg(w, h, b)


def matrix(rows, ncol, cell=14, gap=1, colors=None, w=None, row_labels=None, col_labels=None, lab_w=70, top=24, vline=None, cw=None):
    """rows: list of lists of ints; colors: {value: color}."""
    cw = cw or cell
    ww = lab_w + ncol * (cw + gap) + 6
    hh = top + len(rows) * (cell + gap) + 6
    b = ""
    for i, r in enumerate(rows):
        y = top + i * (cell + gap)
        for j, v in enumerate(r):
            b += f'<rect x="{lab_w + j * (cw + gap)}" y="{y}" width="{cw}" height="{cell}" fill="{colors.get(v, "#fff")}"/>'
        if row_labels and row_labels[i]:
            b += T(lab_w - 6, y + cell - 3, row_labels[i], 13, MUT, "end")
    for j, lab in enumerate(col_labels or []):
        if lab:
            b += T(lab_w + j * (cw + gap) + cw / 2, top - 8, lab, 14, MUT, "middle")
    for x in (vline or []):
        b += f'<line x1="{lab_w + x * (cw + gap) - 0.5}" x2="{lab_w + x * (cw + gap) - 0.5}" y1="{top - 4}" y2="{hh - 6}" stroke="{INK}" stroke-width="1.4"/>'
    return svg(ww, hh, b)


def arrow_defs():
    return ""
