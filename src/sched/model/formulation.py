"""Loss terms from v2_repaired_formulation.md, parity-aware.

Conventions: losses are per-teacher scalars L_i (lists of floats).
Parity: contact of a slot = slot minutes * parity weight (Even/Odd = 0.5).
"""
from __future__ import annotations


def mean_loss(losses: list[float]) -> float:
    return sum(losses) / len(losses)


def cvar(losses: list[float], q: float) -> float:
    """Mean of the worst (1-q) tail. q=0.8 => mean of worst 20%."""
    if not losses:
        return 0.0
    s = sorted(losses, reverse=True)
    k = max(1, int(len(s) * (1 - q)))
    return sum(s[:k]) / k


def range_spread(losses: list[float]) -> float:
    return max(losses) - min(losses) if losses else 0.0


def group_terms(losses_by_group: dict[str, list[float]], q: float) -> tuple[float, float]:
    """(sum of within-group CVaRs, spread of group means)."""
    cvars = {g: cvar(v, q) for g, v in losses_by_group.items()}
    means = {g: sum(v) / len(v) for g, v in losses_by_group.items() if v}
    spread = max(means.values()) - min(means.values()) if means else 0.0
    return sum(cvars.values()), spread


def churn_l1(assign_now: dict, assign_prev: dict) -> int:
    keys = set(assign_now) | set(assign_prev)
    return sum(1 for k in keys if assign_now.get(k) != assign_prev.get(k))


def expected_repair(scenarios: list[dict], repair_cost: dict[str, float]) -> float:
    """E_xi[Delta(xi)]: prob-weighted repair costs (planner supplies costs)."""
    return sum(s["prob"] * repair_cost.get(s["name"], 0.0) for s in scenarios)


def objective(mean: float, cvar_all: float, group_cvar_sum: float,
             group_spread: float, slack: float, repair: float,
             churn: float, w: dict) -> float:
    g = w.get("group", {})
    return (w["alpha"] * mean + w["beta"] * cvar_all
            + g.get("department", 0) * group_cvar_sum
            + w.get("beta_prime", 0) * group_spread
            + w["eta"] * slack + w["delta"] * repair + w["theta"] * churn)


def contact_ok(load: float, slots: list[dict]) -> bool:
    """True if slot contact matches the stated load. Caller must pass a
    catalog-unit load and same-unit slots — units are never converted.
    slots: [{amount, parity_weight}] where amount is in the load's unit."""
    return abs(sum(s["amount"] * s["parity_weight"] for s in slots)
               - load) < 1e-6


def cohort_moves(day_rooms: list[str]) -> int:
    """Room changes between consecutive periods for one student cohort
    in one day. Teachers moving is free; students moving is priced."""
    return sum(1 for a, b in zip(day_rooms, day_rooms[1:]) if a != b)


def stickiness_cost(cohort_days: list[list[str]], price: float) -> float:
    return price * sum(cohort_moves(d) for d in cohort_days)
