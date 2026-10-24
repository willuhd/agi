"""Staged optimizer.

Stage 0 (world.py): sectioning (cohort-preserving) + balanced teacher assignment.
Stage 1 (here, CP-SAT): which slots each section meets. Section-level Booleans z[g,s] instead of
        meeting-level pairwise constraints -> linear in sections x slots, not O(M^2).
Stage 2 (here): home rooms for cohorts, per-slot min-cost room matching, then exact person-seconds
        local search over room swaps (SA).
Same solve_slots() with `fixed`/`prev` powers incremental repair after shocks (shocks.py).
"""
from __future__ import annotations

import math
import random
from collections import Counter, defaultdict

from ortools.sat.python import cp_model

from .config import minutes_band
from .world import World, need_area


def lunch_after(w: World) -> int:
    """Lunch boundary from config, never hardcoded (tt.toml [slots] lunch_after)."""
    return w.cfg["slots"]["lunch_after"]


def travel_policy(w: World) -> dict:
    """Gap-pricing policy from tt.toml [travel] (lunch_free, price_mode, cross_seconds)."""
    return w.cfg.get("travel", {})


def arts_policy(w: World) -> dict:
    """Arts before-lunch preference from tt.toml [arts]."""
    return w.cfg.get("arts", {})


def straddles_lunch_periods(p1: int, p2: int, lunch_after_p: int) -> bool:
    return p1 <= lunch_after_p and p2 > lunch_after_p


def leg_free(w: World, s1: int, s2: int) -> bool:
    """Hard-zero rule, fully config-driven: same-day pair straddling lunch
    is free iff [travel] lunch_free. price_mode reserved for future 'excess'."""
    tp = travel_policy(w)
    if not tp.get("lunch_free", True):
        return False
    a, b = w.slots[s1], w.slots[s2]
    if a["day"] != b["day"]:
        return True  # no overnight walk (not a real leg)
    return straddles_lunch_periods(a["period"], b["period"], lunch_after(w))


def day_groups(w: World) -> list[list[int]]:
    g = defaultdict(list)
    for s in w.slots:
        g[s["day"]].append(s["idx"])
    return [sorted(v, key=lambda i: w.slots[i]["period"]) for v in g.values()]


def consecutive_runs(w: World, day: list[int]) -> list[list[int]]:
    runs, cur = [], [day[0]]
    for a, b in zip(day, day[1:]):
        pa, pb = w.slots[a]["period"], w.slots[b]["period"]
        if pb == pa + 1 and not (pa == w.cfg["slots"]["lunch_after"]):
            cur.append(b)
        else:
            runs.append(cur)
            cur = [b]
    runs.append(cur)
    return runs


def nominal_minutes(w: World) -> float:
    return sum(s["minutes"] for s in w.slots) / len(w.slots)


def solve_slots(w: World, time_limit: float | None = None, hint: dict | None = None,
                fixed: dict | None = None, prev: dict | None = None, churn_w: int = 0,
                forbid_section: dict | None = None, forbid_teacher: dict | None = None,
                weights: dict | None = None, log: bool = False, skip: set | None = None,
                random_obj_seed: int | None = None) -> dict:
    skip = skip or set()
    cfg = w.cfg
    sv = cfg["solve"]
    wt = {k: sv[k] for k in ("w_gap", "w_heavy", "w_spread", "w_morning", "w_tgap")
          if k in sv}
    for k in ("w_arts_p4", "w_xmt_adj"):
        if k in sv:
            wt[k] = sv[k]
    wt.update(weights or {})
    ap = arts_policy(w)
    tp = travel_policy(w)
    arts_on = ap.get("before_lunch_enabled", True) and wt.get("w_arts_p4", 0) > 0
    arts_target = ap.get("target_period", lunch_after(w))
    xmt_on = (sv.get("xmt_adj_enabled", True) and wt.get("w_xmt_adj", 0) > 0
              and tp.get("price_mode", "hard_zero") is not None)
    fixed = fixed or {}
    T = len(w.slots)
    m = cp_model.CpModel()
    S = w.sections
    forbid_section = forbid_section or {}
    forbid_teacher = forbid_teacher or {}

    Z: dict = {}
    for g, sec in S.items():
        t = w.teachers[sec.teacher]
        bad = (set(w.blocked[sec.grade]) | t.external_busy | forbid_section.get(g, set())
               | forbid_teacher.get(sec.teacher, set()))
        row = {}
        if g in fixed:
            for s in range(T):
                row[s] = 1 if s in fixed[g] else 0
        else:
            for s in range(T):
                row[s] = 0 if s in bad else m.NewBoolVar(f"z{g}_{s}")
            m.Add(sum(row[s] for s in range(T)) == sec.n)
        Z[g] = row

    def tot(items):
        return sum(items) if items else 0

    def parity_of(g: str) -> str:
        return getattr(S[g], "parity", "all")

    def lanes(group: list[str]) -> list[list[str]]:
        """Parity lanes: even-only and odd-only sections share a slot with each
        other (alternate weeks) but never with 'all'. Returns the two lane
        groupings [all+even, all+odd]; 'all'-only groups collapse to one lane."""
        ev = [g for g in group if parity_of(g) in ("all", "even")]
        od = [g for g in group if parity_of(g) in ("all", "odd")]
        if ev == od:
            return [ev]
        return [ev, od]

    # --- hard: students (signature = identical section sets), teachers, room capacity -----------
    # Parity-aware: an even-only and an odd-only section may share a slot
    # (alternate weeks); enforced as one cap per lane. Disabled (single lane)
    # when every section is parity "all" — the default with empty split lists.
    sigs = Counter()
    ssec = w.student_sections()
    for sid, lst in ssec.items():
        sigs[frozenset(lst)] += 1
    for sig in ([] if 'student' in skip else sigs):
        for lane in lanes(list(sig)):
            for s in range(T):
                e = tot([Z[g][s] for g in lane])
                if not isinstance(e, int) or e > 1:
                    m.Add(e <= 1)
    by_teacher = defaultdict(list)
    for g, sec in S.items():
        by_teacher[sec.teacher].append(g)
    for tid, gs in ([] if 'teacher' in skip else by_teacher.items()):
        if ('t:' + tid) in skip:
            continue
        for lane in lanes(gs):
            for s in range(T):
                e = tot([Z[g][s] for g in lane])
                if not isinstance(e, int) or e > 1:
                    m.Add(e <= 1)
    days = day_groups(w)
    for tid, gs in ([] if 'consec' in skip else by_teacher.items()):
        mc = w.teachers[tid].max_consec
        for d in days:
            for run in consecutive_runs(w, d):
                for k in range(len(run) - mc):
                    win = run[k:k + mc + 1]
                    ext = sum(1 for s in win if s in w.teachers[tid].external_busy)
                    e = tot([Z[g][s] for g in gs for s in win])
                    if not isinstance(e, int):
                        m.Add(e + ext <= mc)
    # room capacity by kind and area (nested thresholds => Hall's condition is exact)
    # Parity-aware: one cap per lane (even-week / odd-week); collapses to the
    # old single cap when no even/odd sections exist.
    for kind in ([] if 'room' in skip else ("classroom", "lab", "arts")):
        areas = sorted(r.area for r in w.rooms.values() if r.kind == kind)
        gk = [g for g, sec in S.items() if sec.kind == kind]
        levels = sorted({need_area(S[g], cfg) for g in gk})
        for lv in levels:
            cap = sum(1 for a in areas if a >= lv - 1e-9)
            gl = [g for g in gk if need_area(S[g], cfg) >= lv - 1e-9]
            for lane in lanes(gl):
                for s in range(T):
                    e = tot([Z[g][s] for g in lane])
                    if not isinstance(e, int):
                        m.Add(e <= cap)
    # --- hard: minute invariant (two-week mean for parity sections) -------
    # Even/odd-only meetings count at 0.5 (tt.toml [parity] weights): a 4-slot
    # even-only section owes ~2 slots' worth of weekly minutes.
    nom = nominal_minutes(w)
    tol = sv["minutes_tol"]
    pw = {"all": cfg.get("parity", {}).get("standard_weight", 1.0),
          "even": cfg.get("parity", {}).get("even_only_weight", 0.5),
          "odd": cfg.get("parity", {}).get("odd_only_weight", 0.5)}
    for g, sec in S.items():
        if g in fixed:
            continue
        e = tot([Z[g][s] * w.slots[s]["minutes"] for s in range(T) if not isinstance(Z[g][s], int)])
        wgt = pw.get(getattr(sec, "parity", "all"), 1.0)
        lo, hi = minutes_band(sec.n, nom, cfg)
        m.Add(e * wgt >= int(math.ceil(lo * wgt - 1e-6)))
        m.Add(e * wgt <= int(math.floor(hi * wgt + 1e-6)))
    # --- hard: lab double periods ------------------------------------------------------------------
    for g, sec in S.items():
        if g in fixed or not sec.double:
            continue
        ds = []
        for d in days:
            for run in consecutive_runs(w, d):
                for a, b in zip(run, run[1:]):
                    if isinstance(Z[g][a], int) or isinstance(Z[g][b], int):
                        continue
                    v = m.NewBoolVar(f"d{g}_{a}")
                    m.AddImplication(v, Z[g][a])
                    m.AddImplication(v, Z[g][b])
                    ds.append(v)
        if ds:
            m.Add(sum(ds) >= 1)

    # --- objective -------------------------------------------------------------------------------
    soft = "soft" not in skip
    obj = []
    if soft:
        for g, sec in S.items():
            if g in fixed:
                continue
            free = 2 if sec.double else 1
            for d in days:
                c = tot([Z[g][s] for s in d if not isinstance(Z[g][s], int)])
                if isinstance(c, int):
                    continue
                v = m.NewIntVar(0, 7, f"sp{g}_{d[0]}")
                m.Add(v >= c - free)
                obj.append(int(round(wt["w_spread"] * sec.size)) * v)
            if sec.hard and wt["w_morning"] > 0:
                for s in range(T):
                    if not isinstance(Z[g][s], int):
                        obj.append(int(round(wt["w_morning"] * sec.size * (w.slots[s]["period"] - 1))) * Z[g][s])

        def gap_terms(occ_by_slot: dict, weight: int, tag: str):
            """occ_by_slot: slot -> expression (0/1). Adds idle-gap vars; returns objective terms."""
            terms = []
            for di, d in enumerate(days):
                before, after = {}, {}
                for i, s in enumerate(d):
                    before[s] = m.NewBoolVar(f"b{tag}_{s}")
                    after[s] = m.NewBoolVar(f"a{tag}_{s}")
                for i, s in enumerate(d):
                    if i == 0:
                        m.Add(before[s] == 0)
                    else:
                        m.Add(before[s] >= occ_by_slot[d[i - 1]])
                        m.Add(before[s] >= before[d[i - 1]])
                    if i == len(d) - 1:
                        m.Add(after[s] == 0)
                    else:
                        m.Add(after[s] >= occ_by_slot[d[i + 1]])
                        m.Add(after[s] >= after[d[i + 1]])
                for s in d:
                    gp = m.NewBoolVar(f"gp{tag}_{s}")
                    m.Add(gp >= before[s] + after[s] - occ_by_slot[s] - 1)
                    terms.append(weight * gp)
            return terms

        for i, (sig, cnt) in enumerate(sigs.items()):
            grade = S[next(iter(sig))].grade
            occ = {s: (1 if s in w.blocked[grade] else tot([Z[g][s] for g in sig])) for s in range(T)}
            if all(isinstance(v, int) for v in occ.values()):
                continue
            obj += gap_terms(occ, int(round(wt["w_gap"] * cnt)), f"s{i}")
            if wt["w_heavy"] > 0:
                for d in days:
                    hv = m.NewBoolVar(f"hv{i}_{d[0]}")
                    m.Add(sum(occ[s] for s in d) - 5 <= 2 * hv)
                    obj.append(int(round(wt["w_heavy"] * cnt)) * hv)
        for tid, gs in by_teacher.items():
            t = w.teachers[tid]
            occ = {s: (1 if s in t.external_busy else tot([Z[g][s] for g in gs])) for s in range(T)}
            if all(isinstance(v, int) for v in occ.values()):
                continue
            obj += gap_terms(occ, int(round(wt.get("w_tgap", 0) * 10)), f"t{tid}")
        if arts_on:
            # Soft before-lunch preference: each arts-kind meeting in the target
            # period earns w_arts_p4 * size (subtracted from the minimization).
            # All names/thresholds from tt.toml [arts] + [solve]; disable via
            # before_lunch_enabled=false or w_arts_p4=0.
            for g, sec in S.items():
                if g in fixed or sec.kind != "arts":
                    continue
                bonus = int(round(wt["w_arts_p4"] * sec.size))
                if bonus <= 0:
                    continue
                for s in range(T):
                    if isinstance(Z[g][s], int):
                        continue
                    if w.slots[s]["period"] != arts_target:
                        continue
                    if s in w.blocked[sec.grade]:
                        continue
                    obj.append(-bonus * Z[g][s])
        if xmt_on:
            # Teacher ZX<->XMT (external_busy) adjacency: teaching in a slot
            # next to an XMT busy slot on the same day costs w_xmt_adj, unless
            # the pair straddles lunch (free iff [travel] lunch_free).
            # Disable via xmt_adj_enabled=false or w_xmt_adj=0.
            lunch_p = lunch_after(w)
            lunch_free = tp.get("lunch_free", True)
            by_day_idx = defaultdict(list)
            for s in range(T):
                by_day_idx[w.slots[s]["day"]].append(s)
            neigh = defaultdict(list)  # busy slot -> adjacent teachable slots
            for d, lst in by_day_idx.items():
                by_per = {w.slots[s]["period"]: s for s in lst}
                for s in lst:
                    p = w.slots[s]["period"]
                    for q in (p - 1, p + 1):
                        n = by_per.get(q)
                        if n is None:
                            continue
                        if lunch_free and straddles_lunch_periods(
                                min(p, q), max(p, q), lunch_p):
                            continue
                        neigh[s].append(n)
            wxmt = int(round(wt["w_xmt_adj"]))
            if wxmt > 0:
                for tid, gs in by_teacher.items():
                    t = w.teachers[tid]
                    if not t.external_busy:
                        continue
                    teachable = [g for g in gs if g not in fixed]
                    if not teachable:
                        continue
                    for b in t.external_busy:
                        for n in neigh.get(b, []):
                            e = tot([Z[g][n] for g in teachable
                                     if not isinstance(Z[g][n], int)])
                            if isinstance(e, int):
                                continue
                            obj.append(wxmt * e)
        if prev and churn_w:
            for g, old in prev.items():
                if g in fixed or g not in Z:
                    continue
                for s in old:
                    if not isinstance(Z[g][s], int):
                        obj.append(churn_w * (1 - Z[g][s]))
                    else:
                        obj.append(churn_w * (1 - Z[g][s]))
    if random_obj_seed is not None:
        rr = random.Random(random_obj_seed)
        obj = [rr.randint(0, 4) * Z[g][s] for g in S for s in range(T) if not isinstance(Z[g][s], int)]
    if obj:
        m.Minimize(sum(obj))

    if hint:
        for g, sl in hint.items():
            if g in fixed:
                continue
            hs = set(sl)
            for s in range(T):
                if not isinstance(Z[g][s], int):
                    m.AddHint(Z[g][s], 1 if s in hs else 0)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit or sv["time_limit_s"]
    solver.parameters.num_search_workers = sv["workers"]
    solver.parameters.random_seed = sv["seed"]
    solver.parameters.log_search_progress = log
    status = solver.Solve(m)
    name = solver.StatusName(status)
    out = {"status": name, "assignment": {}, "objective": None, "bound": None}
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        out["objective"] = solver.ObjectiveValue()
        out["bound"] = solver.BestObjectiveBound()
        for g in S:
            out["assignment"][g] = sorted(
                s for s in range(T) if (Z[g][s] if isinstance(Z[g][s], int) else solver.Value(Z[g][s])))
    out["wall"] = solver.WallTime()
    return out


# ------------------------------------------------------------------ stage 2: rooms ------------

def tau(w: World, a: str, b: str) -> float:
    if a == b:
        return 0.0
    return w.travel.get((a, b), 120.0)


def home_rooms(w: World) -> dict:
    """homeroom -> classroom id, min travel from grade office (teachers.toml pins), distinct, area ok."""
    from .world import OFFICE
    hrs = sorted({st["homeroom"] for st in w.students.values()})
    size = Counter(st["homeroom"] for st in w.students.values())
    cls = [r for r in w.rooms.values() if r.kind == "classroom"]
    def attempt(strict):
        m = cp_model.CpModel()
        x = {}
        for h in hrs:
            need = size[h] * w.cfg["rooms"]["area_per_student"]
            for r in cls:
                if (not strict) or r.area >= need:
                    x[h, r.id] = m.NewBoolVar(f"{h}{r.id}")
        for h in hrs:
            m.Add(sum(v for (hh, _), v in x.items() if hh == h) == 1)
        for r in cls:
            m.Add(sum(v for (_, rr), v in x.items() if rr == r.id) <= 1)
        m.Minimize(sum(int(tau(w, OFFICE[h.split("-H")[0]], r)) * v for (h, r), v in x.items()))
        sv = cp_model.CpSolver()
        sv.parameters.max_time_in_seconds = 20
        return x, sv, sv.Solve(m)
    x, sv, st = attempt(True)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):   # lost too many rooms: homes may be undersized
        x, sv, st = attempt(False)
    assert st in (cp_model.OPTIMAL, cp_model.FEASIBLE), "no home-room assignment"
    return {h: r for (h, r), v in x.items() if sv.Value(v)}


def legs(w: World, slot_of: dict) -> Counter:
    """Weighted consecutive-class legs: (meetingA, meetingB) -> students. meeting = (section, slot)."""
    ssec = w.student_sections()
    seqs = Counter()
    for sid, lst in ssec.items():
        by_day = defaultdict(list)
        for g in lst:
            for s in slot_of[g]:
                by_day[w.slots[s]["day"]].append((s, g))
        key = []
        for d, items in by_day.items():
            items.sort()
            key.append(tuple(items))
        seqs[tuple(sorted(key))] += 1
    out = Counter()
    for key, cnt in seqs.items():
        for seq in key:
            for (s1, g1), (s2, g2) in zip(seq, seq[1:]):
                out[((g1, s1), (g2, s2))] += cnt
    tw = w.cfg["solve"]["w_teacher_leg"]
    if tw > 0:   # teachers walk too: one teacher-second counts w_teacher_leg of a student-second
        tseq = defaultdict(lambda: defaultdict(list))
        for g, sl in slot_of.items():
            for s in sl:
                tseq[w.sections[g].teacher][w.slots[s]["day"]].append((s, g))
        for days in tseq.values():
            for items in days.values():
                items.sort()
                for (s1, g1), (s2, g2) in zip(items, items[1:]):
                    out[((g1, s1), (g2, s2))] += tw
    return out


def assign_rooms(w: World, slot_of: dict, iters: int | None = None, seed: int = 0,
                 forbid_rooms: set | None = None) -> tuple[dict, dict]:
    """Returns (room[(g,s)] -> room id, info)."""
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
                    cost = sum(c * tau(w, homes[h], r.id) for h, c in sec.homerooms.items())
                    x[g, r.id] = (m.NewBoolVar(f"x{g}{r.id}"), int(cost))
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
            raise RuntimeError(f"room matching infeasible at slot {s}")
        for (g, r), (v, _) in x.items():
            if sv.Value(v):
                room[(g, s)] = r
    info = {"homes": homes}
    L = legs(w, slot_of)
    before = person_seconds(w, room, L)
    room = polish_rooms(w, room, L, iters if iters is not None else cfg["solve"]["room_polish_iters"], seed, forbid_rooms)
    info["ps_before_polish"] = before
    info["ps_after_polish"] = person_seconds(w, room, L)
    return room, info


def person_seconds(w: World, room: dict, L: Counter) -> float:
    """Gap-aware person-seconds: lunch-straddling legs cost 0 iff
    [travel] lunch_free (tt.toml). 1x vs 2x still additive otherwise."""
    total = 0.0
    for (a, b), c in L.items():
        (g1, s1), (g2, s2) = a, b
        if leg_free(w, s1, s2):
            continue
        total += c * tau(w, room[a], room[b])
    return total


def polish_rooms(w, room, L, iters, seed, forbid_rooms):
    cfg = w.cfg
    rng = random.Random(seed)
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
        if r.id not in forbid_rooms:
            rooms_of_kind[r.kind].append(r)

    def cost_of(mt, r):
        g, s = mt
        total = 0.0
        for o, c in adj[mt]:
            go, so = o
            if leg_free(w, s, so):
                continue
            total += c * tau(w, r, room[o])
        return total

    temp0 = 30.0
    for it in range(iters):
        temp = temp0 * (1 - it / iters)
        mt = rng.choice(meets)
        g, s = mt
        sec = w.sections[g]
        need = need_area(sec, cfg)
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
            if w.rooms[r1].area < need_area(so, cfg) - 1e-9:
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
