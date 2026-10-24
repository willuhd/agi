"""Overlay vectorised walls (red) on the raw wall raster (grey) for one floor."""
import sys, cv2, numpy as np
sys.path.insert(0, '.')
from schoolmap.vectorize import vectorize_walls, rasterize_walls
fid, out = sys.argv[1], sys.argv[2]
raw = (cv2.imread(f'output/debug/walls_raw_{fid}.png', 0) < 128).astype(np.uint8)
v = vectorize_walls(raw, 25.0, 1.0)
r = rasterize_walls(v, raw.shape, 25.0, 1.0)
vis = np.full(raw.shape + (3,), 255, np.uint8)
vis[raw > 0] = (190, 190, 190)
vis[r > 0] = (40, 40, 220)
vis[(r > 0) & (raw > 0)] = (30, 30, 120)
for w in v:
    if w['kind'] == 'diag':
        a = tuple(int((c + 1) * 25) for c in w['a']); b = tuple(int((c + 1) * 25) for c in w['b'])
        cv2.line(vis, a, b, (0, 160, 0), 2)
cv2.imwrite(out, vis)
print(len(v), 'walls', sum(w['kind'] == 'diag' for w in v), 'diag')
