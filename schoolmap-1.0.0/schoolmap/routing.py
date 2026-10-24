"""Within-floor walking routes on a clearance-aware 16-connected grid.

Cost model: a step of length L between free cells costs  L * (1 + p * max(0, 1 - d/c)),
where d is the distance to the nearest wall and c the comfort clearance.  This keeps
routes in the middle of corridors and doorways like real pedestrians, while still
allowing narrow doors.  The *reported* distance is the geometric length of the route
after string-pulling (any-angle smoothing that respects the same clearance), so it is
not biased by the grid or by the penalty.
"""
from __future__ import annotations

import cv2
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

# 16-neighbourhood (orthogonal, diagonal, knight moves) with cells each move sweeps through
_MOVES = []
for dx, dy in [(1, 0), (0, 1), (1, 1), (1, -1), (2, 1), (1, 2), (2, -1), (1, -2)]:
    if abs(dx) + abs(dy) == 1:
        via = []
    elif abs(dx) == 1 and abs(dy) == 1:
        via = [(dx, 0), (0, dy)]                       # no corner cutting
    else:
        sx, sy = np.sign(dx), np.sign(dy)
        via = [(sx, 0), (0, sy), (sx, sy)] + ([(2 * sx, 0) if abs(dx) == 2 else (0, 2 * sy)])
        via = [(int(a), int(b)) for a, b in via if (a, b) != (dx, dy)]
    _MOVES.append((dx, dy, via))


class FloorGraph:
    def __init__(self, free: np.ndarray, grid_m: float, comfort_m: float, min_clear_m: float, penalty: float):
        self.grid_m = grid_m
        self.shape = free.shape
        dist = cv2.distanceTransform(free.astype(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE) * grid_m
        self.clear = dist
        self.ok = (free > 0) & (dist >= min_clear_m)
        self.comfort_m = comfort_m
        pen = 1.0 + penalty * np.clip(1.0 - dist / comfort_m, 0, None)
        H, W = self.shape
        idx = -np.ones(self.shape, np.int64)
        ys, xs = np.nonzero(self.ok)
        idx[ys, xs] = np.arange(len(ys))
        self.idx, self.ys, self.xs = idx, ys, xs
        rows, cols, wts = [], [], []
        okp = np.pad(self.ok, 2, constant_values=False)
        penp = np.pad(pen, 2, constant_values=1.0)
        idxp = np.pad(idx, 2, constant_values=-1)
        for dx, dy, via in _MOVES:
            m = okp[2:-2, 2:-2] & okp[2 + dy:2 + dy + H, 2 + dx:2 + dx + W]
            for vx, vy in via:
                m &= okp[2 + vy:2 + vy + H, 2 + vx:2 + vx + W]
            a = idxp[2:-2, 2:-2][m]
            b = idxp[2 + dy:2 + dy + H, 2 + dx:2 + dx + W][m]
            L = np.hypot(dx, dy) * grid_m
            w = L * 0.5 * (penp[2:-2, 2:-2][m] + penp[2 + dy:2 + dy + H, 2 + dx:2 + dx + W][m])
            rows += [a, b]; cols += [b, a]; wts += [w, w]
        n = len(ys)
        self.G = csr_matrix((np.concatenate(wts), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n))

    # ------------------------------------------------------------------
    def snap(self, rc, max_m: float = 3.0, prefer_comfort: bool = True):
        """Nearest routable cell to (row, col); prefers cells with comfortable clearance."""
        r, c = int(round(rc[0])), int(round(rc[1]))
        R = int(max_m / self.grid_m)
        r0, r1 = max(r - R, 0), min(r + R + 1, self.shape[0])
        c0, c1 = max(c - R, 0), min(c + R + 1, self.shape[1])
        ok = self.ok[r0:r1, c0:c1]
        if not ok.any():
            return None
        yy, xx = np.mgrid[r0:r1, c0:c1]
        d2 = (yy - rc[0]) ** 2 + (xx - rc[1]) ** 2
        score = np.where(ok, d2, np.inf)
        if prefer_comfort:
            good = ok & (self.clear[r0:r1, c0:c1] >= min(0.35, self.comfort_m))
            if good.any():
                score = np.where(good, d2, np.inf)
        k = np.unravel_index(np.argmin(score), score.shape)
        return int(yy[k]), int(xx[k])

    def snap_in(self, rc, allowed, max_m: float = 3.0):
        """Nearest cell of `allowed` (prefers comfortable clearance)."""
        r, c = int(round(rc[0])), int(round(rc[1]))
        R = int(max_m / self.grid_m)
        r0, r1 = max(r - R, 0), min(r + R + 1, self.shape[0])
        c0, c1 = max(c - R, 0), min(c + R + 1, self.shape[1])
        ok = allowed[r0:r1, c0:c1] & self.ok[r0:r1, c0:c1]
        if not ok.any():
            return None
        yy, xx = np.mgrid[r0:r1, c0:c1]
        d2 = ((yy - rc[0]) ** 2 + (xx - rc[1]) ** 2).astype(float)
        good = ok & (self.clear[r0:r1, c0:c1] >= min(0.35, self.comfort_m))
        score = np.where(good if good.any() else ok, d2, np.inf)
        k = np.unravel_index(np.argmin(score), score.shape)
        return int(yy[k]), int(xx[k])

    def field(self, rc, allowed):
        """Single-source shortest-path field restricted to `allowed` cells."""
        return _Field(self, rc, allowed)

    def node(self, rc):
        return int(self.idx[rc])

    def solve(self, sources):
        """Dijkstra from many sources; returns (cost[n_src, n], pred[n_src, n])."""
        return dijkstra(self.G, directed=False, indices=sources, return_predecessors=True)

    def cell_path(self, pred_row, src, dst):
        path = [dst]
        while path[-1] != src:
            p = pred_row[path[-1]]
            if p < 0:
                return None
            path.append(p)
        path.reverse()
        return np.stack([self.ys[path], self.xs[path]], 1)

    # ------------------------------------------------------------------
    def _los(self, a, b, thr, allowed=None):
        n = int(np.ceil(np.hypot(*(b - a)) * 2)) + 2
        t = np.linspace(0, 1, n)
        pts = a[None, :] + (b - a)[None, :] * t[:, None]
        r = np.round(pts[:, 0]).astype(int); c = np.round(pts[:, 1]).astype(int)
        if allowed is not None and not allowed[r, c].all():
            return False
        return bool(np.all(self.clear[r, c] >= thr))

    def smooth(self, cells: np.ndarray, allowed=None) -> np.ndarray:
        """Greedy string pulling; each shortcut must keep at least the clearance the raw
        route had over the same stretch (capped at the comfort clearance)."""
        cells = cells.astype(float)
        n = len(cells)
        if n <= 2:
            return cells
        cl = self.clear[cells[:, 0].astype(int), cells[:, 1].astype(int)]
        out = [cells[0]]
        i = 0
        while i < n - 1:
            lo, hi = i + 1, n - 1
            # exponential then binary search for the farthest visible vertex
            best = i + 1
            step = 1
            j = i + 1
            while j <= hi:
                thr = min(self.comfort_m, cl[i:j + 1].min()) - 1e-6
                if self._los(cells[i], cells[j], thr, allowed):
                    best = j
                    step *= 2
                    j = i + step
                else:
                    break
            lo, hi2 = best + 1, min(j, hi)
            while lo <= hi2:
                mid = (lo + hi2) // 2
                thr = min(self.comfort_m, cl[i:mid + 1].min()) - 1e-6
                if self._los(cells[i], cells[mid], thr, allowed):
                    best = mid; lo = mid + 1
                else:
                    hi2 = mid - 1
            out.append(cells[best])
            i = best
        return np.array(out)


class _Field:
    """Dijkstra field from one cell over a sub-graph (cells outside `allowed` removed)."""

    def __init__(self, fg: FloorGraph, rc, allowed):
        self.fg = fg
        keep = allowed[fg.ys, fg.xs]
        self.glob = np.nonzero(keep)[0]                      # local -> global node id
        self.loc = -np.ones(len(fg.ys), np.int64)
        self.loc[self.glob] = np.arange(len(self.glob))
        sub = fg.G[self.glob][:, self.glob]
        self.src = int(self.loc[fg.node(rc)])
        if self.src < 0:
            raise ValueError("source cell not in allowed set")
        self.dist, self.pred = dijkstra(sub, directed=False, indices=self.src, return_predecessors=True)

    def dist_at(self, global_ids):
        li = self.loc[np.asarray(global_ids, np.int64)]
        out = np.full(len(li), np.inf)
        ok = li >= 0
        out[ok] = self.dist[li[ok]]
        return out

    def path_to(self, global_id):
        li = int(self.loc[global_id])
        path = [li]
        while path[-1] != self.src:
            p = self.pred[path[-1]]
            if p < 0:
                raise ValueError("unreachable")
            path.append(p)
        g = self.glob[np.array(path[::-1])]
        return np.stack([self.fg.ys[g], self.fg.xs[g]], 1)
