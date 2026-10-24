"""Course loads from the catalog master extract + credit->slot calibration.

Per the user's ruling the catalog/.gpa credit is the load source. Credits are NOT assumed to equal
slots: the factor k is fitted on the courses where the real grid is observed (apschedule.png) and
carried as a band for sensitivity.
"""
from __future__ import annotations

import re
from pathlib import Path

from .config import ROOT

CATALOG_MD = ROOT / "docs" / "catalog_full_extract.md"
_NUM = re.compile(r"\*\*(\d+(?:\.\d+)?)")


def parse_catalog(path: Path = CATALOG_MD) -> dict[str, float | None]:
    """{course name: first bold credit load or None}. Cells like '4.0 (G10) / 6.0 (G11)' keep the first."""
    out: dict[str, float | None] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or line.startswith("|---") or line.startswith("| Course"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 6:
            continue
        m = _NUM.search(cells[4])
        out[cells[0]] = float(m.group(1)) if m else None
    return out


def fit_k(cfg: dict) -> float:
    """Through-origin least squares: observed_slots ~ k * credit."""
    pairs = cfg["calibration"]["pairs"]
    num = sum(c * o for c, o in pairs)
    den = sum(c * c for c, _ in pairs)
    return num / den


def get_k(cfg: dict) -> float:
    k = cfg["loads"]["k"]
    return fit_k(cfg) if k == "auto" else float(k)


def credits_to_slots(credit: float, cfg: dict) -> int:
    k = get_k(cfg)
    x = credit * k
    n = int(x + 0.5) if cfg["loads"]["rounding"] == "half_up" else round(x)
    return max(cfg["loads"]["min_slots"], n)
