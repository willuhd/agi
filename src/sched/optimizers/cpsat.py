"""CP-SAT core optimizer (OR-Tools). The search layer.

DEPRECATED / REFERENCE ONLY — the integrated runtime is src/tt/model.py
(solve_slots + assign_rooms). This single-cohort stickiness demo is kept for
audit/comparison; its travel scorer lives on in
src/sched/analysis/score_solution.py (gap-aware) and its repair pattern in
src/tt/shocks.py (unified energy). New solver work belongs in src/tt.

Scope v1 (explicit):
- Meetings (unit slots) pre-expanded from sections via expand_sections().
- Teacher per meeting is GIVEN (dept-matched upstream); joint
  teacher-timeslot optimization is v2. Teacher no-overlap IS enforced.
- Rooms chosen from kind-matching candidates. Objective: minimize
  distinct (cohort, day, room) triples = student stickiness, the
  4-moves-Monday figure, driven to zero where feasible.
- Travel seconds and preference loss score the RESULT; they are not
  CP-SAT terms in v1 (linearization noted for v2).

Input:
  meetings: [{id, cohort, teacher, room_kind}]
  rooms: {room_id: kind}
  slots: [(day, period)] indexed 0..S-1
  blocked: set of slot indices (off_slots + fixed blocks)
Output: {status, assignment: {meeting_id: (slot, room)}, objective, gap}
"""
from __future__ import annotations

from ortools.sat.python import cp_model


def expand_sections(sections: list[dict], courses: dict,
                    slot_map: dict) -> tuple[list[dict], list[dict]]:
    """sections: [{course, cohort, teacher, size}].
    Returns (meetings, unknown_loads). Rounding: half up per slot_map."""
    factors = slot_map["unit_to_slots"]
    minimum = slot_map["rounding"]["minimum_slots"]
    meetings, unknown = [], []
    mid = 0
    for s in sections:
        spec = courses.get(s["course"], {})
        load, unit = spec.get("load"), spec.get("unit")
        if load is None or unit not in factors:
            unknown.append(s["course"])
            continue
        n = max(minimum, int(load * factors[unit] + 0.5))
        for _ in range(n):
            meetings.append({"id": mid, "cohort": s["cohort"],
                             "teacher": s["teacher"],
                             "room_kind": spec.get("room_kind", "classroom")})
            mid += 1
    return meetings, unknown


def solve(meetings: list[dict], rooms: dict, slots: list,
          blocked: set[int], time_limit_s: float = 30.0,
          room_penalties: dict | None = None,
          max_consecutive: dict | None = None) -> dict:
    days = sorted({d for d, _ in slots})
    day_slots = {d: [i for i, (dd, _) in enumerate(slots) if dd == d]
                 for d in days}
    allowed = [i for i in range(len(slots)) if i not in blocked]
    room_ids = list(rooms)
    rindex = {r: i for i, r in enumerate(room_ids)}
    cand = {m["id"]: [rindex[r] for r, k in rooms.items()
                      if k == m["room_kind"]] or list(range(len(room_ids)))
            for m in meetings}

    model = cp_model.CpModel()
    t = {m["id"]: model.NewIntVarFromDomain(
        cp_model.Domain.FromValues(allowed), f"t{m['id']}") for m in meetings}
    r = {m["id"]: model.NewIntVarFromDomain(
        cp_model.Domain.FromValues(cand[m["id"]]), f"r{m['id']}")
        for m in meetings}

    # shared cohort or teacher -> different slots
    for i, a in enumerate(meetings):
        for b in meetings[i + 1:]:
            if a["cohort"] == b["cohort"] or a["teacher"] == b["teacher"]:
                model.Add(t[a["id"]] != t[b["id"]])
            # same room instance -> different slots
            same = model.NewBoolVar(f"same{a['id']}_{b['id']}")
            model.Add(r[a["id"]] == r[b["id"]]).OnlyEnforceIf(same)
            model.Add(r[a["id"]] != r[b["id"]]).OnlyEnforceIf(same.Not())
            model.Add(t[a["id"]] != t[b["id"]]).OnlyEnforceIf(same)

    # Fatigue hard cap: no teacher works maxc+1 consecutive slots in a day.
    # Consecutive = adjacent periods; the P4->P5 lunch gap breaks all runs.
    if max_consecutive:
        by_teacher: dict = {}
        for m in meetings:
            by_teacher.setdefault(m["teacher"], []).append(m["id"])
        at: dict = {}
        for m in meetings:
            for s in allowed:
                b = model.NewBoolVar(f"at{m['id']}_{s}")
                model.Add(t[m["id"]] == s).OnlyEnforceIf(b)
                model.Add(t[m["id"]] != s).OnlyEnforceIf(b.Not())
                at[(m["id"], s)] = b
        for teacher, mids in by_teacher.items():
            maxc = max_consecutive.get(teacher)
            if not maxc:
                continue
            for d in days:
                # blocked slots break runs (nobody teaches there)
                order = [i for i in day_slots[d] if i not in blocked]
                # runs of consecutive periods split at the lunch gap
                runs, cur = [], [order[0]]
                for a, b in zip(order, order[1:]):
                    pa, pb = slots[a][1], slots[b][1]
                    if pb == pa + 1 and not (pa == 4 and pb == 5):
                        cur.append(b)
                    else:
                        runs.append(cur)
                        cur = [b]
                runs.append(cur)
                for run in runs:
                    for k in range(len(run) - maxc):
                        window = run[k:k + maxc + 1]
                        model.Add(sum(at[(mid, s)] for mid in mids
                                      for s in window) <= maxc)

    # distinct (cohort, day, room): u[c,d,r] = OR over meetings
    cohorts = sorted({m["cohort"] for m in meetings})
    u, u_list = {}, []
    for c in cohorts:
        for d in days:
            for ri in range(len(room_ids)):
                v = model.NewBoolVar(f"u{c}{d}{ri}")
                u[(c, d, ri)] = v
                u_list.append(v)
    for m in meetings:
        for d in days:
            in_day = model.NewBoolVar(f"in{m['id']}{d}")
            model.AddAllowedAssignments([t[m["id"]]],
                                        [(v,) for v in day_slots[d]]
                                        ).OnlyEnforceIf(in_day)
            model.AddForbiddenAssignments(
                [t[m["id"]]], [(v,) for v in day_slots[d]]
                ).OnlyEnforceIf(in_day.Not())
            for ri in range(len(room_ids)):
                is_r = model.NewBoolVar(f"is{m['id']}{ri}")
                model.Add(r[m["id"]] == ri).OnlyEnforceIf(is_r)
                model.Add(r[m["id"]] != ri).OnlyEnforceIf(is_r.Not())
                hit = model.NewBoolVar(f"hit{m['id']}{d}{ri}")
                model.AddBoolAnd([in_day, is_r]).OnlyEnforceIf(hit)
                model.AddBoolOr(
                    [in_day.Not(), is_r.Not()]).OnlyEnforceIf(hit.Not())
                model.Add(u[(m["cohort"], d, ri)] >= hit)
    w_room = room_penalties or {}
    model.Minimize(sum((1 + w_room.get(room_ids[ri], 0)) * u[(c, d, ri)]
                       for c in cohorts for d in days
                       for ri in range(len(room_ids))))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_search_workers = 8
    status = solver.Solve(model)
    name = solver.StatusName(status)
    out = {"status": name, "objective": None, "assignment": {},
           "gap": None}
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        out["objective"] = solver.ObjectiveValue()
        try:
            out["gap"] = solver.BestObjectiveBound()
        except Exception:
            pass
        for m in meetings:
            out["assignment"][m["id"]] = (
                slots[solver.Value(t[m["id"]])], room_ids[solver.Value(r[m["id"]])])
    return out
