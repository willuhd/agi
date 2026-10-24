"""Tabular exports for the scheduling model."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

from .model import Building


def export_tables(b: Building, out_dir: str | Path):
    out = Path(out_dir)
    ids, T = b.matrix()
    with open(out / "travel_time_s.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["from\\to"] + ids)
        for i, a in enumerate(ids):
            w.writerow([a] + [f"{v:.1f}" for v in T[i]])
    rows = []
    for a in ids:
        for c in ids:
            if a == c:
                continue
            r = b.route(a, c)
            rows.append({
                "from": a, "to": c, "from_floor": b.rooms[a]["floor"], "to_floor": b.rooms[c]["floor"],
                "seconds": round(r.seconds, 1), "walk_m": round(r.walk_m, 1), "walk_s": round(r.walk_s, 1),
                "stairs_s": round(r.vertical_s, 1), "floors_up": r.floors_up, "floors_down": r.floors_down,
                "via": " ".join(dict.fromkeys(l.via for l in r.legs if l.kind != "walk")),
            })
    with open(out / "routes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    with open(out / "rooms.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "name", "kind", "floor", "level", "anchor_x_m", "anchor_y_m", "area_m2", "doors"])
        for rid in ids:
            r = b.rooms[rid]
            w.writerow([rid, r["name"], r["kind"], r["floor"], b.level[r["floor"]], r["anchor"][0], r["anchor"][1],
                        r["area_m2"], ";".join(f"{d[0]},{d[1]}" for d in r["doors"])])
    with open(out / "travel_time_s.json", "w", encoding="utf-8") as f:
        json.dump({"rooms": ids, "seconds": np.round(T, 1).tolist(),
                   "walk_speed_mps": b.speed, "stair_up_s": b.up_s, "stair_down_s": b.down_s}, f)
    return ids, T
