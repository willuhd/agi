"""Image utilities: ink extraction and sub-pixel line snapping on the floor-plan photos."""
from __future__ import annotations

import cv2
import numpy as np


def ink_map(img_bgr: np.ndarray, bg_kernel: int = 61) -> np.ndarray:
    """Per-pixel 'ink strength' = colour distance from the locally estimated paper background.

    Works for every outline colour used on the signs (dark brown, gold, green, blue, pink)
    and is robust to the uneven lighting / glare of the photos.
    """
    img = img_bgr.astype(np.float32)
    bg = np.stack([cv2.medianBlur(img_bgr[..., c], bg_kernel) for c in range(3)], -1).astype(np.float32)
    # only count pixels darker than the background (ink), not highlights / glare
    diff = np.clip(bg - img, 0, None)
    return np.sqrt((diff ** 2).sum(-1))


def snap_line(ink: np.ndarray, p0, p1, half_width: float = 9.0, n: int = 80, trim: float = 0.06):
    """Snap an approximate segment p0-p1 to the centre-line of the drawn wall.

    Samples perpendicular intensity profiles along the segment, takes the ink-weighted
    centroid of each profile and fits a line with iteratively re-weighted least squares.
    Returns (point_on_line, unit_direction, rms_residual_px).
    """
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    d = p1 - p0
    L = np.linalg.norm(d)
    d /= L
    nrm = np.array([-d[1], d[0]])
    offs = np.arange(-half_width, half_width + 0.5, 0.5)
    pts = []
    for t in np.linspace(trim, 1 - trim, n):
        c = p0 + d * L * t
        xy = c[None, :] + offs[:, None] * nrm[None, :]
        vals = cv2.remap(ink.astype(np.float32), xy[:, 0:1].astype(np.float32).reshape(-1, 1),
                         xy[:, 1:2].astype(np.float32).reshape(-1, 1), cv2.INTER_LINEAR).ravel()
        if vals.max() < 25:          # no ink here (gap / door) -> skip sample
            continue
        w = np.clip(vals - 0.5 * vals.max(), 0, None)
        o = (w * offs).sum() / w.sum()
        pts.append(c + o * nrm)
    pts = np.array(pts)
    w = np.ones(len(pts))
    for _ in range(10):
        m = (pts * w[:, None]).sum(0) / w.sum()
        cov = ((pts - m) * w[:, None]).T @ (pts - m)
        evals, evecs = np.linalg.eigh(cov)
        dirn = evecs[:, 1]
        r = (pts - m) @ np.array([-dirn[1], dirn[0]])
        s = max(np.median(np.abs(r)) * 1.4826, 0.3)
        w = 1.0 / np.maximum(1.0, np.abs(r) / (1.5 * s))   # Huber weights
    rms = float(np.sqrt(np.average(r ** 2, weights=w)))
    if dirn @ d < 0:
        dirn = -dirn
    return m, dirn, rms


def intersect(l1, l2):
    (p, d), (q, e) = l1[:2], l2[:2]
    A = np.array([d, -e]).T
    t = np.linalg.solve(A, q - p)
    return p + t[0] * d
