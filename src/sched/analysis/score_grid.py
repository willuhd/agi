"""Old-vs-new harness: score the CURRENT grid, the thing we must beat.

Reads src/data/current_grid.toml (hand-encoded apschedule.png) and reports
the same J-terms the optimizer minimizes: student moves, travel seconds
(schoolmap matrix), contact vs stated loads, teacher daily loads.
Run: PYTHONPATH=src .venv/bin/python -m sched.analysis.score_grid
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def load_travel(path: str) -> dict:
    with open(path) as f:
        rows = list(csv.reader(f))
    ids = rows[0][1:]
    t = {}
    for r in rows[1:]:
        for j, v in enumerate(r[1:]):
            t[(r[0], ids[j])] = float(v)
    return t


def main() -> None:
    import tomllib
    root = Path(__file__).resolve().parent.parent.parent
    grid = tomllib.load(open(root / "data/current_grid.toml", "rb"))["slot"]
    cfg_travel = load_travel(str(root.parent / "schoolmap-1.0.0/output/travel_time_s.csv"))
    days = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    by_day: dict = {d: [] for d in days}
    for s in grid:
        w = {"all": 1.0, "even": 0.5, "odd": 0.5}[s.get("parity", "all")]
        by_day[s["day"]].append((s["period"], s["room"], w, s["course"]))
    total_moves, total_travel = 0.0, 0.0
    contact: dict = {}
    for d in days:
        seq = sorted(by_day[d])
        rooms = [r for _, r, _, _ in seq]
        total_moves += sum(1 for a, b in zip(rooms, rooms[1:]) if a != b)
        for (p1, r1, w1, _), (p2, r2, w2, _) in zip(seq, seq[1:]):
            if r1 != r2 and (r1, r2) in cfg_travel:
                total_travel += cfg_travel[(r1, r2)] * min(w1, w2)
        for _, _, w, c in seq:
            contact[c] = contact.get(c, 0.0) + w
    print(f"student room-changes (two-week mean): {total_moves:.1f}")
    print(f"inter-room travel (two-week mean, s): {total_travel:.0f}")
    print("contact slots by course (two-week mean):")
    for c, n in sorted(contact.items()):
        print(f"  {c}: {n}")
    from collections import Counter
    tl: Counter = Counter()
    for s in grid:
        w = {"all": 1.0, "even": 0.5, "odd": 0.5}[s.get("parity", "all")]
        tl[(s["day"], s["teacher"])] += w
    print("max teacher slots/day:", max(tl.values()))
    print("teacher-days over 4 slots:",
          sorted([k for k, v in tl.items() if v > 4]))


if __name__ == "__main__":
    main()
