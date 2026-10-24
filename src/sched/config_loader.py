"""TOML-first config loading. Every tunable lives in src/config/*.toml.

Units warning: the catalog mixes "periods", "teaching periods" and
"credit hrs" with no stated equivalence, and observed grid slots are a
fourth quantity. NOTHING is equated: courses.toml keeps the unit exactly
as stated per entry. The .gpa "weight" is a GPA credit multiplier and is
not a time quantity at all — it never enters scheduling math.
"""
from __future__ import annotations

import tomllib
from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


def load(name: str) -> dict:
    with open(CONFIG_DIR / f"{name}.toml", "rb") as f:
        return tomllib.load(f)


def load_all() -> dict:
    return {p.stem: load(p.stem) for p in sorted(CONFIG_DIR.glob("*.toml"))}


def parity_weight(tag: str, periods_cfg: dict) -> float:
    p = periods_cfg["parity"]
    return {
        "all": p["standard_weight"],
        "even": p["even_only_weight"],
        "odd": p["odd_only_weight"],
        "split": p["even_only_weight"],  # split slots are half Even / half Odd
    }[tag]


def validate(cfg: dict) -> list[str]:
    """Return a list of problems; empty means OK."""
    problems: list[str] = []
    periods = cfg["periods"]
    if len(periods["period"]) != 7:
        problems.append(f"expected 7 periods, got {len(periods['period'])}")
    w = cfg["knobs"]["weights"]
    for k in ("alpha", "beta", "eta", "delta", "theta"):
        if k not in w:
            problems.append(f"knobs.weights missing {k}")
    pop = cfg["population"]
    arch = pop["teacher_archetypes"]
    if abs(sum(a["share"] for a in arch.values()) - 1.0) > 1e-9:
        problems.append("teacher archetype shares do not sum to 1")
    t = pop["tracks"]["G11"]
    if abs(t["AP_share"] + t["IB_share"] - 1.0) > 1e-9:
        problems.append("G11 track shares do not sum to 1")
    return problems
