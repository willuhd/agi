"""Wall extraction: rectified photo -> clean wall mask -> routing obstacle grid."""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from .imgutil import ink_map

INK_THRESHOLD = 40.0


@dataclass
class Frame:
    """Raster <-> metre mapping. Pixel centre (u, v) is at ((u+.5)/ppm - margin, (v+.5)/ppm - margin)."""
    ppm: float
    margin: float
    shape: tuple

    def to_px(self, xy):
        xy = np.asarray(xy, float)
        return (xy + self.margin) * self.ppm - 0.5

    def to_m(self, uv):
        uv = np.asarray(uv, float)
        return (uv + 0.5) / self.ppm - self.margin

    def poly_px(self, poly):
        return np.round(self.to_px(poly) * 16).astype(np.int32)   # 4 fractional bits for cv2 fills


def fill_poly(mask, frame: Frame, poly, value=1):
    cv2.fillPoly(mask, [frame.poly_px(poly)], value, lineType=cv2.LINE_8, shift=4)


def rect_poly(r):
    x0, y0, x1, y1 = r
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def _char_components(stats, ppm):
    """Indices of connected components that look like plan lettering (digits / capitals)."""
    out = []
    for i in range(1, len(stats)):
        x, y, w, h, a = stats[i]
        if 0.55 * ppm <= h <= 2.4 * ppm and 0.12 * ppm <= w <= 1.8 * ppm and h / max(w, 1) < 8 and a / (w * h) < 0.75:
            out.append(i)
    return out


def _label_clusters(stats, idx):
    """Group character components into horizontal text runs (>= 2 glyphs)."""
    boxes = {i: stats[i][:4] for i in idx}
    parent = {i: i for i in idx}

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    items = sorted(idx)
    for a_i, a in enumerate(items):
        xa, ya, wa, ha = boxes[a]
        for b in items[a_i + 1:]:
            xb, yb, wb, hb = boxes[b]
            if not 0.6 < ha / hb < 1.6:
                continue
            if abs((ya + ha / 2) - (yb + hb / 2)) > 0.35 * max(ha, hb):
                continue
            gap = max(xb - (xa + wa), xa - (xb + wb))
            if gap < 0.7 * max(ha, hb):
                parent[find(a)] = find(b)
    groups = {}
    for i in items:
        groups.setdefault(find(i), []).append(i)
    return [g for g in groups.values() if len(g) >= 2]


@dataclass
class FloorRaster:
    frame: Frame                       # fine frame of the rectified photo
    walls: np.ndarray                  # uint8 {0,1} clean drawn walls (fine)
    removed_text: list = field(default_factory=list)   # label boxes (metres) that were erased


def extract_walls(rect_bgr: np.ndarray, frame: Frame, room_seeds) -> FloorRaster:
    ppm = frame.ppm
    ink = ink_map(rect_bgr, bg_kernel=int(3 * ppm) | 1)
    mask = (ink > INK_THRESHOLD).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)

    kill = np.zeros(n, bool)
    # 1) room-number lettering: clustered glyph runs
    chars = _char_components(stats, ppm)
    boxes = []
    for g in _label_clusters(stats, chars):
        kill[g] = True
        x0 = min(stats[i][0] for i in g); y0 = min(stats[i][1] for i in g)
        x1 = max(stats[i][0] + stats[i][2] for i in g); y1 = max(stats[i][1] + stats[i][3] for i in g)
        boxes.append((x0, y0, x1, y1))
    # 2) isolated glyphs close to a known label position (e.g. a lone '1')
    seeds_px = frame.to_px(np.asarray(room_seeds, float).reshape(-1, 2)) if len(room_seeds) else np.zeros((0, 2))
    for i in chars:
        x, y, w, h, _ = stats[i]
        cx, cy = x + w / 2, y + h / 2
        if len(seeds_px) and np.min(np.abs(seeds_px[:, 0] - cx) / (2.6 * ppm) + np.abs(seeds_px[:, 1] - cy) / (1.2 * ppm)) < 1:
            kill[i] = True
    # 3) pictograms / dots: small, compact blobs (toilet figures, wheelchair, 'you are here')
    for i in range(1, n):
        x, y, w, h, a = stats[i]
        big, small = max(w, h), max(min(w, h), 1)
        if big < 1.5 * ppm and big / small < 4.0:
            kill[i] = True
    kill[0] = False
    clean = mask.copy()
    clean[kill[lab]] = 0
    # bridge 1-px breaks in thin anti-aliased lines (doors are >= 0.6 m so never closed)
    clean = cv2.morphologyEx(clean, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    removed = [tuple(frame.to_m([b[0], b[1]])) + tuple(frame.to_m([b[2], b[3]])) for b in boxes]
    return FloorRaster(frame=frame, walls=clean, removed_text=removed)


def downsample_any(mask: np.ndarray, src: Frame, dst: Frame, frac: float = 0.15) -> np.ndarray:
    """Resample a fine binary mask onto a coarser frame (cell is set if >= frac covered)."""
    # dst pixel centre -> metres -> src pixel coordinates; area-average via box blur + sample
    s = src.ppm / dst.ppm
    off = (src.margin - dst.margin) * src.ppm + 0.5 * s - 0.5
    k = max(1, int(round(s)))
    blurred = cv2.blur(mask.astype(np.float32), (k, k))
    H, W = dst.shape
    vv, uu = np.mgrid[0:H, 0:W].astype(np.float32)
    mx = (s * uu + off).astype(np.float32)
    my = (s * vv + off).astype(np.float32)
    cov = cv2.remap(blurred, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=1.0)
    return (cov >= frac).astype(np.uint8)
