"""Teacher offices + preference loss L_i (soft costs for the optimizer).

Office assignment (hard pins win):
  homeroom teacher (any track incl. IB-only) -> grade office (406/210/110)
  else -> dept default from teachers.toml

Preference loss L_i(S_i; gamma_i): priced soft terms —
  load deviation vs target, travel seconds, office/teaching colocation.
Cross-building (ZX<->XMT) legs have no metric model (schoolmap is ZX-only):
  priced as multiplier * base_cross_seconds (both ASSUMPTIONS in TOML).
"""
from __future__ import annotations

FLOOR_OF = {}  # room_id -> floor label; filled by load_rooms()


def load_rooms(rooms_csv: str) -> dict:
    import csv
    with open(rooms_csv) as f:
        for r in csv.DictReader(f):
            FLOOR_OF[r["id"]] = r["floor"]
    return FLOOR_OF


def floor_index(floor: str) -> int:
    order = {"B2": -2, "B1": -1, "1F": 0, "2F": 1, "3F": 2, "4F": 3}
    return order.get(floor, 0)


def assign_office(teacher, homeroom_grade: str | None,
                  cfg: dict) -> str:
    """Homeroom pin beats everything — including the IB-only edge case.
    G11AP/G11IB both strip to the G11 pin (110). G12 lives in XMT
    (unmodeled): office recorded as the XMT pseudo-room."""
    if homeroom_grade:
        pins = cfg["homeroom"]["pins"]
        if homeroom_grade in pins:
            return pins[homeroom_grade]
        if homeroom_grade[:3] in pins:
            return pins[homeroom_grade[:3]]
        return "XMT"
    return cfg["dept_offices"].get(teacher.dept, "314")


def travel_enabled(cohort: str, cfg: dict) -> bool:
    """Distance travel is priced only for modeled buildings.
    G12 runs in XMT (no metric model) — travel disabled by policy."""
    scope = cfg.get("travel_scope", {}).get("grades", ["G9", "G10", "G11"])
    return cohort.split("-")[0] in scope


def predominant_floor(room_ids: list[str]) -> str | None:
    zx = [r for r in room_ids if not r.startswith("XMT")]
    if not zx:
        return None
    from collections import Counter
    return Counter(FLOOR_OF.get(r, "?") for r in zx).most_common(1)[0][0]


def leg_seconds(a: str, b: str, travel: dict | None,
                buildings_cfg: dict) -> float:
    """ZX<->ZX via schoolmap matrix; anything touching XMT via multiplier."""
    if a.startswith("XMT") or b.startswith("XMT"):
        t = buildings_cfg["travel"]
        return t["cross_building_multiplier"] * t.get("base_cross_seconds", 60)
    if travel and (a, b) in travel:
        return float(travel[(a, b)])
    return 60.0  # unknown ZX pair fallback


DAY_ORDER = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4}


def straddles_lunch(d1: str, p1: int, d2: str, p2: int,
                    lunch_after: int = 4) -> bool:
    """Same-day successive teachings spanning the lunch break.

    Lunch boundary comes from periods.toml [school] lunch_after_period
    (caller threads it through); never hardcoded at the call site.
    Covers target->target+1 as well as wider spans (e.g. P4->P6 when P5 free).
    """
    return d1 == d2 and p1 <= lunch_after and p2 > lunch_after


def leg_cost(a: str, b: str, travel: dict | None, buildings_cfg: dict,
             d1: str | None = None, p1: int | None = None,
             d2: str | None = None, p2: int | None = None,
             lunch_after: int = 4, lunch_free: bool = True,
             overnight_free: bool = True) -> float:
    """Gap-aware leg cost. Policy flags come from knobs.toml [travel_pricing]
    and periods.toml lunch_after_period — no hardcoded periods in code."""
    if d1 is not None and d2 is not None:
        if d1 != d2:
            return (0.0 if overnight_free else leg_seconds(a, b, travel,
                                                           buildings_cfg))
        if (p1 is not None and p2 is not None and lunch_free
                and straddles_lunch(d1, p1, d2, p2, lunch_after)):
            return 0.0
    return leg_seconds(a, b, travel, buildings_cfg)


def preference_loss(periods: int, travel_s: float, office: str,
                    rooms_taught: list[str], cfg: dict,
                    max_run: int = 0,
                    max_allowed: int | None = None) -> tuple[float, dict]:
    """Return (L_i, breakdown). Higher = more dissatisfied.
    Fatigue: each period beyond max_allowed in the longest same-day run
    is priced (soft); the solver enforces the cap as a hard constraint."""
    load, trav, coloc = cfg["load"], cfg["travel"], cfg.get("homeroom", {})
    tgt = load["target_periods"]
    if periods > tgt:
        load_cost = (periods - tgt) * load["overload_price"]
    else:
        load_cost = (tgt - periods) * load["underload_price"]
    travel_cost = travel_s * trav["price_per_second"]
    pred = predominant_floor(rooms_taught)
    if pred and office in FLOOR_OF:
        gap = abs(floor_index(FLOOR_OF[office]) - floor_index(pred))
        coloc_cost = gap * trav["colocation_price_per_floor"]
    else:
        coloc_cost = 0.0  # XMT-only teaching: no ZX floor to compare
    if max_allowed is not None:
        fatigue_cost = (max(0, max_run - max_allowed)
                        * cfg.get("fatigue", {})
                        .get("price_per_extra_consecutive", 0.0))
    else:
        fatigue_cost = 0.0
    total = load_cost + travel_cost + coloc_cost + fatigue_cost
    return total, {"load": load_cost, "travel": travel_cost,
                   "colocation": coloc_cost, "fatigue": fatigue_cost}
