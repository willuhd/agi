"""Stakeholder metrics, all derived from a finished grid (slot_of, room). Units are explicit.

Currency: person-minutes per week, stated once here and used in both the
solver (src/config/tt.toml [solve], per-event weights) and the report (J).
Exchange rates (per-person, per-event parity unless noted):
  idle gap      = nominal period minutes (student and teacher alike);
  walk second   = 1/60 min (solver w_teacher_leg=1 matches J to ~1%);
  contracted load / fatigue overtime = periods x nominal minutes x overload
    (1.0) / underload (1.5) / fatigue (1.5) multipliers;
  office colocation = 0.5 min per floor of separation (stair-cost order).
Solver-vs-report consistency: the solver teacher-gap weight is headcount-balanced
(live students/teachers ratio, ~11.6) so per-GROUP gap totals carry comparable
weight in the search, mirroring how J aggregates per-group MEANS with O(1)
weights; per-person parity holds approximately at w_tgap = w_gap/ratio.
Scale differs between layers (solver integers vs report minutes) by
construction; what agrees is the per-person, per-event exchange ratio (1:1
gaps, ~1:1 walking), stated here instead of hidden.

Students: room changes, walking person-seconds, tight legs, idle periods between classes,
          heavy days (6+ periods), hard-subject lateness, weekly-minute deviation.
Teachers: loss L_i = load deviation + walking + fatigue + idle gaps, all in person-minutes
(constants from config/tt.toml [preference], TCFG below as fallback).
"""
from __future__ import annotations

import statistics
from collections import defaultdict

from world import World

TCFG = dict(target=20, over=1.0, under=1.5, per_second=1 / 60, fatigue=1.5)


def jain(xs):
    xs = list(xs)
    s = sum(xs)
    return (s * s) / (len(xs) * sum(x * x for x in xs)) if s > 0 else 1.0


def cvar(xs, q=0.8):
    s = sorted(xs, reverse=True)
    k = max(1, int(len(s) * (1 - q)))
    return sum(s[:k]) / k


def evaluate(w: World, slot_of: dict, room: dict) -> dict:
    cfg = w.cfg
    S = w.sections
    ssec = w.student_sections()
    gap_s = cfg["slots"]["gap_seconds"]
    lunch = cfg["slots"]["lunch_after"]
    lunch_free = cfg.get("travel", {}).get("lunch_free", True)
    nom = sum(s["minutes"] for s in w.slots) / len(w.slots)
    tau = lambda a, b: 0.0 if a == b else w.travel.get((a, b), 120.0)

    def leg_free_idx(s1: int, s2: int) -> bool:
        if not lunch_free:
            return False
        a, b = w.slots[s1], w.slots[s2]
        if a["day"] != b["day"]:
            return True
        return a["period"] <= lunch and b["period"] > lunch
    days = defaultdict(list)
    for s in w.slots:
        days[s["day"]].append(s["idx"])

    per = {}
    for sid, lst in ssec.items():
        grade = w.students[sid]["grade"]
        blocked = w.blocked[grade]
        ms = sorted((s, g) for g in lst for s in slot_of[g])
        changes = trav = tight = gaps = heavy = 0
        by_day = defaultdict(list)
        for s, g in ms:
            by_day[w.slots[s]["day"]].append((s, g))
        for d, items in by_day.items():
            for (s1, g1), (s2, g2) in zip(items, items[1:]):
                a, b = room[(g1, s1)], room[(g2, s2)]
                if a != b:
                    changes += 1
                    if leg_free_idx(s1, s2):
                        continue
                    t = tau(a, b)
                    trav += t
                    if (w.slots[s2]["period"] == w.slots[s1]["period"] + 1
                            and not leg_free_idx(s1, s2)
                            and t > 0.25 * gap_s):
                        tight += 1
        for d, idxs in days.items():
            occ = [(s in blocked) or any(s in slot_of[g] for g in lst) for s in idxs]
            if any(occ):
                first = occ.index(True)
                last = len(occ) - 1 - occ[::-1].index(True)
                gaps += sum(1 for i in range(first, last + 1) if not occ[i])
            if sum(occ) >= 6:
                heavy += 1
        per[sid] = dict(changes=changes, travel_s=trav, tight=tight, gaps=gaps, heavy=heavy)
    # hard-subject lateness (avg period of credit>=5 meetings, student weighted)
    hw = hs = 0
    for g, sec in S.items():
        if sec.hard:
            for s in slot_of[g]:
                hw += sec.size * (w.slots[s]["period"])
                hs += sec.size
    # minutes deviation across sections of the same course
    dev = []
    for g, sec in S.items():
        mins = sum(w.slots[s]["minutes"] for s in slot_of[g])
        dev.append(abs(mins / (sec.n * nom) - 1))
    by_course = defaultdict(list)
    for g, sec in S.items():
        by_course[sec.course].append(sum(w.slots[s]["minutes"] for s in slot_of[g]))
    course_spread = max((max(v) - min(v)) / (sum(v) / len(v)) for v in by_course.values())
    # teachers
    tl, tstat = {}, {}
    tm = defaultdict(list)
    for g, sec in S.items():
        for s in slot_of[g]:
            tm[sec.teacher].append((s, g))
    for tid, lst in tm.items():
        lst.sort()
        periods = len(lst)
        travel = 0.0
        run = best = 1
        gaps = 0
        for d, idxs in days.items():
            occ = [any(s == i for s, _ in lst) or i in w.teachers[tid].external_busy for i in idxs]
            if any(occ):
                f = occ.index(True)
                l = len(occ) - 1 - occ[::-1].index(True)
                gaps += sum(1 for i in range(f, l + 1) if not occ[i])
        for (s1, g1), (s2, g2) in zip(lst, lst[1:]):
            if w.slots[s1]["day"] == w.slots[s2]["day"]:
                if not leg_free_idx(s1, s2):
                    travel += tau(room[(g1, s1)], room[(g2, s2)])
                if w.slots[s2]["period"] == w.slots[s1]["period"] + 1 and w.slots[s1]["period"] != lunch:
                    run += 1
                    best = max(best, run)
                else:
                    run = 1
            else:
                run = 1
        mc = w.teachers[tid].max_consec
        pref = cfg.get("preference", {})
        target = pref.get("target_periods", TCFG["target"])
        over = pref.get("overload_price", TCFG["over"])
        under = pref.get("underload_price", TCFG["under"])
        per_second = pref.get("price_per_second", TCFG["per_second"])
        fatigue_p = pref.get("price_per_extra_consecutive", TCFG["fatigue"])
        load = ((periods - target) * over if periods > target else (target - periods) * under) * nom
        travel_cost = travel * per_second
        fatigue_cost = max(0, best - mc) * fatigue_p * nom
        gap_cost = gaps * nom
        # office colocation in minutes: floor gap x price (default 0.5 min/floor,
        # stair-cost order); 0 when offices disabled or teaching is XMT-only.
        coloc_cost = 0.0
        office = getattr(w.teachers[tid], "office", "")
        if office:
            from collections import Counter
            floors = [w.rooms[room[(g, s)]].floor for (s, g) in lst
                      if (g, s) in room and not room[(g, s)].startswith("XMT")]
            if floors:
                office_floor = {"406": "4F", "407": "4F", "313": "3F", "314": "3F",
                                "320": "3F", "117": "1F", "110": "1F", "210": "2F"}.get(office)
                if office_floor is None:
                    for r in w.rooms.values():
                        if r.id == office:
                            office_floor = r.floor
                            break
                if office_floor:
                    idx = {"B2": -2, "B1": -1, "1F": 0, "2F": 1, "3F": 2, "4F": 3}
                    pred = Counter(floors).most_common(1)[0][0]
                    coloc_cost = (abs(idx.get(office_floor, 0) - idx.get(pred, 0))
                                  * cfg.get("offices", {}).get("colocation_price_per_floor", 0.5))
        L = load + travel_cost + fatigue_cost + gap_cost + coloc_cost
        tl[tid] = L
        tstat[tid] = dict(periods=periods, travel_s=travel, gaps=gaps, max_run=best, L=L,
                          load_term=load, travel_term=travel_cost, fatigue_term=fatigue_cost,
                          gap_term=gap_cost, coloc_term=coloc_cost, office=office)
    # load term is staffing, identical across designs -> report the schedule-dependent part too
    sched_part = {t: s["L"] - s["load_term"] for t, s in tstat.items()}
    n = len(per)
    trav = [p["travel_s"] for p in per.values()]
    # arts before-lunch placement (config-driven report, not a hard rule)
    arts_cfg = cfg.get("arts", {})
    arts_target = arts_cfg.get("target_period", lunch)
    arts_meet = arts_p4 = 0
    for g, sec in S.items():
        if sec.kind != "arts":
            continue
        for s in slot_of[g]:
            arts_meet += sec.size
            if w.slots[s]["period"] == arts_target:
                arts_p4 += sec.size
    # teacher XMT adjacency: ZX teaching next to external_busy, same-day,
    # non-lunch-straddling (mirrors the solve_slots xmt penalty)
    xmt_adj = 0
    xmt_enabled = cfg.get("solve", {}).get("xmt_adj_enabled", True)
    if xmt_enabled:
        by_per_day = defaultdict(dict)
        for s in w.slots:
            by_per_day[s["day"]][s["period"]] = s["idx"]
        for tid, lst in tm.items():
            busy = w.teachers[tid].external_busy
            if not busy:
                continue
            teach = {s for s, _ in lst}
            for b in busy:
                p, d = w.slots[b]["period"], w.slots[b]["day"]
                for q in (p - 1, p + 1):
                    slot_idx = by_per_day.get(d, {}).get(q)
                    if slot_idx is None or slot_idx in busy:
                        continue
                    if lunch_free and p <= lunch < q or lunch_free and q <= lunch < p:
                        continue
                    if slot_idx in teach:
                        xmt_adj += 1
    # group fairness (ported sched formulation.group_terms): per-department CVaR
    # tail + spread of group means. Groups from teacher dept; weights from
    # tt.toml [objective] group_department / beta_prime. Zero when disabled.
    from collections import Counter as _Counter
    losses_by_dept: dict[str, list[float]] = {}
    for tid, L in tl.items():
        losses_by_dept.setdefault(w.teachers[tid].dept, []).append(L)
    q = cfg.get("objective", {}).get("cvar_q", 0.8)
    group_cvars = {d: cvar(v, q) for d, v in losses_by_dept.items()}
    group_means = {d: sum(v) / len(v) for d, v in losses_by_dept.items() if v}
    group_spread = (max(group_means.values()) - min(group_means.values())) if group_means else 0.0
    out = {
        "students": {
            "n": n,
            "room_changes_mean": sum(p["changes"] for p in per.values()) / n,
            "travel_s_mean": sum(trav) / n,
            "travel_s_cvar80": cvar(trav),
            "travel_total_person_hours": sum(trav) / 3600,
            "tight_legs_total": sum(p["tight"] for p in per.values()),
            "gaps_mean": sum(p["gaps"] for p in per.values()) / n,
            "heavy_days_mean": sum(p["heavy"] for p in per.values()) / n,
            "hard_subject_mean_period": hw / hs if hs else 0,
            "jain_travel": jain(trav),
            "lost_min_week_mean": sum(trav) / n / 60 + sum(p["gaps"] for p in per.values()) / n * nom,
        },
        "teachers": {
            "n": len(tl),
            "L_mean": statistics.mean(tl.values()),
            "L_cvar80": cvar(list(tl.values())),
            "sched_L_mean": statistics.mean(sched_part.values()),
            "sched_L_cvar80": cvar(list(sched_part.values())),
            "travel_s_mean": statistics.mean(s["travel_s"] for s in tstat.values()),
            "gaps_mean": statistics.mean(s["gaps"] for s in tstat.values()),
            "fatigue_excess": sum(max(0, s["max_run"] - w.teachers[t].max_consec) for t, s in tstat.items()),
            "jain_L": jain([1 + v - min(sched_part.values()) for v in sched_part.values()]),
            "xmt_adjacent_lessons": xmt_adj,
            "coloc_mean": statistics.mean(s.get("coloc_term", 0.0) for s in tstat.values()),
            "group_cvar_sum": sum(group_cvars.values()),
            "group_spread": group_spread,
            "group_cvars": group_cvars,
        },
        "arts": {
            "target_period": arts_target,
            "meetings_in_target": arts_p4,
            "meetings_total": arts_meet,
            "share_in_target": (arts_p4 / arts_meet) if arts_meet else 1.0,
        },
        "contact": {
            "minutes_dev_mean": statistics.mean(dev),
            "minutes_dev_max": max(dev),
            "course_section_minutes_spread_max": course_spread,
        },
    }
    out["per_student"] = per
    out["per_teacher"] = tstat
    return out


def objective(m: dict, cfg: dict) -> float:
    """Composite J in person-minutes/week (diagnostic): students' lost minutes +
    weighted teacher loss + group fairness. Per-group parity: each stakeholder
    group's mean enters with an O(1) weight (alpha/beta/group terms); this is
    one point on the efficiency-fairness frontier (see fair.py), not the argmin
    the solver targets -- the solver works the same currency via [solve] weights."""
    o = cfg["objective"]
    s, t = m["students"], m["teachers"]
    base = s["lost_min_week_mean"] + o["alpha"] * t["sched_L_mean"] + o["beta"] * t["sched_L_cvar80"]
    base += o.get("group_department", 0.0) * t.get("group_cvar_sum", 0.0)
    base += o.get("beta_prime", 0.0) * t.get("group_spread", 0.0)
    return base
