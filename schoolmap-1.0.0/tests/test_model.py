"""Consistency checks for the built model:  python -m pytest tests  (or python tests/test_model.py)."""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from schoolmap import Building  # noqa: E402

MODEL = ROOT / "schoolmap" / "data" / "building_model.json"


def _b(**kw):
    return Building.load(MODEL, **kw)


def test_all_rooms_reachable():
    ids, T = _b().matrix()
    assert len(ids) == 103
    assert np.isfinite(T).all()


def test_asymmetry_only_from_stairs():
    """T[a,b] - T[b,a] can only come from up (15 s) vs down (10 s) stair time."""
    b = _b()
    ids, T = b.matrix()
    lv = np.array([b.level[b.rooms[i]["floor"]] for i in ids])
    max_diff = 5.0 * np.abs(lv[:, None] - lv[None, :])
    assert (np.abs(T - T.T) <= max_diff + 1e-6).all()


def test_triangle_inequality():
    """Routes never cut through other rooms, so a detour 'via' room k can only be shorter
    than the direct route when k has two or more doors (a shortcut people may not take)."""
    b = _b()
    ids, T = b.matrix()
    for k, rk in enumerate(ids):
        viol = T > T[:, [k]] + T[[k], :] + 1e-6
        if viol.any():
            assert len(b.rooms[rk]["doors"]) >= 2 or b.rooms[rk].get("passable"), rk


def test_same_floor_is_pure_walking():
    b = _b()
    r = b.route("215", "204")
    assert r.vertical_s == 0 and r.floors_up == r.floors_down == 0
    assert abs(r.seconds - r.walk_m / b.speed) < 1e-6


def test_stair_time_rule():
    b = _b()
    up, down = b.route("109", "409"), b.route("409", "109")
    assert up.floors_up == 3 and abs(up.vertical_s - 45.0) < 1e-9
    assert down.floors_down == 3 and abs(down.vertical_s - 30.0) < 1e-9


def test_speed_scaling():
    a, b = _b(walk_speed=1.2), _b(walk_speed=1.4)
    ra, rb = a.route("101", "320"), b.route("101", "320")
    assert rb.seconds < ra.seconds


def test_deterministic():
    m1 = json.loads(MODEL.read_text())
    ids1, T1 = Building(m1).matrix()
    ids2, T2 = Building(json.loads(MODEL.read_text())).matrix()
    assert ids1 == ids2 and np.array_equal(T1, T2)


def test_walls_orthogonal():
    m = json.loads(MODEL.read_text())
    for f in m["floors"]:
        for w in f["walls"]:
            if w["kind"] == "diag":
                continue
            assert w["a"][0] == w["b"][0] or w["a"][1] == w["b"][1], (f["id"], w)


if __name__ == "__main__":
    fails = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn(); print("PASS", name)
            except AssertionError as e:
                fails += 1; print("FAIL", name, e)
    sys.exit(1 if fails else 0)
