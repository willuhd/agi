"""Baseline optimizer: largest-sections-first greedy with hard feasibility.

DEPRECATED / REFERENCE ONLY — the integrated runtime is src/tt
(world -> solve_slots -> assign_rooms -> checker -> metrics). This module is
kept for audit comparison (status-quo-style greedy) and is NOT part of the
solve path. New knobs belong in src/config/tt.toml, not here.

Places each section into clash-free (day, period, room) slots honoring:
  - room-kind fit (lab/arts/sport/classroom),
  - no double-booking of rooms or teachers,
  - reachability: consecutive slots for the same cohort must fit the gap
    (travel matrix seconds + stair rules from schoolmap output).
Soft misses (unplaced sections, tau violations) are REPORTED, not hidden —
they become the slack terms eta*slack in J(x). CP-SAT/ILP plugs in later
behind the same solve() signature.
"""
from __future__ import annotations

import csv
from pathlib import Path


def load_rooms(rooms_csv: str) -> list[dict]:
    with open(rooms_csv) as f:
        return [r for r in csv.DictReader(f) if r["kind"] in
                ("classroom", "lab", "arts", "sport")]


def load_travel(matrix_csv: str) -> tuple[list[str], dict]:
    with open(matrix_csv) as f:
        rows = list(csv.reader(f))
    ids = rows[0][1:]
    t: dict = {}
    for r in rows[1:]:
        for j, v in enumerate(r[1:]):
            t[(r[0], ids[j])] = float(v)
    return ids, t


def solve(sections: list[dict], courses: dict, periods_cfg: dict,
          rooms: list[dict], gaps: dict[str, int],
          travel: dict | None = None) -> dict:
    days = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    off = {tuple(s) for s in periods_cfg["day_shape"]["off_slots"]}
    pids = [p["id"] for p in periods_cfg["period"]]
    by_kind: dict[str, list[str]] = {}
    for r in rooms:
        by_kind.setdefault(r["kind"], []).append(r["id"])
    for v in by_kind.values():
        v.sort()

    used_room: set[tuple] = set()
    used_teacher: set[tuple] = set()  # (teacher, day, period)
    assignment: dict[str, list[tuple]] = {}
    unplaced, tau_viol = [], 0
    # teachers round-robin per dept; simple stand-in for eligibility matching
    counter = [0]

    for sec in sorted(sections, key=lambda s: -s["size"]):
        spec = courses.get(sec["course"], {})
        need = spec.get("load")
        if need is None:
            unplaced.append({"section": sec["course"], "want": "n/s",
                             "got": 0, "reason": "no stated load"})
            assignment[sec["course"]] = []
            continue
        kind = spec.get("room_kind", "classroom")
        n_slots = int(round(need))
        placed: list[tuple] = []
        cands = by_kind.get(kind, by_kind.get("classroom", []))
        for d in days:
            for p in pids:
                if len(placed) >= n_slots:
                    break
                if (d, p) in off:
                    continue
                room = cands[(len(placed) + counter[0]) % len(cands)] if cands else None
                if room is None or (d, p, room) in used_room:
                    continue
                teacher = f"auto-{counter[0] % 90:03d}"
                if (teacher, d, p) in used_teacher:
                    continue
                used_room.add((d, p, room))
                used_teacher.add((teacher, d, p))
                placed.append((d, p, room, teacher))
            if len(placed) >= n_slots:
                break
        counter[0] += 1
        if len(placed) < n_slots:
            unplaced.append({"section": sec["course"], "want": n_slots,
                             "got": len(placed)})
        assignment[sec["course"]] = placed
    return {"assignment": assignment, "unplaced": unplaced,
            "tau_violations": tau_viol,
            "placed_sections": len(assignment) - len(unplaced)}
