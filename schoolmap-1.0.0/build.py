"""Rebuild the whole model from the floor-plan photos:   python build.py  [--debug]

schoolmap/data/building_spec.yaml + floor_plans/*.jpg  ->
    output/
        building_model.json      complete space model (geometry, rooms, stairs, walking legs)
        travel_time_s.csv/.json  room x room travel time matrix (seconds)
        routes.csv               every ordered pair: time, walk metres, stair time, floors, stairs used
        rooms.csv                room catalogue (floor, kind, centre, doors, area)
        stairs.csv               stair register (shape, floors served, landings)
        renders/                 plan_<floor>.png/.svg, plans_overview.png, example route sheets
        viewer.html              interactive 3-D model with real stairs and live routing
    schoolmap/data/              the same model + viewer bundled inside the package
Needs the [build] extras: numpy, scipy, opencv-python, matplotlib, pyyaml.
"""
import argparse
import csv
import shutil
import time
from pathlib import Path

import numpy as np

from schoolmap import Building
from schoolmap.export import export_tables
from schoolmap.pipeline import build
from schoolmap.render2d import render_all, render_route
from schoolmap.render3d import write_viewer

HERE = Path(__file__).parent
PKG_DATA = HERE / "schoolmap" / "data"
EXAMPLES = [("405", "B208"), ("109", "104"), ("101", "B216"), ("B110", "410"), ("320", "201")]


def export_stairs(model, path):
    order = [f["id"] for f in sorted(model["floors"], key=lambda f: f["level"])]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "name", "type", "shape", "floors", "plan_x0", "plan_y0", "plan_x1", "plan_y1", "landings", "story"])
        for c in model["connectors"]:
            fl = [f for f in order if f in c["floors"]]
            w.writerow([c["id"], c["name"], c["type"], c["shape"], f"{fl[0]}-{fl[-1]}", *c["plan"],
                        "; ".join(f"{f}:{c['floors'][f]['landing'][0]},{c['floors'][f]['landing'][1]}" for f in fl),
                        c.get("story", "")])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", default=PKG_DATA / "building_spec.yaml")
    ap.add_argument("--plans", default=HERE / "floor_plans", help="folder with the floor-plan photos")
    ap.add_argument("--out", default=HERE / "output")
    ap.add_argument("--debug", action="store_true", help="also write raster debug images to output/debug")
    a = ap.parse_args()
    t0 = time.time()
    out = Path(a.out)
    model = build(a.spec, out, debug_dir=out / "debug" if a.debug else None, plans_dir=a.plans,
                  log=lambda *m: print(*m) if (m and (m[0].startswith("[") or "!!" in m[0])) else None)
    b = Building(model)
    ids, T = export_tables(b, out)
    export_stairs(model, out / "stairs.csv")
    render_all(model, out / "renders")
    for x, y in EXAMPLES:
        render_route(b, x, y, out / "renders" / f"route_{x}_to_{y}.png")
    write_viewer(model, out / "viewer.html")
    # bundle into the package so `import schoolmap` works without rebuilding
    shutil.copy(out / "building_model.json", PKG_DATA / "building_model.json")
    shutil.copy(out / "viewer.html", PKG_DATA / "viewer.html")
    off = T[~np.eye(len(ids), dtype=bool)]
    print(f"\n{len(ids)} rooms | travel time min {off.min():.0f} s, median {np.median(off):.0f} s, "
          f"max {off.max():.0f} s | done in {time.time() - t0:.0f} s -> {out.resolve()}")


if __name__ == "__main__":
    main()
