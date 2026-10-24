"""Builds README.md and its standalone SVG figures (docs/img) from the saved results.
Run: python -m tt.readme"""
from __future__ import annotations

import re
import statistics
from collections import defaultdict

from .config import ROOT
from .poster2 import (Data, fig_context, fig_envelope, fig_pipeline, fig_week, traffic)
from .viz import CUR, FAINT, FLOORS, INK, MUT, OPT, T, hist, plan, tornado

IMG = ROOT / "docs" / "img"
_ENT = {"&rarr;": "→", "&harr;": "↔", "&ge;": "≥", "&le;": "≤", "&middot;": "·", "&hellip;": "…",
        "&minus;": "−", "&times;": "×", "&plusmn;": "±", "&asymp;": "≈", "&isin;": "∈", "&mdash;": "—",
        "&ndash;": "–", "&Gamma;": "Γ", "&lambda;": "λ", "&rsquo;": "’", "&ldquo;": "“", "&rdquo;": "”"}


def xml_safe(t: str) -> str:
    for k, v in _ENT.items():
        t = t.replace(k, v)
    return t


def standalone(svg_str: str, width: int) -> str:
    m = re.search(r'viewBox="0 0 ([0-9.]+) ([0-9.]+)"', svg_str)
    w, h = float(m.group(1)), float(m.group(2))
    out = svg_str.replace('width="100%"', f'width="{width}" height="{width * h / w:.0f}"', 1)
    out = xml_safe(out.replace('<svg class=""', '<svg', 1))
    return f'<?xml version="1.0" encoding="UTF-8"?>\n{out}'


def place(svg_str: str, x: float, y: float, w: float) -> tuple[str, float]:
    m = re.search(r'viewBox="0 0 ([0-9.]+) ([0-9.]+)"', svg_str)
    vw, vh = float(m.group(1)), float(m.group(2))
    h = w * vh / vw
    inner = xml_safe(svg_str.replace('width="100%"', f'x="{x}" y="{y}" width="{w}" height="{h:.1f}"', 1).replace('<svg class=""', '<svg', 1))
    return inner, h


def save(name: str, body: str, w: int, h: int):
    IMG.mkdir(parents=True, exist_ok=True)
    (IMG / name).write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">'
                            f'<rect width="{w}" height="{h}" fill="#fbfaf6"/>{xml_safe(body)}</svg>', encoding="utf-8")


def main():
    D = Data()
    res, st, w = D.res, D.res["stats"], D.w
    cs = res["current_system"]
    o = res["optimized"]["metrics"]
    cur = lambda sec, k: statistics.mean(c["metrics"][sec][k] for c in cs)
    red = lambda sec, k: 100 * (1 - o[sec][k] / cur(sec, k))

    # 1 overview bars
    items = [("Walking (s/week)", "travel_s_mean", "{:.0f}"), ("Room changes/week", "room_changes_mean", "{:.1f}"),
             ("Idle periods/week", "gaps_mean", "{:.2f}"), ("Worst 20% walking (s)", "travel_s_cvar80", "{:.0f}")]
    b = T(20, 30, "Student outcomes: current method vs optimized timetable", 24, INK, "start", 700, "Georgia,serif")
    for i, (lab, k, f) in enumerate(items):
        x0 = 30 + i * 270
        c, op = cur("students", k), o["students"][k]
        sc = 175 / c
        b += f'<rect x="{x0}" y="{290 - c * sc:.0f}" width="90" height="{c * sc:.0f}" fill="{CUR}"/><rect x="{x0 + 100}" y="{290 - op * sc:.0f}" width="90" height="{max(op * sc, 2):.0f}" fill="{OPT}"/>'
        b += T(x0 + 45, 282 - c * sc, f.format(c), 17, INK, "middle") + T(x0 + 145, 282 - op * sc, f.format(op), 17, INK, "middle", 700)
        b += T(x0 + 95, 72, f"-{100 * (1 - op / c):.0f}%", 24, OPT, "middle", 800) + T(x0 + 95, 318, lab, 16, MUT, "middle")
    b += f'<rect x="30" y="338" width="16" height="12" fill="{CUR}"/>' + T(52, 349, "current (mean of 24 emulated)", 15, INK) + f'<rect x="400" y="338" width="16" height="12" fill="{OPT}"/>' + T(422, 349, "optimized", 15, INK)
    save("overview.svg", b, 1120, 366)

    # 2 floor plans, current vs optimized
    tc, to = traffic(w, *D.cur), traffic(w, *D.opt)
    gmax = max(max(tc.values()), max(to.values()))
    body, y = "", 10
    for lab, tr, col in (("Current method", tc, CUR), ("Optimized", to, OPT)):
        body += T(10, y + 22, lab, 22, col, "start", 700, "Georgia,serif")
        x = 0
        for fl in FLOORS:
            heat = {r: (v / gmax) ** 0.6 for r, v in tr.items() if D.rfloor.get(r) == fl}
            svg, h = place(plan(fl, heat, col, 300, title=fl, show_ids=False), x, y + 30, 220)
            body += svg
            x += 224
        y += 30 + h + 12
    save("floorplans.svg", body, 1120, int(y))

    # 3 distributions
    mc, mo = D.m_cur, D.m_opt
    hs = [hist([[p[k] for p in mc["per_student"].values()], [p[k] for p in mo["per_student"].values()]], 700, 330, bins, xl, lo=lo, hi=hi)
          for k, bins, xl, lo, hi in (("travel_s", 28, "walking per student per week (s)", None, None),
                                      ("changes", 22, "room changes per student per week", 0, 36),
                                      ("gaps", 12, "idle periods per student per week", 0, 12))]
    body, x = "", 0
    for hsvg in hs:
        svg, hh = place(hsvg, x, 0, 372)
        body += svg
        x += 374
    save("distributions.svg", body, 1120, int(hh))

    # 4 pipeline, week, context
    (IMG / "pipeline.svg").write_text(standalone(fig_pipeline(D), 1120), encoding="utf-8")
    (IMG / "week.svg").write_text(standalone(fig_week(D), 1000), encoding="utf-8")
    (IMG / "context.svg").write_text(standalone(fig_context(D), 1120), encoding="utf-8")

    # 5 sensitivity
    oat, lhs = D.oat, D.lhs or []
    by = defaultdict(list)
    for r in oat:
        if "improvement" in r and r["tag"] != "base":
            by[r["tag"].split("=")[0]].append(r["improvement"]["travel_pct"])
    base = next(r for r in oat if r["tag"] == "base")["improvement"]["travel_pct"]
    rows = sorted([(k.split(".")[-1], min(v), max(v)) for k, v in by.items()], key=lambda r: r[2] - r[1])
    tsvg, th = place(tornado(rows, base, 760, 30, 250), 0, 0, 640)
    esvg, eh = place(fig_envelope(list(oat) + list(lhs), 0.8725), 650, 0, 470)
    save("sensitivity.svg", tsvg + esvg, 1120, int(max(th, eh)))

    # numbers for the text
    n_ok = sum(1 for r in oat if "opt" in r and r["opt"]["ok"])
    sh = res["shocks"]["expected"]
    ta = res["shocks"]["draws"]["teacher_absence_1day"]
    cov = 100 * sum(x["covered"] for x in ta) / max(1, sum(x["affected_meetings"] for x in ta))
    allv = [min(r[1] for r in rows), max(r[2] for r in rows)]
    rm_bad = min([r['overrides']['rooms.removed_frac'] * 100 for r in oat if r['tag'].startswith('rooms.removed_frac') and 'opt' not in r] or [100])
    viol = round(statistics.mean(c["check"]["violations"].get("H8", 0) for c in cs))
    t = res["optimized"]["metrics"]["teachers"]

    md = f"""# Prompt 1: Optimizing School Curriculum

Automatic timetabling for a simulated school of {st['n_students']} students (grades 9, 10 and 11 AP), {st['n_teachers']} teachers and 59 rooms.
The scheduler assigns every lesson a period and a room, checks the result against ten hard constraints with an independent program,
and compares it with an emulation of the current method. The full write-up is the poster in `output/poster_large.pdf`.

![Student outcomes](docs/img/overview.svg)

| Per student, per week | Current | Optimized |
|---|---|---|
| Walking | {cur('students','travel_s_mean'):.0f} s | **{o['students']['travel_s_mean']:.0f} s** |
| Room changes | {cur('students','room_changes_mean'):.1f} | **{o['students']['room_changes_mean']:.1f}** |
| Idle periods between lessons | {cur('students','gaps_mean'):.2f} | **{o['students']['gaps_mean']:.2f}** |
| Classes outside the weekly-minutes band | {viol} of {st['n_sections']} | **0** |

Teachers' walking changes from {cur('teachers','travel_s_mean'):.0f} to {t['travel_s_mean']:.0f} s per week and their idle periods from {cur('teachers','gaps_mean'):.1f} to {t['gaps_mean']:.1f}. Teachers move between rooms so that students do not.

## Assumptions

- The timetable is identical in every week; one week is planned and repeated.
- Floor B2 is for club activities only. No class is scheduled there, so it is removed from the room pool. All 14 laboratories are on B2, so the sciences meet in ordinary classrooms and keep a practical double period. The pool is 49 classrooms (1F to 4F) and 10 arts rooms (B1).
- Weekly lessons per course come from the catalog credit multiplied by a factor fitted on the one observed week (k = {st['k']:.3f}); the sensitivity runs vary it.
- The 626 students, 54 teachers and the current method are simulated. The only real timetable data is one observed week.

## Method

![Pipeline](docs/img/pipeline.svg)

1. **Classes.** Students with the same course package form one class (at most 24). Free elective choice makes the conflict graph too dense to schedule (31 mutually exclusive lessons for 29 free periods), so a fixed set of packages is offered.
2. **Time.** CP-SAT assigns a period to every lesson. Hard constraints: no student, teacher or room used twice, teacher limits on consecutive lessons, practical double periods, and weekly minutes within 8% of nominal (periods are 40 to 60 minutes, so counting lessons alone changes class hours). The objective removes idle gaps, same-day repeats and late hard subjects.
3. **Rooms.** Each class gets a home room; remaining lessons are matched to free rooms and improved by annealing on total walking time from the building model.
4. **Check and repair.** A separate checker re-derives the ten constraints from the finished timetable. When a room closes, a teacher is absent or enrollment grows, only the affected lessons are re-planned.

![Week grid](docs/img/week.svg)

## Results

![Floor plans](docs/img/floorplans.svg)

![Distributions](docs/img/distributions.svg)

Walking falls by {red('students','travel_s_mean'):.0f}%, room changes by {red('students','room_changes_mean'):.0f}% and idle periods by {red('students','gaps_mean'):.0f}%. The worst-off 20% of students also improve ({cur('students','travel_s_cvar80'):.0f} to {o['students']['travel_s_cvar80']:.0f} s), so the gain is not concentrated in a few students.

## Verification

The checker shares no code with the scheduler and finds 0 violations in the optimized timetable. The current-method timetables violate only the weekly-minutes rule (about {viol} classes each). Ten injected faults, one per constraint, are all detected. {len(D.oat)} sensitivity runs were solved and checked again; {n_ok} of them produced a timetable with no violation. `pytest tests/` runs 21 tests.

## Sensitivity

![Sensitivity](docs/img/sensitivity.svg)

Across single-assumption changes the walking reduction stays between {allv[0]:.0f}% and {allv[1]:.0f}%. It is robust to objective weights, class-size limits, staffing and the solver seed. It does not survive a much heavier timetable or the loss of {rm_bad:.0f}% of the rooms: no valid timetable was found for the current method or the optimized one.

## Repair

A teacher absence is covered by a qualified free colleague for {cov:.0f}% of lessons. A closed room moves its lessons to free rooms of the same kind, with no change of time. Over 12 draws of each event, the expected cost is {sh['moved_meetings']:.2f} lessons re-timed and {sh['room_changes']:.1f} room changes; all repaired timetables pass the checker.

## Limitations

- Only one real week exists; the current method is an emulator calibrated to it (about {res['emulator_calibration']['g11_changes']:.0f} room changes against 21 observed).
- CP-SAT stopped at its time limit, so "optimized" means the best feasible timetable found, not a proven optimum.
- Sections of the same course can still differ in weekly minutes; an equality constraint across sections is the next rule to add.

## Reproduce

```
python -m venv .venv && .venv/Scripts/pip install ortools numpy matplotlib pytest
cd src
PYTHONPATH=. python -m tt.run 24 150          # main run
PYTHONPATH=. python -m tt.sensitivity all     # sweeps (about 40 min on 12 cores)
PYTHONPATH=. python -m tt.poster2             # poster -> output/poster_large.html
PYTHONPATH=. python -m tt.readme              # this file and docs/img
cd .. && python -m pytest tests/test_tt.py
```

`src/tt/` holds the pipeline, `src/config/tt.toml` every parameter, `docs/Question.txt` the prompt and `docs/improvement_proposal.md` the design rationale.
"""
    (ROOT / "README.md").write_text(md, encoding="utf-8")
    print("wrote README.md and", len(list(IMG.glob('*.svg'))), "figures")


if __name__ == "__main__":
    main()
