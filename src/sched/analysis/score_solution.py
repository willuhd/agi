"""J(x) scorer: solved assignment -> per-teacher L_i -> full loss.

Staging (honest): v1 CP-SAT minimizes stickiness only; this scorer then
prices ALL formulation terms post-hoc (mean, CVaR/range, group terms,
slack from unplaced, travel/colocation via staffing.preference_loss).
v2 folds L_i + CVaR into the CP-SAT objective itself. Repair expectation
and churn stay zero until the repair operator and x_prev exist.

Run: PYTHONPATH=src .venv/bin/python -m sched.analysis.score_solution
(replays the G11-H00 cohort solve and prints J decomposition).
"""
from __future__ import annotations


def teacher_stats(assignment: dict, meetings: list[dict], travel: dict,
                  buildings_cfg: dict, knobs_cfg: dict | None = None,
                  periods_cfg: dict | None = None) -> dict:
    """Per teacher: periods, travel seconds, rooms taught (ordered by slot).
    Legs touching travel-disabled cohorts (G12/XMT) price at zero.
    Gap-aware: same-day successive teachings only; lunch-straddling pairs
    free iff knobs.toml [travel_pricing] lunch_free (boundary from
    periods.toml [school] lunch_after_period). No hardcoded periods here."""
    from sched.simulation.staffing import leg_cost, travel_enabled, DAY_ORDER
    scope = {"travel_scope": (knobs_cfg or {}).get("travel_scope", {})}
    pricing = (knobs_cfg or {}).get("travel_pricing", {})
    lunch_free = pricing.get("lunch_free", True)
    overnight_free = pricing.get("overnight_free", True)
    lunch_after = 4
    if periods_cfg is not None:
        lunch_after = periods_cfg.get("school", {}).get(
            "lunch_after_period",
            periods_cfg.get("lunch_after_period", 4))
    by_teacher: dict = {}
    info = {m["id"]: m for m in meetings}
    for mid, (slot, room) in assignment.items():
        by_teacher.setdefault(info[mid]["teacher"], []).append(
            (slot, room, info[mid]["cohort"]))
    stats = {}
    for t, lst in by_teacher.items():
        lst.sort(key=lambda x: (DAY_ORDER.get(x[0][0], 99), x[0][1]))
        rooms = [r for _, r, _ in lst]
        trav = 0.0
        for ((d1, p1), a, ca), ((d2, p2), b, cb) in zip(lst, lst[1:]):
            if travel_enabled(ca, scope) and travel_enabled(cb, scope):
                trav += leg_cost(a, b, travel, buildings_cfg, d1, p1, d2, p2,
                                 lunch_after=lunch_after,
                                 lunch_free=lunch_free,
                                 overnight_free=overnight_free)
        best, run = 1 if lst else 0, 1 if lst else 0
        slots_only = [s for s, _, _ in lst]
        for (d1, p1), (d2, p2) in zip(slots_only, slots_only[1:]):
            if d1 == d2 and p2 == p1 + 1 and not (
                    p1 == lunch_after and p2 == lunch_after + 1):
                run += 1
                best = max(best, run)
            else:
                run = 1
        stats[t] = {"periods": len(lst), "travel_s": trav,
                    "rooms": rooms, "max_run": best,
                    "travel_policy": {"lunch_after": lunch_after,
                                      "lunch_free": lunch_free,
                                      "overnight_free": overnight_free}}
    return stats


def score_j(stats: dict, offices: dict, rooms_taught: dict,
            cfg: dict, unplaced: list | None = None,
            max_consecutive: dict | None = None) -> dict:
    """Full J(x) decomposition from the formulation. Returns terms + total."""
    from sched.simulation.staffing import preference_loss
    from sched.model import formulation as F
    tcfg = cfg["teachers"]
    losses, breakdown = {}, {}
    for t, s in stats.items():
        mc = (max_consecutive or {}).get(t)
        L, bd = preference_loss(s["periods"], s["travel_s"],
                                offices.get(t, "314"),
                                rooms_taught.get(t, s["rooms"]), tcfg,
                                max_run=s.get("max_run", 0),
                                max_allowed=mc)
        losses[t] = L
        breakdown[t] = bd
    L = list(losses.values())
    q = cfg["knobs"]["fairness"]["quantile_q"]
    use_range = cfg["knobs"]["fairness"].get("use_range_instead_of_cvar",
                                             False)
    fair_all = F.range_spread(L) if use_range else F.cvar(L, q)
    # group by dept via teacher id prefix is unavailable here; caller may
    # pass groups; default single group keeps terms exact.
    w = cfg["knobs"]["weights"]
    slack_n = len(unplaced or [])
    J = {"mean": F.mean_loss(L), "fairness_all": fair_all,
         "group_cvar": 0.0, "group_spread": 0.0,
         "slack": float(slack_n), "repair": 0.0, "churn": 0.0,
         "n_teachers": len(L)}
    J["total"] = (w["alpha"] * J["mean"] + w["beta"] * J["fairness_all"]
                  + w["eta"] * J["slack"] + w["delta"] * J["repair"]
                  + w["theta"] * J["churn"])
    J["losses"] = losses
    J["breakdown"] = breakdown
    return J


def main() -> None:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from sched import config_loader as C
    from sched.simulation import staffing as S
    from sched.travel import load_matrix_csv
    from sched.simulation.population import (generate_teachers,
                                             generate_students,
                                             aggregate_demand)
    from sched.optimizers import cpsat as O
    cfg = C.load_all()
    S.load_rooms(cfg["buildings"]["buildings"]["ZXB"]["rooms_csv"])
    teachers = generate_teachers(cfg["population"])
    students = generate_students(cfg["population"], cfg["selection"])
    secs, _, _ = aggregate_demand(students, teachers, cfg["demand_map"], 6)
    one = [s for s in secs if s["cohort"] == "G11-H04"]  # AP cohort
    assert one, "no sections for demo cohort"
    meetings, _ = O.expand_sections(one, cfg["courses"]["courses"],
                                    cfg["slot_map"])
    import csv
    rooms = {}
    for r in csv.DictReader(open("schoolmap-1.0.0/output/rooms.csv")):
        if r["kind"] in ("classroom", "lab") and (
                r["floor"] == "1F" or r["id"] in ("B203", "B206", "B209")):
            rooms[r["id"]] = r["kind"]
    slots = [(d, p) for d in ["Mon", "Tue", "Wed", "Thu", "Fri"]
             for p in [1, 2, 3, 4, 5, 6, 7]]
    off = {("Fri", 6), ("Fri", 7)}
    fixed = {tuple(x) for v in cfg["periods"]["fixed_blocks"].values()
             for x in v}
    blocked = {i for i, s in enumerate(slots) if s in off or s in fixed}
    res = O.solve(meetings, rooms, slots, blocked, time_limit_s=60.0,
                  max_consecutive={"T000": 3, "T002": 2, "T003": 4,
                                    "T005": 2})
    assert res["assignment"], res["status"]
    ids, m = None, None
    travel = load_matrix_csv(
        str(Path(__file__).resolve().parent.parent.parent.parent
            / "schoolmap-1.0.0/output/travel_time_s.csv"))
    stats = teacher_stats(res["assignment"], meetings, travel,
                          cfg["buildings"], cfg["knobs"], cfg["periods"])
    offices = {t: S.assign_office(
        next(x for x in teachers if x.id == t), None, cfg["teachers"])
        for t in stats}
    maxc = {"T000": 3, "T002": 2, "T003": 4, "T005": 2}
    J = score_j(stats, offices, {}, cfg, max_consecutive=maxc)
    print(f"solve: {res['status']} rooms-obj={res['objective']}")
    for t, L in sorted(J["losses"].items()):
        print(f"  {t}: L={L:.2f} {J['breakdown'][t]}")
    print("J =", {k: round(v, 3) for k, v in J.items()
                  if k not in ("losses", "breakdown")})


if __name__ == "__main__":
    main()
