"""Wall vectorisation: clean wall raster -> straight, orthogonal, snapped wall segments.

Plans are drawings of a rectilinear building, so the model is rebuilt as vector walls:

1. Straight runs.  Morphological opening along x and y isolates horizontal / vertical
   strokes; each stroke band becomes one segment (centre line, extent, thickness).
2. Line snapping.  Collinear segments whose centre lines differ by < LINE_TOL are moved
   onto one common line (length-weighted), so walls of a corridor line up exactly.
3. Thickness classes.  Each wall is either interior or exterior (thick outline).
4. Junction snapping.  Segment ends close to a perpendicular wall are extended/trimmed
   onto it (+ half its thickness) -> crisp L and T joints, no slivers or gaps.
5. Diagonals.  Remaining long straight strokes (bridges, angled corners) are fitted
   as exact straight segments.  Everything else (icons, hatching, text residue) is
   discarded.
"""
from __future__ import annotations

import cv2
import numpy as np

LINE_TOL = 0.14       # m: centre lines closer than this are one line
EXT_LINE_TOL = 0.40   # m: same for exterior (thick) walls
JOIN_TOL = 0.40       # m: end within this of a perpendicular wall -> joined to it
MERGE_GAP = 0.12      # m: collinear pieces separated by less than this are merged
MIN_RUN = 0.60        # m: shortest straight run considered a wall (> any drawn wall thickness)
ISOLATED_MIN = 2.6    # m: an unconnected run shorter than this is an icon stroke (pictograms are ~2 m)
T_INT, T_EXT = 0.15, 0.32
EXT_THRESHOLD = 0.23  # m: measured stroke thickness above this = exterior wall


def _bands(mask_line, axis, ppm):
    """Track straight strokes along `axis` (0 = horizontal) -> [centre, a0, a1, thickness] (m).

    Every row is split into runs; a run continues the stroke of the previous row only if
    their extents overlap strongly (IoU > 0.5).  So a wall stays separate from a thick
    outline it touches, and a drawn wall of any thickness becomes exactly one stroke.
    """
    m = (mask_line if axis == 0 else mask_line.T) > 0
    n_min = int(MIN_RUN * ppm)
    active, done = [], []                      # stroke: dict(rows=[], s=[], e=[])
    for r in range(m.shape[0]):
        row = m[r]
        if not row.any():
            done += active; active = []; continue
        d = np.diff(np.concatenate([[0], row.astype(np.int8), [0]]))
        starts, ends = np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]
        new_active = []
        used = set()
        for s0, e0 in zip(starts, ends):
            if e0 - s0 < n_min:
                continue
            best, bi = 0.5, None
            for k, st in enumerate(active):
                if k in used:
                    continue
                ps, pe = st["s"][-1], st["e"][-1]
                inter = min(pe, e0) - max(ps, s0)
                iou = inter / (max(pe, e0) - min(ps, s0))
                if iou > best:
                    best, bi = iou, k
            if bi is None:
                st = {"rows": [], "s": [], "e": []}
            else:
                st = active[bi]; used.add(bi)
            st["rows"].append(r); st["s"].append(s0); st["e"].append(e0)
            new_active.append(st)
        done += [st for k, st in enumerate(active) if k not in used]
        active = new_active
    done += active
    segs = []
    for st in done:
        rows, S, E = np.array(st["rows"]), np.array(st["s"]), np.array(st["e"])
        L = E - S
        core = L >= 0.8 * L.max()                 # ignore anti-aliased edge rows
        a0, a1 = np.median(S[core]) / ppm, np.median(E[core]) / ppm
        thick = len(rows) / ppm
        length = a1 - a0
        if thick > 0.6 or length < MIN_RUN or length < 2.5 * thick:
            continue
        centre = (np.average(rows, weights=L) + 0.5) / ppm
        segs.append([float(centre), float(a0), float(a1), float(thick)])
    return segs


def _snap_lines(segs, tol=LINE_TOL):
    """Cluster centre coordinates (length weighted) -> common lines."""
    if not segs:
        return segs
    order = sorted(range(len(segs)), key=lambda i: segs[i][0])
    clusters, cur = [], [order[0]]
    for i in order[1:]:
        if segs[i][0] - segs[cur[-1]][0] <= tol:
            cur.append(i)
        else:
            clusters.append(cur); cur = [i]
    clusters.append(cur)
    for cl in clusters:
        w = np.array([segs[i][2] - segs[i][1] for i in cl])
        c = float(np.average([segs[i][0] for i in cl], weights=w))
        for i in cl:
            segs[i][0] = c
    return segs


def _dedupe_parallel(segs):
    """Fuse parallel strokes that visually overlap (one wall drawn/split as two)."""
    changed = True
    while changed:
        changed = False
        segs.sort(key=lambda s: s[0])
        for i in range(len(segs)):
            for j in range(i + 1, len(segs)):
                a, b = segs[i], segs[j]
                if b[0] - a[0] > max(a[3], b[3]) + 0.45:
                    break
                # an exterior outline absorbs the inner line drawn alongside it
                gap = 0.45 if (a[3] == T_EXT or b[3] == T_EXT) and a[3] != b[3] else 0.12
                if b[0] - a[0] > (a[3] + b[3]) / 2 + gap:
                    continue
                ov = min(a[2], b[2]) - max(a[1], b[1])
                if ov < 0.5 * min(a[2] - a[1], b[2] - b[1]):
                    continue
                la, lb = a[2] - a[1], b[2] - b[1]
                if a[3] != b[3]:                     # keep the exterior line where it is
                    c = a[0] if a[3] == T_EXT else b[0]
                else:
                    c = (a[0] * la + b[0] * lb) / (la + lb)
                segs[i] = [c, min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]
                del segs[j]
                changed = True
                break
            if changed:
                break
    return segs


def _merge_collinear(segs):
    segs = sorted(segs, key=lambda s: (round(s[0], 4), s[1]))
    out = []
    for s in segs:
        if out and abs(out[-1][0] - s[0]) < 1e-6 and s[1] - out[-1][2] <= MERGE_GAP and abs(out[-1][3] - s[3]) < 1e-6:
            out[-1][2] = max(out[-1][2], s[2])
        else:
            out.append(list(s))
    return out


def _residual_strokes(walls, H, V, ppm):
    """Long straight strokes not explained by the orthogonal runs.

    Near-axis ones (< 6 deg, e.g. a slightly skewed outline) are returned as orthogonal
    runs so they go through the same snapping / de-duplication; the rest are true
    diagonals (bridge edges, angled corners)."""
    cover = np.zeros_like(walls)
    for s in H:
        _draw(cover, {"a": [s[1], s[0]], "b": [s[2], s[0]], "t": s[3]}, ppm, 0.0, extra=0.25)
    for s in V:
        _draw(cover, {"a": [s[0], s[1]], "b": [s[0], s[2]], "t": s[3]}, ppm, 0.0, extra=0.25)
    resid = (walls > 0) & (cover == 0)
    resid = cv2.morphologyEx(resid.astype(np.uint8), cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    cnt, lab, st, _ = cv2.connectedComponentsWithStats(resid, connectivity=8)
    addH, addV, diag = [], [], []
    for i in range(1, cnt):
        if max(st[i][2], st[i][3]) < 1.2 * ppm:
            continue
        ys, xs = np.nonzero(lab == i)
        P = np.stack([xs, ys], 1).astype(float) + 0.5
        c = P.mean(0)
        ev, evec = np.linalg.eigh((P - c).T @ (P - c))
        if ev[1] < 40 * max(ev[0], 1e-9):
            continue                                    # not a straight stroke (rink oval, icons)
        d = evec[:, 1]
        tt = (P - c) @ d
        thick = len(P) / max(tt.max() - tt.min(), 1) / ppm
        a, b = (c + d * tt.min()) / ppm, (c + d * tt.max()) / ppm
        ang = np.degrees(np.arctan2(abs(d[1]), abs(d[0])))
        if ang < 6:
            addH.append([float((a[1] + b[1]) / 2), float(min(a[0], b[0])), float(max(a[0], b[0])), thick])
        elif ang > 84:
            addV.append([float((a[0] + b[0]) / 2), float(min(a[1], b[1])), float(max(a[1], b[1])), thick])
        else:
            diag.append({"a": list(a), "b": list(b), "t": T_EXT if thick > EXT_THRESHOLD else T_INT, "kind": "diag"})
    return addH, addV, diag


def vectorize_walls(walls: np.ndarray, ppm: float, margin: float):
    """Return list of walls {"a":[x,y], "b":[x,y], "t":thickness, "kind":"int|ext|diag"} in metres."""
    n = max(3, int(MIN_RUN * ppm))
    hmask = cv2.morphologyEx(walls, cv2.MORPH_OPEN, np.ones((1, n), np.uint8))
    vmask = cv2.morphologyEx(walls, cv2.MORPH_OPEN, np.ones((n, 1), np.uint8))
    H = _bands(hmask, 0, ppm)          # [y, x0, x1, t]   (pixel-frame metres, no margin)
    V = _bands(vmask, 1, ppm)          # [x, y0, y1, t]
    addH, addV, diag = _residual_strokes(walls, H, V, ppm)
    H += addH; V += addV
    for s in H + V:
        s[3] = T_EXT if s[3] > EXT_THRESHOLD else T_INT
    H, V = _snap_lines(H), _snap_lines(V)
    # exterior outlines wobble more on the photos: unify them with a wider tolerance
    for L_ in (H, V):
        ext = [s for s in L_ if s[3] == T_EXT]
        _snap_lines(ext, EXT_LINE_TOL)
    H, V = _dedupe_parallel(H), _dedupe_parallel(V)
    H, V = _snap_lines(H), _snap_lines(V)
    H, V = _merge_collinear(H), _merge_collinear(V)
    H, V = _dedupe_parallel(H), _dedupe_parallel(V)
    # junctions: snap ends of H onto V and vice versa (two passes so both sides settle)
    for _ in range(2):
        for A, B in ((H, V), (V, H)):
            for s in A:
                for end in (1, 2):
                    best = None
                    for p in B:
                        if not (p[1] - JOIN_TOL <= s[0] <= p[2] + JOIN_TOL):
                            continue
                        d = abs(p[0] - s[end])
                        if d <= JOIN_TOL and (best is None or d < best[0]):
                            best = (d, p)
                    if best is not None:
                        p = best[1]
                        ext = p[3] / 2
                        s[end] = p[0] - ext if end == 1 else p[0] + ext
                        # make sure the crossing wall reaches this one too
                        if s[0] < p[1] and p[1] - s[0] <= JOIN_TOL:
                            p[1] = s[0] - s[3] / 2
                        if s[0] > p[2] and s[0] - p[2] <= JOIN_TOL:
                            p[2] = s[0] + s[3] / 2
    H = [s for s in H if s[2] - s[1] > 1e-3]
    V = [s for s in V if s[2] - s[1] > 1e-3]

    # drop isolated short strokes (pictograms) - connected = touches/overlaps another wall
    def rect(s, axis):
        c, a0, a1, t = s
        return (a0, c - t / 2, a1, c + t / 2) if axis == 0 else (c - t / 2, a0, c + t / 2, a1)
    rects = [(rect(s, 0), s, 0) for s in H] + [(rect(s, 1), s, 1) for s in V]
    # keep long walls, then (repeatedly) short strokes that connect to something kept;
    # free-floating clusters of short strokes are pictograms (toilet figures etc.)
    def touch(r, q):
        return r[0] <= q[2] + 0.05 and q[0] <= r[2] + 0.05 and r[1] <= q[3] + 0.05 and q[1] <= r[3] + 0.05
    kept = {i for i, (r, s, ax) in enumerate(rects) if s[2] - s[1] >= ISOLATED_MIN}
    grow = True
    while grow:
        grow = False
        for i, (r, s, ax) in enumerate(rects):
            if i not in kept and any(touch(r, rects[j][0]) for j in kept):
                kept.add(i); grow = True
    keep = sorted(kept)
    out = []
    for i in keep:
        r, s, ax = rects[i]
        c, a0, a1, t = s
        a, b = ([a0, c], [a1, c]) if ax == 0 else ([c, a0], [c, a1])
        out.append({"a": a, "b": b, "t": t, "kind": "ext" if t == T_EXT else "int"})

    out += diag

    # shift from raster frame to building metres
    for w in out:
        w["a"] = [round(w["a"][0] - margin, 3), round(w["a"][1] - margin, 3)]
        w["b"] = [round(w["b"][0] - margin, 3), round(w["b"][1] - margin, 3)]
    return out


def wall_quad(w):
    """Wall as a 4-point polygon (metres)."""
    a, b = np.array(w["a"], float), np.array(w["b"], float)
    d = b - a
    L = np.hypot(*d)
    if L < 1e-9:
        return None
    nrm = np.array([-d[1], d[0]]) / L * w["t"] / 2
    return [list(np.round(p, 3)) for p in (a + nrm, b + nrm, b - nrm, a - nrm)]


def _draw(mask, w, ppm, margin, extra=0.0):
    q = wall_quad({**w, "t": w["t"] + extra})
    if q is None:
        return
    pts = np.round((np.array(q) + margin) * ppm * 16 - 8).astype(np.int32)
    cv2.fillPoly(mask, [pts], 1, lineType=cv2.LINE_8, shift=4)


def rasterize_walls(walls, shape, ppm, margin):
    m = np.zeros(shape, np.uint8)
    for w in walls:
        _draw(m, w, ppm, margin)
    return m
