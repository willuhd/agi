"""Config for the full-school pipeline: src/config/tt.toml + periods.toml, with dotted overrides."""
from __future__ import annotations

import copy
import tomllib
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent
ROOT = SRC.parent
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]


def load(overrides: dict | None = None) -> dict:
    with open(SRC / "config" / "tt.toml", "rb") as f:
        cfg = tomllib.load(f)
    with open(SRC / "config" / "periods.toml", "rb") as f:
        cfg["periods"] = tomllib.load(f)
    for k, v in (overrides or {}).items():
        d = cfg
        parts = k.split(".")
        for p in parts[:-1]:
            d = d[p]
        d[parts[-1]] = v
    return cfg


def clone(cfg: dict, overrides: dict) -> dict:
    out = copy.deepcopy(cfg)
    for k, v in overrides.items():
        d = out
        parts = k.split(".")
        for p in parts[:-1]:
            d = d[p]
        d[parts[-1]] = v
    return out


def slot_table(cfg: dict) -> list[dict]:
    """All grid slots (day, period) that exist. index = position in list."""
    off = {tuple(x) for x in cfg["slots"]["off"]}
    mins = {p["id"]: p["minutes"] for p in cfg["periods"]["period"]}
    out = []
    for d in DAYS:
        for p in sorted(mins):
            if (d, p) in off:
                continue
            out.append({"day": d, "period": p, "minutes": mins[p]})
    for i, s in enumerate(out):
        s["idx"] = i
    return out


def minutes_band(n: int, nom: float, cfg: dict) -> tuple[float, float]:
    """Allowed weekly minutes for an n-slot course: nominal +- max(tol*nominal, granularity floor).
    The floor exists because periods are 40-60 min: a 1-slot course cannot be within 8% of 46 min."""
    tol = cfg["solve"]["minutes_tol"]
    half = max(tol * n * nom, cfg["solve"]["minutes_floor"])
    return n * nom - half, n * nom + half
