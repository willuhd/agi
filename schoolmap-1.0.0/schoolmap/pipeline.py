"""Build the building model from building_spec.yaml + the floor-plan photos."""
from __future__ import annotations

import json
import time
from pathlib import Path

import cv2
import numpy as np
import yaml

from . import calibrate
from .extract import Frame, downsample_any, extract_walls, fill_poly, rect_poly
from .rooms import DEFAULT_MAX_AREA, anchor_cell, extract_room, region_polygon
from .routing import FloorGraph
from .stairs import build_flights
from .vectorize import rasterize_walls, vectorize_walls, wall_quad

FINE_PPM = 25.0     # px / m for rectified photos (4 cm)
MARGIN = 1.0        # m of margin around the envelope in all rasters


def load_spec(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _r2(v, nd=2):
    return [round(float(x), nd) for x in v]


def wall_polygons(mask: np.ndarray, frame: Frame, min_area_m2=0.01):
    """Vectorise a binary wall raster into polygons (outer ring + holes), metres."""
    cnts, hier = cv2.findContours(mask.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    polys = []
    if hier is None:
        return polys
    hier = hier[0]
    for i, c in enumerate(cnts):
        if hier[i][3] != -1:
            continue                                  # holes are attached to their parent
        if cv2.contourArea(c) / frame.ppm ** 2 < min_area_m2:
            continue
        outer = cv2.approxPolyDP(c, 0.9, True)[:, 0, :]
        holes = []
        j = hier[i][2]
        while j != -1:
            h = cnts[j]
            if cv2.contourArea(h) / frame.ppm ** 2 >= min_area_m2:
                holes.append(cv2.approxPolyDP(h, 0.9, True)[:, 0, :])
            j = hier[j][0]
        polys.append({"outer": [_r2(p) for p in frame.to_m(outer)],
                      "holes": [[_r2(p) for p in frame.to_m(h)] for h in holes]})
    return polys


def build(spec_path: str | Path, out_dir: str | Path, debug_dir: str | Path | None = None, log=print,
          plans_dir: str | Path | None = None):
    t0 = time.time()
    spec_path = Path(spec_path).resolve()
    # floor-plan photos: <project>/floor_plans unless given explicitly
    plans = Path(plans_dir) if plans_dir else Path(__file__).resolve().parents[1] / "floor_plans"
    spec = load_spec(spec_path)
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    if debug_dir:
        debug_dir = Path(debug_dir); debug_dir.mkdir(parents=True, exist_ok=True)

    W, H = calibrate.envelope_size(spec["meta"])
    rcfg = spec["routing"]
    gm = float(rcfg["grid_m"])
    fine = Frame(FINE_PPM, MARGIN, (int(round((H + 2 * MARGIN) * FINE_PPM)), int(round((W + 2 * MARGIN) * FINE_PPM))))
    grid = Frame(1.0 / gm, MARGIN, (int(round((H + 2 * MARGIN) / gm)), int(round((W + 2 * MARGIN) / gm))))
    speed = float(spec["timing"]["walk_speed_mps"])

    model = {
        "meta": {**spec["meta"], "envelope_m": [round(W, 3), H], "built": time.strftime("%Y-%m-%d %H:%M:%S"),
                 "coordinate_frame": "metres; origin = NW envelope corner; x east, y south"},
        "timing": spec["timing"], "routing": rcfg,
        "floors": [], "connectors": [], "legs": {}, "calibration": {},
    }
    floor_ids = [f["id"] for f in spec["floors"]]
    conns = spec["connectors"]

    for fl in spec["floors"]:
        fid = fl["id"]
        img = cv2.imread(str(plans / fl["image"]))
        if img is None:
            raise FileNotFoundError(plans / fl["image"])
        cal = calibrate.envelope_corners(img, spec["calibration"][fid])
        Hm = calibrate.homography(cal["corners"], W, H)
        aspect = calibrate.metric_aspect(cal["corners"], img.shape)
        model["calibration"][fid] = {
            "corners_px": {k: _r2(v, 2) for k, v in cal["corners"].items()},
            "line_rms_px": {k: round(v, 3) for k, v in cal["rms_px"].items()},
            "self_calibrated_aspect": None if aspect is None else round(aspect, 4),
            "homography_px_to_m": [_r2(r, 9) for r in Hm],
        }
        seeds = [r["seed"] for r in fl["rooms"]]
        # pass 1: envelope rectification -> measure interior wall runs -> squareness fix
        rect0 = calibrate.rectify(img, Hm, W, H, FINE_PPM, MARGIN)
        runs = calibrate.wall_runs(extract_walls(rect0, fine, seeds).walls, FINE_PPM, MARGIN)
        warp = calibrate.StraighteningWarp.fit(runs, W, H)
        grid_pts = np.array([[x, y] for x in np.linspace(0, W, 41) for y in np.linspace(0, H, 51)])
        disp = np.linalg.norm(warp.apply(grid_pts) - grid_pts, axis=1)
        model["calibration"][fid]["straightening_warp"] = {**warp.to_dict(), "max_shift_m": round(float(disp.max()), 3),
                                                          "mean_shift_m": round(float(disp.mean()), 3)}
        model["calibration"][fid]["tilt_before_deg"] = _tilt_stats(calibrate.run_tilts(runs), runs)
        # pass 2: final rectification (homography + straightening warp)
        rect = calibrate.rectify(img, Hm, W, H, FINE_PPM, MARGIN, warp)
        fr = extract_walls(rect, fine, seeds)
        for box in fl.get("erase", []):
            er = np.zeros(fine.shape, np.uint8)
            fill_poly(er, fine, rect_poly(box))
            fr.walls[er > 0] = 0
        runs2 = calibrate.wall_runs(fr.walls, FINE_PPM, MARGIN)
        model["calibration"][fid]["tilt_after_deg"] = _tilt_stats(calibrate.run_tilts(runs2), runs2)

        # ---------------- obstacles (fine) ----------------
        inside = np.zeros(fine.shape, np.uint8)
        fill_poly(inside, fine, fl["footprint"])
        blocked = np.zeros(fine.shape, np.uint8)
        for b in fl.get("blocked", []):
            fill_poly(blocked, fine, b["poly"])
        fp_mask = np.zeros(fine.shape, np.uint8)
        fl_conns = []
        for c in conns:
            if fid in c["floors"]:
                fill_poly(fp_mask, fine, rect_poly(_block(c, fid)))
                fl_conns.append(c)
        # ---------------- vector walls (straight, orthogonal, snapped) ----------------
        # stairs / lifts are modelled as connectors: erase their drawn treads first
        raw = fr.walls.copy()
        for c in fl_conns:
            x0, y0, x1, y1 = _block(c, fid)
            er = np.zeros(fine.shape, np.uint8)
            fill_poly(er, fine, rect_poly([x0 + .12, y0 + .12, x1 - .12, y1 - .12]))
            raw[er > 0] = 0
        vwalls = vectorize_walls(raw, FINE_PPM, MARGIN)
        fp_poly = np.array(fl["footprint"], np.float32)
        keep = []
        for w in vwalls:
            mid = ((w["a"][0] + w["b"][0]) / 2, (w["a"][1] + w["b"][1]) / 2)
            if cv2.pointPolygonTest(fp_poly, mid, True) < -0.4:
                continue                                # drawn outside the building (exterior stairs)
            if any(cv2.pointPolygonTest(np.array(b["poly"], np.float32), mid, True) > 0.25 for b in fl.get("blocked", [])):
                continue                                # drawing inside a void (e.g. stair seen below)
            if any(_tread(w, _block(c, fid)) for c in fl_conns):
                continue                                # stair treads / lift car drawings
            w["poly"] = wall_quad(w)
            keep.append(w)
        vwalls = keep
        wall_r = rasterize_walls(vwalls, fine.shape, FINE_PPM, MARGIN)
        obst = (wall_r | blocked | fp_mask | (1 - inside)).astype(np.uint8)
        free = 1 - downsample_any(obst, fine, grid, frac=0.15)
        fg = FloorGraph(free, gm, float(rcfg["comfort_clearance_m"]), float(rcfg["min_clearance_m"]), float(rcfg["wall_penalty"]))
        dist = fg.clear

        # ---------------- rooms ----------------
        to_rc = lambda xy: tuple(np.round(grid.to_px(xy)[::-1]).astype(int))
        landing_rc = [to_rc(c["floors"][fid]["landing"]) for c in fl_conns]
        seed_rc = {r["id"]: to_rc(r["seed"]) for r in fl["rooms"]}
        rooms_out, room_masks = [], {}
        for r in fl["rooms"]:
            rid = r["id"]
            if "region" in r:
                m = np.zeros(grid.shape, np.uint8)
                fill_poly(m, grid, r["region"])
                mask = (m > 0) & (free > 0)
                core = mask & (dist > 0.6)
                poly_m = [_r2(p) for p in r["region"]]
                Rr = None
            else:
                others = [v for k, v in seed_rc.items() if k != rid] + landing_rc
                res = extract_room(free, dist, gm, seed_rc[rid], others, float(r.get("max_area", DEFAULT_MAX_AREA)))
                if res is None:
                    log(f"  !! {fid} {rid}: room extraction failed; using 1.5 m disc at seed")
                    m = np.zeros(grid.shape, np.uint8)
                    cv2.circle(m, seed_rc[rid][::-1], int(1.5 / gm), 1, -1)
                    mask = (m > 0) & (free > 0); core = mask & (dist > 0.3); Rr = None
                    poly_cells = cv2.approxPolyDP(cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)[0][0], 1.5, True)[:, 0, :]
                else:
                    mask, core, Rr = res["mask"], res["core"], res["radius"]
                    poly_cells = region_polygon(core, mask, Rr / gm)
                poly_m = [_r2(p) for p in grid.to_m(poly_cells)]
            # the room's routing/render footprint is exactly its outline polygon
            pm = np.zeros(grid.shape, np.uint8)
            fill_poly(pm, grid, poly_m)
            if "region" not in r and pm.sum() * gm * gm > float(r.get("max_area", DEFAULT_MAX_AREA)):
                # outline leaked into circulation space -> fall back to the core's rectangle
                log(f"  !! {fid} {rid}: outline leaked, using core rectangle")
                ys_, xs_ = np.nonzero(core)
                Rp = (Rr or 0.6) / gm
                poly_cells = np.array([[xs_.min() - Rp, ys_.min() - Rp], [xs_.max() + Rp, ys_.min() - Rp],
                                       [xs_.max() + Rp, ys_.max() + Rp], [xs_.min() - Rp, ys_.max() + Rp]])
                poly_m = [_r2(p) for p in grid.to_m(poly_cells)]
                pm[:] = 0
                fill_poly(pm, grid, poly_m)
            mask = (pm > 0) & fg.ok
            arc = anchor_cell(core if core.any() else mask)
            if not mask[arc]:
                arc = fg.snap(arc, prefer_comfort=True)
            room_masks[rid] = mask
            area = float(mask.sum() * gm * gm)
            rooms_out.append({
                "id": rid, "name": r.get("name", rid), "kind": r.get("kind", "room"),
                "polygon": poly_m, "area_m2": round(area, 1),
                "anchor": _r2(grid.to_m([arc[1], arc[0]])), "_anchor_rc": arc,
                "door_close_radius_m": Rr, "passable": bool(r.get("passable", False)),
            })
            log(f"  {fid} {rid:>9}: area {area:6.1f} m2  R={Rr}")

        # ---------------- routing nodes & legs ----------------
        # Pedestrians never cut through other rooms: each node gets its own search on
        # corridor space + its own room only; room-to-room legs meet at the destination's
        # door "portal" cells.
        any_room = np.zeros(grid.shape, bool)
        passable = {r["id"] for r in fl["rooms"] if r.get("passable")}
        for rid_, m_ in room_masks.items():
            if rid_ not in passable:
                any_room |= m_
        corridor = fg.ok & ~any_room
        nodes = [("R:" + ro["id"], ro["_anchor_rc"], room_masks[ro["id"]]) for ro in rooms_out]
        for c in fl_conns:
            lrc = fg.snap_in(to_rc(c["floors"][fid]["landing"]), corridor)
            if lrc is None:
                raise RuntimeError(f"{fid}: landing of {c['id']} not routable")
            nodes.append((f"C:{c['id']}@{fid}", lrc, None))
        fields = [fg.field(rc, corridor | m_ if m_ is not None else corridor) for _, rc, m_ in nodes]
        portals = {}
        for name, rc, m_ in nodes:
            if m_ is not None:
                ring = cv2.dilate(m_.astype(np.uint8), np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], np.uint8)) > 0
                portals[name] = fg.idx[ring & corridor]
        legs = {}
        for i, (ni, rci, mi) in enumerate(nodes):
            for j in range(i + 1, len(nodes)):
                nj, rcj, mj = nodes[j]
                Fi, Fj = fields[i], fields[j]
                if mj is not None:
                    P = portals[nj]
                    tot = Fi.dist_at(P) + Fj.dist_at(P)
                elif mi is not None:
                    P = portals[ni]
                    tot = Fi.dist_at(P) + Fj.dist_at(P)
                else:
                    P = np.array([fg.node(rcj)])
                    tot = Fi.dist_at(P)
                k = int(np.argmin(tot)) if len(tot) else 0
                if not len(tot) or not np.isfinite(tot[k]):
                    log(f"  !! {fid}: {ni} -> {nj} unreachable")
                    continue
                meet = int(P[k])
                ci = Fi.path_to(meet)
                cj = Fj.path_to(meet) if (mj is not None or mi is not None) else np.zeros((0, 2), int)
                cells = np.concatenate([ci, cj[::-1][1:]]) if len(cj) else ci
                allowed = corridor | (mi if mi is not None else False) | (mj if mj is not None else False)
                sm = fg.smooth(cells, allowed)
                L = float(np.sum(np.hypot(*np.diff(sm, axis=0).T))) * gm
                pts = grid.to_m(sm[:, ::-1])
                legs[f"{ni}|{nj}"] = {"m": round(L, 2), "path": [_r2(p) for p in pts]}
        nodes = [(n, rc) for n, rc, _ in nodes]
        # doors: where each room's routes leave the room region
        for ro in rooms_out:
            exits = []
            mask = room_masks[ro["id"]]
            for k, lg in legs.items():
                a, b = k.split("|")
                if "R:" + ro["id"] not in (a, b):
                    continue
                pts = np.array(lg["path"]) if a == "R:" + ro["id"] else np.array(lg["path"])[::-1]
                if len(pts) < 2:
                    continue
                dense = np.concatenate([np.linspace(pts[q], pts[q + 1], max(2, int(np.hypot(*(pts[q + 1] - pts[q])) / gm) + 1)) for q in range(len(pts) - 1)])
                rc = np.round(grid.to_px(dense)[:, ::-1]).astype(int)
                inside_m = mask[rc[:, 0], rc[:, 1]]
                out_i = np.nonzero(~inside_m)[0]
                if len(out_i):
                    exits.append(dense[max(out_i[0] - 1, 0)])
            doors = []
            for e in exits:
                if all(np.hypot(*(e - d)) > 1.5 for d in doors):
                    doors.append(e)
            ro["doors"] = [_r2(d) for d in doors]
            del ro["_anchor_rc"]
        model["legs"][fid] = legs

        # ---------------- geometry for rendering ----------------
        model["floors"].append({
            "id": fid, "level": fl["level"], "elevation_m": fl["level"] * float(spec["meta"]["floor_to_floor_m"]),
            "footprint": fl["footprint"], "blocked": fl.get("blocked", []),
            "walls": vwalls,
            "rooms": rooms_out,
        })
        if debug_dir:
            _debug_images(debug_dir, fid, rect, fr, free, grid, rooms_out, room_masks, nodes, legs)
        log(f"[{fid}] {len(rooms_out)} rooms, {len(nodes)} nodes, {len(legs)} legs   ({time.time() - t0:.1f}s)")

    storey = float(spec["meta"]["floor_to_floor_m"])
    for c in conns:
        model["connectors"].append({
            "id": c["id"], "name": c["name"], "story": c.get("story", ""), "type": c["type"],
            "shape": c.get("shape", "dogleg"), "plan": c["plan"], "enabled": c.get("enabled", True),
            "floors": {f: {"landing": c["floors"][f]["landing"], "footprint": _block(c, f)}
                       for f in floor_ids if f in c["floors"]},
            "flights": build_flights(c, floor_ids, storey),
        })
    with open(out_dir / "building_model.json", "w", encoding="utf-8") as f:
        json.dump(model, f, separators=(",", ":"))
    log(f"model written ({time.time() - t0:.1f}s)")
    return model


def _tilt_stats(t, runs):
    """Length-weighted wall-angle statistics (deg) for horizontal and vertical runs."""
    w = np.array([r[2] for r in runs]); ax = np.array([r[3] for r in runs])
    out = {"wall_runs": int(len(t))}
    for name, sel in (("horizontal", ax == 0), ("vertical", ax == 1), ("all", ax >= 0)):
        tt, ww = t[sel], w[sel]
        out[name] = {"mean": round(float(np.average(tt, weights=ww)), 3),
                     "median_abs": round(float(np.median(np.abs(tt))), 3)}
    return out


def _block(c, fid):
    """Walking obstacle of a connector on one floor (its shaft unless overridden)."""
    return c["floors"][fid].get("block", c["plan"])


def _tread(w, r):
    """Wall lies inside a stair/lift footprint and is not one of its boundary walls."""
    x0, y0, x1, y1 = r
    pts = (w["a"], w["b"])
    L = float(np.hypot(w["b"][0] - w["a"][0], w["b"][1] - w["a"][1]))
    mid = ((w["a"][0] + w["b"][0]) / 2, (w["a"][1] + w["b"][1]) / 2)
    if L < 1.2 and x0 - .8 <= mid[0] <= x1 + .8 and y0 - .8 <= mid[1] <= y1 + .8:
        return True                                 # tread ends sticking out of the stair
    if not all(x0 - .1 <= p[0] <= x1 + .1 and y0 - .1 <= p[1] <= y1 + .1 for p in pts):
        return False
    a, b = w["a"], w["b"]
    on_edge = (abs(a[0] - b[0]) < 1e-6 and min(abs(a[0] - x0), abs(a[0] - x1)) < 0.2) or               (abs(a[1] - b[1]) < 1e-6 and min(abs(a[1] - y0), abs(a[1] - y1)) < 0.2)
    return not on_edge


def _inside_rect(p, r, shrink):
    return r[0] + shrink <= p[0] <= r[2] - shrink and r[1] + shrink <= p[1] <= r[3] - shrink


def inside_dilated(inside: np.ndarray, frame: Frame, pad_m: float = 0.35):
    k = int(pad_m * frame.ppm) * 2 + 1
    return cv2.dilate(inside, np.ones((k, k), np.uint8))


def _debug_images(debug_dir, fid, rect, fr, free, grid, rooms_out, room_masks, nodes, legs):
    vis = cv2.cvtColor((free * 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
    vis[free == 0] = (60, 60, 60)
    rng = np.random.default_rng(7)
    for ro in rooms_out:
        col = rng.integers(80, 230, 3)
        vis[room_masks[ro["id"]]] = (0.5 * vis[room_masks[ro["id"]]] + 0.5 * col).astype(np.uint8)
    vis = cv2.resize(vis, None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST)
    for lg in legs.values():
        p = (grid.to_px(np.array(lg["path"])) * 3 + 1).astype(np.int32)
        cv2.polylines(vis, [p], False, (40, 120, 255), 1, cv2.LINE_AA)
    for ro in rooms_out:
        a = (grid.to_px(ro["anchor"]) * 3 + 1).astype(int)
        cv2.circle(vis, tuple(a), 5, (0, 0, 200), -1)
        cv2.putText(vis, ro["id"], (a[0] + 6, a[1] - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 120), 1, cv2.LINE_AA)
        for d in ro["doors"]:
            q = (grid.to_px(d) * 3 + 1).astype(int)
            cv2.drawMarker(vis, tuple(q), (0, 150, 0), cv2.MARKER_DIAMOND, 10, 2)
    for name, rc in nodes:
        if name.startswith("C:"):
            cv2.drawMarker(vis, (rc[1] * 3 + 1, rc[0] * 3 + 1), (200, 0, 200), cv2.MARKER_TILTED_CROSS, 14, 2)
            cv2.putText(vis, name[2:].split("@")[0], (rc[1] * 3 + 8, rc[0] * 3 + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 0, 150), 1)
    cv2.imwrite(str(debug_dir / f"route_{fid}.png"), vis)
    cv2.imwrite(str(debug_dir / f"walls_raw_{fid}.png"), 255 - fr.walls * 255)
