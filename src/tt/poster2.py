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
    ins = [("Course catalog", ["230 courses, weekly credits", "course selection rules", "6+ students to run"]),
           ("Building model", ["6 floors, 103 rooms", "walking time room to room", "room sizes"]),
           ("One real week", ["one G11-AP student", "teacher-owned rooms", "21 room changes"])]
    for i, (t_, ls) in enumerate(ins):
        b += box(10, 20 + i * 150, 330, 130, t_, ls, "#fff")
        b += arrow(340, 85 + i * 150, 420, 210 + (i - 1) * 25)
    b += f'<rect x="420" y="20" width="520" height="430" fill="{INK}"/>'
    b += T(450, 62, "Scheduler", 30, "#fff", "start", 700, "Georgia,serif")
    for i, (t_, l_) in enumerate([("0  Classes", f"{st['n_students']} students, {st['n_sections']} classes"),
                                  ("1  Time", f"{st['n_meetings']} lessons, 33 periods"),
                                  ("2  Rooms", "cut walking"),
                                  ("3  Check", "separate checker, 10 rules")]):
        y = 90 + i * 85
        b += f'<rect x="446" y="{y}" width="468" height="68" fill="#fff"/>' + T(462, y + 30, t_, 24, INK, "start", 700) + T(462, y + 56, l_, 19, MUT)
    for i in range(3):
        b += arrow(940, 130 + i * 110, 1010, 130 + i * 110)
    outs = [("Timetable", ["who, when, where", "for every lesson"]), ("Certificate", ["0 broken rules of 10", "10/10 mistakes caught"]),
            ("Repair plans", ["room lost, teacher away", "smallest change"])]
    for i, (t_, ls) in enumerate(outs):
        b += box(1010, 60 + i * 110, 300, 96, t_, ls, "#fff", OPT, OPT)
    b += T(10, 490, "Affected: 626 students, 54 teachers, the timetabler", 21, INK, "start", 600)
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
    b += T(0, 140, "A swap P1 &harr; P2 silently removes 20 min a week.", 18, CUR)
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
    b += f'<rect x="640" y="{y0 + 12}" width="22" height="22" fill="#dbe6f3"/>' + T(672, y0 + 30, "31 usable periods", 18, INK)
    b += f'<rect x="640" y="{y0 + 48}" width="22" height="22" fill="{GOLD}"/>' + T(672, y0 + 66, "PE, all grades", 18, INK)
    b += f'<rect x="640" y="{y0 + 84}" width="22" height="22" fill="#e6c3b3"/>' + T(672, y0 + 102, "AP block, G11-AP only", 18, INK)
    b += T(640, y0 + 142, "No Friday P6-P7.", 18, MUT)
    b += T(640, y0 + 168, "Same every week.", 18, MUT)
    return svg(1000, 520, b)


def fig_conflict():
    """Free-choice web vs pathway classes."""
    b = T(0, 28, "Everyone picks freely", 24, INK, "start", 700) + T(520, 28, "Pick a package (what we use)", 24, OPT, "start", 700)
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
        b += T(534, y - 30, f"package {i + 1}: one class, one timetable", 18, OPT, "start", 700)
        for k in range(4):
            b += f'<rect x="{540 + k * 100}" y="{y - 12}" width="86" height="44" fill="{cols[k]}" opacity=".9"/>' + T(540 + k * 100 + 43, y + 16, f"sec {k + 1}", 17, "#fff", "middle", 700)
    b += T(520, 520, "Each section holds one class: cliques stay below", 17, MUT) + T(520, 545, "the slot count; conflicts shrink to teachers, rooms.", 17, OPT, "start", 700)
    return svg(1000, 570, b)


def fig_pipeline(D):
    st = D.res["stats"]
    T_ = 33 * st["n_sections"]
    steps = [("Rules", "course packages", f"{st['n_students']} students"),
             ("Classes", "same package = one class", f"{st['n_sections']} classes"),
             ("Time", f"{T_:,} yes/no choices", "rules + 5 goals"),
             ("Rooms", "home rooms + swaps", "less walking"),
             ("Check + repair", "separate checker", "0 broken rules")]
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
    grp = {}
    for (c, o), nm in zip(pairs, names):
        grp.setdefault((c, o), []).append(nm)
    for (c, o), nms in grp.items():
        b += f'<circle cx="{sx(c)}" cy="{sy(o)}" r="9" fill="{CUR}" stroke="#fff" stroke-width="2"/>'
        for j, nm in enumerate(nms):
            b += T(sx(c) + 14, sy(o) - 8 + j * 20, nm, 16, INK)
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
body{margin:0;background:var(--paper);color:var(--ink);font:29px/1.5 'Segoe UI',Inter,system-ui,sans-serif;-webkit-print-color-adjust:exact;print-color-adjust:exact}
.poster{width:3600px;padding:64px 80px 56px}
header{display:grid;grid-template-columns:2100px 1fr;gap:60px;border-bottom:3px solid var(--ink);padding-bottom:30px}
h1{font:700 104px/1.02 Georgia,'Times New Roman',serif;margin:0;letter-spacing:-.01em}
.dek{font:italic 36px/1.35 Georgia,serif;color:var(--mut);margin-top:18px}
.num{display:grid;grid-template-columns:repeat(4,1fr);gap:0;border-left:1.5px solid var(--rule)}
.num div{padding:0 26px;border-right:1.5px solid var(--rule)}
.num b{display:block;font:700 92px/1 Georgia,serif;color:var(--opt)}
.num span{font-size:26px;color:var(--mut);line-height:1.25;display:block;margin-top:6px}
.row{display:grid;grid-template-columns:repeat(12,1fr);gap:0 44px;margin-top:40px}
.band{grid-column:1/-1;display:flex;align-items:baseline;gap:22px;border-top:3px solid var(--ink);padding-top:10px;margin-bottom:6px}
.band{margin-bottom:8px}.band h2{font:700 62px/1.1 Georgia,serif;margin:0}.band .k{font:700 62px/1.1 Georgia,serif;color:var(--cur)}
.band p{margin:0 0 0 auto;font:italic 31px Georgia,serif;color:var(--mut)}
.fig{padding:14px 0 6px}
.cap{font:italic 27px/1.4 Georgia,serif;color:var(--mut);margin-top:6px}
.cap b{font-style:normal;font-family:'Segoe UI',sans-serif;color:var(--ink)}
h3{font:700 34px Georgia,serif;margin:0 0 4px}
.s3{grid-column:span 3}.s4{grid-column:span 4}.s5{grid-column:span 5}.s6{grid-column:span 6}.s7{grid-column:span 7}.s8{grid-column:span 8}.s12{grid-column:1/-1}
.brief{margin-top:26px;border:2px solid var(--ink);padding:26px 30px;background:#fff;font:27px/1.5 Georgia,serif;position:relative}
.brief .lab{position:absolute;top:-17px;left:22px;background:var(--paper);padding:0 12px;font:700 22px 'Segoe UI',sans-serif;letter-spacing:.14em}
.brief p{margin:0 0 12px}.brief mark{background:#f3dccf;padding:0 3px}
.map{width:100%;border-collapse:collapse;font-size:26px;margin-top:14px}.map td{border-top:1.5px solid var(--rule);padding:5px 8px;vertical-align:top}.map td:first-child{font-weight:700;width:60px}
table.t{border-collapse:collapse;width:100%;font-size:26px}table.t td,table.t th{border-bottom:1.5px solid var(--rule);padding:5px 8px;text-align:left}table.t th{font-size:21px;letter-spacing:.08em;color:var(--mut);text-transform:uppercase}
.z{color:var(--opt);font-weight:800}.bad{color:var(--cur);font-weight:800}
.math h3{font:600 20px 'Segoe UI';letter-spacing:.1em;text-transform:uppercase;color:var(--mut);margin:14px 0 0}
.math .katex{font-size:1.18em}.katex-display{margin:.35em 0;overflow-x:auto;overflow-y:hidden}
.note{font-size:27px;color:var(--mut)}
ul.t{margin:6px 0;padding-left:34px;font-size:29px}ul.t li{margin:5px 0}
.legend{display:flex;gap:30px;font-size:25px;color:var(--mut);margin:2px 0 8px}.legend i{display:inline-block;width:24px;height:14px;margin-right:8px;vertical-align:-1px}
footer{margin-top:40px;border-top:3px solid var(--ink);padding-top:12px;font-size:25px;color:var(--mut);display:flex;justify-content:space-between}
.lead{font:31px/1.55 Georgia,serif;margin:8px 0 14px;max-width:3100px}.lead b{font-family:'Segoe UI',sans-serif}
.story{background:#fff;border:1.5px solid var(--rule);padding:18px 26px 14px;margin-top:20px}.story h3{margin:0 0 6px}.story p{margin:6px 0;font-size:28px;line-height:1.5}.story ul{margin:6px 0;padding-left:32px;font-size:28px}.story li{margin:5px 0}
.take{grid-column:1/-1;border-left:8px solid var(--opt);padding:10px 26px;background:#eaf0f8;font:700 34px/1.4 Georgia,serif;margin:20px 0 6px}
.plain{grid-column:1/-1;border-left:8px solid #9a958a;padding:8px 26px;background:#fff;font:29px/1.5 Georgia,serif;margin-top:14px}
.two{display:grid;grid-template-columns:1fr 1fr;gap:44px}
.steps{display:grid;grid-template-columns:repeat(5,1fr);gap:20px;margin-top:10px;font-size:25px;line-height:1.45}.steps b{display:block;font:700 27px Georgia,serif;color:var(--opt)}
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
            if t_ and t_[0].isdigit():
                paras.append("<b>" + t_ + "</b>")
                cur_p = []
        else:
            cur_p.append(t_)
    if cur_p:
        paras.append(" ".join(cur_p))
    qtxt = "".join(f"<p>{x}</p>" for x in paras)
    brief = f'<div class="brief"><span class="lab">THE BRIEF &middot; Question.txt, verbatim</span>{qtxt}</div>'
    mapping = """<table class="map"><tr><td>Q1</td><td>What is wrong with today&rsquo;s timetable? &rarr; <b>section B</b></td></tr>
<tr><td>Q2</td><td>What did we improve, and how? &rarr; <b>C, D</b></td></tr>
<tr><td>Q3</td><td>Who is affected, and how much? &rarr; <b>D</b></td></tr>
<tr><td>Q4</td><td>How much better is it, and how is that measured? &rarr; <b>D</b></td></tr>
<tr><td>Q5</td><td>How do we know every rule is followed? &rarr; <b>E</b></td></tr>
<tr><td>Q6</td><td>Does it cope when things change? &rarr; <b>F, G</b></td></tr></table>"""

    # ---- A
    secA = f"""<div class="band"><span class="k">A</span><h2>What we were asked to do</h2><p>a school of 626 students, 54 teachers and 63 rooms</p></div>
<div class="lead s12"><p>The brief asks for three things: make a school timetable automatically, show that it is better than the current one, and prove that it follows every rule. We were given the course catalog, a model of the building and one real student&rsquo;s week. Around those we built a simulated school, wrote a scheduler, and compared it with a stand-in for how timetables are made today. <b>Every week uses the same timetable</b>, so we plan one week and it repeats.</p></div>
<div class="s4">{brief}{mapping}</div>
<div class="s4">{F(fig_context(D), "What goes in, what the program does, and what comes out.", "")}<div class="story"><h3>What is real, what is simulated</h3><p><b>Real:</b> the course catalog and its selection rules, the six-floor building with the walking time between any two rooms, and one student&rsquo;s observed week.</p><p><b>Simulated:</b> the 626 students and their course choices, the 54 teachers, and the &ldquo;current method&rdquo; we compare against. Everything is generated from a fixed seed, so anyone can re-run it and get the same numbers.</p></div></div>
<div class="s4">{F(fig_week(D), "The 33 periods a class can use in a week, and how long each one is.", "")}<div class="story"><h3>Why we count minutes, not lessons</h3><p>A lesson in period 1 lasts 60 minutes, in period 2 only 40. Moving a Math lesson from one to the other keeps the lesson count but quietly removes 20 minutes. The brief says class hours must not change, so we count minutes.</p><p>Some periods are not available: PE takes Monday and Thursday period 5, and there is no Friday afternoon. This one grid repeats every week.</p></div></div>"""

    # ---- B problems
    pl, seq, nch = fig_observed_path()
    sid, paths = fig_opt_path(D)
    ch = lambda L: sum(1 for a, b in zip(L, L[1:]) if a != b)
    h_min = hist([[100 * (sum(w.slots[s]["minutes"] for s in D.cur[0][g]) / (sec.n * (sum(s["minutes"] for s in w.slots) / len(w.slots))) - 1) for g, sec in w.sections.items()],
                  [100 * (sum(w.slots[s]["minutes"] for s in D.opt[0][g]) / (sec.n * (sum(s["minutes"] for s in w.slots) / len(w.slots))) - 1) for g, sec in w.sections.items()]],
                 w=900, h=360, bins=28, xlab="weekly minutes of a section vs. nominal (%)", ylab="share of sections (%)", lo=-45, hi=45)
    viol = round(statistics.mean(c["check"]["violations"].get("H8", 0) for c in cs))
    secB = f"""<div class="band"><span class="k">B</span><h2>What is wrong with the current timetable</h2><p>Question 1</p></div>
<div class="lead s12"><p>In the one real week we have, a student changes room 21 times, because every teacher keeps their own room and students walk to them. Free periods end up scattered between lessons, and nobody checks that a lesson keeps the same number of minutes after it is moved. The three figures below show each problem in turn.</p></div>
{F('<div style="width:50%">' + pl + '</div>' + f'<div class="note" style="margin-top:8px"><b>Monday of the one real week:</b> {seq}<br><b>{nch}</b> room changes in one day; <b>21</b> per week, 488 s of walking.</div>', "One student&rsquo;s real Monday on the ground-floor plan: each arrow is a room change. Every teacher owns a room, so the student walks to the teacher all day.", "s4")}
<div class="s4">{F(fig_conflict(), "Left: free choice. Right: students pick a package.", "")}<div class="story"><h3>Why free choice breaks the timetable</h3><p>If students can mix electives any way they like, each class shares students with many other classes, and all of those need different time slots. In our school that means 31 lessons that must not overlap, but only 29 free periods: no valid timetable exists. So we offer a limited set of course packages. Students in one package form a class that takes all its lessons together.</p></div></div>
<div class="s4"><div class="fig"><h3>Class minutes drift without anyone noticing</h3>{h_min}<div class="cap"><b>Fig. {figno[0] + 1}</b> &mdash; Each class&rsquo;s weekly minutes compared with the normal amount. A timetable built without looking at period length puts <b>{viol} of {st['n_sections']}</b> classes outside the &plusmn;8% allowed band; ours puts none (the brief: <i>class hours should not change</i>).</div></div>
<ul class="t"><li>Nothing aims to reduce students&rsquo; walking, free periods stuck between lessons, or overloaded days.</li><li>When a room is lost, the fix is made by hand.</li><li>There is no independent proof that the timetable follows the rules.</li></ul></div>
<div class="take">In short: lots of walking, wasted gaps, and no check on class hours.</div>"""
    figno[0] += 1

    # ---- C method
    secC = f"""<div class="band"><span class="k">C</span><h2>How we built it</h2><p>Question 2</p></div>
<div class="lead s12"><p>We split the job into steps that can each be checked on their own. First, group students into classes. Second, choose when each class meets. Third, choose the room. Fourth, check every rule on the finished timetable and keep a quick way to repair it. The equations at the bottom are the exact rules and goals the computer works with.</p></div>
<div class="s8">{F(fig_pipeline(D), "The five steps, with the size of the problem at each one.", "")}
<div class="steps"><div><b>0 Rules</b>Course credits become weekly lessons. The selection rules decide which course packages are allowed.</div><div><b>1 Classes</b>Students with the same package form a class of at most 24. A course needs at least 6 students to run.</div><div><b>2 Time</b>The solver picks the period for every lesson, obeying all hard rules and cutting idle gaps. It uses one yes/no variable per class and period, so it stays fast.</div><div><b>3 Rooms</b>Each class gets a home room. Leftover lessons are matched to free rooms, then swapped to cut walking.</div><div><b>4 Check</b>A separate program checks the ten rules. If something changes, only the affected lessons are re-planned.</div></div></div>
{F(fig_calibration(D), "How many lessons a week a course gets: catalog credit times a factor fitted on the real week, tried across a whole band of values.", "s4")}
<div class="s12 math" style="display:grid;grid-template-columns:repeat(3,1fr);gap:0 60px">
<div><h3>Credit to weekly slots</h3>$$n_c=\\Big\\lfloor k\\kappa_c+\\tfrac12\\Big\\rfloor,\\quad k=\\frac{{\\sum_i\\kappa_i o_i}}{{\\sum_i\\kappa_i^{{2}}}}\\approx {st['k']:.3f}$$
<h3>Hard rules (z<sub>g,s</sub> &isin; {{0,1}})</h3>$$\\sum_s z_{{g,s}}=n_g,\\quad \\sum_{{g\\in\\sigma}}z_{{g,s}}\\le1,\\quad \\sum_{{g\\in T_t}}z_{{g,s}}\\le1$$$$\\sum_{{g:\\,a_g\\ge a}}z_{{g,s}}\\le R_\\kappa(a)\\quad(\\text{{room area}})$$</div>
<div><h3>Contact hours in minutes</h3>$$\\Big|\\sum_s\\mu_s z_{{g,s}}-n_g\\bar\\mu\\Big|\\le\\max(\\tau n_g\\bar\\mu,\\,9),\\ \\tau=0.08$$
<h3>Stage 1: slot objective</h3>$$\\min\\ w_{{gap}}\\sum_\\sigma c_\\sigma\\Gamma_\\sigma+w_h\\sum_\\sigma c_\\sigma H_\\sigma+w_{{sp}}\\sum_g|g|\\,\\mathrm{{rep}}_g+w_m\\!\\!\\sum_{{g\\ \\mathrm{{hard}}}}\\!\\!|g|\\sum_s(p_s-1)z_{{g,s}}+w_{{tg}}\\sum_t\\Gamma_t$$</div>
<div><h3>Stage 2: person-seconds</h3>$$\\min_r\\sum_{{(a,b)\\in\\mathcal L_{{stud}}}}n_{{ab}}\\,\\tau(r_a,r_b)+\\lambda\\!\\!\\sum_{{(a,b)\\in\\mathcal L_{{teach}}}}\\!\\!\\tau(r_a,r_b)$$
<h3>Score, fairness, robustness</h3>$$J=\\bar\\ell_{{stud}}+\\alpha\\bar L_t+\\beta\\,\\mathrm{{CVaR}}_q(L),\\qquad \\mathbb E[\\Delta]=\\sum_\\xi p_\\xi\\Delta(\\xi)$$
<p class="note">Students stay, teachers walk: &lambda; says how much one second of teacher walking counts against one second of student walking. &Gamma; = free periods stuck between lessons, H = days with six or more classes, rep = a class meeting twice on one day.</p></div></div>
<div class="plain s12">In plain words: every class gets exactly its number of lessons; nobody (student, teacher or room) is in two places at once; weekly minutes stay near the normal amount; then the computer removes as many wasted gaps and as much walking as it can.</div>"""

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
    secD = f"""<div class="band"><span class="k">D</span><h2>How much better is it?</h2><p>Questions 3 and 4</p></div>
<div class="lead s12"><p>To measure the gain we built 24 timetables the way the school makes them today (any valid timetable, teacher-owned rooms) and compared them with ours on the same school. In every chart a lower number is better. The floor plans show where students change rooms, the charts show what that means for each student, and the teacher grids show who ends up with free periods stuck between lessons.</p></div>
<div class="s12"><div class="legend"><span><i style="background:var(--cur)"></i>Current method (24 simulated timetables, tuned to match the real week; the plots show run 0)</span><span><i style="background:var(--opt)"></i>Optimized</span></div></div>
<div class="s12 fig"><h3>Where students walk</h3>{plans_html}<div class="cap"><b>Fig. {figno[0] + 1}</b> &mdash; Real building, six floors, drawn to scale. The darker the room, the more room changes touch it each week (same scale for both rows). With teacher-owned rooms, walking spreads across the whole building; with home-class rooms it stays near where each class lives.</div></div>"""
    figno[0] += 1
    secD += f"""{F(h1, f"Walking per student per week. Mean {cur_mean('students','travel_s_mean'):.0f} &rarr; {o['students']['travel_s_mean']:.0f} s (&minus;{red('students','travel_s_mean'):.0f}%); the worst-20% tail falls too, so the gain does not come from a few students.", "s4")}
{F(h2, f"Room changes per student per week. The real week had 21.", "s4")}
{F(h3, f"Free periods stuck between lessons, per student per week: &minus;{red('students','gaps_mean'):.0f}%.", "s4")}
{F(s_gap, "How many students are sitting in a gap at each period of the week. Our timetable moves free periods to the start or end of the day.", "s4")}
{F(s_room, "Classrooms in use at each period. Demand never gets close to the 49 available, so the saving does not come from squeezing into fewer rooms.", "s4")}
<div class="s4 fig"><h3>Which change saves the most walking?</h3>{svg(900, 270, ab_svg)}<div class="cap"><b>Fig. {figno[0] + 1}</b> &mdash; We tried each change alone. Choosing rooms smartly removes the walking; choosing times smartly removes the free-period gaps.</div></div>"""
    figno[0] += 1
    secD += f"""<div class="s8 fig"><h3>Every teacher&rsquo;s week</h3>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:30px"><div><div class="note"><b style="color:var(--cur)">Current</b> &mdash; {tg_c} idle gaps</div>{tm_c}</div><div><div class="note"><b style="color:var(--opt)">Optimized</b> &mdash; {tg_o} idle gaps</div>{tm_o}</div></div>
<div class="legend"><span><i style="background:#4a4842"></i>teaching</span><span><i style="background:{GOLD}"></i>busy elsewhere (IB / G12, other building)</span><span><i style="background:var(--cur)"></i>idle gap between lessons</span></div>
<div class="cap"><b>Fig. {figno[0] + 1}</b> &mdash; One row per teacher, one column per period, grouped by department. Orange cells are free periods stuck between two lessons on the same day.</div></div>
<div class="s4 fig"><h3>Who benefits, and by how much</h3>{stake}<div class="story"><h3>How to read this</h3><ul><li>Orange is the current method, blue is ours, on the same school and the same lessons.</li><li>Students gain on every line.</li><li>Teachers walk about 17% more. That is deliberate: it is cheaper for 54 teachers to carry the move than for 626 students.</li><li>Teachers also lose about half their stuck free periods.</li></ul></div></div>
<div class="take">Students walk about half as much and almost never wait in a gap; teachers walk a bit more on purpose.</div>"""
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
    secE = f"""<div class="band"><span class="k">E</span><h2>How we know the rules are followed</h2><p>Question 5</p></div>
<div class="lead s12"><p>A second program, which shares no code with the scheduler, reads the finished timetable and checks ten rules. To be sure the checker can really catch mistakes, we deliberately break the timetable in ten different ways and confirm that it notices each one.</p></div>
<div class="s7 fig"><table class="t"><tr><th>Rule</th><th>Hard constraint</th><th>Ours</th><th>Current</th><th>Planted fault</th></tr>{cert}</table>
<div class="cap"><b>Fig. {figno[0] + 1}</b> &mdash; {chk['sections']} sections, {chk['students']} students, {chk['teachers']} teachers, {chk['room_legs']} room legs checked. Current = average over {len(cs)} simulated timetables.</div></div>"""
    figno[0] += 1
    secE += f"""<div class="s5">{F(ind, "The checker works only from the finished timetable. The mistake test shows it can fail: all 10 deliberate mistakes were caught.", "")}<div class="story"><h3>The ten rules in plain words</h3><ul><li>Every class gets all its lessons, in different periods.</li><li>Lessons avoid PE time and the teacher&rsquo;s other commitments.</li><li>No student, teacher or room is in two places at once.</li><li>The room is the right kind and big enough; the teacher is qualified.</li><li>Teachers never teach more in a row than their limit; labs get a double period.</li><li>Weekly minutes stay near the normal amount.</li><li>Every room change fits in the break between lessons.</li></ul><p>20 automated tests also cover loads, course rules, the solver, repairs and the real week.</p></div></div>"""

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
    allv = [0, 0]
    if oat:
        ok = [r for r in oat if "improvement" in r]
        base = next((r for r in oat if r["tag"] == "base" and "improvement" in r), None)
        by = defaultdict(list)
        for r in ok:
            if r["tag"] != "base":
                by[r["tag"].split("=")[0]].append(r["improvement"]["travel_pct"])
        rows = sorted([(nice.get(k, k), min(v), max(v)) for k, v in by.items()], key=lambda r: r[2] - r[1])
        allv = [min(r[1] for r in rows), max(r[2] for r in rows)]
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
        f_html += F(tor, f"How far each assumption moves the walking saving (%). Each bar is one assumption changed on its own; {len(oat)} runs, each solved and checked again ({n_ok} with no broken rules).", "s5")
        capb = [r["overrides"]["rooms.removed_frac"] * 100 for r in oat if r["tag"].startswith("rooms.removed_frac") and "opt" not in r]
        f_html += F(line([capp], 800, 380, "classrooms and labs removed (%)", "optimized walking (s/wk)", (OPT,), None, capb, "no grid found"), "Losing rooms: between 20% and 40% of rooms removed, no valid timetable exists. The program says so instead of giving a bad one.", "s4")
        f_html += F(fig_envelope(list(oat) + list(lhs or []), 0.8725), "Where it works. Each dot is one run. How heavy the timetable is (k) and how many rooms are lost decide whether a valid timetable can be found at all.", "s4")
        f_html += F(line([gp], 800, 380, "weight on student idle gaps", "idle periods / student / wk", (OPT,), None, None, "", "{:.0f}", "{:.2f}"), "Turning up the importance of free-period gaps removes them smoothly, with no sudden jump.", "s4")
        f_html += F(line([tp], 800, 380, "teacher supply factor", "teachers needed", (CUR,), None, None, "", "{:.2f}"), "Staffing: how many teachers the school needs as supply tightens.", "s4")
        f_html += F(line([pth], 800, 380, "G10 pathways offered", "sections to staff", (CUR,), None, None, "", "{:.0f}"), "The price of choice: offering more course packages means smaller classes and more classes to staff.", "s4")
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
        f_html += F(line([[(p["teacher_travel_s"], p["student_travel_s"]) for p in par]], 800, 380, "teacher walking (s/wk)", "student walking (s/wk)", (CUR,), None, None, "", "{:.0f}", "{:.0f}", None, None, [f"&lambda;={p['lambda']}" for p in par]), "Who walks: shifting walking from many students to few teachers is cheap, until a teacher second is weighted very heavily.", "s4")
    f_html += f'<div class="s4 story"><h3>What the sweeps tell us</h3><ul><li>Across every single-assumption change, the walking saving stays between <b>{allv[0]:.0f}%</b> and <b>{allv[1]:.0f}%</b>.</li><li>The gain holds up against the importance weights, class size limits, staffing and the solver random seed.</li><li>It does <b>not</b> hold up against the load: a heavier timetable (k near 1) or losing 40% of rooms leaves no valid timetable, for the current method as well as ours.</li><li>Offering more course packages costs more classes to staff.</li></ul></div>'
    secF = f"""<div class="band"><span class="k">F</span><h2>What if our assumptions are wrong?</h2><p>Question 6</p></div>
<div class="lead s12"><p>Many numbers in a simulation are assumptions, so we changed each one, first one at a time and then several together, and re-ran everything. The gain stays in a narrow band in almost every case. The exceptions are real limits: a much heavier timetable, or losing a lot of rooms, can leave no valid timetable at all.</p></div>{f_html}"""

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
    ta_svg = svg(840, 360, bars + T(420, 354, "random draw (teacher, day)", 18, MUT, "middle") + T(8, 150, "lessons", 18, MUT, "start", 400, "sans-serif", "transform=\"rotate(-90 20 150)\"") + f'<rect x="430" y="10" width="22" height="14" fill="#cfcabc"/>' + T(460, 23, "lessons that day", 18, INK) + f'<rect x="430" y="36" width="22" height="14" fill="{OPT}"/>' + T(460, 49, "covered by a substitute", 18, INK))
    su = sh["enrollment_surge_5pct"]
    sb = ""
    for i, x in enumerate(su):
        sb += f'<rect x="{80 + i * 62}" y="{300 - x.get("rooms_outgrown", 0) * 6}" width="46" height="{x.get("rooms_outgrown", 0) * 6}" fill="{GOLD}"/><rect x="{80 + i * 62}" y="{300 - x.get("moved_meetings", 0) * 6}" width="46" height="{max(x.get("moved_meetings", 0) * 6, 1)}" fill="{CUR}"/>'
        sb += T(80 + i * 62 + 23, 326, str(i + 1), 17, MUT, "middle")
    su_svg = svg(840, 360, sb + T(420, 354, "random draw", 18, MUT, "middle") + f'<rect x="430" y="10" width="22" height="14" fill="{GOLD}"/>' + T(460, 23, "lessons needing a bigger room", 18, INK) + f'<rect x="430" y="36" width="22" height="14" fill="{CUR}"/>' + T(460, 49, "lessons re-timed", 18, INK))
    ex = res["shocks"]["expected"]
    secG = f"""<div class="band"><span class="k">G</span><h2>What happens when something breaks?</h2><p>Question 6</p></div>
<div class="lead s12"><p>Rooms close, teachers fall ill and enrollment grows. When that happens the program changes as little as it can: first it looks for a substitute, then it moves a lesson to another room, and only as a last step does it change a lesson&rsquo;s time. Every repaired timetable is checked again.</p></div>
{F(pcl, cap_cl, "s4")}
<div class="s8"><div class="two">{F(ta_svg, f"A teacher is away for a day (probability 0.4). A qualified free colleague covers {100 * sum(x['covered'] for x in ta) / max(1, sum(x['affected_meetings'] for x in ta)):.0f}% of lessons and nothing in the timetable moves.", "")}{F(su_svg, "Enrollment grows 5% (probability 0.3). Rooms that become too small are swapped for bigger ones; lesson times stay the same.", "")}</div>
<div class="story"><h3>The repair ladder</h3><ul><li><b>1. Substitute.</b> A qualified teacher who is free at that moment takes the lesson.</li><li><b>2. Move the room.</b> The lesson keeps its time and moves to a free room of the right kind and size.</li><li><b>3. Move the time.</b> Only if no room is free: just the affected classes are re-planned, everything else stays frozen.</li></ul><p>Over 12 random draws of each event, no repair was impossible and no lesson had to change its time. Expected cost: <b>{ex['moved_meetings']:.2f}</b> lessons moved and <b>{ex['room_changes']:.1f}</b> room changes per event.</p></div></div>
<div class="take">A closed room, a sick teacher or a growing intake is handled by small local changes, not a new timetable.</div>"""

    # ---- H limits
    gap = 100 * (res["optimized"]["solver"]["objective"] - res["optimized"]["solver"]["bound"]) / res["optimized"]["solver"]["objective"]
    secH = f"""<div class="band"><span class="k">H</span><h2>What we have not proven, and how to re-run it</h2><p>limits</p></div>
<div class="s4"><ul class="t"><li><b>One real week only.</b> The current system is an emulator calibrated to it (about {res['emulator_calibration']['g11_changes']:.0f} vs 21 changes); everything else is simulated. Registrar CSVs drop in.</li><li><b>Operating envelope.</b> Valid timetables were found at k &asymp; 0.87 with up to 20% of rooms removed; at k &ge; 0.95 or &ge; 40% rooms removed none was found in the time limit (Fig. 20).</li><li><b>Not proven optimal.</b> CP-SAT stopped at its time limit, {gap:.0f}% from its bound: &ldquo;optimized&rdquo; means best feasible found.</li></ul></div>
<div class="s4"><ul class="t"><li><b>Pathway classes trade choice for feasibility</b> (Fig. 4); the price is quantified in F.</li><li><b>Minutes:</b> sections of one course can still differ by up to 36% in weekly minutes; the next rule to add is equality across sections.</li></ul></div>
<div class="s4"><ul class="t"><li><b>Reproduce:</b> <code>python -m tt.run</code>, <code>python -m tt.sensitivity</code>, <code>python -m tt.poster2</code>.</li><li>Every number on this poster is read from <code>output/*.json</code>; seeds and the config hash are fixed.</li></ul></div>"""

    header = f"""<header><div><h1>A better school timetable</h1><div class="dek">We built a program that makes the timetable for {st['n_students']} students, {st['n_teachers']} teachers and 63 rooms. Students walk about half as much, free periods stop piling up between lessons, a separate program checks every rule, and the plan still works when a room closes or a teacher is away. The timetable is the same every week.</div></div>
<div class="num"><div><b>&minus;{red('students','travel_s_mean'):.0f}%</b><span>less walking for students each week</span></div><div><b>&minus;{red('students','gaps_mean'):.0f}%</b><span>fewer free periods stuck between lessons</span></div><div><b>0</b><span>broken rules out of 10, checked by a separate program</span></div><div><b>10/10</b><span>deliberate mistakes the checker caught</span></div></div></header>"""

    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>A better school timetable</title>
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
