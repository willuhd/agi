"""Runtime API: load building_model.json and answer room-to-room travel questions.

    >>> from schoolmap import Building
    >>> b = Building.load("output/building_model.json")
    >>> b.travel_time("101", "B216")          # seconds, deterministic
    >>> r = b.route("101", "B216")            # full itinerary (legs, stairs, polylines)
    >>> ids, T = b.matrix()                   # all-pairs seconds (numpy, rooms x rooms)

No image processing happens here; the JSON is the complete, self-contained model.
Travel time = horizontal walking length / walk speed  +  per-floor stair time
(15 s up, 10 s down by default).  Routes are optimal over every stair combination.
"""
from __future__ import annotations

import heapq
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


DEFAULT_MODEL = Path(__file__).with_name("data") / "building_model.json"


@dataclass
class Leg:
    kind: str                 # "walk" | "stair" | "elevator"
    floor: str                # floor of a walk leg, "A->B" for vertical legs
    frm: str
    to: str
    seconds: float
    metres: float = 0.0
    path: list = field(default_factory=list)   # [[x, y], ...] metres (walk legs)
    via: str = ""             # connector id for vertical legs


@dataclass
class Route:
    origin: str
    destination: str
    seconds: float
    walk_m: float
    walk_s: float
    vertical_s: float
    floors_up: int
    floors_down: int
    legs: list

    def to_dict(self) -> dict:
        return {"from": self.origin, "to": self.destination, "seconds": round(self.seconds, 2),
                "walk_m": round(self.walk_m, 2), "walk_s": round(self.walk_s, 2), "stairs_s": round(self.vertical_s, 2),
                "floors_up": self.floors_up, "floors_down": self.floors_down,
                "legs": [{"kind": l.kind, "floor": l.floor, "seconds": round(l.seconds, 2), "metres": round(l.metres, 2),
                          "via": l.via, "path": l.path} for l in self.legs]}

    def summary(self) -> str:
        parts = []
        for lg in self.legs:
            if lg.kind == "walk":
                parts.append(f"walk {lg.metres:.0f} m on {lg.floor}")
            else:
                parts.append(f"{lg.via} {lg.floor}")
        return f"{self.origin} -> {self.destination}: {self.seconds:.0f} s  (" + ", ".join(parts) + ")"


class Building:
    def __init__(self, model: dict, walk_speed: float | None = None, elevator: bool | None = None,
                 stair_up_s: float | None = None, stair_down_s: float | None = None,
                 disabled_connectors: tuple = ()):
        self.model = model
        t = model["timing"]
        self.speed = float(walk_speed or t["walk_speed_mps"])
        self.up_s = float(stair_up_s if stair_up_s is not None else t["stair_up_s_per_floor"])
        self.down_s = float(stair_down_s if stair_down_s is not None else t["stair_down_s_per_floor"])
        self.elev = dict(t["elevator"])
        if elevator is not None:
            self.elev["enabled"] = elevator
        self.floor_order = [f["id"] for f in sorted(model["floors"], key=lambda f: f["level"])]
        self.level = {f["id"]: f["level"] for f in model["floors"]}
        self.rooms = {}
        for f in model["floors"]:
            for r in f["rooms"]:
                self.rooms[r["id"]] = {**r, "floor": f["id"]}
        self._build_graph(set(disabled_connectors))

    @classmethod
    def load(cls, path=None, **kw) -> "Building":
        """Load a built model (default: the one bundled inside the package)."""
        path = Path(path) if path else DEFAULT_MODEL
        with open(path, encoding="utf-8") as fh:
            return cls(json.load(fh), **kw)

    # ------------------------------------------------------------------
    def _build_graph(self, disabled):
        adj: dict[str, list] = {}

        def add(a, b, s, leg):
            adj.setdefault(a, []).append((b, s, leg))

        for fid, legs in self.model["legs"].items():
            for key, lg in legs.items():
                a, b = key.split("|")
                if any(n.startswith("C:") and not self._conn_on(n, disabled) for n in (a, b)):
                    continue
                s = lg["m"] / self.speed
                add(a, b, s, ("walk", fid, lg, False))
                add(b, a, s, ("walk", fid, lg, True))
        for c in self.model["connectors"]:
            if not self._conn_ok(c, disabled):
                continue
            fl = [f for f in self.floor_order if f in c["floors"]]
            if c["type"] == "stair":
                for lo, hi in zip(fl, fl[1:]):
                    n_lo, n_hi = f"C:{c['id']}@{lo}", f"C:{c['id']}@{hi}"
                    dl = self.level[hi] - self.level[lo]
                    add(n_lo, n_hi, self.up_s * dl, ("stair", f"{lo}->{hi}", c["id"], dl))
                    add(n_hi, n_lo, self.down_s * dl, ("stair", f"{hi}->{lo}", c["id"], -dl))
            elif c["type"] == "elevator":
                e = self.elev
                for i, a in enumerate(fl):
                    for b in fl[i + 1:]:
                        dl = abs(self.level[b] - self.level[a])
                        s = e["wait_s"] + e["door_s"] + e["per_floor_s"] * dl
                        add(f"C:{c['id']}@{a}", f"C:{c['id']}@{b}", s, ("elevator", f"{a}->{b}", c["id"], dl))
                        add(f"C:{c['id']}@{b}", f"C:{c['id']}@{a}", s, ("elevator", f"{b}->{a}", c["id"], -dl))
        for k in adj:                       # deterministic expansion order
            adj[k].sort(key=lambda e: e[0])
        self.adj = adj

    def _conn_ok(self, c, disabled):
        if c["id"] in disabled or not c.get("enabled", True):
            return False
        return c["type"] != "elevator" or self.elev.get("enabled", False)

    def _conn_on(self, node, disabled):
        cid = node[2:].split("@")[0]
        c = next(c for c in self.model["connectors"] if c["id"] == cid)
        return self._conn_ok(c, disabled)

    def _dijkstra(self, src: str):
        dist = {src: 0.0}
        prev = {}
        pq = [(0.0, src)]
        while pq:
            d, u = heapq.heappop(pq)
            if d > dist.get(u, np.inf) + 1e-12:
                continue
            if u.startswith("R:") and u != src:
                continue                    # never walk *through* another room
            for v, w, leg in self.adj.get(u, ()):
                nd = d + w
                if nd < dist.get(v, np.inf) - 1e-9 or (abs(nd - dist.get(v, np.inf)) <= 1e-9 and u < prev[v][0]):
                    dist[v] = nd
                    prev[v] = (u, leg, w)
                    heapq.heappush(pq, (nd, v))
        return dist, prev

    # ------------------------------------------------------------------
    def room_ids(self, floor: str | None = None):
        ids = [r["id"] for f in sorted(self.model["floors"], key=lambda f: -f["level"]) for r in f["rooms"]]
        return [i for i in ids if floor is None or self.rooms[i]["floor"] == floor]

    def travel_time(self, a: str, b: str) -> float:
        """Seconds from the centre of room a to the centre of room b."""
        if a == b:
            return 0.0
        dist, _ = self._dijkstra("R:" + self._check(a))
        return float(dist.get("R:" + self._check(b), np.inf))

    def route(self, a: str, b: str) -> Route:
        a, b = self._check(a), self._check(b)
        dist, prev = self._dijkstra("R:" + a)
        node = "R:" + b
        if node not in dist:
            raise ValueError(f"no route {a} -> {b}")
        legs = []
        while node != "R:" + a:
            u, leg, w = prev[node]
            if leg[0] == "walk":
                _, fid, lg, rev = leg
                legs.append(Leg("walk", fid, u, node, w, lg["m"], lg["path"][::-1] if rev else lg["path"]))
            else:
                legs.append(Leg(leg[0], leg[1], u, node, w, via=leg[2]))
            node = u
        legs.reverse()
        merged = []                         # a route may pass a stair landing: one walk per floor
        for lg in legs:
            if merged and lg.kind == "walk" and merged[-1].kind == "walk" and merged[-1].floor == lg.floor:
                m = merged[-1]
                m.to, m.seconds, m.metres, m.path = lg.to, m.seconds + lg.seconds, m.metres + lg.metres, m.path + lg.path[1:]
            else:
                merged.append(lg)
        legs = merged
        walk_m = sum(l.metres for l in legs)
        walk_s = sum(l.seconds for l in legs if l.kind == "walk")
        up = sum(int(round(abs(self.level[l.floor.split('->')[1]] - self.level[l.floor.split('->')[0]])))
                 for l in legs if l.kind != "walk" and self.level[l.floor.split('->')[1]] > self.level[l.floor.split('->')[0]])
        down = sum(int(round(abs(self.level[l.floor.split('->')[1]] - self.level[l.floor.split('->')[0]])))
                   for l in legs if l.kind != "walk" and self.level[l.floor.split('->')[1]] < self.level[l.floor.split('->')[0]])
        return Route(a, b, float(dist["R:" + b]), walk_m, walk_s, float(dist["R:" + b]) - walk_s, up, down, legs)

    def matrix(self, ids=None):
        """(ids, T) with T[i, j] = seconds from ids[i] to ids[j]."""
        ids = list(ids or self.room_ids())
        T = np.zeros((len(ids), len(ids)))
        for i, a in enumerate(ids):
            dist, _ = self._dijkstra("R:" + a)
            T[i] = [0.0 if a == b else dist.get("R:" + b, np.inf) for b in ids]
        return ids, T

    def _check(self, rid: str) -> str:
        rid = str(rid).strip().upper()
        if rid not in self.rooms:
            raise KeyError(f"unknown room {rid!r}")
        return rid
