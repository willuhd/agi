"""Current-system emulator: how the timetable is built today, calibrated to the observed week.

Observed (apschedule.png / current_grid.toml): every teacher keeps THEIR OWN room (He=114, Haig=103,
Balli=108, Zhang=106...), students walk to the teacher; slots are filled teacher-first with no objective
on student walking, gaps, or period length. Two independent policies, emulated separately so the effect
of each can be isolated (2x2 ablation in the report):

  slot policy  = "blind":  any clash-free grid (CP-SAT with a RANDOM objective, minute band ignored)
  room policy  = "owned":  each teacher teaches in one base room per room kind; a share (1-p_own) of
                           meetings lands in an arbitrary free room (cover / overflow)

Hand greedy placement cannot even find a clash-free grid at this load (it dead-ends: see tests), which is
itself a finding; the blind-CP-SAT stand-in is therefore *generous* to the current system.
"""
from __future__ import annotations

import copy
import random
from collections import defaultdict

from . import model
from .config import clone
from .world import World, need_area


def blind_slots(w: World, seed: int = 0, time_limit: float = 20.0) -> dict:
    w2 = copy.copy(w)
    w2.cfg = clone(w.cfg, {"solve.minutes_tol": 9.0, "solve.minutes_floor": 1e6})
    r = model.solve_slots(w2, time_limit=time_limit, skip={"soft"}, random_obj_seed=seed + 101)
    if not r["assignment"]:
        raise RuntimeError(f"blind slot solve failed: {r['status']}")
    return r["assignment"]


def teacher_owned_rooms(w: World, slot_of: dict, seed: int = 0, p_own: float = 1.0) -> dict:
    rng = random.Random(seed)
    S = w.sections
    cfg = w.cfg
    by_kind = defaultdict(list)
    for r in w.rooms.values():
        by_kind[r.kind].append(r)
    for v in by_kind.values():
        rng.shuffle(v)
    taken, base = set(), {}
    for tid in sorted(w.teachers):
        for k in ("classroom", "lab", "arts"):
            gs = [g for g in S if S[g].teacher == tid and S[g].kind == k]
            if not gs:
                continue
            need = max(need_area(S[g], cfg) for g in gs)
            c = [r for r in by_kind[k] if r.id not in taken and r.area >= need - 1e-9] or                 [r for r in by_kind[k] if r.area >= need - 1e-9]
            base[tid, k] = c[0].id
            taken.add(c[0].id)
    busy = defaultdict(set)
    room = {}
    meets = sorted(((s, g) for g in S for s in slot_of[g]), key=lambda x: (x[0], rng.random()))
    for s, g in meets:
        sec = S[g]
        own = base.get((sec.teacher, sec.kind))
        need = need_area(sec, cfg)
        if own and own not in busy[s] and rng.random() < p_own:
            rid = own
        else:
            cands = [r.id for r in by_kind[sec.kind] if r.area >= need - 1e-9 and r.id not in busy[s]]
            if not cands:
                cands = [own] if own and own not in busy[s] else []
            if not cands:
                raise RuntimeError(f"no room at slot {s} for {g}")
            rid = rng.choice(cands)
        room[(g, s)] = rid
        busy[s].add(rid)
    return room


def emulate(w: World, seed: int = 0, p_own: float = 1.0):
    slot_of = blind_slots(w, seed)
    return slot_of, teacher_owned_rooms(w, slot_of, seed, p_own)
