"""Conflict graph certificate for tt (ported from sched/graph/conflicts.py).

Nodes = sections (weighted by meetings n). Edge = shared student (any overlap
in student sets within the same grade pathway class) or shared teacher.
Greedy max-clique = lower bound on slots needed; greedy coloring = upper bound.
Grid slots available = len(slots) - blocked. If clique LB > available, the
instance is infeasible before CP-SAT even starts (repair gets zero slack).

Stdlib only. No hardcoded thresholds — caller passes slots_available.
"""
from __future__ import annotations


def build_edges(sections: dict, student_sections: dict | None = None) -> dict[str, set[str]]:
    adj: dict[str, set[str]] = {g: set() for g in sections}

    def clashes(a: str, b: str) -> bool:
        pa = getattr(sections[a], "parity", "all")
        pb = getattr(sections[b], "parity", "all")
        if {pa, pb} == {"even", "odd"}:
            return False  # alternate weeks: shareable slot
        return True
    ids = list(sections)
    # teacher edges
    by_teacher: dict[str, list[str]] = {}
    for g in ids:
        by_teacher.setdefault(sections[g].teacher, []).append(g)
    for gs in by_teacher.values():
        for i, a in enumerate(gs):
            for b in gs[i + 1:]:
                if not clashes(a, b):
                    continue
                adj[a].add(b)
                adj[b].add(a)
    # student edges: shared student id in section student lists
    if student_sections is not None:
        by_student = student_sections
        # invert: section -> students known; build co-membership via student loop
        from collections import defaultdict
        members: dict[str, set[str]] = defaultdict(set)
        for sid, lst in by_student.items():
            for g in lst:
                if g in adj:
                    members[sid].add(g)
        for gs in members.values():
            gs = sorted(gs)
            for i, a in enumerate(gs):
                for b in gs[i + 1:]:
                    if not clashes(a, b):
                        continue
                    adj[a].add(b)
                    adj[b].add(a)
    else:
        # fallback: sections sharing any homeroom cohort overlap
        for i, a in enumerate(ids):
            ha = set(sections[a].homerooms)
            for b in ids[i + 1:]:
                if (ha & set(sections[b].homerooms)) and clashes(a, b):
                    adj[a].add(b)
                    adj[b].add(a)
    return adj


def greedy_coloring(adj: dict[str, set[str]]) -> dict[str, int]:
    color: dict[str, int] = {}
    for v in sorted(adj, key=lambda x: -len(adj[x])):
        used = {color[u] for u in adj[v] if u in color}
        c = 0
        while c in used:
            c += 1
        color[v] = c
    return color


def greedy_clique(adj: dict[str, set[str]]) -> list[str]:
    best: list[str] = []
    for start in sorted(adj, key=lambda x: -len(adj[x])):
        clique, cand = [start], set(adj[start])
        while cand:
            v = max(cand, key=lambda x: len(cand & adj[x]))
            clique.append(v)
            cand &= adj[v]
        if len(clique) > len(best):
            best = clique
    return best


def certificate(sections: dict, slots_available: int,
                student_sections: dict | None = None) -> dict:
    adj = build_edges(sections, student_sections)
    ub = max(greedy_coloring(adj).values(), default=-1) + 1
    lb = len(greedy_clique(adj))
    return {"nodes": len(sections), "edges": sum(map(len, adj.values())) // 2,
            "clique_lb": lb, "color_ub": ub,
            "slots_available": slots_available, "slack": slots_available - lb,
            "feasible_necessary": lb <= slots_available,
            "clique": greedy_clique(adj) if lb <= 8 else greedy_clique(adj)[:8]}
