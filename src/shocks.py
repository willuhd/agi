"""Shocks and minimal-change repair. Scenario probabilities live in SCENARIOS below:
  teacher_absence_1day (p .4) | room_closure_1week (p .3) | enrollment_surge_5pct (p .3)

Repair ladder (cheapest first): substitute teacher -> re-room affected meetings -> re-slot only the
affected sections (all else frozen, churn priced) . Every repaired grid goes back through checker.check.
"""
from __future__ import annotations

import copy
import random
from collections import defaultdict

from ortools.sat.python import cp_model

import checker, metrics, model
from world import World, need_area

SCENARIOS = [("teacher_absence_1day", 0.4), ("room_closure_1week", 0.3), ("enrollment_surge_5pct", 0.3)]


def _rematch(w: World, slot_of, room, affected: set, forbid_rooms: set):
    """Re-room only `affected` (section, slot) meetings around frozen others. Returns new room dict or None."""
    cfg = w.cfg
    new = dict(room)
    by_slot = defaultdict(list)
    for (g, s) in affected:
        by_slot[s].append(g)
    for s, gs in by_slot.items():
        used = {r for (g, ss), r in room.items() if ss == s and (g, ss) not in affected}
        m = cp_model.CpModel()
        x = {}
        for g in gs:
            sec = w.sections[g]
            need = need_area(sec, cfg)
            for r in w.rooms.values():
                if r.kind == sec.kind and r.area >= need - 1e-9 and r.id not in used and r.id not in forbid_rooms:
                    prev = room.get((g, s))
                    cost = 0 if prev == r.id else 1 + model.tau(w, prev, r.id) / 100 if prev else 1
                    x[g, r.id] = (m.NewBoolVar(f"{g}{r.id}"), int(cost * 100))
        for g in gs:
            m.Add(sum(v for (gg, _), (v, _) in x.items() if gg == g) == 1)
        byr = defaultdict(list)
        for (g, r), (v, _) in x.items():
            byr[r].append(v)
        for vs in byr.values():
            m.Add(sum(vs) <= 1)
        m.Minimize(sum(c * v for v, c in x.values()))
        sv = cp_model.CpSolver()
        sv.parameters.max_time_in_seconds = 5
        if sv.Solve(m) not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return None
        for (g, r), (v, _) in x.items():
            if sv.Value(v):
                new[(g, s)] = r
    return new


def _delta(w, base, so1, rm1, so0, rm0, extra=None):
    c = checker.check(w, so1, rm1)
    m1 = metrics.evaluate(w, so1, rm1)
    moved = sum(len(set(so1[g]) ^ set(so0[g])) // 2 if set(so1[g]) != set(so0[g]) else 0 for g in so0)
    rchg = sum(1 for k, r in rm1.items() if rm0.get(k) != r)
    out = {"feasible": c["ok"], "violations": c["violations"], "moved_meetings": moved,
           "room_changes": rchg,
           # unified repair energy (ported sched repair.solve_incremental):
           # rooms-changed + 10 x moved-meetings; uncovered periods priced
           # separately via lost_student_periods. Weights are convention, not TOML.
           "energy_total": rchg + 10 * moved,
           "delta_student_lost_min_mean": m1["students"]["lost_min_week_mean"] - base["students"]["lost_min_week_mean"],
           "delta_student_travel_s_mean": m1["students"]["travel_s_mean"] - base["students"]["travel_s_mean"]}
    out.update(extra or {})
    return out


def room_closure(w: World, slot_of, room, base_metrics, rng: random.Random, n_rooms=1, time_limit=20):
    cands = sorted({r for r in room.values() if w.rooms[r].kind in ("classroom", "lab")})
    closed = set(rng.sample(cands, n_rooms))
    aff = {k for k, r in room.items() if r in closed}
    w2 = copy.copy(w)
    w2.rooms = {k: v for k, v in w.rooms.items() if k not in closed}
    rm = _rematch(w2, slot_of, room, aff, closed)
    so = {g: list(s) for g, s in slot_of.items()}
    level = "re-room"
    if rm is None:   # some slot has no free room of that kind: re-slot only the affected sections
        free = {g for g, s in aff}
        r = model.solve_slots(w2, time_limit=time_limit, fixed={g: so[g] for g in so if g not in free},
                              prev={g: so[g] for g in free}, churn_w=40)
        if not r["assignment"]:
            return {"feasible": False, "level": "infeasible", "closed": sorted(closed)}
        so = r["assignment"]
        keep = {k: v for k, v in room.items() if k[0] not in free and v not in closed}
        moved_meets = {(g, s) for g in free for s in so[g]}
        rm = _rematch(w2, so, keep, moved_meets, closed)
        level = "re-slot"
        if rm is None:
            return {"feasible": False, "level": "infeasible", "closed": sorted(closed)}
    mv = [(g, sl, room[(g, sl)], rm[(g, sl)]) for (g, sl) in aff if (g, sl) in rm and rm[(g, sl)] != room[(g, sl)]]
    return _delta(w2, base_metrics, so, rm, slot_of, room, {"level": level, "closed": sorted(closed),
                                                             "affected_meetings": len(aff), "moves": mv})


def teacher_absence(w: World, slot_of, room, base_metrics, rng: random.Random):
    """Substitute-teacher repair (unified with sched repair.replacement_teachers:
    eligible = dept-qualified, non-busy, non-external-busy; least-loaded first).
    Reports the replacement map + unified energy (moved=0, rooms=0 here)."""
    tid = rng.choice(sorted({s.teacher for s in w.sections.values()}))
    day = rng.choice(sorted({s["day"] for s in w.slots}))
    meets = [(g, s) for g, sec in w.sections.items() if sec.teacher == tid for s in slot_of[g]
             if w.slots[s]["day"] == day]
    busy = defaultdict(set)
    load = defaultdict(int)
    for g, sec in w.sections.items():
        for s in slot_of[g]:
            busy[sec.teacher].add(s)
            load[sec.teacher] += 1
    covered = 0
    replacements: dict[str, str] = {}
    for g, s in meets:
        dept = w.sections[g].dept
        cands = [t for t in w.teachers.values() if t.id != tid and dept in t.depts
                 and s not in busy[t.id] and s not in t.external_busy]
        if cands:
            sub = min(cands, key=lambda t: load[t.id])
            busy[sub.id].add(s)
            load[sub.id] += 1
            replacements[f"{g}|{s}"] = sub.id
            covered += 1
    n = len(meets)
    return {"feasible": True, "level": "substitute", "teacher": tid, "day": day, "affected_meetings": n,
            "covered": covered, "uncovered": n - covered, "moved_meetings": 0, "room_changes": 0,
            "energy_total": 0,
            "replacements": replacements,
            "delta_student_lost_min_mean": 0.0, "delta_student_travel_s_mean": 0.0,
            "lost_student_periods": sum(w.sections[g].size for (g, s) in meets[covered:]) if covered < n else 0}


def enrollment_surge(w: World, slot_of, room, base_metrics, rng: random.Random, pct=0.05, time_limit=20):
    cfg = w.cfg
    w2 = copy.copy(w)
    w2.sections = {k: copy.copy(v) for k, v in w.sections.items()}
    extra = 0
    over = []
    for g, sec in w2.sections.items():
        add = int(round(sec.size * pct + rng.random() - 0.5))
        if add > 0:
            sec.students = list(sec.students) + [f"surge{g}{i}" for i in range(add)]
            extra += add
            over.append(g)
    # sections over the planning cap need a bigger room (and eventually a split, reported)
    cap = cfg["school"]["section_cap"]
    split_needed = [g for g in over if w2.sections[g].size > cap]
    bad = {(g, s) for g in over for s in slot_of[g]
           if w.rooms[room[(g, s)]].area < need_area(w2.sections[g], cfg) - 1e-9}
    # student-level checks use real students only; dummy ids have no other sections
    w2.student_sections = w.student_sections   # unchanged for real students
    rm = _rematch(w2, slot_of, room, bad, set()) if bad else dict(room)
    so = {g: list(s) for g, s in slot_of.items()}
    level = "re-room"
    if rm is None:
        free = {g for g, s in bad}
        r = model.solve_slots(w2, time_limit=time_limit, fixed={g: so[g] for g in so if g not in free},
                              prev={g: so[g] for g in free}, churn_w=40)
        if not r["assignment"]:
            return {"feasible": False, "level": "infeasible", "extra_seats": extra}
        so = r["assignment"]
        keep = {k: v for k, v in room.items() if k[0] not in free}
        rm = _rematch(w2, so, keep, {(g, s) for g in free for s in so[g]}, set())
        level = "re-slot"
        if rm is None:
            return {"feasible": False, "level": "infeasible", "extra_seats": extra}
    out = _delta(w2, base_metrics, so, rm, slot_of, room,
                 {"level": level if bad else "none-needed", "extra_seats": extra,
                  "rooms_outgrown": len(bad), "sections_over_cap": len(split_needed)})
    return out


def run_scenarios(w: World, slot_of, room, n_draws=10, seed=0):
    base = metrics.evaluate(w, slot_of, room)
    rng = random.Random(seed)
    res = {k: [] for k, _ in SCENARIOS}
    for i in range(n_draws):
        res["teacher_absence_1day"].append(teacher_absence(w, slot_of, room, base, rng))
        res["room_closure_1week"].append(room_closure(w, slot_of, room, base, rng))
        res["enrollment_surge_5pct"].append(enrollment_surge(w, slot_of, room, base, rng))
    return res


def expected_delta(res: dict) -> dict:
    """E_xi[Delta]: probability-weighted mean of moved meetings / room changes / uncovered periods."""
    out = {"moved_meetings": 0.0, "room_changes": 0.0, "uncovered_student_periods": 0.0, "infeasible_rate": 0.0}
    for name, p in SCENARIOS:
        L = res[name]
        n = len(L)
        out["moved_meetings"] += p * sum(x.get("moved_meetings", 0) for x in L) / n
        out["room_changes"] += p * sum(x.get("room_changes", 0) for x in L) / n
        out["uncovered_student_periods"] += p * sum(x.get("lost_student_periods", 0) for x in L) / n
        out["infeasible_rate"] += p * sum(0 if x.get("feasible") else 1 for x in L) / n
    return out
