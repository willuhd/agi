"""Photo calibration: snap outer walls, build image->building-metre homographies.

Each floor-plan photo is a perspective view of a printed plan.  Four outer-wall lines
(N, W, S, E) are snapped to sub-pixel accuracy and intersected into the envelope
corners, which are mapped to the envelope rectangle in metres.  Because all floors share
the same envelope, this one step both removes perspective and registers the floors.
"""
from __future__ import annotations

import cv2
import numpy as np

from .imgutil import ink_map, intersect, snap_line


def envelope_size(meta: dict) -> tuple[float, float]:
    h = float(meta["envelope_ns_m"])
    return h * float(meta["envelope_aspect"]), h


def envelope_corners(img_bgr: np.ndarray, approx: dict) -> dict:
    ink = ink_map(img_bgr)
    lines = {k: snap_line(ink, *v) for k, v in approx.items()}
    corners = {c: intersect(lines[c[0]], lines[c[1]]) for c in ("NW", "NE", "SE", "SW")}
    return {"corners": corners, "rms_px": {k: v[2] for k, v in lines.items()}}


def homography(corners: dict, W: float, H: float) -> np.ndarray:
    """3x3 homography: image px -> building metres."""
    src = np.float32([corners[k] for k in ("NW", "NE", "SE", "SW")])
    dst = np.float32([[0, 0], [W, 0], [W, H], [0, H]])
    return cv2.getPerspectiveTransform(src, dst)


def metric_aspect(corners: dict, img_shape) -> float | None:
    """Self-calibrated envelope aspect (W/H) of one photo.

    The two vanishing points of the envelope rectangle give the focal length
    (orthogonality constraint, principal point = image centre); back-projecting the
    corners onto the recovered plane yields the true width/height ratio.
    """
    h_, w_ = img_shape[:2]
    c = np.array([w_ / 2, h_ / 2])
    P = {k: np.array([*v, 1.0]) for k, v in corners.items()}
    v1 = np.cross(np.cross(P["NW"], P["NE"]), np.cross(P["SW"], P["SE"]))
    v2 = np.cross(np.cross(P["NW"], P["SW"]), np.cross(P["NE"], P["SE"]))
    if abs(v1[2]) < 1e-12 or abs(v2[2]) < 1e-12:
        return None
    f2 = -((v1[:2] / v1[2] - c) @ (v2[:2] / v2[2] - c))
    if f2 <= 0:
        return None
    f = np.sqrt(f2)
    Ki = np.linalg.inv(np.array([[f, 0, c[0]], [0, f, c[1]], [0, 0, 1]]))
    n = np.cross(Ki @ v1, Ki @ v2)
    X = {k: (Ki @ p) / (n @ (Ki @ p)) for k, p in P.items()}
    w = (np.linalg.norm(X["NE"] - X["NW"]) + np.linalg.norm(X["SE"] - X["SW"])) / 2
    h = (np.linalg.norm(X["SW"] - X["NW"]) + np.linalg.norm(X["SE"] - X["NE"])) / 2
    return float(w / h)


def wall_runs(walls: np.ndarray, ppm: float, margin: float, min_len_m: float = 2.5):
    """Straight wall runs (least-squares lines) in metres: list of (p0, p1, length, axis)."""
    n = int(min_len_m * ppm)
    runs = []
    for axis, k in ((0, np.ones((1, n), np.uint8)), (1, np.ones((n, 1), np.uint8))):
        op = cv2.morphologyEx(walls, cv2.MORPH_OPEN, k)
        cnt, lab, st, _ = cv2.connectedComponentsWithStats(op, connectivity=8)
        for i in range(1, cnt):
            ys, xs = np.nonzero(lab == i)
            P = np.stack([xs, ys], 1).astype(float)
            c = P.mean(0)
            ev, evec = np.linalg.eigh((P - c).T @ (P - c))
            if ev[1] < 25 * max(ev[0], 1e-9):
                continue
            d = evec[:, 1]
            t = (P - c) @ d
            p0, p1 = c + d * t.min(), c + d * t.max()
            runs.append(((p0 + 0.5) / ppm - margin, (p1 + 0.5) / ppm - margin, float(t.max() - t.min()) / ppm, axis))
    return runs


def run_tilts(runs, C=None):
    """Signed deviation (deg) of each run from its axis after optional metric->metric map C."""
    out = []
    for p0, p1, L, axis in runs:
        q = np.array([p0, p1], float)
        if C is not None:
            q = cv2.perspectiveTransform(q[None].astype(np.float64), C)[0]
        dx, dy = q[1] - q[0]
        a = np.degrees(np.arctan2(dy, dx)) if axis == 0 else -np.degrees(np.arctan2(dx, dy))
        out.append((a + 90.0) % 180.0 - 90.0)          # direction sign of a line is arbitrary
    return np.array(out)


class StraighteningWarp:
    """Smooth correction p' = p + D(p) (cubic bivariate polynomial per axis) that makes
    long interior wall runs exactly axis-parallel.

    Perspective is removed by the homography, but the printed signs are not perfectly
    drawn/flat: on several floors interior walls drift by up to ~1.7 deg between the
    north and south facades, which no homography can model.  D is fitted by linear
    least squares (Huber re-weighted): every sample along a horizontal run must map to
    the same y, every sample along a vertical run to the same x; the four envelope
    corners are pinned (D = 0) so the metric scale is untouched; a minimum-displacement
    prior keeps the field as small as possible where walls give no information.
    """
    DEG = 3

    def __init__(self, W: float, H: float, cu=None, cv=None):
        self.W, self.H = W, H
        n = len(self._terms())
        self.cu = np.zeros(n) if cu is None else np.asarray(cu, float)
        self.cv = np.zeros(n) if cv is None else np.asarray(cv, float)

    def _terms(self):
        return [(i, j) for i in range(self.DEG + 1) for j in range(self.DEG + 1 - i)]

    def basis(self, P):
        P = np.asarray(P, float).reshape(-1, 2)
        xn, yn = P[:, 0] / self.W, P[:, 1] / self.H
        return np.stack([xn ** i * yn ** j for i, j in self._terms()], 1)

    def apply(self, P):
        P = np.asarray(P, float).reshape(-1, 2)
        B = self.basis(P)
        return P + np.stack([B @ self.cu, B @ self.cv], 1)

    def inverse(self, Q, iters: int = 4):
        Q = np.asarray(Q, float).reshape(-1, 2)
        P = Q.copy()
        for _ in range(iters):
            B = self.basis(P)
            P = Q - np.stack([B @ self.cu, B @ self.cv], 1)
        return P

    @classmethod
    def fit(cls, runs, W: float, H: float, samples: int = 9, smallness: float = 0.08):
        warp = cls(W, H)
        corners = np.array([[0, 0], [W, 0], [W, H], [0, H]], float)
        Bc = warp.basis(corners)
        # minimum-displacement prior over the whole floor (keeps the field as small as possible)
        gp = np.array([[x, y] for x in np.linspace(0, W, 9) for y in np.linspace(0, H, 11)])
        Bg = warp.basis(gp) * smallness
        for axis, attr in ((0, "cv"), (1, "cu")):          # horizontal runs fix v, vertical fix u
            rs = [r for r in runs if r[3] == axis]
            blocks, rhs, wrun = [], [], []
            for p0, p1, L, _ in rs:
                t = np.linspace(0, 1, samples)[:, None]
                S = p0[None, :] * (1 - t) + p1[None, :] * t
                B = warp.basis(S)
                c = S[:, 1 - axis]                            # the coordinate that must be constant
                blocks.append(B - B.mean(0)); rhs.append(-(c - c.mean())); wrun.append(np.sqrt(L / samples))
            wr = np.ones(len(rs))
            n = Bc.shape[1]
            for _ in range(6):
                A = np.concatenate([blk * (w * q) for blk, w, q in zip(blocks, wrun, wr)] + [Bc * 100.0, Bg])
                y = np.concatenate([r * (w * q) for r, w, q in zip(rhs, wrun, wr)] + [np.zeros(4), np.zeros(len(Bg))])
                coef = np.linalg.lstsq(A, y, rcond=None)[0]
                # Huber weights per run on its rms straightness error (m)
                err = np.array([np.sqrt(np.mean((blk @ coef - r) ** 2)) for blk, r in zip(blocks, rhs)])
                wr = 1.0 / np.maximum(1.0, err / 0.08)
            setattr(warp, attr, coef)
        return warp

    def to_dict(self):
        return {"degree": self.DEG, "terms_xn^i_yn^j": self._terms(), "cu": [round(float(v), 6) for v in self.cu],
                "cv": [round(float(v), 6) for v in self.cv]}


def rectify(img_bgr: np.ndarray, Hm: np.ndarray, W: float, H: float, ppm: float, margin: float,
            warp: "StraighteningWarp | None" = None):
    """Warp a photo into the metric frame.  Pixel (u,v) <-> metres ((u+.5)/ppm - margin, ...).

    Full mapping photo -> metres is  p_m = warp.apply(Hm(p_px)); for resampling each output
    pixel is pulled back through warp.inverse and Hm^-1.
    """
    size = (int(round((W + 2 * margin) * ppm)), int(round((H + 2 * margin) * ppm)))
    vv, uu = np.mgrid[0:size[1], 0:size[0]].astype(np.float64)
    Q = np.stack([(uu.ravel() + 0.5) / ppm - margin, (vv.ravel() + 0.5) / ppm - margin], 1)
    P = warp.inverse(Q) if warp is not None else Q
    src = cv2.perspectiveTransform(P[None], np.linalg.inv(Hm))[0]
    mx = src[:, 0].reshape(size[1], size[0]).astype(np.float32)
    my = src[:, 1].reshape(size[1], size[0]).astype(np.float32)
    return cv2.remap(img_bgr, mx, my, cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))
