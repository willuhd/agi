"""Publication-quality 2-D plan renders (PNG + SVG) with matplotlib."""
from __future__ import annotations

import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import Circle, FancyBboxPatch, PathPatch, Polygon, Rectangle  # noqa: E402
from matplotlib.path import Path as MPath  # noqa: E402

KIND_COLORS = {
    "classroom": "#cfe0f3", "office": "#f5e3c3", "lab": "#d6ecd2", "library": "#e6dcf3",
    "arts": "#f6d5dc", "sport": "#cdeceb", "service": "#e7e5df", "room": "#eeeeee",
}
KIND_EDGE = {
    "classroom": "#5b8cc4", "office": "#c7963f", "lab": "#5e9e57", "library": "#8a6bbf",
    "arts": "#c2627a", "sport": "#3d9c98", "service": "#9a958a", "room": "#999999",
}
BG = "#fbfaf7"
FLOOR = "#ffffff"
WALL = "#2b2d33"
STAIR = "#7a4fd0"
LIFT = "#d0613a"
ROUTE = "#ff5a1f"


def _poly_path(outer, holes=()):
    verts, codes = [], []
    for ring in [outer, *holes]:
        ring = list(ring)
        verts += ring + [ring[0]]
        codes += [MPath.MOVETO] + [MPath.LINETO] * (len(ring) - 1) + [MPath.CLOSEPOLY]
    return MPath(verts, codes)


def draw_floor(ax, model, fid, show_names=True, label_scale=1.0, route_paths=(), highlight=()):
    fl = next(f for f in model["floors"] if f["id"] == fid)
    W, H = model["meta"]["envelope_m"]
    ax.set_facecolor(BG)
    ax.add_patch(Polygon(fl["footprint"], closed=True, fc=FLOOR, ec="none", zorder=0))
    for b in fl.get("blocked", []):
        ax.add_patch(Polygon(b["poly"], closed=True, fc="#eef0f3", ec="#b9bec7", lw=0.6, hatch="////", zorder=1))
    for r in fl["rooms"]:
        k = r["kind"]
        hl = r["id"] in highlight
        ax.add_patch(Polygon(r["polygon"], closed=True, fc=KIND_COLORS.get(k, "#eee"), ec=KIND_EDGE.get(k, "#999"),
                             lw=2.0 if hl else 0.6, alpha=1.0, zorder=2))
    for c in model["connectors"]:
        if fid not in c["floors"] or not c.get("enabled", True):
            continue
        _draw_connector(ax, c, fid, label_scale)
    for w in fl["walls"]:
        ax.add_patch(Polygon(w["poly"], closed=True, fc=WALL, ec=WALL, lw=0.1, joinstyle="miter", zorder=5))
    for p in route_paths:
        p = np.asarray(p)
        ax.plot(p[:, 0], p[:, 1], c="white", lw=4.2, solid_capstyle="round", zorder=11)
        ax.plot(p[:, 0], p[:, 1], c=ROUTE, lw=2.4, solid_capstyle="round", zorder=12)
    for r in fl["rooms"]:
        xs, ys = np.array(r["polygon"]).T
        cx, cy = r["anchor"]
        w_ = xs.max() - xs.min()
        fs = 7.5 * label_scale
        ax.text(cx, cy - 0.15, r["id"], ha="center", va="bottom", fontsize=fs, fontweight="bold", color="#1f2430", zorder=8)
        if show_names and r["name"] != r["id"]:
            chars = max(8, int(w_ * 2.3 / label_scale))
            ax.text(cx, cy + 0.25, "\n".join(textwrap.wrap(r["name"], chars)[:3]), ha="center", va="top",
                    fontsize=4.3 * label_scale, color="#3b4252", zorder=8, linespacing=1.05)
        for d in r["doors"]:
            ax.plot(*d, marker="o", ms=1.6, c=KIND_EDGE.get(r["kind"], "#777"), zorder=7)
    ax.set_xlim(-1.5, W + 1.5); ax.set_ylim(H + 3.2, -1.5)
    ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)


def _draw_connector(ax, c, fid, label_scale=1.0):
    """Stair / lift symbol from the shared stair geometry: shaft, treads, half-landing,
    walking line with an UP arrow (plan convention), id badge at the landing."""
    x0, y0, x1, y1 = c["plan"]
    col = LIFT if c["type"] == "elevator" else STAIR
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc="white", ec=col, lw=0.9, zorder=3))
    if c["type"] == "elevator":
        mx = (x0 + x1) / 2
        for a, b in ((x0 + .12, mx - .08), (mx + .08, x1 - .12)):
            ax.add_patch(Rectangle((a, y0 + .12), b - a, y1 - y0 - .24, fc=LIFT, alpha=0.12, ec=col, lw=0.5, zorder=3))
            ax.plot([a, b], [y0 + .12, y1 - .12], c=col, lw=0.5, zorder=3)
            ax.plot([a, b], [y1 - .12, y0 + .12], c=col, lw=0.5, zorder=3)
    else:
        # the flight that leaves this floor upwards; on the top floor the one that arrives
        fl = next((f for f in c["flights"] if f["lo"] == fid), None) or next(f for f in c["flights"] if f["hi"] == fid)
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc=STAIR, alpha=0.08, ec="none", zorder=3))
        for part in fl["parts"]:
            if part["type"] == "run":
                rx0, ry0, rx1, ry1 = part["rect"]
                horiz = abs(part["end"][0] - part["start"][0]) > abs(part["end"][1] - part["start"][1])
                n = part["steps"]
                for t in np.linspace(0, 1, n + 1):
                    if horiz:
                        xx = rx0 + t * (rx1 - rx0); ax.plot([xx, xx], [ry0, ry1], c=col, lw=0.4, alpha=0.75, zorder=3)
                    else:
                        yy = ry0 + t * (ry1 - ry0); ax.plot([rx0, rx1], [yy, yy], c=col, lw=0.4, alpha=0.75, zorder=3)
                ax.add_patch(Rectangle((rx0, ry0), rx1 - rx0, ry1 - ry0, fc="none", ec=col, lw=0.6, zorder=3))
            elif part["type"] == "landing":
                lx0, ly0, lx1, ly1 = part["rect"]
                ax.add_patch(Rectangle((lx0, ly0), lx1 - lx0, ly1 - ly0, fc=STAIR, alpha=0.18, ec=col, lw=0.6, zorder=3))
            elif part["type"] == "spiral":
                cx, cy = part["c"]
                ax.add_patch(Circle((cx, cy), part["r1"], fc="white", ec=col, lw=0.8, zorder=3))
                ax.add_patch(Circle((cx, cy), part["r0"], fc=col, ec=col, lw=0.5, zorder=4))
                for k in range(part["steps"] + 1):
                    a = part["a0"] + part["sweep"] * k / part["steps"]
                    ax.plot([cx + part["r0"] * np.cos(a), cx + part["r1"] * np.cos(a)],
                            [cy + part["r0"] * np.sin(a), cy + part["r1"] * np.sin(a)], c=col, lw=0.35, alpha=0.75, zorder=3)
        # walking line inside the stair with an arrow pointing up the flight
        P = np.array([p[:2] for p in fl["path"][1:-1]])
        if fl["lo"] != fid:
            P = P[::-1]                      # top floor: arrow shows the way down
        ax.plot(P[:, 0], P[:, 1], c=col, lw=0.7, zorder=4)
        ax.annotate("", xy=P[-1], xytext=P[-2], arrowprops=dict(arrowstyle="-|>", color=col, lw=0.7, mutation_scale=6), zorder=4)
        ax.plot(*P[0], marker="o", ms=1.8, c=col, zorder=4)
    lx, ly = c["floors"][fid]["landing"]
    ax.add_patch(FancyBboxPatch((lx - 0.55, ly - 0.38), 1.1, 0.76, boxstyle="round,pad=0.05,rounding_size=0.3",
                                fc=col, ec="white", lw=0.6, zorder=9))
    ax.text(lx, ly, c["id"], ha="center", va="center", fontsize=5.2 * label_scale, color="white",
            fontweight="bold", zorder=10)


def _furniture(ax, W, H, fid, title=True, scale=1.0):
    # scale bar + north arrow
    yb = H + 1.9
    ax.plot([1, 11], [yb, yb], c=WALL, lw=1.5 * scale)
    for x in (1, 6, 11):
        ax.plot([x, x], [yb - 0.3, yb + 0.3], c=WALL, lw=1 * scale)
    for x, t in ((1, "0"), (6, "5"), (11, "10 m")):
        ax.text(x, yb + 0.45, t, ha="center", va="top", fontsize=6 * scale, color=WALL)
    ax.annotate("", xy=(W + 0.6, -0.8), xytext=(W + 0.6, 2.2), arrowprops=dict(arrowstyle="-|>", color=WALL, lw=1 * scale))
    ax.text(W + 0.6, -1.25, "N", ha="center", va="bottom", fontsize=7 * scale, color=WALL, fontweight="bold")
    if title:
        ax.set_title(fid, fontsize=16 * scale, fontweight="bold", color=WALL, loc="left", pad=6)


def legend(fig, loc=(0.5, 0.015), ncol=8, fs=8):
    from matplotlib.patches import Patch
    hs = [Patch(fc=KIND_COLORS[k], ec=KIND_EDGE[k], label=k.capitalize()) for k in KIND_COLORS if k != "room"]
    hs += [Patch(fc=STAIR, alpha=0.4, ec=STAIR, label="Stair (id = landing)"), Patch(fc=LIFT, alpha=0.4, ec=LIFT, label="Lift"),
           Patch(fc="#eef0f3", ec="#b9bec7", hatch="////", label="Void / no access")]
    fig.legend(handles=hs, loc="lower center", bbox_to_anchor=loc, ncol=ncol, frameon=False, fontsize=fs)


def render_all(model, out_dir):
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    W, H = model["meta"]["envelope_m"]
    order = [f["id"] for f in sorted(model["floors"], key=lambda f: -f["level"])]
    for fid in order:
        fig, ax = plt.subplots(figsize=(8.2, 10), dpi=220)
        fig.patch.set_facecolor(BG)
        draw_floor(ax, model, fid)
        _furniture(ax, W, H, fid)
        legend(fig, ncol=5, fs=6.5)
        fig.subplots_adjust(0.02, 0.07, 0.98, 0.96)
        fig.savefig(out / f"plan_{fid}.png", facecolor=BG)
        fig.savefig(out / f"plan_{fid}.svg", facecolor=BG)
        plt.close(fig)
    fig, axs = plt.subplots(2, 3, figsize=(21, 17.5), dpi=170)
    fig.patch.set_facecolor(BG)
    for ax, fid in zip(axs.ravel(), order):
        draw_floor(ax, model, fid, show_names=False, label_scale=0.95)
        _furniture(ax, W, H, fid, scale=1.1)
    legend(fig, ncol=10, fs=11)
    fig.suptitle("School building - metric floor model (all levels, common coordinate frame)", fontsize=18,
                 fontweight="bold", color=WALL, y=0.985)
    fig.subplots_adjust(0.01, 0.04, 0.99, 0.95, wspace=0.03, hspace=0.07)
    fig.savefig(out / "plans_overview.png", facecolor=BG)
    plt.close(fig)


def render_route(b, a, c, path):
    """Plan sheet showing every floor a route touches, with the route highlighted."""
    r = b.route(a, c)
    model = b.model
    W, H = model["meta"]["envelope_m"]
    floors = list(dict.fromkeys(l.floor for l in r.legs if l.kind == "walk"))
    fig, axs = plt.subplots(1, len(floors), figsize=(6.2 * len(floors), 8.6), dpi=170, squeeze=False)
    fig.patch.set_facecolor(BG)
    for ax, fid in zip(axs[0], floors):
        paths = [l.path for l in r.legs if l.kind == "walk" and l.floor == fid]
        draw_floor(ax, model, fid, show_names=False, route_paths=paths, highlight=(a, c))
        _furniture(ax, W, H, fid)
    steps = " -> ".join(f"{l.floor} ({l.metres:.0f} m)" if l.kind == "walk" else f"{l.via} {l.floor}" for l in r.legs)
    fig.suptitle(f"{a} -> {c}:  {r.seconds:.0f} s   (walk {r.walk_m:.0f} m = {r.walk_s:.0f} s, stairs {r.vertical_s:.0f} s)\n{steps}",
                 fontsize=11, color=WALL, y=0.985)
    fig.subplots_adjust(0.01, 0.01, 0.99, 0.9, wspace=0.03)
    fig.savefig(path, facecolor=BG)
    plt.close(fig)
    return r
