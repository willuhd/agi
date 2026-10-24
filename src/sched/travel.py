"""Single import site for the schoolmap dependency.

schoolmap stays a vendored sibling (src/../schoolmap-1.0.0), never forked
into src/: it owns its rebuild pipeline (floor photos -> model) and its
version pin (buildings.toml). Everything here reads paths from config so a
rebuild can never silently invalidate tau — paths change in one place.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SCHOOLMAP = ROOT / "schoolmap-1.0.0"
sys.path.insert(0, str(SCHOOLMAP))

import schoolmap as _sm  # noqa: E402  (vendored, path above)


def travel_time(a: str, b: str, **scenario) -> float:
    return float(_sm.travel_time(a, b, **scenario))


def route(a: str, b: str, **scenario):
    return _sm.route(a, b, **scenario)


def matrix(ids: list | None = None, **scenario):
    return _sm.matrix(ids, **scenario)


def load_matrix_csv(path: str) -> dict:
    """Raw travel_time_s.csv as {(from, to): seconds} — no numpy needed."""
    with open(path) as f:
        rows = list(csv.reader(f))
    ids = rows[0][1:]
    return {(r[0], ids[j]): float(v)
            for r in rows[1:] for j, v in enumerate(r[1:])}
