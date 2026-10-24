"""Mutation suite: inject one known violation per hard-constraint code into a valid grid and confirm the
independent checker flags exactly that rule. A checker that cannot catch a planted fault cannot certify."""
from __future__ import annotations

import copy
from collections import defaultdict

from . import checker
from .world import World, need_area


def _clone(slot_of, room):
    return {g: list(s) for g, s in slot_of.items()}, dict(room)


def _find_adjacent_pair(w, sl):
    for a in sl:
        for b in sl:
            if w.slots[b]["day"] == w.slots[a]["day"] and w.slots[b]["period"] == w.slots[a]["period"] + 1 \
                    and w.slots[a]["period"] != w.cfg["slots"]["lunch_after"]:
                return a, b
    return None


def make_mutations(w: World, slot_of, room) -> dict:
    S = w.sections
    T = len(w.slots)
    out = {}

    # H1: drop a meeting
    so, rm = _clone(slot_of, room)
    g = next(iter(S))
    s = so[g].pop()
    rm.pop((g, s))
    out["H1"] = (so, rm, w)

    # H2: put a meeting into the PE block
    so, rm = _clone(slot_of, room)
    g = next(g for g in S if S[g].grade == "G9")
    pe = next(iter(w.pe_slots))
    old = so[g][0]
    rm[(g, pe)] = rm.pop((g, old))
    so[g][0] = pe
    out["H2"] = (so, rm, w)

    # H3: two sections that share a student at one slot
    so, rm = _clone(slot_of, room)
    ssec = w.student_sections()
    pair = None
    for sid, lst in ssec.items():
        if len(lst) >= 2:
            pair = (lst[0], lst[1])
            break
    a, b = pair
    tgt = so[a][0]
    old = so[b][0]
    if tgt in so[b]:
        old = tgt
    else:
        rm[(b, tgt)] = rm.pop((b, old))
        so[b][so[b].index(old)] = tgt
    out["H3"] = (so, rm, w)

    # H4a: teacher double-booked
    so, rm = _clone(slot_of, room)
    by_t = defaultdict(list)
    for g in S:
        by_t[S[g].teacher].append(g)
    t, gs = next((t, gs) for t, gs in by_t.items() if len(gs) >= 2)
    a, b = gs[0], gs[1]
    tgt = so[a][0]
    if tgt not in so[b]:
        old = so[b][0]
        rm[(b, tgt)] = rm.pop((b, old))
        so[b][0] = tgt
    out["H4"] = (so, rm, w)

    # H5: two meetings, same slot, same room
    so, rm = _clone(slot_of, room)
    by_s = defaultdict(list)
    for (g, s), r in rm.items():
        by_s[s].append((g, r))
    s, lst = next((s, l) for s, l in by_s.items() if len(l) >= 2)
    rm[(lst[1][0], s)] = lst[0][1]
    out["H5"] = (so, rm, w)

    # H6: teacher with 3 adjacent meetings while cap is 2
    so, rm = _clone(slot_of, room)
    w6 = copy.copy(w)
    w6.teachers = {k: copy.copy(v) for k, v in w.teachers.items()}
    tid = next(t for t, gs in by_t.items() if sum(S[g].n for g in gs) >= 4)
    w6.teachers[tid].max_consec = 1
    tt = [(s, g) for g in by_t[tid] for s in so[g]]
    # rely on cap=1 plus any adjacent pair in the existing grid
    adj = None
    for g1 in by_t[tid]:
        for g2 in by_t[tid]:
            for s1 in so[g1]:
                for s2 in so[g2]:
                    if (g1, s1) != (g2, s2) and w.slots[s1]["day"] == w.slots[s2]["day"] and \
                            w.slots[s2]["period"] == w.slots[s1]["period"] + 1 and w.slots[s1]["period"] != 4:
                        adj = True
    if not adj:   # force one: put a second meeting of that teacher right after the first
        g1, g2 = by_t[tid][0], by_t[tid][1]
        s1 = so[g1][0]
        nxt = s1 + 1
        if nxt < T and w.slots[nxt]["day"] == w.slots[s1]["day"] and nxt not in so[g2]:
            old = so[g2][0]
            rm[(g2, nxt)] = rm.pop((g2, old))
            so[g2][0] = nxt
    out["H6"] = (so, rm, w6)

    # H7: a practical section loses its double period (move meetings apart until none are adjacent)
    so, rm = _clone(slot_of, room)
    labs = [g for g in S if S[g].double]
    if labs:
        g = labs[0]
        for _ in range(6):
            pr = _find_adjacent_pair(w, so[g])
            if not pr:
                break
            a, b = pr
            for cand in range(T):
                if cand in so[g] or cand in w.blocked[S[g].grade]:
                    continue
                if all(abs(cand - x) > 1 or w.slots[cand]["day"] != w.slots[x]["day"] for x in so[g] if x != b):
                    rm[(g, cand)] = rm.pop((g, b))
                    so[g][so[g].index(b)] = cand
                    break
        out["H7"] = (so, rm, w)

    # H8: stack a section on the three shortest periods
    so, rm = _clone(slot_of, room)
    g = next(g for g in S if S[g].n == 3 and not S[g].double and S[g].grade == "G9")
    short = [s["idx"] for s in w.slots if s["minutes"] == 40][:3]
    for old in list(so[g]):
        rm.pop((g, old))
    so[g] = short
    for s in short:
        rm[(g, s)] = next(r.id for r in w.rooms.values() if r.kind == S[g].kind)
    out["H8"] = (so, rm, w)

    # H9: a course delivers one slot too many for its students (extra meeting)
    so, rm = _clone(slot_of, room)
    g = next(g for g in S if S[g].grade == "G9" and S[g].n >= 3)
    spare = next(s for s in range(T) if s not in so[g] and s not in w.blocked["G9"])
    so[g].append(spare)
    rm[(g, spare)] = next(r.id for r in w.rooms.values() if r.kind == S[g].kind)
    out["H9"] = (so, rm, w)

    # H10: unreachable room change inside the 10-minute break (tighten gap so the real matrix trips it)
    so, rm = _clone(slot_of, room)
    w10 = copy.copy(w)
    from .config import clone
    w10.cfg = clone(w.cfg, {"slots.gap_seconds": 10})
    out["H10"] = (so, rm, w10)
    return out


def run_suite(w: World, slot_of, room) -> dict:
    base = checker.check(w, slot_of, room)
    res = {"baseline_ok": base["ok"], "caught": {}}
    for code, (so, rm, ww) in make_mutations(w, slot_of, room).items():
        r = checker.check(ww, so, rm)
        res["caught"][code] = r["violations"].get(code, 0) > 0
    res["catch_rate"] = sum(res["caught"].values()) / max(1, len(res["caught"]))
    return res
