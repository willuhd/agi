"""Stair-congestion model. Run: PYTHONPATH=src python -m crowd.model [--event exit]."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

from config import ROOT, load as load_cfg

sys.path.insert(0, str(ROOT / "schoolmap-1.0.0"))
import schoolmap  # noqa: E402  (onboard routing engine, numpy-only)

FLOOR_ORDER = {"B2": -2, "B1": -1, "1F": 0, "2F": 1, "3F": 2, "4F": 3}
GRADES_IN_SCOPE = ("G9", "G10")  # multi-floor grades; G11 is single-floor


def load_solution(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_rooms() -> dict:
    out = {}
    with open(ROOT / "data/building/rooms.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out[r["id"]] = r["floor"]
    return out


def load_via() -> dict:
    """(from_room, to_room) -> [stair ids] from the precomputed routes export."""
    out = {}
    with open(ROOT / "schoolmap-1.0.0/output/routes.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            via = (r["via"] or "").split()
            if via:
                out[(r["from"], r["to"])] = via
    return out


def gap_seconds(cfg: dict, p1: int, p2: int) -> float:
    gaps = cfg["periods"].get("gaps_minutes", {})
    return float(gaps.get(f"{p1}-{p2}", 10 if p2 == p1 + 1 else 70)) * 60.0


def legs_per_break(sol: dict, rooms: dict, lift_share: float, seed: int) -> dict:
    """break -> list of (grade, roomA, roomB, weight). Students weight 1;
    teachers weight (1 - lift_share) since lift users skip the stairs."""
    rng = random.Random(seed)
    out = defaultdict(list)
    rm, sec = sol["room"], sol["sections"]
    slots = {s["idx"]: s for s in sol["slots"]}
    for sid, lst in sol["student_sections"].items():
        grade = sol["students"][sid]["grade"]
        ms = sorted((s, g) for g in lst for s in sol["slot_of"][g])
        for (s1, g1), (s2, g2) in zip(ms, ms[1:]):
            a, b = slots[s1], slots[s2]
            if a["day"] != b["day"] or b["period"] != a["period"] + 1:
                continue
            r1, r2 = rm[f"{g1}|{s1}"], rm[f"{g2}|{s2}"]
            if r1 != r2 and rooms[r1] != rooms[r2]:
                out[(a["day"], a["period"])].append((grade, r1, r2, 1.0))
    by_t = defaultdict(list)
    for g, sl in sol["slot_of"].items():
        for s in sl:
            by_t[sec[g]["teacher"]].append((s, g))
    for lst in by_t.values():
        lst.sort()
        for (s1, g1), (s2, g2) in zip(lst, lst[1:]):
            a, b = slots[s1], slots[s2]
            if a["day"] != b["day"] or b["period"] != a["period"] + 1:
                continue
            r1, r2 = rm[f"{g1}|{s1}"], rm[f"{g2}|{s2}"]
            if r1 != r2 and rooms[r1] != rooms[r2] and rng.random() > lift_share:
                grade = sec[g1].get("grade", "G9")
                out[(a["day"], a["period"])].append((grade, r1, r2, 1.0))
    return out


def slowdown(load: float, cap: float, k: float = 0.5) -> float:
    """Fruin/Weidmann-lite: free flow up to cap persons/break, quadratic
    penalty above. Median normal-operation load sits far below cap."""
    if load <= cap or cap <= 0:
        return 1.0
    return 1.0 + k * (load / cap) ** 2


def alternative(via_list: list, r1: str, r2: str, cache: dict) -> tuple | None:
    """Real alternative route with the primary stair disabled (onboard engine).
    Returns (alt_via, alt_seconds) or None if disconnected."""
    if not via_list:
        return None
    key = (r1, r2, via_list[0])
    if key not in cache:
        try:
            t = schoolmap.travel_time(r1, r2, disabled_connectors=(via_list[0],))
            r = schoolmap.route(r1, r2, disabled_connectors=(via_list[0],))
            stairs = [l.via for l in r.legs if l.kind in ("stair", "elevator") and l.via]
            cache[key] = (stairs, t)
        except Exception:
            cache[key] = None
    return cache[key]


def run(solution: Path, stair_cap: float, split_tau: float, lift_share: float,
        seed: int, event: str | None, grades: tuple) -> dict:
    cfg = load_cfg()
    sol = load_solution(solution)
    rooms = load_rooms()
    via = load_via()
    sec = {}
    with open(ROOT / "schoolmap-1.0.0/output/routes.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            sec[(r["from"], r["to"])] = float(r["seconds"])
    legs = legs_per_break(sol, rooms, lift_share, seed)
    cache: dict = {}
    out_breaks = {}
    for (day, p), items in sorted(legs.items()):
        if event == "exit":
            # single destination: everyone to RECEPTION, no spreading
            dest = "RECEPTION"
            loads: dict = defaultdict(float)
            for grade, r1, r2, w in items:
                v = via.get((r1, dest), via.get((r1, r2), []))
                for s in v:
                    loads[s] += w
            q = {s: max(0.0, (L - stair_cap)) * (600.0 / max(stair_cap, 1)) for s, L in loads.items()}
            out_breaks[f"{day} P{p}->P{p+1}"] = {
                "mode": "exit-drill", "stair_loads": dict(loads), "queue_s": q,
                "slowdown": {}, "rerouted": 0}
            continue
        loads = defaultdict(float)
        scoped = []
        for grade, r1, r2, w in items:
            v = via.get((r1, r2), [])
            scoped.append((grade, r1, r2, w, v))
            if grade in grades:
                for s in v:
                    loads[s] += w
        factors = {s: slowdown(L, stair_cap) for s, L in loads.items()}
        rerouted = 0
        alt_used = defaultdict(int)
        # iterate to convergence: each move must not push a receiving stair
        # past 1.5x capacity (no pile-ups), lottery is content-hashed so it
        # is stable across processes (str-seeded Random is hash-seed dependent)
        for ppass in range(5):
            moved = 0
            for grade, r1, r2, w, v in scoped:
                if grade not in grades or not v:
                    continue
                prim = max((factors.get(s, 1.0), s) for s in v)[1]
                if factors.get(prim, 1.0) <= 1.05:
                    continue
                alt = alternative(v, r1, r2, cache)
                if not alt or not alt[0]:
                    continue
                alt_via, alt_t = alt
                if any(loads.get(s, 0.0) + w > stair_cap * 1.5 for s in alt_via):
                    continue  # receiving stair would saturate: hold
                prim_t = sec.get((r1, r2), alt_t)
                p_alt = 1.0 / (1.0 + math.exp((alt_t - prim_t * factors[prim]) / split_tau))
                draw = random.Random(int(hashlib.md5(f"{r1}|{r2}|{ppass}".encode()).hexdigest(), 16) % 2**32)
                if draw.random() < p_alt * w:
                    for s in v:
                        loads[s] -= w
                    for s in alt_via:
                        loads[s] = loads.get(s, 0.0) + w
                    rerouted += w
                    moved += w
                    alt_used[alt_via[0]] += w
            factors = {s: slowdown(L, stair_cap) for s, L in loads.items() if L > 0}
            if moved == 0:
                break
        out_breaks[f"{day} P{p}->P{p+1}"] = {
            "mode": "normal", "stair_loads": {s: round(L, 1) for s, L in loads.items() if L > 0},
            "slowdown": {s: round(f, 3) for s, f in factors.items()},
            "rerouted": rerouted, "alt_stairs": dict(alt_used)}
    return {"stair_cap": stair_cap, "split_tau_s": split_tau, "lift_share": lift_share,
            "grades_in_scope": list(grades), "event": event,
            "assumptions": ["stair capacity/break unmeasured", "logit tau unmeasured",
                            "walk legs unslowed (wide corridors)", "lift users skip stairs"],
            "breaks": out_breaks}


def main() -> None:
    ap = argparse.ArgumentParser(description="Stair-congestion model on a finished timetable.")
    ap.add_argument("solution", nargs="?", default=str(ROOT / "output/main_solution.json"))
    ap.add_argument("--stair-cap", type=float, default=150.0,
                      help="free-flow persons per stair per 10-min break (Fruin-order stair throughput)")
    ap.add_argument("--split-tau", type=float, default=15.0)
    ap.add_argument("--lift-share", type=float, default=0.85)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--event", default=None, help="'exit' for single-destination drill mode")
    ap.add_argument("--grades", default="G9,G10")
    ap.add_argument("--out", default=str(ROOT / "output/crowd.json"))
    a = ap.parse_args()
    out = run(Path(a.solution), a.stair_cap, a.split_tau, a.lift_share, a.seed,
              a.event, tuple(a.grades.split(",")))
    Path(a.out).write_text(json.dumps(out, indent=1))
    n = len(out["breaks"])
    peak = max(((k, max(v.get("slowdown", {}).values() or [1.0])) for k, v in out["breaks"].items()),
               key=lambda kv: kv[1], default=(None, 1.0))
    print(f"breaks: {n}, peak slowdown: {peak[0]} x{peak[1]:.2f}")


if __name__ == "__main__":
    main()
