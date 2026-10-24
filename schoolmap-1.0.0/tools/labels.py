import sys, cv2, numpy as np
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
from schoolmap.imgutil import ink_map
PPM, M = 25, 2.0
S = sys.argv[1]
for f in sys.argv[2:]:
    r = cv2.imread(rf'{S}/rect_{f}.png')
    m = (ink_map(r, 75) > 40).astype(np.uint8)
    n, lab, st, cen = cv2.connectedComponentsWithStats(m, 8)
    chars = []
    for i in range(1, n):
        x, y, w, h, a = st[i]
        if 14 <= h <= 60 and 3 <= w <= 45 and h / max(w, 1) < 8 and a / (w * h) < 0.75:
            chars.append((x, y, w, h))
    # cluster: same row, horizontally adjacent
    chars.sort()
    used = [False] * len(chars); clusters = []
    for i, c in enumerate(chars):
        if used[i]: continue
        grp = [c]; used[i] = True; changed = True
        while changed:
            changed = False
            for j, d in enumerate(chars):
                if used[j]: continue
                for g in grp:
                    cy1, cy2 = g[1] + g[3] / 2, d[1] + d[3] / 2
                    gap = max(d[0] - (g[0] + g[2]), g[0] - (d[0] + d[2]))
                    if abs(cy1 - cy2) < 0.35 * max(g[3], d[3]) and gap < 0.7 * max(g[3], d[3]) and 0.6 < g[3] / d[3] < 1.6:
                        grp.append(d); used[j] = True; changed = True; break
        if len(grp) >= 2:
            x0 = min(g[0] for g in grp); y0 = min(g[1] for g in grp)
            x1 = max(g[0] + g[2] for g in grp); y1 = max(g[1] + g[3] for g in grp)
            clusters.append((x0, y0, x1, y1, len(grp)))
    clusters.sort(key=lambda c: (round(c[1] / 50), c[0]))
    print(f, len(clusters))
    for x0, y0, x1, y1, k in clusters:
        print(f'   n={k} ctr=({(x0+x1)/2/PPM-M:5.1f},{(y0+y1)/2/PPM-M:5.1f})  w={(x1-x0)/PPM:4.1f} h={(y1-y0)/PPM:4.1f}')
