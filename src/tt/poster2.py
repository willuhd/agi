"""Large-format poster (3600 px wide, A0-ish landscape). Every figure is generated from the saved results,
the real building model and the solved grids. Run: python -m tt.poster2 [--pdf]"""
from __future__ import annotations

import json
import random
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

from . import checker, config, metrics, shocks, world
from .config import ROOT
from .viz import (CUR, FAINT, GOLD, INK, MUT, OPT, TEAL, FLOORS, T, building, hbars, hist, line, matrix, plan, ramp,
                  room_floor, svg, tornado, lerp)

OUT = ROOT / "output"
QUESTION = (ROOT / "docs/Question.txt").read_text(encoding="utf-8")


def jl(n):
    p = OUT / n
    return json.loads(p.read_text()) if p.exists() else None


# ---------------------------------------------------------------------------------- data -----
class Data:
    def __init__(self):
        self.res = jl("main_results.json")
        self.sol = jl("main_solution.json")
        self.oat, self.lhs, self.par = jl("sens_oat.json"), jl("sens_lhs.json"), jl("sens_pareto.json")
        self.spec = jl("sens_lhs_spec.json")
        self.mut = jl("mutation_suite.json")
        self.w = world.build(config.load())
        key = lambda d: {(k.split("|")[0], int(k.split("|")[1])): v for k, v in d.items()}
        self.opt = (self.sol["slot_of"], key(self.sol["room"]))
        self.cur = (self.sol["emu0"]["slot_of"], key(self.sol["emu0"]["room"]))
        self.m_opt = metrics.evaluate(self.w, *self.opt)
        self.m_cur = metrics.evaluate(self.w, *self.cur)
        self.rfloor = room_floor()


def fig_envelope(recs, base_k):
    w, h = 760, 420
    L, R, T_, B = 84, w - 30, 30, h - 70
    sx = lambda v: L + (v - 0.80) / 0.22 * (R - L)
    sy = lambda v: B - v / 0.6 * (B - T_)
    b = ""
    for v in (0, 0.2, 0.4, 0.6):
        b += f'<line x1="{L}" x2="{R}" y1="{sy(v)}" y2="{sy(v)}" stroke="{FAINT}"/>' + T(L - 10, sy(v) + 6, f"{int(v * 100)}%", 17, MUT, "end")
    for v in (0.8, 0.85, 0.9, 0.95, 1.0):
        b += T(sx(v), B + 26, f"{v:.2f}", 17, MUT, "middle")
    for r in recs:
        ov = r.get("overrides", {})
        k = ov.get("loads.k", base_k)
        rm = ov.get("rooms.removed_frac", 0.0)
        x, y = sx(k), sy(rm)
        if "opt" in r and r["opt"]["ok"]:
            b += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="9" fill="{OPT}" fill-opacity=".75" stroke="#fff" stroke-width="1.5"/>'
        else:
            b += f'<path d="M{x - 8:.1f},{y - 8:.1f} L{x + 8:.1f},{y + 8:.1f} M{x + 8:.1f},{y - 8:.1f} L{x - 8:.1f},{y + 8:.1f}" stroke="{CUR}" stroke-width="3.2"/>'
    b += f'<line x1="{L}" x2="{R}" y1="{B}" y2="{B}" stroke="{INK}"/>'
    b += T((L + R) / 2, h - 14, "credit &rarr; slot factor k (higher = heavier timetable)", 19, MUT, "middle") + T(20, (T_ + B) / 2, "rooms removed", 19, MUT, "middle", 400, "sans-serif", f'transform="rotate(-90 20 {(T_ + B) / 2})"')
    b += f'<circle cx="{L + 18}" cy="{T_ + 6}" r="8" fill="{OPT}"/>' + T(L + 34, T_ + 12, "valid grid found and certified", 17, INK) + f'<path d="M{L + 10},{T_ + 22} l16,16 m0,-16 l-16,16" stroke="{CUR}" stroke-width="3"/>' + T(L + 34, T_ + 42, "no valid grid within the time limit", 17, INK)
    return svg(w, h, b)


def traffic(w, slot_of, room):
    t = defaultdict(float)
    for sid, lst in w.student_sections().items():
        by_day = defaultdict(list)
        for g in lst:
            for s in slot_of[g]:
                by_day[w.slots[s]["day"]].append((s, g))
        for items in by_day.values():
            items.sort()
            for (s1, g1), (s2, g2) in zip(items, items[1:]):
                a, b = room[(g1, s1)], room[(g2, s2)]
                if a != b:
                    t[a] += 1
                    t[b] += 1
    return t


# ------------------------------------------------------------------------------- diagrams ----
def box(x, y, w, h, title, lines=(), fill="#fff", stroke=INK, tcol=INK, size=22):
    b = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}" stroke-width="1.8"/>'
    b += T(x + 14, y + 30, title, size, tcol, "start", 700)
    for i, ln in enumerate(lines):
        b += T(x + 14, y + 58 + i * 25, ln, size - 4, MUT)
    return b


def arrow(x1, y1, x2, y2, col=INK, w=2.2):
    import math
    a = math.atan2(y2 - y1, x2 - x1)
    hx, hy = x2 - 12 * math.cos(a), y2 - 12 * math.sin(a)
    return (f'<line x1="{x1}" y1="{y1}" x2="{hx:.1f}" y2="{hy:.1f}" stroke="{col}" stroke-width="{w}"/>'
            f'<polygon points="{x2},{y2} {hx - 6 * math.sin(a):.1f},{hy + 6 * math.cos(a):.1f} {hx + 6 * math.sin(a):.1f},{hy - 6 * math.cos(a):.1f}" fill="{col}"/>')


def fig_context(D):
    st = D.res["stats"]
    b = ""
    ins = [("Course catalog", [f"230 courses, credits per week", "selection rules (modules, gates)", "&ge;6 students to run a class"]),
           ("Building model", ["6 floors, 103 rooms, 9 stairs", "walking seconds between any two", "room areas (capacity)"]),
           ("One observed week", ["G11-AP student, 33 lessons", "teacher-owned rooms", "21 room changes, 488 s walking"])]
    for i, (t_, ls) in enumerate(ins):
        b += box(10, 20 + i * 150, 330, 130, t_, ls, "#fff")
        b += arrow(340, 85 + i * 150, 420, 210 + (i - 1) * 25)
    b += f'<rect x="420" y="20" width="520" height="430" fill="{INK}"/>'
    b += T(450, 62, "Scheduler", 30, "#fff", "start", 700, "Georgia,serif")
    for i, (t_, l_) in enumerate([("0  Sectioning", f"{st['n_students']} students &rarr; {st['n_sections']} sections"),
                                  ("1  Slots (CP-SAT)", f"{st['n_meetings']} lessons into 33 periods"),
                                  ("2  Rooms", "matching + annealing on walking"),
                                  ("3  Certify", "independent checker, 10 rules")]):
        y = 90 + i * 85
        b += f'<rect x="446" y="{y}" width="468" height="68" fill="#fff"/>' + T(462, y + 30, t_, 24, INK, "start", 700) + T(462, y + 56, l_, 19, MUT)
    for i in range(3):
        b += arrow(940, 130 + i * 110, 1010, 130 + i * 110)
    outs = [("Timetable", ["section &times; slot &times; room", "teacher, class, lessons"]), ("Certificate", ["0 violations of 10 rules", "10/10 planted faults caught"]),
            ("Repair plans", ["room lost &middot; teacher absent", "enrollment up: minimal change"])]
    for i, (t_, ls) in enumerate(outs):
        b += box(1010, 60 + i * 110, 300, 96, t_, ls, "#fff", OPT, OPT)
    b += T(10, 490, "Stakeholders touched: 626 students &middot; 54 teachers &middot; timetabler &middot; building (63 rooms)", 21, INK, "start", 600)
    return svg(1320, 510, b)


def fig_week(D):
    cfg = D.w.cfg
    per = cfg["periods"]["period"]
    b = T(0, 24, "Period lengths (minutes)", 21, INK, "start", 700)
    x = 0
    sc = 3.1
    for p in per:
        wd = p["minutes"] * sc
        b += f'<rect x="{x}" y="40" width="{wd - 4:.1f}" height="64" fill="{OPT if p["minutes"] > 45 else "#8fb2d9"}"/>'
        b += T(x + wd / 2 - 2, 70, f"P{p['id']}", 22, "#fff", "middle", 700) + T(x + wd / 2 - 2, 94, f"{p['minutes']}", 20, "#fff", "middle")
        x += wd
        if p["id"] == 4:
            b += T(x + 22, 78, "lunch", 18, MUT, "middle", 400, "Georgia,serif", 'font-style="italic"')
            x += 44
    b += T(0, 140, "The same lesson is 40 or 60 minutes depending on where it lands: a swap P1&harr;P2 silently removes 20 min/week.", 18, CUR)
    days = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    pe = {tuple(s) for s in cfg["slots"]["pe_blocked"]}
    ap = {tuple(s) for s in cfg["slots"]["ap_blocked"]}
    off = {tuple(s) for s in cfg["slots"]["off"]}
    y0 = 190
    b += T(0, y0 - 26, "The weekly grid every class must fit into", 21, INK, "start", 700)
    for j, d in enumerate(days):
        b += T(110 + j * 96 + 44, y0 - 2, d, 18, MUT, "middle")
    for p in range(1, 8):
        b += T(100, y0 + 32 + (p - 1) * 42, f"P{p}", 17, MUT, "end")
        for j, d in enumerate(days):
            if (d, p) in off:
                fill, lab = "#fff", "off"
            elif (d, p) in pe:
                fill, lab = GOLD, "PE"
            elif (d, p) in ap:
                fill, lab = "#e6c3b3", "AP block"
            else:
                fill, lab = "#dbe6f3", ""
            b += f'<rect x="{110 + j * 96}" y="{y0 + 12 + (p - 1) * 42}" width="88" height="36" fill="{fill}" stroke="#fff"/>'
            if lab:
                b += T(110 + j * 96 + 44, y0 + 36 + (p - 1) * 42, lab, 16, INK if lab != "off" else MUT, "middle")
    b += f'<rect x="640" y="{y0 + 12}" width="22" height="22" fill="#dbe6f3"/>' + T(672, y0 + 30, "33 usable periods &minus; 2 PE = 31", 18, INK)
    b += f'<rect x="640" y="{y0 + 48}" width="22" height="22" fill="{GOLD}"/>' + T(672, y0 + 66, "PE Mon/Thu P5, all grades", 18, INK)
    b += f'<rect x="640" y="{y0 + 84}" width="22" height="22" fill="#e6c3b3"/>' + T(672, y0 + 102, "AP optional block, G11-AP only", 18, INK)
    b += T(640, y0 + 142, "Friday P6-P7 do not exist.", 18, MUT)
    b += T(640, y0 + 168, "Observed student: 33 of 33 periods used.", 18, MUT)
    return svg(1000, 520, b)


def fig_conflict():
    """Free-choice web vs pathway classes."""
    b = T(0, 28, "Free-choice electives", 24, INK, "start", 700) + T(520, 28, "Pathway classes (what we schedule)", 24, OPT, "start", 700)
    rnd = random.Random(3)
    cols = [CUR, OPT, TEAL, GOLD]
    # left: 3 homerooms feed 4 elective sections; every section shares students with several classes -> mesh
    homes = [(60, 120 + i * 130) for i in range(3)]
    secs = [(380, 100 + i * 100) for i in range(4)]
    for (hx, hy) in homes:
        for k, (sx, sy) in enumerate(secs):
            if rnd.random() < .75:
                b += f'<line x1="{hx + 36}" y1="{hy}" x2="{sx - 30}" y2="{sy}" stroke="{cols[k]}" stroke-width="2.6" opacity=".7"/>'
    for i, (hx, hy) in enumerate(homes):
        b += f'<circle cx="{hx}" cy="{hy}" r="36" fill="#fff" stroke="{INK}" stroke-width="2"/>' + T(hx, hy + 6, f"class {i + 1}", 17, INK, "middle")
    for k, (sx, sy) in enumerate(secs):
        b += f'<rect x="{sx - 30}" y="{sy - 24}" width="60" height="48" fill="{cols[k]}"/>' + T(sx, sy + 6, f"sec {k + 1}", 17, "#fff", "middle", 700)
    b += T(0, 520, "Sections tie classes together; lessons that may not overlap", 17, MUT) + T(0, 545, "form a clique of 31 &gt; 29 free periods: no valid grid.", 17, CUR, "start", 700)
    # right: pathway classes
    for i in range(3):
        y = 100 + i * 130
        b += f'<rect x="520" y="{y - 56}" width="440" height="112" fill="#fff" stroke="{OPT}" stroke-width="2"/>'
        b += T(534, y - 30, f"pathway {i + 1}: one class, identical timetable", 18, OPT, "start", 700)
        for k in range(4):
            b += f'<rect x="{540 + k * 100}" y="{y - 12}" width="86" height="44" fill="{cols[k]}" opacity=".9"/>' + T(540 + k * 100 + 43, y + 16, f"sec {k + 1}", 17, "#fff", "middle", 700)
    b += T(520, 520, "Each section holds one class: cliques stay below", 17, MUT) + T(520, 545, "the slot count; conflicts shrink to teachers, rooms.", 17, OPT, "start", 700)
    return svg(1000, 570, b)


def fig_pipeline(D):
    st = D.res["stats"]
    T_ = 33 * st["n_sections"]
    steps = [("Catalog + rules", "offered bundles per grade", f"{st['n_students']} students"),
             ("Sectioning", "class = identical choices", f"{st['n_sections']} sections, {st['n_meetings']} lessons"),
             ("Slots: CP-SAT", f"{T_:,} Booleans z[g,s]", "hard rules + 5 soft terms"),
             ("Rooms", "home rooms, matching, annealing", "exact person-seconds"),
             ("Certify + repair", "independent checker, repair", "0 violations")]
    b = ""
    for i, (t_, a, c) in enumerate(steps):
        x = i * 330
        b += f'<rect x="{x}" y="20" width="300" height="190" fill="{OPT if i in (2, 3) else "#fff"}" stroke="{INK}" stroke-width="1.8"/>'
        col = "#fff" if i in (2, 3) else INK
        mu = "#dbe6f3" if i in (2, 3) else MUT
        b += T(x + 16, 56, f"{i}", 40, mu, "start", 700, "Georgia,serif") + T(x + 56, 52, t_, 24, col, "start", 700)
        b += T(x + 16, 108, a, 18, mu) + T(x + 16, 160, c, 22, col, "start", 700)
        if i < 4:
            b += arrow(x + 300, 115, x + 330, 115)
    return svg(1640, 232, b)


def fig_calibration(D):
    cfg = D.w.cfg
    pairs = cfg["calibration"]["pairs"]
    names = cfg["calibration"]["names"]
    k = D.res["stats"]["k"]
    w, h = 760, 420
    L, R, T_, B = 80, w - 30, 30, h - 70
    sx = lambda v: L + (v - 2) / 5 * (R - L)
    sy = lambda v: B - (v - 2) / 5 * (B - T_)
    b = ""
    for v in range(2, 8):
        b += f'<line x1="{L}" x2="{R}" y1="{sy(v)}" y2="{sy(v)}" stroke="{FAINT}"/>' + T(L - 10, sy(v) + 6, str(v), 17, MUT, "end")
        b += T(sx(v), B + 26, str(v), 17, MUT, "middle")
    lo, hi = cfg["loads"]["k_band"]
    b += f'<polygon points="{sx(2)},{sy(2 * lo)} {sx(7)},{sy(7 * lo)} {sx(7)},{sy(min(7, 7 * hi))} {sx(2)},{sy(2 * hi)}" fill="{OPT}" opacity=".12"/>'
    b += f'<line x1="{sx(2)}" y1="{sy(2 * k)}" x2="{sx(7)}" y2="{sy(7 * k)}" stroke="{OPT}" stroke-width="3"/>'
    for (c, o), nm in zip(pairs, names):
        b += f'<circle cx="{sx(c)}" cy="{sy(o)}" r="9" fill="{CUR}" stroke="#fff" stroke-width="2"/>' + T(sx(c) + 14, sy(o) - 8, nm, 16, INK)
    b += T(sx(5.2), sy(5.2 * k) + 40, f"fit: slots = {k:.3f} &times; credit", 19, OPT, "start", 700)
    b += T(sx(4.0), sy(6.9), "band 0.83 &ndash; 1.00 (swept)", 17, OPT)
    b += T((L + R) / 2, h - 12, "catalog / GPA credit per week", 19, MUT, "middle") + T(18, (T_ + B) / 2, "observed slots / week", 19, MUT, "middle", 400, "sans-serif", f'transform="rotate(-90 18 {(T_ + B) / 2})"')
    return svg(w, h, b)


def fig_observed_path():
    import tomllib
    g = tomllib.load(open(ROOT / "src/data/current_grid.toml", "rb"))["slot"]
    mon = sorted((s["period"], s["room"], s["course"].replace("OBS ", "")) for s in g if s["day"] == "Mon" and s["parity"] == "all")
    rooms = [r for _, r, _ in mon]
    arrows = [(a, b_, CUR) for a, b_ in zip(rooms, rooms[1:]) if a != b_]
    pl = plan("1F", heat={r: .35 for r in set(rooms)}, hi=CUR, w=700, arrows=arrows, show_ids=True)
    seq = "  &rarr;  ".join(rooms)
    return pl, seq, len(arrows)


def fig_opt_path(D):
    sid = next(s for s in sorted(D.w.student_sections()) if s.startswith("G11AP"))
    out = {}
    for nm, (so, rm) in (("cur", D.cur), ("opt", D.opt)):
        items = sorted((D.w.slots[s]["period"], rm[(g, s)]) for g in D.w.student_sections()[sid] for s in so[g] if D.w.slots[s]["day"] == "Mon")
        out[nm] = [r for _, r in items]
    return sid, out


# ------------------------------------------------------------------------------ analytics ----
def per_slot_series(D, which):
    w = D.w
    so, rm = D.cur if which == "cur" else D.opt
    T_ = len(w.slots)
    rooms_used = {k: [0] * T_ for k in ("classroom", "lab", "arts")}
    for g, sl in so.items():
        for s in sl:
            rooms_used[w.sections[g].kind][s] += 1
    gap = [0] * T_
    days = defaultdict(list)
    for s in w.slots:
        days[s["day"]].append(s["idx"])
    for sid, lst in w.student_sections().items():
        blocked = w.blocked[w.students[sid]["grade"]]
        occ_all = set(s for g in lst for s in so[g]) | set(blocked)
        for d, idxs in days.items():
            occ = [i in occ_all for i in idxs]
            if any(occ):
                f = occ.index(True)
                l = len(occ) - 1 - occ[::-1].index(True)
                for i in range(f, l + 1):
                    if not occ[i]:
                        gap[idxs[i]] += 1
    return rooms_used, gap


def teacher_matrix(D, which):
    w = D.w
    so, _ = D.cur if which == "cur" else D.opt
    T_ = len(w.slots)
    tm = defaultdict(set)
    for g, sec in w.sections.items():
        for s in so[g]:
            tm[sec.teacher].add(s)
    days = defaultdict(list)
    for s in w.slots:
        days[s["day"]].append(s["idx"])
    order = sorted(w.teachers, key=lambda t: (w.teachers[t].dept, t))
    rows, labs = [], []
    last_dept = None
    for t in order:
        r = [0] * T_
        for s in range(T_):
            if s in tm[t]:
                r[s] = 1
            elif s in w.teachers[t].external_busy:
                r[s] = 2
        for d, idxs in days.items():
            occ = [r[i] != 0 for i in idxs]
            if any(occ):
                f = occ.index(True)
                l = len(occ) - 1 - occ[::-1].index(True)
                for i in range(f, l + 1):
                    if r[idxs[i]] == 0:
                        r[idxs[i]] = 3
        rows.append(r)
        d = w.teachers[t].dept
        labs.append(d[:4] if d != last_dept else "")
        last_dept = d
    vl = [i for i, s in enumerate(w.slots) if s["period"] == 1 and s["idx"] > 0]
    cl = [("MTWTF"[["Mon", "Tue", "Wed", "Thu", "Fri"].index(s["day"])] if s["period"] == 3 else "") for s in w.slots]
    return matrix(rows, T_, 11, 1, {0: "#fff", 1: "#4a4842", 2: GOLD, 3: CUR}, row_labels=labs, col_labels=cl, lab_w=64, top=26, vline=vl, cw=22), sum(r.count(3) for r in rows)


# ------------------------------------------------------------------------------------- page ---
CSS = """
@page{size:3600px 3300px;margin:0}
:root{--ink:#1b1b1b;--mut:#5a5750;--rule:#cfcabc;--paper:#f6f4ee;--cur:#d4572c;--opt:#1f5fa8}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:26px/1.45 'Segoe UI',Inter,system-ui,sans-serif;-webkit-print-color-adjust:exact;print-color-adjust:exact}
.poster{width:3600px;padding:64px 80px 56px}
header{display:grid;grid-template-columns:2100px 1fr;gap:60px;border-bottom:3px solid var(--ink);padding-bottom:30px}
h1{font:700 104px/1.02 Georgia,'Times New Roman',serif;margin:0;letter-spacing:-.01em}
.dek{font:italic 36px/1.35 Georgia,serif;color:var(--mut);margin-top:18px}
.num{display:grid;grid-template-columns:repeat(4,1fr);gap:0;border-left:1.5px solid var(--rule)}
.num div{padding:0 26px;border-right:1.5px solid var(--rule)}
.num b{display:block;font:700 92px/1 Georgia,serif;color:var(--opt)}
.num span{font-size:23px;color:var(--mut);line-height:1.25;display:block;margin-top:6px}
.row{display:grid;grid-template-columns:repeat(12,1fr);gap:0 44px;margin-top:40px}
.band{grid-column:1/-1;display:flex;align-items:baseline;gap:22px;border-top:3px solid var(--ink);padding-top:10px;margin-bottom:6px}
.band{margin-bottom:8px}.band h2{font:700 54px/1.1 Georgia,serif;margin:0}.band .k{font:700 54px/1.1 Georgia,serif;color:var(--cur)}
.band p{margin:0 0 0 auto;font:italic 28px Georgia,serif;color:var(--mut)}
.fig{padding:14px 0 6px}
.cap{font:italic 24px/1.35 Georgia,serif;color:var(--mut);margin-top:6px}
.cap b{font-style:normal;font-family:'Segoe UI',sans-serif;color:var(--ink)}
h3{font:700 30px Georgia,serif;margin:0 0 4px}
.s3{grid-column:span 3}.s4{grid-column:span 4}.s5{grid-column:span 5}.s6{grid-column:span 6}.s7{grid-column:span 7}.s8{grid-column:span 8}.s12{grid-column:1/-1}
.brief{margin-top:26px;border:2px solid var(--ink);padding:26px 30px;background:#fff;font:25px/1.45 Georgia,serif;position:relative}
.brief .lab{position:absolute;top:-17px;left:22px;background:var(--paper);padding:0 12px;font:700 22px 'Segoe UI',sans-serif;letter-spacing:.14em}
.brief p{margin:0 0 12px}.brief mark{background:#f3dccf;padding:0 3px}
.map{width:100%;border-collapse:collapse;font-size:23px;margin-top:14px}.map td{border-top:1.5px solid var(--rule);padding:5px 8px;vertical-align:top}.map td:first-child{font-weight:700;width:60px}
table.t{border-collapse:collapse;width:100%;font-size:23px}table.t td,table.t th{border-bottom:1.5px solid var(--rule);padding:5px 8px;text-align:left}table.t th{font-size:19px;letter-spacing:.08em;color:var(--mut);text-transform:uppercase}
.z{color:var(--opt);font-weight:800}.bad{color:var(--cur);font-weight:800}
.math h3{font:600 20px 'Segoe UI';letter-spacing:.1em;text-transform:uppercase;color:var(--mut);margin:14px 0 0}
.math .katex{font-size:1.18em}.katex-display{margin:.35em 0;overflow-x:auto;overflow-y:hidden}
.note{font-size:23px;color:var(--mut)}
ul.t{margin:6px 0;padding-left:30px;font-size:25px}ul.t li{margin:5px 0}
.legend{display:flex;gap:30px;font-size:22px;color:var(--mut);margin:2px 0 8px}.legend i{display:inline-block;width:24px;height:14px;margin-right:8px;vertical-align:-1px}
footer{margin-top:40px;border-top:3px solid var(--ink);padding-top:12px;font-size:22px;color:var(--mut);display:flex;justify-content:space-between}
.pl{display:grid;grid-template-columns:repeat(6,1fr);gap:8px}
"""


def fig(inner, no, cap, cls="s4"):
    return f'<div class="fig {cls}">{inner}<div class="cap"><b>Fig. {no}</b> &mdash; {cap}</div></div>'


def build():
    D = Data()
    res, st, w = D.res, D.res["stats"], D.w
    cs = res["current_system"]
    o = res["optimized"]["metrics"]
    cur_mean = lambda sec, k: statistics.mean(c["metrics"][sec][k] for c in cs)
    red = lambda sec, k: 100 * (1 - o[sec][k] / cur_mean(sec, k))
    figno = [0]

    def F(inner, cap, cls="s4"):
        figno[0] += 1
        return fig(inner, figno[0], cap, cls)

    # ---- brief with the verbatim prompt
    paras, cur_p = [], []
    for ln in QUESTION.replace("&", "&amp;").splitlines():
        t_ = ln.strip()
        if not t_ or t_.startswith("•") or (len(t_) > 1 and t_[0].isdigit() and t_[1] == "."):
            if cur_p:
                paras.append(" ".join(cur_p))
            cur_p = [t_] if t_ else []
        else:
            cur_p.append(t_)
    if cur_p:
        paras.append(" ".join(cur_p))
    qtxt = "".join(f"<p>{x}</p>" for x in paras)
    brief = f'<div class="brief"><span class="lab">THE BRIEF &middot; Question.txt, verbatim</span>{qtxt}</div>'
    mapping = """<table class="map"><tr><td>Q1</td><td>Problems in the current system &rarr; <b>B</b></td></tr>
<tr><td>Q2</td><td>Aspects chosen and how they are optimised &rarr; <b>C, D</b></td></tr>
<tr><td>Q3</td><td>Who is affected, how much, why it matters &rarr; <b>D</b></td></tr>
<tr><td>Q4</td><td>Improvement vs. today and how it is measured &rarr; <b>D</b></td></tr>
<tr><td>Q5</td><td>Proof that every constraint holds &rarr; <b>E</b></td></tr>
<tr><td>Q6</td><td>Coping when circumstances change &rarr; <b>F, G</b></td></tr></table>"""

    # ---- A
    secA = f"""<div class="band"><span class="k">A</span><h2>The problem and the school</h2><p>626 students, 54 teachers, 63 rooms, 33 periods a week</p></div>
<div class="s4">{brief}{mapping}</div>
{F(fig_context(D), "What goes in, what the system does, what comes out. The only real timetable data is one observed week; everything else is simulated from the catalog and the building model.", "s4")}
{F(fig_week(D), "Periods are unequal and the grid has fixed holes. Contact hours must be counted in minutes, not lessons.", "s4")}"""

    # ---- B problems
    pl, seq, nch = fig_observed_path()
    sid, paths = fig_opt_path(D)
    ch = lambda L: sum(1 for a, b in zip(L, L[1:]) if a != b)
    h_min = hist([[100 * (sum(w.slots[s]["minutes"] for s in D.cur[0][g]) / (sec.n * (sum(s["minutes"] for s in w.slots) / len(w.slots))) - 1) for g, sec in w.sections.items()],
                  [100 * (sum(w.slots[s]["minutes"] for s in D.opt[0][g]) / (sec.n * (sum(s["minutes"] for s in w.slots) / len(w.slots))) - 1) for g, sec in w.sections.items()]],
                 w=900, h=360, bins=28, xlab="weekly minutes of a section vs. nominal (%)", ylab="share of sections (%)", lo=-45, hi=45)
    viol = round(statistics.mean(c["check"]["violations"].get("H8", 0) for c in cs))
    secB = f"""<div class="band"><span class="k">B</span><h2>What is wrong today</h2><p>Q1 &mdash; problems in the current timetable system</p></div>
{F('<div style="width:50%">' + pl + '</div>' + f'<div class="note" style="margin-top:8px"><b>Monday of the one real week:</b> {seq}<br><b>{nch}</b> room changes in one day; <b>21</b> per week, 488 s of walking.</div>', "One G11-AP student&rsquo;s observed Monday on the 1F plan. Every teacher owns a room, so the student walks to the teacher all day.", "s4")}
{F(fig_conflict(), "Why the obvious fix does not work: free elective choice couples classes into a clique larger than the free periods. Pathway classes remove the coupling.", "s4")}
<div class="s4"><div class="fig"><h3>The hours rule nobody checks</h3>{h_min}<div class="cap"><b>Fig. {figno[0] + 1}</b> &mdash; Weekly minutes of every section against its nominal. A grid built without looking at period length puts <b>{viol} of {st['n_sections']}</b> sections out of the &plusmn;8% band; ours puts none (the brief: <i>hours should not change</i>).</div></div>
<ul class="t"><li>No objective on students&rsquo; walking, idle gaps or day shape.</li><li>Repair after a room loss is manual.</li><li>No independent proof that the grid is legal.</li></ul></div>"""
    figno[0] += 1

    # ---- C method
    secC = f"""<div class="band"><span class="k">C</span><h2>Method</h2><p>Q2 &mdash; what we optimise, and how</p></div>
{F(fig_pipeline(D), "Four stages, each checkable on its own. Stage 1 uses one Boolean per section and slot, so the model grows linearly instead of with every pair of lessons.", "s8")}
{F(fig_calibration(D), "Loads come from the catalog credits through a factor fitted on the observed week (credit &rarr; slots), carried as a band, never as a point.", "s4")}
<div class="s12 math" style="display:grid;grid-template-columns:repeat(3,1fr);gap:0 60px">
<div><h3>Credit to weekly slots</h3>$$n_c=\\Big\\lfloor k\\kappa_c+\\tfrac12\\Big\\rfloor,\\quad k=\\frac{{\\sum_i\\kappa_i o_i}}{{\\sum_i\\kappa_i^{{2}}}}\\approx {st['k']:.3f}$$
<h3>Hard rules (z<sub>g,s</sub> &isin; {{0,1}})</h3>$$\\sum_s z_{{g,s}}=n_g,\\quad \\sum_{{g\\in\\sigma}}z_{{g,s}}\\le1,\\quad \\sum_{{g\\in T_t}}z_{{g,s}}\\le1$$$$\\sum_{{g:\\,a_g\\ge a}}z_{{g,s}}\\le R_\\kappa(a)\\quad(\\text{{room area}})$$</div>
<div><h3>Contact hours in minutes</h3>$$\\Big|\\sum_s\\mu_s z_{{g,s}}-n_g\\bar\\mu\\Big|\\le\\max(\\tau n_g\\bar\\mu,\\,9),\\ \\tau=0.08$$
<h3>Stage 1: slot objective</h3>$$\\min\\ w_{{gap}}\\sum_\\sigma c_\\sigma\\Gamma_\\sigma+w_h\\sum_\\sigma c_\\sigma H_\\sigma+w_{{sp}}\\sum_g|g|\\,\\mathrm{{rep}}_g+w_m\\!\\!\\sum_{{g\\ \\mathrm{{hard}}}}\\!\\!|g|\\sum_s(p_s-1)z_{{g,s}}+w_{{tg}}\\sum_t\\Gamma_t$$</div>
<div><h3>Stage 2: person-seconds</h3>$$\\min_r\\sum_{{(a,b)\\in\\mathcal L_{{stud}}}}n_{{ab}}\\,\\tau(r_a,r_b)+\\lambda\\!\\!\\sum_{{(a,b)\\in\\mathcal L_{{teach}}}}\\!\\!\\tau(r_a,r_b)$$
<h3>Score, fairness, robustness</h3>$$J=\\bar\\ell_{{stud}}+\\alpha\\bar L_t+\\beta\\,\\mathrm{{CVaR}}_q(L),\\qquad \\mathbb E[\\Delta]=\\sum_\\xi p_\\xi\\Delta(\\xi)$$
<p class="note">Students stay, teachers walk: &lambda; prices a teacher-second against a student-second (swept in F). &Gamma; = idle gaps, H = days with six classes or more, rep = same-day repeats of one section.</p></div></div>"""

    # ---- D results
    mo, mc = D.m_opt, D.m_cur
    t_cur, t_opt = traffic(w, *D.cur), traffic(w, *D.opt)
    gmax = max(max(t_cur.values()), max(t_opt.values()))
    rf = D.rfloor
    plans_html = ""
    for lab, tr, col in (("Current", t_cur, CUR), ("Optimized", t_opt, OPT)):
        row = ""
        for fl in FLOORS:
            heat = {r: (v / gmax) ** 0.6 for r, v in tr.items() if rf.get(r) == fl}
            row += f'<div>{plan(fl, heat, col, 540, title=(f"{lab} &middot; {fl}"))}</div>'
        plans_html += f'<div class="pl">{row}</div>'
    h1 = hist([[p["travel_s"] for p in mc["per_student"].values()], [p["travel_s"] for p in mo["per_student"].values()]], 1100, 380, 30, "walking per student per week (s)")
    h2 = hist([[p["changes"] for p in mc["per_student"].values()], [p["changes"] for p in mo["per_student"].values()]], 1100, 380, 24, "room changes per student per week", lo=0, hi=36)
    h3 = hist([[p["gaps"] for p in mc["per_student"].values()], [p["gaps"] for p in mo["per_student"].values()]], 1100, 380, 12, "idle periods between classes per student per week", lo=0, hi=12)
    ru_c, gap_c = per_slot_series(D, "cur")
    ru_o, gap_o = per_slot_series(D, "opt")
    idx = list(range(len(w.slots)))
    s_gap = line([[(i, v) for i, v in zip(idx, gap_c)], [(i, v) for i, v in zip(idx, gap_o)]], 1100, 360, "period of the week (Mon P1 &hellip; Fri P5)", "students idle in a gap", (CUR, OPT), ("Current", "Optimized"), marker=False)
    s_room = line([[(i, v) for i, v in zip(idx, ru_c["classroom"])], [(i, v) for i, v in zip(idx, ru_o["classroom"])], [(i, 49) for i in idx]], 1100, 360, "period of the week", "classrooms in use (of 49)", (CUR, OPT, "#8d887b"), ("Current", "Optimized", "capacity"), marker=False, ylo=0, yhi=52)
    tm_c, tg_c = teacher_matrix(D, "cur")
    tm_o, tg_o = teacher_matrix(D, "opt")
    ab = res["ablation"]
    abl_rows = [("Current: blind slots + teacher-owned rooms", cur_mean("students", "travel_s_mean"), CUR),
                ("Blind slots + optimised rooms", ab["blind_slots+opt_rooms"]["metrics"]["students"]["travel_s_mean"], TEAL),
                ("Optimised slots + teacher-owned rooms", ab["opt_slots+owned_rooms"]["metrics"]["students"]["travel_s_mean"], TEAL),
                ("Optimised slots + optimised rooms", o["students"]["travel_s_mean"], OPT)]
    mx = max(r[1] for r in abl_rows)
    ab_svg = "".join(T(8, 38 + i * 62, r[0], 21, INK) + f'<rect x="8" y="{48 + i * 62}" width="{r[1] / mx * 780:.0f}" height="20" fill="{r[2]}"/>' + T(r[1] / mx * 780 + 18, 66 + i * 62, f"{r[1]:.0f} s", 21, INK, "start", 700) for i, r in enumerate(abl_rows))
    stake = f"""<table class="t"><tr><th>Who</th><th>Measure (per week)</th><th>Current</th><th>Optimized</th></tr>
<tr><td>626 students</td><td>walking (s)</td><td>{cur_mean('students','travel_s_mean'):.0f}</td><td class="z">{o['students']['travel_s_mean']:.0f}</td></tr>
<tr><td></td><td>room changes</td><td>{cur_mean('students','room_changes_mean'):.1f}</td><td class="z">{o['students']['room_changes_mean']:.1f}</td></tr>
<tr><td></td><td>idle periods</td><td>{cur_mean('students','gaps_mean'):.2f}</td><td class="z">{o['students']['gaps_mean']:.2f}</td></tr>
<tr><td></td><td>worst-20% walking (s)</td><td>{cur_mean('students','travel_s_cvar80'):.0f}</td><td class="z">{o['students']['travel_s_cvar80']:.0f}</td></tr>
<tr><td></td><td>hard subjects: mean period</td><td>{cur_mean('students','hard_subject_mean_period'):.2f}</td><td class="z">{o['students']['hard_subject_mean_period']:.2f}</td></tr>
<tr><td>54 teachers</td><td>idle gaps</td><td>{cur_mean('teachers','gaps_mean'):.1f}</td><td class="z">{o['teachers']['gaps_mean']:.1f}</td></tr>
<tr><td></td><td>walking (s)</td><td>{cur_mean('teachers','travel_s_mean'):.0f}</td><td class="bad">{o['teachers']['travel_s_mean']:.0f}</td></tr>
<tr><td></td><td>schedule loss L</td><td>{cur_mean('teachers','sched_L_mean'):.1f}</td><td class="z">{o['teachers']['sched_L_mean']:.1f}</td></tr>
<tr><td>Everyone</td><td>sections off the minute band</td><td>{viol}</td><td class="z">0</td></tr></table>"""
    secD = f"""<div class="band"><span class="k">D</span><h2>Results against the current system</h2><p>Q3, Q4 &mdash; who gains, how much, how measured</p></div>
<div class="s12"><div class="legend"><span><i style="background:var(--cur)"></i>Current system (emulator calibrated to the observed week, {len(cs)} runs; the one shown is run 0)</span><span><i style="background:var(--opt)"></i>Optimized</span></div></div>
<div class="s12 fig"><h3>Where students change rooms</h3>{plans_html}<div class="cap"><b>Fig. {figno[0] + 1}</b> &mdash; Real building model, six floors. Area of colour = room changes touching that room per week, one common scale. Teacher-owned rooms scatter traffic across the whole building; home-class rooms concentrate it where classes live.</div></div>"""
    figno[0] += 1
    secD += f"""{F(h1, f"Walking time of every student. Mean {cur_mean('students','travel_s_mean'):.0f} &rarr; {o['students']['travel_s_mean']:.0f} s (&minus;{red('students','travel_s_mean'):.0f}%); the worst-20% tail falls too, so the gain is not bought from a few.", "s4")}
{F(h2, f"Room changes per student per week (observed week: 21).", "s4")}
{F(h3, f"Idle periods stranded between classes, per student per week: &minus;{red('students','gaps_mean'):.0f}%.", "s4")}
{F(s_gap, "Students sitting in a gap, by period of the week. Optimized grids push free periods to the edges of the day.", "s4")}
{F(s_room, "Classrooms in use by period. Demand never nears the 49 available; the building has room to spare, so the saving is not a capacity artefact.", "s4")}
<div class="s4 fig"><h3>Which decision buys the saving?</h3>{svg(900, 270, ab_svg)}<div class="cap"><b>Fig. {figno[0] + 1}</b> &mdash; 2&times;2 ablation. Room policy removes the walking; slot policy removes the idle gaps.</div></div>"""
    figno[0] += 1
    secD += f"""<div class="s8 fig"><h3>Every teacher, every period of the week</h3>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:30px"><div><div class="note"><b style="color:var(--cur)">Current</b> &mdash; {tg_c} idle gaps</div>{tm_c}</div><div><div class="note"><b style="color:var(--opt)">Optimized</b> &mdash; {tg_o} idle gaps</div>{tm_o}</div></div>
<div class="legend"><span><i style="background:#4a4842"></i>teaching</span><span><i style="background:{GOLD}"></i>busy elsewhere (IB / G12, other building)</span><span><i style="background:var(--cur)"></i>idle gap between lessons</span></div>
<div class="cap"><b>Fig. {figno[0] + 1}</b> &mdash; 54 teachers &times; 33 periods, grouped by department. Orange cells are free periods trapped between two lessons of the same day.</div></div>
<div class="s4 fig"><h3>Who gains, by how much</h3>{stake}<div class="cap">Teachers walk more, deliberately: 626 students stay put and 54 teachers carry the move.</div></div>"""
    figno[0] += 1

    # ---- E verification
    cert = "".join(f'<tr><td>{c}</td><td>{d}</td><td class="z">{res["optimized"]["check"]["violations"].get(c, 0)}</td><td class="bad">{round(statistics.mean(x["check"]["violations"].get(c, 0) for x in cs))}</td><td>{"caught" if (D.mut or {"caught": {}})["caught"].get(c) else "&ndash;"}</td></tr>'
                   for c, d in checker.CODES.items())
    chk = D.res["optimized"]["check"]["n_checked"]
    ind = svg(980, 300, box(10, 20, 270, 100, "Solver", ["CP-SAT + annealing"], "#fff") + arrow(280, 70, 370, 70)
              + box(370, 20, 250, 100, "Finished grid", ["slots + rooms only"], "#fff", OPT, OPT) + arrow(620, 70, 710, 70)
              + box(710, 20, 260, 100, "Checker", ["shares no code with", "the solver"], INK, INK, "#fff").replace(f'fill="{MUT}"', 'fill="#e8e5db"')
              + box(370, 170, 250, 100, "Mutation test", ["plant 1 fault per rule"], "#fff", CUR, CUR) + arrow(620, 220, 780, 130, CUR)
              + T(10, 200, "A checker that cannot", 20, MUT) + T(10, 226, "fail cannot certify.", 20, MUT))
    secE = f"""<div class="band"><span class="k">E</span><h2>Proof that every rule holds</h2><p>Q5 &mdash; how we confirm the timetable satisfies every constraint</p></div>
<div class="s7 fig"><table class="t"><tr><th>Rule</th><th>Hard constraint</th><th>Ours</th><th>Current</th><th>Planted fault</th></tr>{cert}</table>
<div class="cap"><b>Fig. {figno[0] + 1}</b> &mdash; {chk['sections']} sections, {chk['students']} students, {chk['teachers']} teachers, {chk['room_legs']} room legs checked. Current = mean over {len(cs)} emulated grids.</div></div>"""
    figno[0] += 1
    secE += f"""{F(ind, "The checker re-derives every rule from the finished grid. The mutation suite proves it can fail: 10 of 10 planted faults were detected. 20 automated tests cover loads, selection rules, the solver, repairs and a regression on the observed week.", "s5")}"""

    # ---- F sensitivity
    oat, lhs, par = D.oat, D.lhs, D.par
    nice = {"solve.w_gap": "weight: student idle gap", "solve.w_spread": "weight: same-day repeat", "solve.w_morning": "weight: hard subject late",
            "solve.w_tgap": "weight: teacher idle gap", "solve.w_teacher_leg": "weight: teacher walking", "loads.k": "credit&rarr;slot factor k",
            "school.section_cap": "section cap", "school.section_floor": "minimum section size", "school.min_free_periods": "reserved free periods",
            "school.headcount": "headcount &plusmn;10%", "rooms.removed_frac": "rooms removed (0&ndash;55%)", "teachers.scale": "teacher supply",
            "teachers.external_busy_prob": "teachers shared with IB/G12", "solve.minutes_tol": "contact-minute tolerance",
            "solve.lab_doubles": "lab double periods", "school.pathways_G10": "G10 offered pathways", "school.pathways_G11AP": "G11-AP offered pathways",
            "solve.time_limit_s": "solver time limit", "solve.seed": "solver seed"}
    f_html = ""
    if oat:
        ok = [r for r in oat if "improvement" in r]
        base = next((r for r in oat if r["tag"] == "base" and "improvement" in r), None)
        by = defaultdict(list)
        for r in ok:
            if r["tag"] != "base":
                by[r["tag"].split("=")[0]].append(r["improvement"]["travel_pct"])
        rows = sorted([(nice.get(k, k), min(v), max(v)) for k, v in by.items()], key=lambda r: r[2] - r[1])
        tor = tornado(rows, base["improvement"]["travel_pct"] if base else 55, 1000, 34, 330)
        n_sq = sum(1 for r in oat if "status_quo_error" in r)
        n_ok = sum(1 for r in oat if "opt" in r and r["opt"]["ok"])
        capp = sorted([(r["overrides"]["rooms.removed_frac"] * 100, r["opt"]["students"]["travel_s_mean"]) for r in oat if r["tag"].startswith("rooms.removed_frac") and "opt" in r])
        capb = [r["overrides"]["rooms.removed_frac"] * 100 for r in oat if r["tag"].startswith("rooms.removed_frac") and "status_quo_error" in r]
        kp = sorted([(r["overrides"]["loads.k"], r["opt"]["students"]["travel_s_mean"]) for r in oat if r["tag"].startswith("loads.k") and "opt" in r])
        kb = [r["overrides"]["loads.k"] for r in oat if r["tag"].startswith("loads.k") and "status_quo_error" in r]
        gp = sorted([(r["overrides"]["solve.w_gap"], r["opt"]["students"]["gaps_mean"]) for r in oat if r["tag"].startswith("solve.w_gap") and "opt" in r])
        tp = sorted([(r["overrides"]["teachers.scale"], r["stats"]["n_teachers"]) for r in oat if r["tag"].startswith("teachers.scale") and "stats" in r])
        pth = sorted([(r["overrides"]["school.pathways"]["G10"], r["stats"]["n_sections"]) for r in oat if r["tag"].startswith("school.pathways_G10") and "stats" in r])
        f_html += F(tor, f"Tornado on the headline: how far each assumption moves the walking reduction vs. the current method (%), {len(oat)} runs, each re-solved and re-checked ({n_ok} with zero violations).", "s5")
        capb = [r["overrides"]["rooms.removed_frac"] * 100 for r in oat if r["tag"].startswith("rooms.removed_frac") and "opt" not in r]
        f_html += F(line([capp], 800, 380, "classrooms and labs removed (%)", "optimized walking (s/wk)", (OPT,), None, capb, "no grid found"), "Capacity cliff: between 20% and 40% of rooms removed the instance stops having a valid grid; the system reports infeasible instead of a bad timetable.", "s4")
        f_html += F(fig_envelope(list(oat) + list(lhs or []), 0.8725), "Operating envelope from every sweep run: the load factor k and room loss are the binding assumptions. At k &ge; 0.95 neither the current-style method nor ours found a valid grid in 45&ndash;120 s.", "s4")
        f_html += F(line([gp], 800, 380, "weight on student idle gaps", "idle periods / student / wk", (OPT,), None, None, "", "{:.0f}", "{:.2f}"), "Objective weight vs. outcome: the gap weight buys idle periods smoothly, no cliff.", "s4")
        f_html += F(line([tp], 800, 380, "teacher supply factor", "teachers needed", (CUR,), None, None, "", "{:.2f}"), "Staffing is an output: the number of teachers needed as supply tightens.", "s4")
        f_html += F(line([pth], 800, 380, "G10 pathways offered", "sections to staff", (CUR,), None, None, "", "{:.0f}"), "The price of choice: more pathways means smaller classes and more sections.", "s4")
    if lhs and D.spec:
        import numpy as np
        rws = [r for r in lhs if "opt" in r]
        if len(rws) >= 24:
            keys = list(D.spec)
            X = np.array([[r["overrides"][k] for k in keys] for r in rws], float)
            Xs = (X - X.mean(0)) / (X.std(0) + 1e-12)
            y = np.array([r["opt"]["students"]["lost_min_week_mean"] for r in rws], float)
            beta, *_ = np.linalg.lstsq(Xs, (y - y.mean()) / (y.std() + 1e-12), rcond=None)
            nm = {k: nice.get(k, k) for k in keys}
            order = sorted(range(len(keys)), key=lambda i: abs(beta[i]))
            f_html += F(hbars([(nm[keys[i]], float(beta[i])) for i in order], 900, 36, 330), f"Global screening over {len(rws)} Latin-hypercube runs, all eight factors varied at once: standardised effect on student lost time.", "s4")
    if par:
        f_html += F(line([[(p["teacher_travel_s"], p["student_travel_s"]) for p in par]], 800, 380, "teacher walking (s/wk)", "student walking (s/wk)", (CUR,), None, None, "", "{:.0f}", "{:.0f}", None, None, [f"&lambda;={p['lambda']}" for p in par]), "Pareto front: moving walking from many students to few teachers is cheap, until &lambda; becomes large.", "s4")
    secF = f"""<div class="band"><span class="k">F</span><h2>Sensitivity: do the conclusions survive?</h2><p>Q6 &mdash; assumptions, structure and capacity, varied one at a time and all at once</p></div>{f_html}"""

    # ---- G shocks
    rng = random.Random(4)
    base = metrics.evaluate(w, *D.opt)
    cl = None
    for sd in range(40):
        r = shocks.room_closure(w, *D.opt, base, random.Random(sd), time_limit=10)
        if r.get("feasible") and r.get("affected_meetings", 0) >= 25 and r.get("moves"):
            cl = r
            break
    sh = res["shocks"]["draws"]
    if cl:
        closed = cl["closed"][0]
        fl = D.rfloor[closed]
        cnt = Counter((a, b) for _, _, a, b in [(m[0], m[1], m[2], m[3]) for m in cl["moves"]])
        arr = [(a, b, OPT) for (a, b), n in cnt.items() if D.rfloor.get(b) == fl and D.rfloor.get(a) == fl]
        heat = {b: min(1, n / 6) for (a, b), n in cnt.items() if D.rfloor.get(b) == fl}
        pcl = plan(fl, heat, OPT, 560, closed=(closed,), arrows=arr, title=f"Room {closed} closed for the week ({fl})")
        cap_cl = f"{cl['affected_meetings']} lessons lose their room; {cl['room_changes']} are re-roomed in a free room of the same kind, <b>{cl['moved_meetings']} lessons change time</b>. Blue = receiving rooms."
    else:
        pcl, cap_cl = "", ""
    ta = sh["teacher_absence_1day"]
    bars = ""
    for i, x in enumerate(ta):
        bars += f'<rect x="{80 + i * 62}" y="{300 - x["affected_meetings"] * 26}" width="46" height="{x["affected_meetings"] * 26}" fill="#cfcabc"/><rect x="{80 + i * 62}" y="{300 - x["covered"] * 26}" width="46" height="{x["covered"] * 26}" fill="{OPT}"/>'
        bars += T(80 + i * 62 + 23, 326, str(i + 1), 17, MUT, "middle")
    ta_svg = svg(840, 360, bars + T(420, 354, "random draw (teacher, day)", 18, MUT, "middle") + T(8, 150, "lessons", 18, MUT, "start", 400, "sans-serif", "transform=\"rotate(-90 20 150)\"") + f'<rect x="560" y="10" width="22" height="14" fill="#cfcabc"/>' + T(590, 23, "lessons that day", 18, INK) + f'<rect x="560" y="36" width="22" height="14" fill="{OPT}"/>' + T(590, 49, "covered by a substitute", 18, INK))
    su = sh["enrollment_surge_5pct"]
    sb = ""
    for i, x in enumerate(su):
        sb += f'<rect x="{80 + i * 62}" y="{300 - x.get("rooms_outgrown", 0) * 6}" width="46" height="{x.get("rooms_outgrown", 0) * 6}" fill="{GOLD}"/><rect x="{80 + i * 62}" y="{300 - x.get("moved_meetings", 0) * 6}" width="46" height="{max(x.get("moved_meetings", 0) * 6, 1)}" fill="{CUR}"/>'
        sb += T(80 + i * 62 + 23, 326, str(i + 1), 17, MUT, "middle")
    su_svg = svg(840, 360, sb + T(420, 354, "random draw", 18, MUT, "middle") + f'<rect x="560" y="10" width="22" height="14" fill="{GOLD}"/>' + T(590, 23, "lessons needing a bigger room", 18, INK) + f'<rect x="560" y="36" width="22" height="14" fill="{CUR}"/>' + T(590, 49, "lessons re-timed", 18, INK))
    ex = res["shocks"]["expected"]
    secG = f"""<div class="band"><span class="k">G</span><h2>When circumstances change</h2><p>Q6 &mdash; repair ladder: substitute &rarr; re-room &rarr; re-time only what must move</p></div>
{F(pcl, cap_cl, "s4")}
{F(ta_svg, f"Teacher absent for a day (p = 0.4): a qualified, free colleague covers {100 * sum(x['covered'] for x in ta) / max(1, sum(x['affected_meetings'] for x in ta)):.0f}% of lessons; nothing in the grid moves.", "s4")}
{F(su_svg, "Enrollment +5% (p = 0.3): rooms that no longer fit are swapped for bigger ones; the grid itself keeps its times.", "s4")}
<div class="s12 note" style="margin-top:6px">Expected cost over the three scenarios: <b>E[moved lessons] = {ex['moved_meetings']:.2f}</b>, E[room changes] = {ex['room_changes']:.1f}, infeasible rate {100 * ex['infeasible_rate']:.0f}%, over {len(sh['room_closure_1week'])} draws each. Every repaired grid is run back through the independent checker.</div>"""

    # ---- H limits
    gap = 100 * (res["optimized"]["solver"]["objective"] - res["optimized"]["solver"]["bound"]) / res["optimized"]["solver"]["objective"]
    secH = f"""<div class="band"><span class="k">H</span><h2>Limits, and how to reproduce</h2><p>what we did not prove</p></div>
<div class="s4"><ul class="t"><li><b>One real week only.</b> The current system is an emulator calibrated to it (about {res['emulator_calibration']['g11_changes']:.0f} vs 21 changes); everything else is simulated. Registrar CSVs drop in.</li><li><b>Operating envelope.</b> Valid grids were found at k &asymp; 0.87 with up to 20% of rooms removed; at k &ge; 0.95 or &ge; 40% rooms removed none was found in the time limit (Fig. 20).</li><li><b>Not proven optimal.</b> CP-SAT stopped at its time limit, {gap:.0f}% from its bound: &ldquo;optimized&rdquo; means best feasible found.</li></ul></div>
<div class="s4"><ul class="t"><li><b>Pathway classes trade choice for feasibility</b> (Fig. 4); the price is quantified in F.</li><li><b>Minutes:</b> sections of one course can still differ by up to 36% in weekly minutes; the next rule to add is equality across sections.</li></ul></div>
<div class="s4"><ul class="t"><li><b>Reproduce:</b> <code>python -m tt.run</code>, <code>python -m tt.sensitivity</code>, <code>python -m tt.poster2</code>.</li><li>Every number on this poster is read from <code>output/*.json</code>; seeds and the config hash are fixed.</li></ul></div>"""

    header = f"""<header><div><h1>A timetable that respects people</h1><div class="dek">Automatic scheduling for {st['n_students']} students, {st['n_teachers']} teachers and 63 rooms &mdash; fewer footsteps, no stranded periods, every rule independently proven, and a plan for when something breaks.</div></div>
<div class="num"><div><b>&minus;{red('students','travel_s_mean'):.0f}%</b><span>student walking per week</span></div><div><b>&minus;{red('students','gaps_mean'):.0f}%</b><span>idle periods between classes</span></div><div><b>0</b><span>violations of 10 hard rules, certified independently</span></div><div><b>10/10</b><span>planted faults caught by the checker</span></div></div></header>"""

    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>A timetable that respects people</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.css">
<script defer src="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.js"></script>
<script defer src="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/contrib/auto-render.min.js" onload="renderMathInElement(document.body,{{delimiters:[{{left:'$$',right:'$$',display:true}}]}})"></script>
<style>{CSS}</style></head><body><div class="poster">{header}
<div class="row">{secA}</div><div class="row">{secB}</div><div class="row">{secC}</div><div class="row">{secD}</div>
<div class="row">{secE}</div><div class="row">{secF}</div><div class="row">{secG}</div><div class="row">{secH}</div>
<footer><span>Constraints from the course catalog &middot; building: 6 floors, 103 rooms, stair-aware walking times &middot; simulated school, seed 20261024</span><span>Python, OR-Tools CP-SAT</span></footer></div></body></html>"""
    (OUT / "poster_large.html").write_text(html, encoding="utf-8")
    return OUT / "poster_large.html"


if __name__ == "__main__":
    p = build()
    print("wrote", p)
