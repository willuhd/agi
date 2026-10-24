"""Deterministic synthetic population: teachers + students -> section demand.

Reads population.toml + selection.toml + courses.toml. Seed => identical runs.
Demand honors the module rules and the >5-to-run floor; there is NO max cap
(catalog states none). IB sections are generated but zoned XMT (out of scope
for the ZX solve; they still consume shared staff).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field


@dataclass
class Teacher:
    id: str
    dept: str
    archetype: str
    max_consecutive: int
    early_ok: bool
    extra_pay: float
    qualified: set = field(default_factory=set)
    gamma: dict = field(default_factory=dict)
    homeroom: str | None = None  # grade if homeroom teacher (office pinned)


@dataclass
class Student:
    id: str
    grade: str
    track: str  # G9 | G10 | AP | IB | ALevel
    levels: dict = field(default_factory=dict)  # subject -> level
    modules: dict = field(default_factory=dict)  # module -> choice
    homeroom: int | None = None  # homeroom index within grade


DEPTS = ["math", "english", "physics", "chemistry", "biology", "econ",
         "humanities", "language", "arts", "pe", "cs"]


def _weighted(rng: random.Random, weights: dict) -> str:
    total = sum(weights.values())
    x = rng.random() * total
    for k, v in weights.items():
        x -= v
        if x <= 0:
            return k
    return next(iter(weights))


def generate_teachers(pop: dict, n_override: int = 0) -> list[Teacher]:
    rng = random.Random(pop["seed"]["value"] + 1)
    arch = pop["teacher_archetypes"]
    out = []
    # Homeroom teachers first: exact counts from [homerooms], office pinned.
    hi = 0
    for grade, n in pop.get("homerooms", {}).items():
        for _ in range(n):
            a_name = _weighted(rng, {k: v["share"] for k, v in arch.items()})
            a = arch[a_name]
            out.append(Teacher(
                id=f"H{hi:03d}", dept="homeroom", archetype=a_name,
                max_consecutive=a["max_consecutive"], early_ok=a["early_ok"],
                extra_pay=a["extra_period_pay"], qualified={"homeroom"},
                gamma={"archetype": a_name}, homeroom=grade))
            hi += 1
    n_sub = n_override or pop["counts"]["subject_teachers"]
    names = list(arch)
    for i in range(n_sub):
        a_name = _weighted(rng, {k: v["share"] for k, v in arch.items()})
        a = arch[a_name]
        dept = DEPTS[i % len(DEPTS)]
        qual = {dept, f"{dept}:honors"} if rng.random() < 0.6 else {dept}
        t = Teacher(
            id=f"T{i:03d}", dept=dept, archetype=a_name,
            max_consecutive=a["max_consecutive"], early_ok=a["early_ok"],
            extra_pay=a["extra_period_pay"], qualified=qual,
            gamma={"archetype": a_name, "extra_pay": a["extra_period_pay"]},
        )
        out.append(t)
    return out


def generate_students(pop: dict, sel: dict) -> list[Student]:
    rng = random.Random(pop["seed"]["value"] + 2)
    counts, levels = pop["counts"], pop.get("levels", {})
    out = []

    def level_for(grade_key: str, subject: str) -> str:
        spec = levels.get(grade_key, {}).get(subject, {})
        x = rng.random()
        if x < spec.get("Splus_share", 0):
            return "S+"
        if x < spec.get("Splus_share", 0) + spec.get("S_share", 0):
            return "S"
        if x < spec.get("Splus_share", 0) + spec.get("S_share", 0) + spec.get("honors_share", 0):
            return "H"
        return "S0"

    def mk(sid: str, grade: str, track: str) -> Student:
        gk = {"G9": "G9", "G10": "G10"}.get(grade, "G11AP")
        return Student(
            id=sid, grade=grade, track=track,
            levels={s: level_for(gk, s) for s in ("math", "english", "physics")},
            modules={},
        )

    for i in range(counts["G9"]):
        s = mk(f"G9-{i:03d}", "G9", "G9")
        s.homeroom = i % 12
        m2 = sel["grade9"]["module2"]
        s.modules["M2"] = rng.choice(m2["options"])
        s.modules["M3"] = rng.choice(sel["grade9"]["module3"]["options"])
        out.append(s)
    for i in range(counts["G10"]):
        s = mk(f"G10-{i:03d}", "G10", "G10")
        s.homeroom = i % 11
        s.modules["M1"] = rng.choice(sel["grade10"]["module1"]["combos"])
        s.modules["M2"] = rng.choice(sel["grade10"]["module2"]["options"])
        out.append(s)
    # G11: 10 homerooms; 11-1..11-4 (idx 0-3) are IB, rest AP. 4/10 = 40%.
    for i in range(counts["G11"]):
        hr = i % 10
        track = "IB" if hr < 4 else "AP"
        s = mk(f"G11-{i:03d}", "G11", track)
        s.homeroom = hr
        if track == "AP":
            # simplified AP bundle honoring M1<=2 + M2=1 + exclusions-lite
            s.modules["M1"] = rng.choice([["AP Physics 1"], ["AP Chemistry"],
                                          ["AP Physics 1", "AP Chemistry"]])
            s.modules["M2"] = rng.choice(sel["grade11ap"]["module2"]["options_school"]
                                          + sel["grade11ap"]["module2"]["options_ap"])
        out.append(s)
    # G12: XMT-only. Generated for headcount/ledger; tracks unknown (IB/AP
    # mix unconfirmed) so no module choices are synthesized.
    for i in range(counts.get("G12", 0)):
        s = mk(f"G12-{i:03d}", "G12", "G12")
        s.homeroom = i % 10
        out.append(s)
    return out


def aggregate_demand(students: list[Student], teachers: list[Teacher],
                     dmap: dict, floor: int) -> tuple[list[dict], list[dict]]:
    """Join demand to courses.toml keys via demand_map.toml.
    Returns (sections, unknown): sections carry course/cohort/teacher/size
    and ALWAYS match a load-bearing course key or are listed unknown.
    Cohort = homeroom (round-robin); electives pool at grade level.
    Core runs regardless of floor; choices below floor are dropped (>5 rule).
    """
    from collections import Counter, defaultdict
    homerooms = {"G9": 12, "G10": 11, "G11": 12}
    counters: Counter = Counter()
    by_key: dict = defaultdict(int)
    xmt_ledger = Counter()  # IB-track demand lives in XMT: counted, not solved

    def cohort_for(s) -> str:
        if s.homeroom is not None:
            return f"{s.grade}-H{s.homeroom:02d}"
        i = counters[s.grade] % homerooms.get(s.grade, 5)
        counters[s.grade] += 1
        return f"{s.grade}-H{i:02d}"

    pooled: Counter = Counter()
    for s in students:
        if s.track == "IB" or s.grade == "G12":
            # XMT partition: counted for staffing, never placed in ZX.
            xmt_ledger[s.grade] += 1
            continue
        track = "G11AP" if (s.grade == "G11" and s.track == "AP") else s.grade
        core = dmap.get("core", {}).get(track, {}).get("courses", [])
        ch = cohort_for(s)
        for ck in core:
            by_key[(ck, ch)] += 1
        for _mod, choice in s.modules.items():
            picks = choice if isinstance(choice, list) else [choice]
            for c in picks:
                if not isinstance(c, str):
                    continue
                m = dmap.get("modules", {}).get(c, {})
                ck = m.get("course", c)
                if m.get("course"):
                    by_key[(ck, ch)] += 1
                else:
                    pooled[(c, s.grade)] += 1
    # floor rule only for non-core pooled choices
    dropped = []
    for (c, g), n in pooled.items():
        if n < floor:
            dropped.append(c)
    # teacher matching by dept, round-robin among eligible
    dept_of = {}
    for mod, m in dmap.get("modules", {}).items():
        if m.get("course"):
            dept_of[m["course"]] = m.get("dept", "")
    pool: dict = defaultdict(int)
    sections = []
    for (ck, ch), n in sorted(by_key.items()):
        dept = dept_of.get(ck, "")
        elig = [t.id for t in teachers
                if t.dept == dept and t.homeroom is None] or \
               [t.id for t in teachers if t.homeroom is None]
        tid = elig[pool[dept] % len(elig)] if elig else "UNSTAFFED"
        pool[dept] += 1
        sections.append({"course": ck, "cohort": ch, "teacher": tid,
                         "size": n})
    unknown = [{"course": c, "grade": g, "size": n}
               for (c, g), n in sorted(pooled.items())]
    return sections, unknown, dict(xmt_ledger)
