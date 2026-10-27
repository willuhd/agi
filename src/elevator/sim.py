"""Break-by-break lift simulation. Run: PYTHONPATH=src python -m elevator.sim."""

from __future__ import annotations

import argparse
import csv
import json
import random
from collections import defaultdict
from pathlib import Path

from config import ROOT, load as load_cfg

FLOOR_ORDER = {"B2": -2, "B1": -1, "1F": 0, "2F": 1, "3F": 2, "4F": 3}


def load_solution(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_rooms() -> dict:
    out = {}
    with open(ROOT / "data/building/rooms.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out[r["id"]] = r["floor"]
    return out


def load_timing() -> dict:
    bm = json.loads((ROOT / "data/building/building_model.json").read_text(encoding="utf-8"))
    return bm["timing"]["elevator"]  # wait_s / per_floor_s / door_s (spec defaults, unmeasured)


def gap_seconds(cfg: dict, p1: int, p2: int) -> float:
    gaps = cfg["periods"].get("gaps_minutes", {})
    return float(gaps.get(f"{p1}-{p2}", 10 if p2 == p1 + 1 else 70)) * 60.0


def teacher_legs(sol: dict, rooms: dict, share: float, seed: int) -> dict:
    """break_key -> list of (teacher, floor_from, floor_to). One break = same-day
    consecutive periods (p, p+1); lunch pairs excluded by the caller via gap."""
    rng = random.Random(seed)
    by_teacher = defaultdict(list)
    for g, sl in sol["slot_of"].items():
        for s in sl:
            by_teacher[sol["sections"][g]["teacher"]].append((s, g))
    out = defaultdict(list)
    for tid, lst in by_teacher.items():
        lst.sort()
        for (s1, g1), (s2, g2) in zip(lst, lst[1:]):
            a, b = sol["slots"][s1], sol["slots"][s2]
            if a["day"] != b["day"] or b["period"] != a["period"] + 1:
                continue
            fa, fb = rooms[sol["room"][f"{g1}|{s1}"]], rooms[sol["room"][f"{g2}|{s2}"]]
            if fa == fb:
                continue
            if rng.random() < share:
                out[(a["day"], a["period"])].append((tid, fa, fb))
    return out


def simulate_break(reqs: list, gap: float, timing: dict, capacity: int,
                    rest: list, seed: int) -> dict:
    """Pooled FIFO queue, 2 cars with collective control. Cars start at
    ``rest`` floors (order values); empty travel to pickup costs per_floor_s
    per floor (no doors); a loaded trip takes up to ``capacity`` waiting
    passengers, costs door + per_floor_s * span + door, and rests at the
    farthest drop. Collective control: a car is never dispatched empty to a
    pickup floor where the other car is already heading with spare room --
    no double-dispatch to the same hall call (shared_avoided counts these).
    Returns waits, rides, misses (board + ride > gap) plus the trip log
    (car trajectories for the visual)."""
    import heapq
    rng = random.Random(seed)
    arr = sorted((rng.uniform(0, 45.0), tid, fa, fb) for tid, fa, fb in reqs)
    cars = [{"floor": r, "target": None, "spare": 0} for r in rest]
    free_at = [(0.0, c) for c in range(len(cars))]
    heapq.heapify(free_at)
    waits, rides, missed, trips, avoided = [], [], 0, [], 0
    i = 0
    waiting = []  # arrived, not yet boarded
    while i < len(arr) or waiting:
        ft, c = heapq.heappop(free_at)
        if not waiting:
            # jump to next arrival; car idles (stays where it rests)
            start = max(ft, arr[i][0])
        else:
            start = ft
        while i < len(arr) and arr[i][0] <= start:
            waiting.append(arr[i])
            i += 1
        if not waiting:
            heapq.heappush(free_at, (start, c))
            continue
        batch = waiting[:capacity]
        pickup = FLOOR_ORDER[batch[0][2]]
        o = 1 - c if len(cars) == 2 else None
        if o is not None and cars[o]["target"] == pickup and cars[o]["spare"] >= len(batch):
            # other car already serving this hall call with room: hold
            avoided += 1
            heapq.heappush(free_at, (start + 1.0, c))
            continue
        waiting = waiting[capacity:]
        empty = timing["per_floor_s"] * abs(cars[c]["floor"] - pickup)
        span = max(abs(FLOOR_ORDER[fb] - pickup) for _, _, _, fb in batch)
        ride = timing["door_s"] + timing["per_floor_s"] * max(span, 1) + timing["door_s"]
        board = start + empty
        for t0, tid, fa, fb in batch:
            waits.append(max(0.0, board - t0))
            rides.append(ride)
            if board + ride > gap:
                missed += 1
        drop = max(FLOOR_ORDER[fb] for _, _, _, fb in batch)
        cars[c]["floor"] = drop
        cars[c]["target"] = pickup
        cars[c]["spare"] = capacity - len(batch)
        trips.append({"car": c, "t_board": round(board, 1), "pickup": pickup,
                      "drop": drop, "t_free": round(board + ride, 1)})
        heapq.heappush(free_at, (board + ride, c))
    return {"requests": len(reqs), "avg_wait_s": sum(waits) / len(waits) if waits else 0.0,
            "p95_wait_s": sorted(waits)[min(len(waits) - 1, int(len(waits) * 0.95))] if waits else 0.0,
            "missed": missed, "shared_avoided": avoided, "trips": trips}


def main() -> None:
    ap = argparse.ArgumentParser(description="Lift-queue simulation on a finished timetable.")
    ap.add_argument("solution", nargs="?", default=str(ROOT / "output/main_solution.json"))
    ap.add_argument("--share", type=float, default=0.85, help="P(teacher takes lift on a floor-changing leg)")
    ap.add_argument("--capacity", type=int, default=8, help="assumed car capacity")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--rest", default="1F,3F", help="initial car rest floors, comma separated")
    ap.add_argument("--out", default=str(ROOT / "output/elevator_sim.json"))
    a = ap.parse_args()
    cfg = load_cfg()
    sol = load_solution(a.solution)
    rooms = load_rooms()
    timing = load_timing()
    rest = [FLOOR_ORDER[f.strip()] for f in a.rest.split(",")]
    while len(rest) < 2:
        rest = rest + rest
    legs = teacher_legs(sol, rooms, a.share, a.seed)
    # slot lookup: (day, period) -> idx, then gap to next period
    by_dp = {(s["day"], s["period"]): s["idx"] for s in sol["slots"]}
    breaks = {}
    for (day, p), reqs in sorted(legs.items()):
        g = gap_seconds(cfg, p, p + 1)
        if g > 3600:  # lunch: no queue forms
            continue
        r = simulate_break(reqs, g, timing, a.capacity, rest, a.seed + p)
        r["gap_s"] = g
        breaks[f"{day} P{p}->P{p+1}"] = r
    tot_req = sum(b["requests"] for b in breaks.values())
    tot_miss = sum(b["missed"] for b in breaks.values())
    peak = max(breaks.items(), key=lambda kv: kv[1]["avg_wait_s"]) if breaks else (None, {})
    out = {"share": a.share, "capacity": a.capacity, "seed": a.seed, "rest": a.rest,
           "timing_src": "data/building/building_model.json (spec defaults, unmeasured)",
           "total_lift_requests": tot_req, "total_missed": tot_miss,
           "peak_break": peak[0], "breaks": breaks}
    Path(a.out).write_text(json.dumps(out, indent=1))
    print(f"breaks with lift demand: {len(breaks)}, requests: {tot_req}, missed: {tot_miss}")
    print(f"peak: {peak[0]} avg_wait {peak[1].get('avg_wait_s', 0):.1f}s "
          f"p95 {peak[1].get('p95_wait_s', 0):.1f}s (gap {peak[1].get('gap_s', 0):.0f}s)")


if __name__ == "__main__":
    main()
