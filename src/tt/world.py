"""Synthetic school: curriculum -> students -> sections -> teachers -> rooms. Seeded, deterministic.

Scope (user ruling): G9 + G10 + G11-AP in the ZX building. IB / G12 live in XMT and enter only as
external busy slots on shared teachers. PE is a fixed all-grade block (outdoor venues, not pooled).
"""
from __future__ import annotations

import csv
import math
import random
from collections import defaultdict
from dataclasses import dataclass, field

from . import catalog
from .config import ROOT, slot_table

# (key, label, catalog name or None, fallback credit, room kind, dept). Credits are looked up in the
# catalog extract when the name matches; fallback is the catalog/courses.toml value for that row.
CUR = {
    "G9": {
        "core": [
            ("eng9", "English 9", "Survey Western Lit I S", 6.0, "classroom", "english"),
            ("math9", "Math 9 (Geometry)", "Geometry S", 6.0, "classroom", "math"),
            ("chi9", "Chinese 9", "Chinese Level I Lang+Cult", 3.0, "classroom", "language"),
            ("phy9", "Physics 9", "Physics 9 S", 3.0, "lab", "physics"),
            ("che9", "Chemistry 9", "Chemistry 9 S", 3.0, "lab", "chemistry"),
            ("his9", "World History 9", "World Hist to 1500 S", 4.0, "classroom", "humanities"),
        ],
        "M2": [  # choose 1
            ("bio9", "Biology 9", "Biology 9 S", 4.0, "lab", "biology"),
            ("cmp9", "Computing Essentials", "Computing Essentials S", 4.0, "classroom", "cs"),
            ("prg9", "Programming Methodology", "Programming Methodology H", 4.0, "classroom", "cs"),
            ("geo9", "Physical Geography", "Physical Geography S", 4.0, "classroom", "humanities"),
        ],
        "M3": [  # choose 1, 2 credit-hrs (catalog form)
            ("mus9", "Music", None, 2.0, "arts", "arts"),
            ("art9", "Arts", None, 2.0, "arts", "arts"),
        ],
    },
    "G10": {
        "core": [
            ("eng10", "English 10", "Survey Western Lit II S", 5.5, "classroom", "english"),
            ("math10", "Math 10 (Pre-calc)", "Pre-calculus S", 5.5, "classroom", "math"),
            ("chi10", "Chinese 10", "Chinese Level I Lang+Cult", 3.0, "classroom", "language"),
            ("his10", "World History 10", "World Hist since 1500 S", 4.0, "classroom", "humanities"),
            ("gm10", "Global Mindset", None, 1.0, "classroom", "humanities"),
        ],
        "M1": [  # choose 2 of 3 (combo)
            ("phy10", "Physics 10", "Physics 10 S", 3.0, "lab", "physics"),
            ("che10", "Chemistry 10", "Chemistry 10 S", 3.0, "lab", "chemistry"),
            ("bio10", "Biology 10", "Biology 10 S", 3.0, "lab", "biology"),
        ],
        "M2": [
            ("va10", "Visual Arts", "Visual Arts Standard", 3.0, "arts", "arts"),
            ("eco10", "Economics & Business", None, 4.0, "classroom", "econ"),
            ("cf10", "Computer Fundamentals", "Computer Fundamentals S", 3.0, "classroom", "cs"),
            ("hg10", "Human Geography 1", "Human Geography 1 S", 3.0, "classroom", "humanities"),
            ("wt10", "Western Theatre", None, 3.0, "arts", "arts"),
            ("ma10", "Music Appreciation", None, 3.0, "arts", "arts"),
        ],
    },
    "G11AP": {
        "core": [
            ("eng11", "AP English Lang", "AP Lang+Comp (1Y)", 6.0, "classroom", "english"),
            ("math11", "Math 11", "Calculus S", 6.0, "classroom", "math"),
            ("chi11", "Chinese 11", "Chinese Level I Lang+Cult", 3.0, "classroom", "language"),
        ],
        "M1": [
            ("ap_phy", "AP Physics 1", "AP Physics 1", 6.0, "lab", "physics"),
            ("ap_che", "AP Chemistry", "AP Chemistry", 6.0, "lab", "chemistry"),
            ("ap_bio", "AP Biology", "AP Biology", 6.0, "lab", "biology"),
        ],
        "M2": [
            ("ap_psy", "AP Psychology", "AP Psychology", 6.0, "classroom", "econ"),
            ("ap_hg", "AP Human Geography", "AP Human Geography", 6.0, "classroom", "humanities"),
            ("ap_mac", "AP Macroeconomics", "AP Macroeconomics", 6.0, "classroom", "econ"),
            ("ap_mic", "AP Microeconomics", "AP Microeconomics", 6.0, "classroom", "econ"),
            ("us11", "US Overview", "US Overview S", 4.5, "classroom", "humanities"),
            ("ch11", "Chinese History", None, 4.5, "classroom", "humanities"),
        ],
        "M3": [
            ("bm11", "Business Management", "Business Management", 4.5, "classroom", "econ"),
            ("cw11", "Creative Writing", "Creative Writing", 4.5, "classroom", "english"),
            ("phi11", "Philosophy", None, 4.5, "classroom", "humanities"),
            ("law11", "Intro to Law", None, 4.5, "classroom", "humanities"),
        ],
        "M4": [
            ("art11", "Arts 1", "Arts 1", 4.5, "arts", "arts"),
            ("acap11", "A Cappella", None, 4.5, "arts", "arts"),
        ],
    },
}
GRADE_SIZE_KEY = {"G9": "G9", "G10": "G10", "G11AP": "G11AP"}
OFFICE = {"G9": "406", "G10": "210", "G11AP": "110"}   # homeroom offices (teachers.toml pins)


@dataclass
class Course:
    key: str
    label: str
    credit: float
    slots: int
    kind: str
    dept: str
    grade: str
    credit_src: str
    hard: bool = False


@dataclass
class Section:
    id: str
    course: str
    grade: str
    students: list
    n: int
    kind: str
    dept: str
    teacher: str = ""
    homerooms: dict = field(default_factory=dict)  # homeroom -> count
    double: bool = False
    hard: bool = False

    @property
    def size(self) -> int:
        return len(self.students)


@dataclass
class Room:
    id: str
    kind: str
    floor: str
    area: float


@dataclass
class Teacher:
    id: str
    dept: str
    depts: set
    max_consec: int
    external_busy: set = field(default_factory=set)  # slot idx


@dataclass
class World:
    cfg: dict
    slots: list
    courses: dict
    students: dict          # sid -> {grade, homeroom, courses:[keys]}
    sections: dict          # id -> Section
    teachers: dict
    rooms: dict
    travel: dict            # (a,b) -> seconds
    blocked: dict           # grade -> set(slot idx)
    pe_slots: set
    stats: dict = field(default_factory=dict)

    def student_sections(self) -> dict:
        out = defaultdict(list)
        for s in self.sections.values():
            for sid in s.students:
                out[sid].append(s.id)
        return out


def load_rooms_and_travel():
    rooms = {}
    with open(ROOT / "data/building/rooms.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["kind"] in ("classroom", "lab", "arts"):
                rooms[r["id"]] = Room(r["id"], r["kind"], r["floor"], float(r["area_m2"]))
    with open(ROOT / "data/building/travel_time_s.csv", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    ids = rows[0][1:]
    tr = {}
    for r in rows[1:]:
        for j, v in enumerate(r[1:]):
            try:
                tr[(r[0], ids[j])] = float(v)
            except ValueError:
                pass
    return rooms, tr


def build_courses(cfg: dict) -> dict:
    cat = catalog.parse_catalog()
    out = {}
    for g, mods in CUR.items():
        for mod, lst in mods.items():
            for key, label, cname, fb, kind, dept in lst:
                credit = cat.get(cname) if cname else None
                src = "catalog" if credit is not None else "fallback(catalog form / courses.toml)"
                credit = credit if credit is not None else fb
                n = catalog.credits_to_slots(credit, cfg)
                out[key] = Course(key, label, credit, n, kind, dept, g, src, hard=credit >= 5.0)
    return out


def _avail(cfg, slots, grade):
    return len([s for s in slots if s["idx"] not in blocked_for(cfg, slots, grade)])


def blocked_for(cfg, slots, grade) -> set:
    pe = {tuple(x) for x in cfg["slots"]["pe_blocked"]}
    ap = {tuple(x) for x in cfg["slots"]["ap_blocked"]} if grade == "G11AP" else set()
    return {s["idx"] for s in slots if (s["day"], s["period"]) in pe | ap}


PATHWAY_GRADES = ("G10", "G11AP")   # timetable-aware choice design: offered bundles, class = identical choices


def grade_pathways(cfg, courses, slots, grade):
    """Legal bundles for a grade (catalog rules) whose weekly slots fit the grid; P are offered.
    Pathway classes keep every section's student set identical to one class, so conflict cliques stay
    below the slot count (the free-choice web is what made the instance infeasible: finding F2)."""
    import itertools
    sc = cfg["school"]
    avail = len(slots) - len(blocked_for(cfg, slots, grade)) - sc["min_free_periods"]
    core = sum(courses[c[0]].slots for c in CUR[grade]["core"])
    legal = []
    if grade == "G10":
        m1 = [c[0] for c in CUR[grade]["M1"]]
        for a in itertools.combinations(m1, 2):
            for b in [c[0] for c in CUR[grade]["M2"]]:
                legal.append(tuple(a) + (b,))
    else:  # G11AP: M1<=2, 2-in-M1 => no M3/M4, M2=1, M3/M4 optional
        m1 = [c[0] for c in CUR[grade]["M1"]]
        m2 = [c[0] for c in CUR[grade]["M2"]]
        m3 = [None] + [c[0] for c in CUR[grade]["M3"]]
        m4 = [None] + [c[0] for c in CUR[grade]["M4"]]
        for r in (1, 2):
            for a in itertools.combinations(m1, r):
                for b in m2:
                    for c3 in (m3 if r == 1 else [None]):
                        for c4 in (m4 if r == 1 else [None]):
                            legal.append(tuple(a) + (b,) + tuple(x for x in (c3, c4) if x))
    legal = [b for b in legal if core + sum(courses[x].slots for x in b) <= avail]
    rng2 = random.Random(sc["seed"] + 5 + len(grade))
    P = min(sc["pathways"][grade], len(legal))
    chosen = rng2.sample(legal, P)
    weights = [1.0 / (i + 1) ** sc["pathway_skew"][grade] for i in range(P)]
    return chosen, weights


def build_students(cfg, courses, slots, rng):
    sc = cfg["school"]
    students = {}
    paths = {g: grade_pathways(cfg, courses, slots, g) for g in PATHWAY_GRADES}
    for g in ("G9", "G10", "G11AP"):
        nh = sc["homerooms"][g]
        avail = len(slots) - len(blocked_for(cfg, slots, g)) - sc["min_free_periods"]
        pid_of = {}
        for i in range(sc[g]):
            sid = f"{g}-{i:03d}"
            cs = [c[0] for c in CUR[g]["core"]]
            pid = None
            if g == "G9":
                cs.append(rng.choice(CUR[g]["M2"])[0])
                cs.append(rng.choice(CUR[g]["M3"])[0])
                hr = i % nh
            else:
                bundles, weights = paths[g]
                pid = rng.choices(range(len(bundles)), weights=weights)[0]
                cs += list(bundles[pid])
                hr = pid
            students[sid] = {"grade": g, "homeroom": f"{g}-H{hr:02d}", "courses": cs, "avail": avail,
                             "pathway": pid}
        if g in PATHWAY_GRADES:  # a pathway bigger than the section cap becomes several classes
            members = defaultdict(list)
            for sid, st in students.items():
                if st["grade"] == g:
                    members[st["pathway"]].append(sid)
            cls = 0
            for pid in sorted(members):
                ms = members[pid]
                k = math.ceil(len(ms) / sc["section_cap"])
                for j in range(k):
                    for sid in ms[j::k]:
                        students[sid]["homeroom"] = f"{g}-H{cls:02d}"
                    cls += 1
    return students, 0



def build_sections(cfg, courses, students, rng):
    sc = cfg["school"]
    cap, floor = sc["section_cap"], sc["section_floor"]
    by_course = defaultdict(list)
    for sid, st in students.items():
        for c in st["courses"]:
            by_course[c].append(sid)
    core_keys = {c[0] for g in CUR.values() for c in g["core"]}
    sections, floor_dropped = {}, []
    for ck, sids in sorted(by_course.items()):
        crs = courses[ck]
        if ck in core_keys:  # core: one section per homeroom (cohort kept together)
            groups = defaultdict(list)
            for s in sids:
                groups[students[s]["homeroom"]].append(s)
            chunks = list(groups.values())
        elif crs.grade in PATHWAY_GRADES:
            groups = defaultdict(list)
            for sid in sids:
                groups[students[sid]["homeroom"]].append(sid)
            chunks = []
            for pid, members in sorted(groups.items()):
                if len(members) >= floor:
                    chunks.append(sorted(members, key=lambda x: (students[x]["homeroom"], x)))
                else:
                    floor_dropped.append(f"{ck}@P{pid}")
        else:
            # timetable-aware sectioning: electives are formed inside a "band" of adjacent homerooms so
            # a section only couples a few cohorts (see docs/improvement_proposal.md, finding F2)
            bs = sc["band_size"][crs.grade]
            bands = defaultdict(list)
            for sid in sids:
                bands[int(students[sid]["homeroom"].split("-H")[1]) // bs].append(sid)
            chunks, resid = [], []
            for b, members in sorted(bands.items()):
                if len(members) < floor:
                    resid += members
                    continue
                members = sorted(members, key=lambda x: (students[x]["homeroom"], x))
                k = math.ceil(len(members) / cap)
                size = math.ceil(len(members) / k)
                chunks += [members[i:i + size] for i in range(0, len(members), size)]
            if len(resid) >= floor:
                chunks.append(sorted(resid, key=lambda x: (students[x]["homeroom"], x)))
            elif resid:
                floor_dropped.append(ck)
        for i, ch in enumerate(chunks):
            hr = defaultdict(int)
            for s in ch:
                hr[students[s]["homeroom"]] += 1
            sec = Section(f"{ck}#{i}", ck, crs.grade, ch, crs.slots, crs.kind, crs.dept,
                          homerooms=dict(hr), hard=crs.hard,
                          double=(crs.kind == "lab" and crs.slots >= 3 and cfg["solve"]["lab_doubles"]))
            sections[sec.id] = sec
    return sections, floor_dropped


def build_teachers(cfg, sections, slots, rng):
    tc = cfg["teachers"]
    load = defaultdict(int)
    for s in sections.values():
        load[s.dept] += s.n
    teachers = {}
    arch = list(tc["archetype_share"].items())
    for dept, L in sorted(load.items()):
        nt = max(1, math.ceil(L / (tc["target_load"] * tc["scale"])))
        for i in range(nt):
            a = rng.choices([k for k, _ in arch], [v for _, v in arch])[0]
            tid = f"{dept[:3].upper()}{i:02d}"
            ds = {dept}
            teachers[tid] = Teacher(tid, dept, ds, tc["max_consecutive"][a])
    # a share of teachers can also cover a second department (cross-qualified)
    depts = sorted(load)
    near = {"math": ["cs", "econ"], "cs": ["math"], "econ": ["math", "humanities"],
            "physics": ["chemistry", "math"], "chemistry": ["physics", "biology"], "biology": ["chemistry"],
            "english": ["humanities", "language"], "humanities": ["english", "econ"], "language": ["english"],
            "arts": []}
    for t in teachers.values():
        opts = [d for d in near.get(t.dept, []) if d in depts]
        if opts and rng.random() < tc["second_dept_prob"]:
            t.depts.add(rng.choice(opts))
    # external (IB / G12 in XMT) busy slots
    for t in teachers.values():
        if rng.random() < tc["external_busy_prob"]:
            t.external_busy = set(rng.sample(range(len(slots)), tc["external_busy_slots"]))
    # assign sections: heavy first, least-loaded eligible teacher under the load cap their fatigue
    # limit allows (a 2-in-a-row teacher cannot carry 26 periods); prefer one already teaching the course;
    # hire another teacher in the department when nobody fits (staffing need is an OUTPUT, not a guess)
    cap_by_mc = {2: tc["max_load"] - 8, 3: tc["max_load"] - 4, 4: tc["max_load"]}
    tl = defaultdict(int)
    has = defaultdict(set)
    cohorts_of = defaultdict(set)
    nxt = defaultdict(int)
    for t in teachers:
        nxt[teachers[t].dept] += 1
    for s in sorted(sections.values(), key=lambda x: -x.n):
        elig = [t for t in teachers.values() if s.dept in t.depts
                and tl[t.id] + s.n <= cap_by_mc.get(t.max_consec, tc["max_load"]) - len(t.external_busy)]
        # parallel sections (they share cohorts) must not share a teacher: they would be forced into
        # different slots inside the same cohort window and starve it (found by the infeasibility probe)
        elig = [t for t in elig if not (cohorts_of[t.id] & set(s.homerooms))]
        if not elig:
            a = rng.choices([k for k, _ in arch], [v for _, v in arch])[0]
            tid = f"{s.dept[:3].upper()}{nxt[s.dept]:02d}"
            nxt[s.dept] += 1
            teachers[tid] = Teacher(tid, s.dept, {s.dept}, tc["max_consecutive"][a])
            if rng.random() < tc["external_busy_prob"]:
                teachers[tid].external_busy = set(rng.sample(range(len(slots)), tc["external_busy_slots"]))
            elig = [teachers[tid]]
        def key(t):
            return tl[t.id] + (-3 if s.course in has[t.id] else 0)
        best = min(elig, key=key)
        cohorts_of[best.id] |= set(s.homerooms)
        s.teacher = best.id
        tl[best.id] += s.n
        has[best.id].add(s.course)
    return teachers, dict(tl)


def build(cfg: dict) -> World:
    rng = random.Random(cfg["school"]["seed"])
    slots = slot_table(cfg)
    courses = build_courses(cfg)
    students, _ = build_students(cfg, courses, slots, rng)
    sections, fdrop = build_sections(cfg, courses, students, rng)
    # students keep only courses they are actually sectioned into
    got = {(sid, sec.course) for sec in sections.values() for sid in sec.students}
    lost = 0
    for sid, st in students.items():
        keep = [c for c in st["courses"] if (sid, c) in got]
        lost += len(st["courses"]) - len(keep)
        st["courses"] = keep
    teachers, tload = build_teachers(cfg, sections, slots, rng)
    rooms, travel = load_rooms_and_travel()
    rf = cfg["rooms"]["removed_frac"]
    if rf > 0:
        rr = random.Random(7)
        ids = sorted(r for r, x in rooms.items() if x.kind in ("classroom", "lab"))
        for r in rr.sample(ids, int(len(ids) * rf)):
            rooms.pop(r)
    blocked = {g: blocked_for(cfg, slots, g) for g in ("G9", "G10", "G11AP")}
    pe = {s["idx"] for s in slots if (s["day"], s["period"]) in {tuple(x) for x in cfg["slots"]["pe_blocked"]}}
    w = World(cfg, slots, courses, students, sections, teachers, rooms, travel, blocked, pe)
    sec_by_stud = w.student_sections()
    w.stats = {"k": catalog.get_k(cfg), "n_students": len(students), "n_sections": len(sections),
               "n_meetings": sum(s.n for s in sections.values()), "n_teachers": len(teachers),
               "course_slots_lost_to_floor": lost, "floor_dropped": fdrop,
               "mean_section_size": sum(s.size for s in sections.values()) / len(sections),
               "teacher_load_max": max(tload.values()), "teacher_load_mean": sum(tload.values()) / len(tload),
               "students_with_free_periods": sum(1 for sid, st in students.items()
                    if sum(sections[x].n for x in sec_by_stud[sid]) < st["avail"])}
    return w


def need_area(sec: Section, cfg: dict) -> float:
    return sec.size * cfg["rooms"]["area_per_student"]
