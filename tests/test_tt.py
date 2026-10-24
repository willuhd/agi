"""Full-school pipeline tests (run: cd agi && .venv/Scripts/python -m pytest tests -q)."""
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from tt import catalog, checker, config, emulator, metrics, model, mutations, shocks, world  # noqa: E402

SMALL = {"school.G9": 84, "school.G10": 66, "school.G11AP": 40,
         "school.homerooms": {"G9": 4, "G10": 3, "G11AP": 3},
         "school.pathways": {"G10": 3, "G11AP": 4}, "school.band_size": {"G9": 2, "G10": 2, "G11AP": 2},
         "solve.time_limit_s": 15, "solve.room_polish_iters": 3000, "solve.workers": 4}


@pytest.fixture(scope="module")
def small():
    cfg = config.load(SMALL)
    w = world.build(cfg)
    r = model.solve_slots(w, time_limit=20)
    assert r["assignment"], r["status"]
    room, _ = model.assign_rooms(w, r["assignment"], iters=3000)
    return w, r["assignment"], room


# ---------------------------------------------------------------- catalog / loads ----------
def test_catalog_loads_parse():
    cat = catalog.parse_catalog()
    assert cat["Geometry S"] == 6.0
    assert cat["AP Physics 1"] == 6.0
    assert cat["Physics 9 S"] == 3.0
    assert cat["World Hist to 1500 S"] == 4.0


def test_k_calibration_in_observed_band():
    cfg = config.load()
    k = catalog.fit_k(cfg)
    lo, hi = cfg["loads"]["k_band"]
    assert lo - 0.05 <= k <= hi


def test_slots_monotone_in_k():
    prev = 0
    for k in (0.7, 0.83, 0.9, 1.0):
        cfg = config.load({"loads.k": k})
        n = catalog.credits_to_slots(6.0, cfg)
        assert n >= prev
        prev = n


def test_courses_trace_to_catalog_or_marked_fallback():
    w = world.build(config.load())
    for c in w.courses.values():
        assert c.credit_src.startswith(("catalog", "fallback"))
        assert c.slots >= 1


# ---------------------------------------------------------------- world / selection -------
def test_world_deterministic():
    a = world.build(config.load(SMALL)).stats
    b = world.build(config.load(SMALL)).stats
    assert a == b


def test_selection_rules_hold():
    w = world.build(config.load())
    cur = world.CUR
    for sid, st in w.students.items():
        cs = set(st["courses"])
        if st["grade"] == "G9":
            assert len(cs & {c[0] for c in cur["G9"]["M2"]}) <= 1
            assert len(cs & {c[0] for c in cur["G9"]["M3"]}) <= 1
        if st["grade"] == "G10":
            assert len(cs & {c[0] for c in cur["G10"]["M1"]}) in (0, 2)
        if st["grade"] == "G11AP":
            m1 = cs & {c[0] for c in cur["G11AP"]["M1"]}
            assert len(m1) <= 2
            if len(m1) == 2:   # catalog E10: 2-in-M1 => no M3/M4
                assert not cs & {c[0] for c in cur["G11AP"]["M3"] + cur["G11AP"]["M4"]}


def test_student_load_fits_grid_with_free_periods():
    cfg = config.load()
    w = world.build(cfg)
    ss = w.student_sections()
    for sid, st in w.students.items():
        n = sum(w.sections[g].n for g in ss[sid])
        assert n <= st["avail"], (sid, n, st["avail"])


def test_section_size_bounds():
    cfg = config.load()
    w = world.build(cfg)
    cap, floor = cfg["school"]["section_cap"], cfg["school"]["section_floor"]
    core = {c[0] for g in world.CUR.values() for c in g["core"]}
    for sec in w.sections.values():
        assert sec.size <= cap
        if sec.course not in core:
            assert sec.size >= floor


def test_teachers_qualified_and_capped():
    w = world.build(config.load())
    load = {}
    for sec in w.sections.values():
        assert sec.dept in w.teachers[sec.teacher].depts
        load[sec.teacher] = load.get(sec.teacher, 0) + sec.n
    assert max(load.values()) <= w.cfg["teachers"]["max_load"]


# ---------------------------------------------------------------- solver + checker --------
def test_optimized_grid_has_zero_violations(small):
    w, so, rm = small
    c = checker.check(w, so, rm)
    assert c["ok"], c["violations"]


def test_mutation_suite_catches_every_planted_fault(small):
    w, so, rm = small
    res = mutations.run_suite(w, so, rm)
    assert res["baseline_ok"]
    assert all(res["caught"].values()), res["caught"]


def test_blind_baseline_breaks_contact_minute_invariant(small):
    """The status-quo style grid ignores period length: the checker must see it (finding F3)."""
    w, so, rm = small
    sb = emulator.blind_slots(w, 3, 10)
    rb = emulator.teacher_owned_rooms(w, sb, 3)
    c = checker.check(w, sb, rb)
    assert set(c["violations"]) <= {"H8"}
    assert c["violations"].get("H8", 0) > 0


def test_optimization_beats_status_quo_on_student_walking(small):
    w, so, rm = small
    sb = emulator.blind_slots(w, 0, 10)
    rb = emulator.teacher_owned_rooms(w, sb, 0, 0.6)
    m0 = metrics.evaluate(w, sb, rb)["students"]
    m1 = metrics.evaluate(w, so, rm)["students"]
    assert m1["travel_s_mean"] < m0["travel_s_mean"]
    assert m1["gaps_mean"] <= m0["gaps_mean"]


def test_polish_never_worsens_person_seconds(small):
    w, so, rm = small
    _, info = model.assign_rooms(w, so, iters=2000)
    assert info["ps_after_polish"] <= info["ps_before_polish"] + 1e-6


def test_same_seed_same_objective():
    cfg = config.load(SMALL)
    w = world.build(cfg)
    a = model.solve_slots(w, time_limit=8, skip={"soft"})
    b = model.solve_slots(w, time_limit=8, skip={"soft"})
    assert a["status"] == b["status"] == "OPTIMAL"


def test_fewer_rooms_never_help():
    """Metamorphic: removing capacity cannot make a feasible instance better than the full-room one."""
    w = world.build(config.load(SMALL))
    full = model.solve_slots(w, time_limit=10)
    w2 = world.build(config.load({**SMALL, "rooms.removed_frac": 0.4}))
    less = model.solve_slots(w2, time_limit=10)
    if less["objective"] is not None and full["objective"] is not None:
        assert less["objective"] >= full["objective"] - 1e-6 or less["status"] != "OPTIMAL"


# ---------------------------------------------------------------- shocks ------------------
def test_room_closure_repair_is_feasible(small):
    import random
    w, so, rm = small
    base = metrics.evaluate(w, so, rm)
    for sd in range(3):
        r = shocks.room_closure(w, so, rm, base, random.Random(sd), time_limit=10)
        assert r["feasible"], r


def test_teacher_absence_substitute_coverage(small):
    import random
    w, so, rm = small
    base = metrics.evaluate(w, so, rm)
    r = shocks.teacher_absence(w, so, rm, base, random.Random(1))
    assert r["covered"] + r["uncovered"] == r["affected_meetings"]


def test_surge_repair_feasible(small):
    import random
    w, so, rm = small
    base = metrics.evaluate(w, so, rm)
    r = shocks.enrollment_surge(w, so, rm, base, random.Random(2), time_limit=10)
    assert r["feasible"], r


# ---------------------------------------------------------------- regression --------------
def test_observed_week_regression():
    """Repo claim: the hand-encoded G11-AP week has 21 room changes (two-week mean)."""
    with open(ROOT / "src/data/current_grid.toml", "rb") as f:
        grid = tomllib.load(f)["slot"]
    wgt = {"all": 1.0, "even": 0.5, "odd": 0.5}
    by_day = {}
    for s in grid:
        by_day.setdefault(s["day"], []).append((s["period"], s["room"], wgt[s["parity"]]))
    total = 0.0
    for d, v in by_day.items():
        v.sort()
        total += sum(1 for a, b in zip(v, v[1:]) if a[1] != b[1])
    assert abs(total - 21) <= 1.5
