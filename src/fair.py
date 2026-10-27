"""Fairness Stage 2: room-side epsilon frontier (additive; changes no solver code).

Stage 1 (model.solve_slots + model.assign_rooms) minimises totals. This stage
re-optimises ONLY rooms, trading total person-seconds against tail burdens:
minimise  total_ps + mu * tail_cost, sweeping mu over a grid. tail_cost is a
minimax-flavoured proxy for CVaR (worst-quintile sections up-weighted),
stated as an approximation: exact CVaR is non-additive over meetings, while
this Lagrangian is. The mu sweep IS the epsilon frontier in Lagrangian form;
J (metrics.objective) is reported per point as one diagnostic, not the argmin.

Tail reweighting is IRLS-style: round-0 rooms give per-person travel via
metrics.evaluate; sections touching tail persons get their legs up-weighted by
(1 + mu * share) for two more matching rounds, then a fairness-weighted
polish. Teachers count via solve.w_teacher_leg, same convention as legs().

Run: PYTHONPATH=src python -m fair [--mus 0,0.5,1,2,4] [--iters 15000]
"""

from __future__ import annotations

import argparse
import json
import math
import random
from collections import defaultdict
from pathlib import Path

from ortools.sat.python import cp_model

from config import ROOT, load as load_cfg
from model import home_rooms, leg_free, legs, person_seconds, tau
from world import World, build, need_area
from checker import check
from metrics import evaluate


def match(w: World, slot_of: dict, mult: dict, forbid_rooms: set | None = None) -> dict:
    """Per-slot min-cost room matching. mult[(g,s)] scales that meeting's cost
    (tail sections > 1). Mirrors model.assign_rooms matching + fairness weight."""
    from world import floor_affinity
    cfg = w.cfg
    S = w.sections
    forbid_rooms = forbid_rooms or set()
    homes = home_rooms(w)
    per_slot = defaultdict(list)
    for g, sl in slot_of.items():
        for s in sl:
            per_slot[s].append(g)
    room: dict = {}
    for s, gs in per_slot.items():
        m = cp_model.CpModel()
        x = {}
        for g in gs:
            sec = S[g]
            need = need_area(sec, cfg)
            for r in w.rooms.values():
                if r.kind == sec.kind and r.area >= need - 1e-9 and r.id not in forbid_rooms:
                    aff = floor_affinity(sec.grade, r.floor, sec.kind)
                    base = sum(c * (tau(w, homes[h], r.id) + aff) for h, c in sec.homerooms.items())
                    x[g, r.id] = (m.NewBoolVar(f"x{g}{r.id}"),
                                   int(base * mult.get((g, s), 1.0)))
        for g in gs:
            m.Add(sum(v for (gg, _), (v, _) in x.items() if gg == g) == 1)
        byr = defaultdict(list)
        for (g, r), (v, _) in x.items():
            byr[r].append(v)
        for r, vs in byr.items():
            m.Add(sum(vs) <= 1)
        m.Minimize(sum(c * v for (v, c) in x.values()))
        sv = cp_model.CpSolver()
        sv.parameters.max_time_in_seconds = 10
        sv.parameters.num_search_workers = 4
        st = sv.Solve(m)
        if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            raise RuntimeError(f"fair room matching infeasible at slot {s}")
        for (g, r), (v, _) in x.items():
            if sv.Value(v):
                room[(g, s)] = r
    return room


def tail_mult(w: World, slot_of: dict, room: dict, mu: float, frac: float = 0.2) -> dict:
    """Meeting -> cost multiplier from worst-quintile persons."""
    m = evaluate(w, slot_of, room)
    st = sorted(m["per_student"].items(), key=lambda kv: kv[1]["travel_s"], reverse=True)
    tail_sids = {sid for sid, _ in st[:max(1, int(len(st) * frac))]}
    tt = sorted(m["per_teacher"].items(), key=lambda kv: kv[1]["travel_s"], reverse=True)
    tail_tids = {tid for tid, _ in tt[:max(1, int(len(tt) * frac))]}
    mult = {}
    for g, sec in w.sections.items():
        share = sum(1 for sid in sec.students if sid in tail_sids) / max(1, len(sec.students))
        if sec.teacher in tail_tids:
            share = max(share, 1.0)
        if share > 0 and mu > 0:
            for s in slot_of[g]:
                mult[(g, s)] = 1.0 + mu * share
    return mult


def polish_fair(w: World, room: dict, slot_of: dict, mult: dict, iters: int, seed: int) -> dict:
    """Simulated-annealing room swaps with fairness-weighted legs (mirrors
    model.polish_rooms cost structure + meeting multipliers)."""
    rng = random.Random(seed)
    L = legs(w, slot_of)
    adj = defaultdict(list)
    for (a, b), c in L.items():
        adj[a].append((b, c))
        adj[b].append((a, c))
    meets = list(room)
    at_slot = defaultdict(list)
    for mt in meets:
        at_slot[mt[1]].append(mt)
    occupied = {(mt[1], r): mt for mt, r in room.items()}
    rooms_of_kind = defaultdict(list)
    for r in w.rooms.values():
        rooms_of_kind[r.kind].append(r)

    def cost_of(mt, r):
        g, s = mt
        total = 0.0
        for o, c in adj[mt]:
            go, so = o
            if leg_free(w, s, so):
                continue
            total += mult.get(mt, 1.0) * c * tau(w, r, room[o])
        return total

    temp0 = 30.0
    for it in range(iters):
        temp = temp0 * (1 - it / iters)
        mt = rng.choice(meets)
        g, s = mt
        sec = w.sections[g]
        need = need_area(sec, w.cfg)
        cands = [r for r in rooms_of_kind[sec.kind] if r.area >= need - 1e-9]
        r2 = rng.choice(cands).id
        r1 = room[mt]
        if r2 == r1:
            continue
        other = occupied.get((s, r2))
        if other is None:
            d = cost_of(mt, r2) - cost_of(mt, r1)
            if d < 0 or (temp > 0 and rng.random() < math.exp(-d / max(temp, 1e-9))):
                del occupied[(s, r1)]
                room[mt] = r2
                occupied[(s, r2)] = mt
        else:
            so = w.sections[other[0]]
            if so.kind != sec.kind or r1 not in {x.id for x in rooms_of_kind[so.kind]}:
                continue
            if w.rooms[r1].area < need_area(so, w.cfg) - 1e-9:
                continue
            old = cost_of(mt, r1) + cost_of(other, r2)
            room[mt], room[other] = r2, r1
            new = cost_of(mt, r2) + cost_of(other, r1)
            d = new - old
            if d < 0 or (temp > 0 and rng.random() < math.exp(-d / max(temp, 1e-9))):
                occupied[(s, r2)], occupied[(s, r1)] = mt, other
            else:
                room[mt], room[other] = r1, r2
    return room


def stage2_point(w: World, slot_of: dict, mu: float, seed: int, iters: int) -> tuple[dict, dict]:
    room = match(w, slot_of, {})
    for _ in range(2):
        mult = tail_mult(w, slot_of, room, mu)
        if mu <= 0:
            break
        room = match(w, slot_of, mult)
    room = polish_fair(w, room, slot_of, tail_mult(w, slot_of, room, mu) if mu > 0 else {}, iters, seed)
    m = evaluate(w, slot_of, room)
    c = check(w, slot_of, room)
    sched = [s["L"] - s["load_term"] for s in m["per_teacher"].values()]
    pt = {
        "mu": mu,
        "total_person_seconds": person_seconds(w, room, legs(w, slot_of)),
        "student_travel_mean": m["students"]["travel_s_mean"],
        "student_travel_cvar80": m["students"]["travel_s_cvar80"],
        "teacher_sched_mean": sum(sched) / len(sched),
        "teacher_travel_mean": m["teachers"]["travel_s_mean"],
        "J": objective_safe(m, w.cfg),
        "ok": c["ok"], "violations": c["violations"],
    }
    return room, pt


def objective_safe(m: dict, cfg: dict) -> float:
    from metrics import objective
    try:
        return objective(m, cfg)
    except Exception:
        return float("nan")


def main() -> None:
    ap = argparse.ArgumentParser(description="Fairness Stage-2 epsilon frontier (rooms only).")
    ap.add_argument("--solution", default=None,
                    help="optional finished timetable to re-room (must match the fresh world); "
                         "default re-solves Stage-1 slots so the frontier stands alone")
    ap.add_argument("--mus", default="0,0.5,1,2,4")
    ap.add_argument("--iters", type=int, default=15000)
    ap.add_argument("--time-limit", type=float, default=90.0,
                    help="Stage-1 slot solve limit (ignored with --solution)")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default=str(ROOT / "output/fair_frontier.json"))
    a = ap.parse_args()
    cfg = load_cfg()
    w = build(cfg)
    if a.solution:
        sol = json.loads(Path(a.solution).read_text(encoding="utf-8"))
        slot_of = {g: list(s) for g, s in sol["slot_of"].items()}
        missing = [g for g in w.sections if g not in slot_of]
        if missing:
            raise KeyError(f"solution lacks {len(missing)} fresh-world sections "
                           f"(e.g. {missing[0]}); drop --solution to re-solve slots")
    else:
        from model import solve_slots
        r = solve_slots(w, time_limit=a.time_limit)
        if not r["assignment"]:
            raise RuntimeError(f"Stage-1 slot solve failed: {r['status']}")
        slot_of = r["assignment"]
    pts = []
    for mu in [float(x) for x in a.mus.split(",")]:
        _, pt = stage2_point(w, slot_of, mu, a.seed, a.iters)
        pts.append(pt)
        print(f"mu={mu:<5} total_ps={pt['total_person_seconds']:9.1f} "
              f"stu_cvar={pt['student_travel_cvar80']:7.1f} tea_sched={pt['teacher_sched_mean']:6.2f} "
              f"ok={pt['ok']}", flush=True)
    Path(a.out).write_text(json.dumps({"mus": a.mus, "points": pts}, indent=1))
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
