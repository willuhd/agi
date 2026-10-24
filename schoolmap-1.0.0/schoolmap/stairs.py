"""Stair geometry: one physical shaft per stair, flights between consecutive floors.

Every stair is described by its plan rectangle (identical on every floor it serves - a
stairwell is vertical), its shape and the landing point on each floor (where people enter
from the corridor).  From that this module derives, for every pair of consecutive floors,
the actual flights: treads, mid-landings and the walking centre-line.  Heights are given
as a fraction (0 = lower floor, 1 = upper floor) so any renderer can scale them.

Shapes
  dogleg    two parallel flights with a half-landing at the far end (most stairwells)
  straight  one run from the end nearest the lower landing to the opposite end
  spiral    helical treads around a central column
Lifts are not stairs and get no flights.
"""
from __future__ import annotations

import math

RISER_M = 0.17          # typical school riser height -> step count per storey
LANDING_DEPTH = 1.2     # m, half-landing depth of a dog-leg stair


def _r(v, nd=3):
    return [round(float(x), nd) for x in v]


def _steps(storey_m: float, share: float) -> int:
    return max(4, int(round(storey_m * share / RISER_M)))


def _long_axis(rect):
    x0, y0, x1, y1 = rect
    return 0 if (x1 - x0) >= (y1 - y0) else 1


def _dogleg(rect, lo_land, storey_m):
    x0, y0, x1, y1 = rect
    ax = _long_axis(rect)
    lo, hi = (x0, x1) if ax == 0 else (y0, y1)          # along the run
    so, sh = (y0, y1) if ax == 0 else (x0, x1)          # across the run
    entry_at_hi = lo_land[ax] > (lo + hi) / 2           # entry end = end nearest the landing
    e, f = (hi, lo) if entry_at_hi else (lo, hi)        # entry end, far end
    dsgn = -1 if entry_at_hi else 1                     # direction entry -> far
    depth = min(LANDING_DEPTH, 0.28 * (hi - lo))
    turn = f - dsgn * depth                             # where flight 1 ends / flight 2 starts
    mid = (so + sh) / 2
    a_near_landing = lo_land[1 - ax] > mid              # first flight on the landing's side
    A = (mid, sh) if a_near_landing else (so, mid)
    B = (so, mid) if a_near_landing else (mid, sh)

    def rect_of(a0, a1, s0, s1):
        a0, a1 = min(a0, a1), max(a0, a1)
        return [a0, s0, a1, s1] if ax == 0 else [s0, a0, s1, a1]

    def pt(a, s):
        return [a, s] if ax == 0 else [s, a]
    n = _steps(storey_m, 0.5)
    cA, cB = (A[0] + A[1]) / 2, (B[0] + B[1]) / 2
    parts = [
        {"type": "run", "rect": _r(rect_of(e, turn, *A)), "start": _r(pt(e, cA)), "end": _r(pt(turn, cA)),
         "z0": 0.0, "z1": 0.5, "steps": n},
        {"type": "landing", "rect": _r(rect_of(turn, f, so, sh)), "z": 0.5},
        {"type": "run", "rect": _r(rect_of(turn, e, *B)), "start": _r(pt(turn, cB)), "end": _r(pt(e, cB)),
         "z0": 0.5, "z1": 1.0, "steps": n},
    ]
    lm = (turn + f) / 2
    path = [pt(e, cA) + [0.0], pt(turn, cA) + [0.5], pt(lm, cA) + [0.5], pt(lm, cB) + [0.5],
            pt(turn, cB) + [0.5], pt(e, cB) + [1.0]]
    return parts, path


def _straight(rect, lo_land, storey_m):
    x0, y0, x1, y1 = rect
    ax = _long_axis(rect)
    lo, hi = (x0, x1) if ax == 0 else (y0, y1)
    so, sh = (y0, y1) if ax == 0 else (x0, x1)
    b, t = (hi, lo) if lo_land[ax] > (lo + hi) / 2 else (lo, hi)    # bottom end nearest lower landing
    c = (so + sh) / 2
    pt = (lambda a: [a, c]) if ax == 0 else (lambda a: [c, a])
    parts = [{"type": "run", "rect": _r(rect), "start": _r(pt(b)), "end": _r(pt(t)), "z0": 0.0, "z1": 1.0,
              "steps": _steps(storey_m, 1.0)}]
    return parts, [pt(b) + [0.0], pt(t) + [1.0]]


def _spiral(rect, lo_land, hi_land, storey_m):
    x0, y0, x1, y1 = rect
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    r1 = min(x1 - x0, y1 - y0) / 2
    r0 = 0.22
    a0 = math.atan2(lo_land[1] - cy, lo_land[0] - cx)
    a1 = math.atan2(hi_land[1] - cy, hi_land[0] - cx)
    sweep = (a1 - a0) % (2 * math.pi)
    if sweep < math.pi:                       # a spiral turns at least half a revolution
        sweep += 2 * math.pi
    n = _steps(storey_m, 1.0)
    parts = [{"type": "spiral", "c": _r([cx, cy]), "r0": round(r0, 3), "r1": round(r1, 3), "a0": round(a0, 4),
              "sweep": round(sweep, 4), "z0": 0.0, "z1": 1.0, "steps": n}]
    rm = (r0 + r1) / 2
    path = [[cx + rm * math.cos(a0 + sweep * k / 24), cy + rm * math.sin(a0 + sweep * k / 24), k / 24] for k in range(25)]
    return parts, path


def build_flights(conn: dict, floor_order: list, storey_m: float):
    """List of flights for every consecutive pair of floors a stair serves."""
    if conn["type"] != "stair":
        return []
    fl = [f for f in floor_order if f in conn["floors"]]
    rect = conn["plan"]
    out = []
    for lo, hi in zip(fl, fl[1:]):
        L0, L1 = conn["floors"][lo]["landing"], conn["floors"][hi]["landing"]
        shape = conn.get("shape", "dogleg")
        if shape == "straight":
            parts, path = _straight(rect, L0, storey_m)
        elif shape == "spiral":
            parts, path = _spiral(rect, L0, L1, storey_m)
        else:
            parts, path = _dogleg(rect, L0, storey_m)
        # full walking line: lower landing -> flights -> upper landing
        path = [list(L0) + [0.0]] + path + [list(L1) + [1.0]]
        out.append({"lo": lo, "hi": hi, "parts": parts, "path": [_r(p) for p in path]})
    return out
