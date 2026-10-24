"""Stakeholder metrics, all derived from a finished grid (slot_of, room). Units are explicit.

Students: room changes, walking person-seconds, tight legs, idle periods between classes,
          heavy days (6+ periods), hard-subject lateness, weekly-minute deviation.
Teachers: loss L_i = load deviation + walking + fatigue + idle gaps (constants from teachers.toml).
"""
from __future__ import annotations

import statistics
from collections import defaultdict

from .world import World

TCFG = dict(target=20, over=1.0, under=1.5, per_second=0.02, fatigue=1.5, gap=0.5)


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
    nom = sum(s["minutes"] for s in w.slots) / len(w.slots)
    tau = lambda a, b: 0.0 if a == b else w.travel.get((a, b), 120.0)
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
                    t = tau(a, b)
                    trav += t
                    if w.slots[s2]["period"] == w.slots[s1]["period"] + 1 and t > 0.25 * gap_s:
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
                travel += tau(room[(g1, s1)], room[(g2, s2)])
                if w.slots[s2]["period"] == w.slots[s1]["period"] + 1 and w.slots[s1]["period"] != lunch:
                    run += 1
                    best = max(best, run)
                else:
                    run = 1
            else:
                run = 1
        mc = w.teachers[tid].max_consec
        load = (periods - TCFG["target"]) * TCFG["over"] if periods > TCFG["target"] else (TCFG["target"] - periods) * TCFG["under"]
        L = load + travel * TCFG["per_second"] + max(0, best - mc) * TCFG["fatigue"] + gaps * TCFG["gap"]
        tl[tid] = L
        tstat[tid] = dict(periods=periods, travel_s=travel, gaps=gaps, max_run=best, L=L, load_term=load)
    # load term is staffing, identical across designs -> report the schedule-dependent part too
    sched_part = {t: s["L"] - s["load_term"] for t, s in tstat.items()}
    n = len(per)
    trav = [p["travel_s"] for p in per.values()]
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
    """Composite J in 'person-minute' currency: students' lost minutes + weighted teacher loss."""
    o = cfg["objective"]
    s, t = m["students"], m["teachers"]
    return s["lost_min_week_mean"] + o["alpha"] * t["sched_L_mean"] + o["beta"] * t["sched_L_cvar80"]
