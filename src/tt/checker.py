"""Independent constraint checker. Re-derives every hard rule from the finished grid only
(slot_of: section -> slots, room: (section, slot) -> room id). Shares no code with the solver
except data access, so a solver bug cannot hide here (see tests/test_tt_checker.py mutations).
"""
from __future__ import annotations

from collections import defaultdict

from .config import minutes_band
from .world import World, need_area

CODES = {
    "H1": "section meets exactly its weekly slot count, on distinct slots",
    "H2": "slot exists, is not a fixed block for the grade, not teacher-external-busy",
    "H3": "no student in two places at once",
    "H4": "no teacher double-booked; teacher qualified for the department",
    "H5": "room exists (not on excluded floor B2), right kind, big enough, not double-booked",
    "H6": "teacher consecutive-period cap",
    "H7": "practical (science) sections have a double period",
    "H8": "weekly minutes within tolerance of nominal (contact-hours invariant)",
    "H9": "each student receives every course's stated weekly slots",
    "H10": "every consecutive-period room change reachable inside the break",
}


def check(w: World, slot_of: dict, room: dict, tol: float | None = None) -> dict:
    cfg = w.cfg
    tol = cfg["solve"]["minutes_tol"] if tol is None else tol
    T = len(w.slots)
    S = w.sections
    v = defaultdict(list)
    nom = sum(s["minutes"] for s in w.slots) / T
    lunch = cfg["slots"]["lunch_after"]

    def adjacent(a, b):
        sa, sb = w.slots[a], w.slots[b]
        return sa["day"] == sb["day"] and sb["period"] == sa["period"] + 1 and sa["period"] != lunch

    for g, sec in S.items():
        sl = slot_of.get(g, [])
        if len(sl) != sec.n or len(set(sl)) != len(sl):
            v["H1"].append((g, len(sl), sec.n))
        t = w.teachers[sec.teacher]
        for s in sl:
            if not (0 <= s < T) or s in w.blocked[sec.grade] or s in t.external_busy:
                v["H2"].append((g, s))
        mins = sum(w.slots[s]["minutes"] for s in sl if 0 <= s < T)
        lo, hi = minutes_band(sec.n, nom, cfg)
        if not (lo - 1e-6 <= mins <= hi + 1e-6):
            v["H8"].append((g, mins))
        if sec.double and not any(adjacent(a, b) for a in sl for b in sl):
            v["H7"].append(g)
        if sec.dept not in t.depts:
            v["H4"].append((g, "ineligible", sec.teacher))
    # teachers (parity-aware: even-only + odd-only may share a slot)
    tslots = defaultdict(list)
    for g, sec in S.items():
        for s in slot_of.get(g, []):
            tslots[sec.teacher].append((s, g))
    for tid, lst in tslots.items():
        lanes = defaultdict(int)  # (slot, lane) counts; lane = even-week / odd-week
        for s, g in lst:
            p = getattr(S[g], "parity", "all")
            if p in ("all", "even"):
                lanes[(s, "even")] += 1
            if p in ("all", "odd"):
                lanes[(s, "odd")] += 1
        for (s, lane), n in lanes.items():
            if n > 1:
                v["H4"].append((tid, s, f"double-{lane}"))
        seen = defaultdict(int)
        for s, g in lst:
            seen[s] += 1
        occ = set(seen)
        mc = w.teachers[tid].max_consec
        by_day = defaultdict(list)
        for s in occ | w.teachers[tid].external_busy:
            by_day[w.slots[s]["day"]].append(s)
        for d, ss in by_day.items():
            ss.sort()
            run = 1
            for a, b in zip(ss, ss[1:]):
                run = run + 1 if adjacent(a, b) else 1
                if run > mc:
                    v["H6"].append((tid, d))
                    break
    # students (parity-aware: even-only + odd-only may share a slot)
    ssec = w.student_sections()
    for sid, lst in ssec.items():
        lanes = defaultdict(int)
        per_course = defaultdict(int)
        for g in lst:
            p = getattr(S[g], "parity", "all")
            for s in slot_of.get(g, []):
                if p in ("all", "even"):
                    lanes[(s, "even")] += 1
                if p in ("all", "odd"):
                    lanes[(s, "odd")] += 1
            per_course[S[g].course] += len(set(slot_of.get(g, [])))
        if any(n > 1 for n in lanes.values()):
            v["H3"].append(sid)
        for ck in w.students[sid]["courses"]:
            if per_course.get(ck, 0) != w.courses[ck].slots:
                v["H9"].append((sid, ck))
                break
    # rooms
    rs = defaultdict(list)
    for (g, s), r in room.items():
        rs[(s, r)].append(g)
        sec = S[g]
        room_obj = w.rooms.get(r)
        if room_obj is None or room_obj.kind != sec.kind or room_obj.area < need_area(sec, cfg) - 1e-9:
            v["H5"].append((g, s, r))
    for (s, r), gs in rs.items():
        lanes = defaultdict(int)
        for g in gs:
            p = getattr(S[g], "parity", "all")
            if p in ("all", "even"):
                lanes["even"] += 1
            if p in ("all", "odd"):
                lanes["odd"] += 1
        if any(n > 1 for n in lanes.values()):
            v["H5"].append((s, r, "double"))
    for g, sec in S.items():
        for s in slot_of.get(g, []):
            if (g, s) not in room:
                v["H5"].append((g, s, "none"))
    # reachability along every student sequence (adjacent periods only: gap is 10 min)
    gap = cfg["slots"]["gap_seconds"]
    pairs = set()
    for sid, lst in ssec.items():
        ms = sorted((s, g) for g in lst for s in slot_of.get(g, []))
        for (s1, g1), (s2, g2) in zip(ms, ms[1:]):
            if adjacent(s1, s2) and (g1, s1) in room and (g2, s2) in room:
                pairs.add(((g1, s1), (g2, s2)))
    for a, b in pairs:
        ra, rb = room[a], room[b]
        if ra != rb and w.travel.get((ra, rb), 120.0) > gap:
            v["H10"].append((a, b))
    return {"violations": {k: len(x) for k, x in v.items()}, "examples": {k: x[:3] for k, x in v.items()},
            "ok": not v, "n_checked": {"sections": len(S), "students": len(ssec),
                                       "teachers": len(tslots), "room_legs": len(pairs)}}
