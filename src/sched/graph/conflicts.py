"""Conflict graph: timetabling as graph coloring (structure + certificates).

Nodes = unit-slot meetings. Edge = shared cohort or shared teacher
(must differ in time). A valid slot assignment IS a proper coloring;
chromatic number chi <= available slots is necessary for feasibility.
We report: greedy max-clique (lower bound on chi) vs greedy coloring
(upper bound) vs grid slots. Gap between clique LB and grid = slack
the repair operator gets to spend.
Stdlib only.
"""
from __future__ import annotations


def build_edges(meetings: list[dict]) -> dict[int, set[int]]:
    adj: dict[int, set[int]] = {m["id"]: set() for m in meetings}
    for i, a in enumerate(meetings):
        for b in meetings[i + 1:]:
            if a["cohort"] == b["cohort"] or a["teacher"] == b["teacher"]:
                adj[a["id"]].add(b["id"])
                adj[b["id"]].add(a["id"])
    return adj


def greedy_coloring(adj: dict[int, set[int]]) -> dict[int, int]:
    """Largest-first greedy: upper bound on chi. Returns node -> color."""
    color: dict[int, int] = {}
    for v in sorted(adj, key=lambda x: -len(adj[x])):
        used = {color[u] for u in adj[v] if u in color}
        c = 0
        while c in used:
            c += 1
        color[v] = c
    return color


def greedy_clique(adj: dict[int, set[int]]) -> list[int]:
    """Greedy max-clique heuristic: lower bound on chi."""
    best: list[int] = []
    for start in sorted(adj, key=lambda x: -len(adj[x])):
        clique, cand = [start], set(adj[start])
        while cand:
            v = max(cand, key=lambda x: len(cand & adj[x]))
            clique.append(v)
            cand &= adj[v]
        if len(clique) > len(best):
            best = clique
    return best


def certificate(meetings: list[dict], slots_available: int) -> dict:
    adj = build_edges(meetings)
    ub = max(greedy_coloring(adj).values(), default=-1) + 1
    lb = len(greedy_clique(adj))
    return {"nodes": len(meetings), "edges": sum(map(len, adj.values())) // 2,
            "clique_lb": lb, "color_ub": ub,
            "slots_available": slots_available, "slack": slots_available - lb,
            "feasible_necessary": lb <= slots_available}
