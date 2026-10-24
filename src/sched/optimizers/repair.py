"""Repair operator: minimal-energy response to shocks.

Two repairs (the ones the school actually faces):
- teacher quits: staffing fix (eligible, least-loaded replacement) +
  frozen re-solve of that teacher's meetings only.
- student AP->IB (real case): demand shifts to the XMT ledger; ZX sections
  that empty out are dropped, added sections placed; all else frozen.

"solve_incremental" reuses the CP-SAT core pattern but constrains each
re-solved meeting to (slot, room) pairs that are free given frozen
background occupancy. Energy = meetings moved + rooms changed vs original.
"""
from __future__ import annotations

from ortools.sat.python import cp_model


def solve_incremental(new_meetings: list[dict], background: list[dict],
                      rooms: dict, slots: list, blocked: set[int],
                      orig: dict | None = None,
                      time_limit_s: float = 30.0) -> dict:
    """Place new_meetings around frozen background occupancy.
    background: [{slot, room, cohort, teacher}]. orig: mid -> (slot, room)
    for the energy count. Returns {status, assignment, energy}.
    """
    orig = orig or {}
    room_ids = list(rooms)
    rindex = {r: i for i, r in enumerate(room_ids)}
    days = sorted({d for d, _ in slots})
    day_of = [slots[i][0] for i in range(len(slots))]

    def clashes(m, s):
        for b in background:
            if b["slot"] != s:
                continue
            if b["cohort"] == m["cohort"] or b["teacher"] == m["teacher"]:
                return True
        return False

    def room_taken(m, s, r):
        return any(b["slot"] == s and b["room"] == r for b in background)

    model = cp_model.CpModel()
    t, r = {}, {}
    allowed_pairs: dict = {}
    for m in new_meetings:
        pairs = [(s, rindex[rm]) for s in range(len(slots))
                 if s not in blocked and not clashes(m, s)
                 for rm, k in rooms.items()
                 if k == m["room_kind"] and not room_taken(m, s, rm)]
        if not pairs:
            return {"status": "INFEASIBLE", "assignment": {},
                    "energy": None, "reason": f"no free pair for {m['id']}"}
        allowed_pairs[m["id"]] = pairs
        t[m["id"]] = model.NewIntVar(0, len(slots) - 1, f"t{m['id']}")
        r[m["id"]] = model.NewIntVar(0, len(room_ids) - 1, f"r{m['id']}")
        model.AddAllowedAssignments([t[m["id"]], r[m["id"]]], pairs)

    for i, a in enumerate(new_meetings):
        for b in new_meetings[i + 1:]:
            if a["cohort"] == b["cohort"] or a["teacher"] == b["teacher"]:
                model.Add(t[a["id"]] != t[b["id"]])
            same = model.NewBoolVar(f"same{a['id']}_{b['id']}")
            model.Add(r[a["id"]] == r[b["id"]]).OnlyEnforceIf(same)
            model.Add(r[a["id"]] != r[b["id"]]).OnlyEnforceIf(same.Not())
            model.Add(t[a["id"]] != t[b["id"]]).OnlyEnforceIf(same)

    # stickiness + stay-close-to-original
    cohorts = sorted({m["cohort"] for m in new_meetings})
    u = []
    for c in cohorts:
        for d in days:
            for ri in range(len(room_ids)):
                v = model.NewBoolVar(f"u{c}{d}{ri}")
                u.append(v)
                hits = []
                for m in new_meetings:
                    if m["cohort"] != c:
                        continue
                    in_day = model.NewBoolVar(f"in{m['id']}{d}")
                    dslots = [i for i in range(len(slots))
                              if day_of[i] == d]
                    model.AddAllowedAssignments(
                        [t[m["id"]]], [(v,) for v in dslots]
                        ).OnlyEnforceIf(in_day)
                    model.AddForbiddenAssignments(
                        [t[m["id"]]], [(v,) for v in dslots]
                        ).OnlyEnforceIf(in_day.Not())
                    is_r = model.NewBoolVar(f"is{m['id']}{ri}")
                    model.Add(r[m["id"]] == ri).OnlyEnforceIf(is_r)
                    model.Add(r[m["id"]] != ri).OnlyEnforceIf(is_r.Not())
                    hit = model.NewBoolVar(f"hit{m['id']}{d}{ri}")
                    model.AddBoolAnd([in_day, is_r]).OnlyEnforceIf(hit)
                    model.AddBoolOr([in_day.Not(), is_r.Not()]
                                     ).OnlyEnforceIf(hit.Not())
                    hits.append(hit)
                if hits:
                    model.AddMaxEquality(v, hits)
                else:
                    model.Add(v == 0)
    moved = []
    for m in new_meetings:
        if m["id"] in orig:
            oslot, oroom = orig[m["id"]]
            same_s = model.NewBoolVar(f"ss{m['id']}")
            model.Add(t[m["id"]] == oslot).OnlyEnforceIf(same_s)
            model.Add(t[m["id"]] != oslot).OnlyEnforceIf(same_s.Not())
            same_r = model.NewBoolVar(f"sr{m['id']}")
            model.Add(r[m["id"]] == rindex[oroom]).OnlyEnforceIf(same_r)
            model.Add(r[m["id"]] != rindex[oroom]).OnlyEnforceIf(same_r.Not())
            keep = model.NewBoolVar(f"keep{m['id']}")
            model.AddBoolAnd([same_s, same_r]).OnlyEnforceIf(keep)
            model.AddBoolOr([same_s.Not(), same_r.Not()]
                             ).OnlyEnforceIf(keep.Not())
            moved.append(keep.Not())
    model.Minimize(sum(u) + 10 * sum(moved))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_search_workers = 8
    status = solver.Solve(model)
    out = {"status": solver.StatusName(status), "assignment": {},
           "energy": None}
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        asg = {m["id"]: (slots[solver.Value(t[m["id"]])],
                         room_ids[solver.Value(r[m["id"]])])
               for m in new_meetings}
        out["assignment"] = asg
        moves = sum(1 for mid, v in asg.items()
                    if mid in orig and v != orig[mid])
        out["energy"] = {"moved": moves, "total": len(asg)}
    return out


def replacement_teachers(affected: list[dict], teachers: list,
                         background: list[dict]) -> dict:
    """Map quit teacher's meetings -> replacement teacher id.
    Eligible = dept-qualified subject teacher; least-loaded first.
    Availability is enforced later by the solver via background occupancy.
    """
    from collections import Counter
    load = Counter(b["teacher"] for b in background)
    out = {}
    for m in affected:
        dept = {"OBS AP Physics 1": "physics",
                "OBS AP Chemistry": "chemistry"}.get(m.get("course", ""), "")
        cands = [t for t in teachers
                 if t.homeroom is None and (not dept or t.dept == dept)]
        cands.sort(key=lambda t: load.get(t.id, 0))
        if not cands:
            raise ValueError(f"no replacement for meeting {m['id']}")
        out[m["id"]] = cands[0].id
        load[cands[0].id] += 1
    return out


def repair_teacher_quit(assignment: dict, meetings: list[dict],
                        quit_teacher: str, teachers: list, rooms: dict,
                        slots: list, blocked: set[int],
                        time_limit_s: float = 30.0) -> dict:
    """Full teacher-quit flow. Returns new assignment patch + energy."""
    info = {m["id"]: m for m in meetings}
    background = [{"slot": slots.index(sl), "room": rm,
                   "cohort": info[mid]["cohort"],
                   "teacher": info[mid]["teacher"]}
                  for mid, (sl, rm) in assignment.items()
                  if info[mid]["teacher"] != quit_teacher]
    affected = [dict(info[mid], teacher=None) for mid, _ in assignment.items()
                if info[mid]["teacher"] == quit_teacher]
    repl = replacement_teachers(affected, teachers, background)
    for m in affected:
        m["teacher"] = repl[m["id"]]
    sidx = {s: i for i, s in enumerate(slots)}
    orig = {mid: (sidx[sl], rm) for mid, (sl, rm) in assignment.items()
            if mid in repl}
    res = solve_incremental(affected, background, rooms, slots, blocked,
                            orig, time_limit_s)
    res["replacements"] = repl
    return res


def repair_student_move(students: list, student_id: str, to_track: str,
                        teachers: list, dmap: dict, floor: int) -> dict:
    """Move one student AP->IB (or reverse): re-aggregate demand and report
    the section diff. Dropped sections free meetings; added sections are
    returned for incremental placement. Energy = sections touched."""
    from sched.simulation.population import aggregate_demand
    before, _, _ = aggregate_demand(students, teachers, dmap, floor)
    target = next(s for s in students if s.id == student_id)
    target.track = to_track
    if to_track == "IB":
        target.modules = {}
    after, _, _ = aggregate_demand(students, teachers, dmap, floor)
    key = lambda s: (s["course"], s["cohort"])
    bmap, amap = {key(s): s for s in before}, {key(s): s for s in after}
    dropped = [k for k in bmap if k not in amap]
    added = [k for k in amap if k not in bmap]
    shrunk = [k for k in bmap if k in amap
              and amap[k]["size"] < bmap[k]["size"]]
    return {"dropped": dropped, "added": added, "shrunk": shrunk,
            "energy": {"dropped": len(dropped), "added": len(added),
                       "shrunk": len(shrunk)}}
