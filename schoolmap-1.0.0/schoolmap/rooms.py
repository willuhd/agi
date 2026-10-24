"""Room-region extraction ("closing the doors") on the routing grid."""
from __future__ import annotations

import cv2
import numpy as np

RADII = (0.45, 0.6, 0.75, 0.9, 1.05, 1.2, 1.35, 1.5)
DEFAULT_MAX_AREA = 260.0


def _disk(r_px):
    k = 2 * r_px + 1
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))


def extract_room(free: np.ndarray, dist_m: np.ndarray, grid_m: float, seed_rc, other_rc, max_area: float):
    """Return dict(mask, poly_cells, anchor_rc, radius) or None.

    For increasing door-closing radius R, take the connected component of {dist > R}
    containing the seed.  The first R whose component neither contains another room's
    seed / a stair landing nor exceeds max_area is accepted; the room is then
    reconstructed by dilating that core by R inside free space.
    """
    H, W = free.shape
    sr, sc = seed_rc
    for R in RADII:
        core = (dist_m > R).astype(np.uint8)
        # the label seed may sit near a wall in a small room: snap to nearest core cell
        r0, r1 = max(sr - 25, 0), min(sr + 26, H)
        c0, c1 = max(sc - 25, 0), min(sc + 26, W)
        win = core[r0:r1, c0:c1]
        if not win.any():
            continue
        yy, xx = np.nonzero(win)
        k = np.argmin((yy + r0 - sr) ** 2 + (xx + c0 - sc) ** 2)
        s = (int(yy[k] + r0), int(xx[k] + c0))
        n, lab = cv2.connectedComponents(core, connectivity=8)
        comp = lab == lab[s]
        area = comp.sum() * grid_m ** 2
        if area > max_area:
            continue
        if any(comp[r, c] for r, c in other_rc if 0 <= r < H and 0 <= c < W):
            continue
        Rpx = int(np.ceil(R / grid_m))
        region = cv2.dilate(comp.astype(np.uint8), np.ones((2 * Rpx + 1, 2 * Rpx + 1), np.uint8)) & free
        return {"core": comp, "mask": region.astype(bool), "radius": R, "seed_rc": s}
    return None


def region_polygon(core: np.ndarray, mask: np.ndarray, R_px: float):
    """Room outline in grid coords (x=col, y=row). Rectangular rooms -> exact rectangle."""
    # strip door bulges (thin protrusions of the core through openings) before testing
    k = max(3, int(round(R_px)) * 2 + 1)
    body = cv2.morphologyEx(core.astype(np.uint8), cv2.MORPH_OPEN, np.ones((k, k), np.uint8)) > 0
    if body.sum() < 0.6 * core.sum():
        body = core
    ys, xs = np.nonzero(body)
    bbox_area = (ys.max() - ys.min() + 1) * (xs.max() - xs.min() + 1)
    if body.sum() / bbox_area > 0.9:
        my, mx = np.nonzero(mask)
        x0, x1 = max(xs.min() - R_px, mx.min()), min(xs.max() + R_px, mx.max())
        y0, y1 = max(ys.min() - R_px, my.min()), min(ys.max() + R_px, my.max())
        return np.array([[x0 - .5, y0 - .5], [x1 + .5, y0 - .5], [x1 + .5, y1 + .5], [x0 - .5, y1 + .5]], float)
    # non-rectangular: rebuild from the bulge-free body with a square kernel (keeps the
    # outline rectilinear along the walls), simplify, then square up near-axis edges
    k = int(round(R_px)) * 2 + 1
    m = (cv2.dilate(body.astype(np.uint8), np.ones((k, k), np.uint8)) & mask.astype(np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    c = max(cnts, key=cv2.contourArea)
    c = cv2.approxPolyDP(c, 2.0, True)[:, 0, :].astype(float)
    return orthogonalize(c)


def orthogonalize(poly, max_dev_deg: float = 15.0, min_edge: float = 2.5):
    """Square up a polygon: edges within max_dev of an axis become exactly axis-parallel
    (shared vertices are moved consistently); very short jogs are removed."""
    P = [np.array(p, float) for p in poly]
    for _ in range(3):
        n = len(P)
        for i in range(n):
            a, b = P[i], P[(i + 1) % n]
            d = b - a
            ang = np.degrees(np.arctan2(abs(d[1]), abs(d[0])))
            if ang <= max_dev_deg:
                y = (a[1] + b[1]) / 2; a[1] = y; b[1] = y
            elif ang >= 90 - max_dev_deg:
                x = (a[0] + b[0]) / 2; a[0] = x; b[0] = x
        # drop zero-length / collinear vertices and tiny jogs
        Q = []
        for i in range(len(P)):
            p, q, r = P[i - 1], P[i], P[(i + 1) % len(P)]
            if np.hypot(*(q - p)) < 1e-6:
                continue
            cross = (q - p)[0] * (r - q)[1] - (q - p)[1] * (r - q)[0]
            if abs(cross) < 1e-6:
                continue
            Q.append(q)
        P = Q if len(Q) >= 3 else P
        # remove jogs shorter than min_edge cells by projecting the neighbour edge through
        n = len(P)
        if n > 4:
            for i in range(n):
                a, b = P[i], P[(i + 1) % n]
                if np.hypot(*(b - a)) < min_edge:
                    mid = (a + b) / 2
                    if abs(b[0] - a[0]) < 1e-6:          # vertical jog -> align y of neighbours
                        P[i] = np.array([a[0], mid[1]]); P[(i + 1) % n] = np.array([b[0], mid[1]])
                    elif abs(b[1] - a[1]) < 1e-6:
                        P[i] = np.array([mid[0], a[1]]); P[(i + 1) % n] = np.array([mid[0], b[1]])
    return np.array(P)


def anchor_cell(core: np.ndarray):
    """Pole of the core: interior cell farthest from the core boundary (stable, inside)."""
    d = cv2.distanceTransform(np.pad(core.astype(np.uint8), 1), cv2.DIST_L2, 5)[1:-1, 1:-1]
    # among the deepest cells pick the one closest to the core centroid (deterministic)
    ys, xs = np.nonzero(d >= d.max() - 1.0)
    cy, cx = np.nonzero(core)
    my, mx = cy.mean(), cx.mean()
    k = np.lexsort((xs, ys, (ys - my) ** 2 + (xs - mx) ** 2))[0]
    return int(ys[k]), int(xs[k])
