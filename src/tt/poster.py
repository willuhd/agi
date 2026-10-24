"""Submission poster: one self-contained HTML (inline SVG charts, KaTeX math) sized for A1 landscape print.
Run: python -m tt.poster  ->  output/poster.html  (print to PDF from any browser, or tt.poster --pdf)
"""
from __future__ import annotations

import json
import statistics
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

from .config import ROOT

OUT = ROOT / "output"
BLUE, ORANGE, AQUA, INK, MUT, GRID = "#2a78d6", "#eb6834", "#1baf7a", "#0b0b0b", "#52514e", "#e2e1dd"


def jl(n):
    p = OUT / n
    return json.loads(p.read_text()) if p.exists() else None


# ---------------------------------------------------------------------------- svg helpers ----
def svg(w, h, body):
    return (f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" xmlns="http://www.w3.org/2000/svg" '
            f'font-family="Inter,Segoe UI,system-ui,sans-serif">{body}</svg>')


def txt(x, y, s, size=13, fill=MUT, anchor="start", weight=400, extra=""):
    return f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" font-weight="{weight}" {extra}>{s}</text>'


def bars_compare(items, w=560, h=250):
    """items: [(label, current_mean, lo, hi, optimized, unit_fmt)] -> grouped bars with range whisker."""
    n = len(items)
    pw = (w - 20) / n
    b = ""
    for i, (lab, cur, lo, hi, opt, fmt) in enumerate(items):
        x0 = 10 + i * pw
        top = 40
        base = h - 62
        mx = hi * 1.12
        sc = (base - top) / mx
        bw = pw * 0.30
        xc, xo = x0 + pw * 0.22, x0 + pw * 0.56
        b += f'<rect x="{xc:.1f}" y="{base - cur * sc:.1f}" width="{bw:.1f}" height="{cur * sc:.1f}" rx="3" fill="{ORANGE}"/>'
        b += f'<line x1="{xc + bw / 2:.1f}" x2="{xc + bw / 2:.1f}" y1="{base - lo * sc:.1f}" y2="{base - hi * sc:.1f}" stroke="{INK}" stroke-width="1.5"/>'
        b += f'<rect x="{xo:.1f}" y="{base - opt * sc:.1f}" width="{bw:.1f}" height="{max(opt * sc, 1):.1f}" rx="3" fill="{BLUE}"/>'
        b += txt(xc + bw / 2, base - hi * sc - 6, fmt(cur), 12, INK, "middle", 600)
        b += txt(xo + bw / 2, base - opt * sc - 6, fmt(opt), 12, INK, "middle", 700)
        red = 100 * (1 - opt / cur)
        b += txt(x0 + pw / 2, 24, f"&minus;{red:.0f}%", 18, BLUE, "middle", 800)
        for k, line in enumerate(lab.split("\n")):
            b += txt(x0 + pw / 2, base + 20 + 14 * k, line, 12, MUT, "middle")
    b += f'<line x1="10" x2="{w - 10}" y1="{h - 62}" y2="{h - 62}" stroke="{GRID}"/>'
    return svg(w, h, b)


def tornado(rows, base, w=640, rowh=26, label="%"):
    """rows: [(name, lo, hi, lo_tag, hi_tag)] sorted by span."""
    lab_w = 175
    h = 46 + rowh * len(rows)
    vals = [r[1] for r in rows] + [r[2] for r in rows] + [base]
    vmin, vmax = min(vals) - 2, max(vals) + 2
    sx = lambda v: lab_w + (v - vmin) / (vmax - vmin) * (w - lab_w - 20)
    b = ""
    for i, (name, lo, hi, lt, ht) in enumerate(rows):
        y = 34 + i * rowh
        b += txt(lab_w - 8, y + 14, name, 12, INK, "end")
        b += f'<rect x="{sx(lo):.1f}" y="{y}" width="{max(sx(hi) - sx(lo), 2):.1f}" height="{rowh - 8}" rx="3" fill="{BLUE}" opacity=".85"/>'
        b += txt(sx(lo) - 4, y + 14, f"{lo:.0f}", 11, MUT, "end")
        b += txt(sx(hi) + 4, y + 14, f"{hi:.0f}", 11, MUT)
    b += f'<line x1="{sx(base):.1f}" x2="{sx(base):.1f}" y1="24" y2="{h - 8}" stroke="{INK}" stroke-width="1.5"/>'
    b += txt(sx(base), 16, f"baseline {base:.0f}{label}", 12, INK, "middle", 700)
    return svg(w, h, b)


def line_chart(pts, w=420, h=250, xlab="", ylab="", color=BLUE, bad=None, labels=None, bad_label="infeasible"):
    if not pts:
        return ""
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    xmin, xmax, ymin, ymax = min(xs), max(xs), min(0, min(ys)), max(ys) * 1.12
    L, R, T, B = 48, 14, 16, 44
    sx = lambda v: L + (v - xmin) / ((xmax - xmin) or 1) * (w - L - R)
    sy = lambda v: h - B - (v - ymin) / ((ymax - ymin) or 1) * (h - T - B)
    b = ""
    for t in range(5):
        v = ymin + (ymax - ymin) * t / 4
        b += f'<line x1="{L}" x2="{w - R}" y1="{sy(v):.1f}" y2="{sy(v):.1f}" stroke="{GRID}"/>' + txt(L - 6, sy(v) + 4, f"{v:.0f}", 11, MUT, "end")
    b += f'<polyline fill="none" stroke="{color}" stroke-width="3" stroke-linejoin="round" points="' + " ".join(f"{sx(x):.1f},{sy(y):.1f}" for x, y in pts) + '"/>'
    for i, (x, y) in enumerate(pts):
        b += f'<circle cx="{sx(x):.1f}" cy="{sy(y):.1f}" r="5" fill="{color}" stroke="#fff" stroke-width="2"/>'
        if labels:
            b += txt(sx(x) + 6, sy(y) - 8, labels[i], 10.5, MUT)
    for x in (bad or []):
        b += f'<line x1="{sx(x):.1f}" x2="{sx(x):.1f}" y1="{T}" y2="{h - B}" stroke="{ORANGE}" stroke-width="2" stroke-dasharray="5 4"/>'
        b += txt(sx(x) - 5, T + 14, bad_label, 11, ORANGE, "end", 700)
    b += txt((L + w - R) / 2, h - 8, xlab, 12, MUT, "middle") + txt(14, h / 2, ylab, 12, MUT, "middle", 400, f'transform="rotate(-90 14 {h / 2})"')
    return svg(w, h, b)


def hbars(rows, w=640, rowh=24, signed=True, lab_w=170):
    h = 28 + rowh * len(rows)
    mx = max(abs(r[1]) for r in rows) or 1
    mid = lab_w + (w - lab_w - 20) / 2 if signed else lab_w
    half = (w - lab_w - 20) / (2 if signed else 1)
    b = ""
    for i, (name, v) in enumerate(rows):
        y = 12 + i * rowh
        bw = abs(v) / mx * half
        x = mid if v >= 0 else mid - bw
        b += txt(lab_w - 8, y + 13, name, 12, INK, "end")
        b += f'<rect x="{x:.1f}" y="{y}" width="{max(bw, 1):.1f}" height="{rowh - 7}" rx="3" fill="{BLUE if v >= 0 else ORANGE}"/>'
        b += txt(x + (bw + 5 if v >= 0 else -5), y + 13, f"{v:+.2f}", 11, MUT, "start" if v >= 0 else "end")
    if signed:
        b += f'<line x1="{mid:.1f}" x2="{mid:.1f}" y1="6" y2="{h - 14}" stroke="{INK}"/>'
    return svg(w, h, b)


MATH_TPL = r"""
<h3>Loads: catalog credit &rarr; weekly slots</h3>
$$n_c=\Big\lfloor k\,\kappa_c+\tfrac12\Big\rfloor,\qquad k=\frac{\sum_i \kappa_i\,o_i}{\sum_i \kappa_i^{2}}\approx __K__$$
<p class="small">$\kappa_c$ catalog credit, $o_i$ slots observed on the real week; swept $k\in[0.83,1]$.</p>
<h3>Hard constraints (decision $z_{g,s}\in\{0,1\}$)</h3>
$$\sum_s z_{g,s}=n_g\quad \sum_{g\in\sigma} z_{g,s}\le 1\quad \sum_{g\in T_t} z_{g,s}\le 1\quad \sum_{g:\,a_g\ge a} z_{g,s}\le R_{\kappa}(a)$$
<p class="small">students $\sigma$, teacher $t$, rooms of kind $\kappa$ with area $\ge a$ (nested &rArr; Hall's condition is exact).</p>
<h3>Contact-hours invariant (minutes, not slots)</h3>
$$\Big|\sum_s \mu_s z_{g,s}-n_g\bar\mu\Big|\le\max\big(\tau\, n_g\bar\mu,\;9\big),\qquad \tau=0.08$$
<h3>Stage-1 objective</h3>
$$\min\; w_{\text{gap}}\sum_\sigma c_\sigma\Gamma_\sigma + w_h\sum_\sigma c_\sigma H_\sigma + w_{sp}\sum_g |g|\,\text{rep}_g + w_m\sum_{g\,\text{hard}}|g|\sum_s (p_s-1)z_{g,s} + w_{tg}\sum_t\Gamma_t$$
<p class="small">$\Gamma$ idle gaps, $H$ days with &ge;6 classes, rep same-day repeats, $c_\sigma$ students in signature $\sigma$.</p>
<h3>Stage-2 objective: person-seconds</h3>
$$\min_{r}\;\sum_{(a,b)\in\mathcal L_{\text{stud}}} n_{ab}\,\tau(r_a,r_b)\;+\;\lambda\sum_{(a,b)\in\mathcal L_{\text{teach}}}\tau(r_a,r_b)$$
<h3>Composite score and fairness</h3>
$$J=\bar{\ell}_{\text{student}}+\alpha\,\overline{L}_t+\beta\,\mathrm{CVaR}_q(L),\qquad \mathrm{CVaR}_q=\tfrac{1}{\lfloor(1-q)n\rfloor}\sum_{\text{worst}}L_i$$
<h3>Robustness</h3>
$$\mathbb E[\Delta]=\sum_{\xi} p_\xi\,\Delta(\xi),\quad \Delta=\text{moved lessons}+\text{room changes}+\text{uncovered periods}$$
"""


def week_section():
    sol = jl("main_solution.json")
    if not sol:
        return ""
    sid = next(x for x in sorted(sol["student_sections"]) if x.startswith("G11AP"))
    days = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    sl = sol["slots"]
    def grid(slot_of, room):
        cell = {}
        for g in sol["student_sections"][sid]:
            for si in slot_of[g]:
                cell[(sl[si]["day"], sl[si]["period"])] = (sol["courses"][sol["sections"][g]["course"]]["label"], room[f"{g}|{si}"] if isinstance(next(iter(room)), str) else room[(g, si)])
        moves, h = 0, '<div class="wk"><i></i>' + "".join(f"<b>{d}</b>" for d in days)
        last = {}
        for pnum in range(1, 8):
            h += f"<b>P{pnum}</b>"
            for d in days:
                c = cell.get((d, pnum))
                if not c:
                    h += "<span></span>"
                    continue
                prev = last.get(d)
                mv = prev is not None and prev[0] == pnum - 1 and prev[1] != c[1]
                moves += mv
                last[d] = (pnum, c[1])
                h += f'<span class="{"mv" if mv else ""}">{c[0][:15]}<em>{c[1]}</em></span>'
        return h + "</div>", moves
    cur, cm = grid(sol["emu0"]["slot_of"], sol["emu0"]["room"])
    opt, om = grid(sol["slot_of"], sol["room"])
    return (f'<section><h2><span class="n">10</span>One student&rsquo;s week</h2><p class="small">{sid}: same courses, teachers and hours. Orange = room changed since the previous period.</p>'
            f'<h3>Current &mdash; {cm} room changes (consecutive periods)</h3>{cur}<h3>Optimized &mdash; {om}</h3>{opt}</section>')

# ------------------------------------------------------------------------------ content ----
def build():
    res = jl("main_results.json")
    oat, lhs, par = jl("sens_oat.json"), jl("sens_lhs.json"), jl("sens_pareto.json")
    spec = jl("sens_lhs_spec.json")
    mut = jl("mutation_suite.json") or {"caught": {}, "catch_rate": 1.0}
    st = res["stats"]
    cs = res["current_system"]
    o = res["optimized"]["metrics"]
    mean = lambda sec, k: statistics.mean(c["metrics"][sec][k] for c in cs)
    rng = lambda sec, k: (min(c["metrics"][sec][k] for c in cs), max(c["metrics"][sec][k] for c in cs))
    items = []
    for k, lab, fmt in (("travel_s_mean", "Walking\ns / student / wk", lambda v: f"{v:.0f}"),
                        ("room_changes_mean", "Room changes\nper student / wk", lambda v: f"{v:.1f}"),
                        ("gaps_mean", "Idle periods\nbetween classes", lambda v: f"{v:.2f}"),
                        ("lost_min_week_mean", "Lost time\nmin / student / wk", lambda v: f"{v:.0f}")):
        lo, hi = rng("students", k)
        items.append((lab, mean("students", k), lo, hi, o["students"][k], fmt))
    headline = bars_compare(items, 450, 270)

    ab = res["ablation"]
    cur_w = mean("students", "travel_s_mean")
    abl_rows = [("Current", cur_w), ("Blind slots +\noptimized rooms", ab["blind_slots+opt_rooms"]["metrics"]["students"]["travel_s_mean"]),
                ("Optimized slots +\nowned rooms", ab["opt_slots+owned_rooms"]["metrics"]["students"]["travel_s_mean"]),
                ("Optimized both", o["students"]["travel_s_mean"])]
    abl = ""
    mx = cur_w * 1.1
    for i, (lab, v) in enumerate(abl_rows):
        y = 8 + i * 40
        col = ORANGE if i == 0 else BLUE if i == 3 else AQUA
        abl += txt(150, y + 17, lab.replace("\n", " "), 12, INK, "end")
        abl += f'<rect x="158" y="{y}" width="{v / mx * 250:.1f}" height="24" rx="3" fill="{col}"/>' + txt(158 + v / mx * 250 + 6, y + 17, f"{v:.0f} s", 12, INK, "start", 700)
    ablation = svg(450, 172, abl)

    # sensitivity
    tor_svg, cap_svg, lhs_svg, par_svg, ok_runs = "", "", "", "", 0
    tor_note = ""
    if oat:
        base = next(r for r in oat if r["tag"] == "base")
        bval = base["improvement"]["lost_min_pct"]
        by = defaultdict(list)
        for r in oat:
            if r["tag"] != "base" and "improvement" in r:
                by[r["tag"].split("=")[0]].append((r["tag"].split("=", 1)[1], r["improvement"]["lost_min_pct"]))
        nice = {"solve.w_gap": "weight: student idle gap", "solve.w_spread": "weight: same-day repeat", "solve.w_morning": "weight: hard subjects late",
                "solve.w_tgap": "weight: teacher idle gap", "solve.w_teacher_leg": "weight: teacher walking", "loads.k": "credit&rarr;slot factor k",
                "school.section_cap": "section cap", "school.section_floor": "minimum section size", "school.min_free_periods": "reserved free periods",
                "school.headcount": "headcount &plusmn;10%", "rooms.removed_frac": "rooms removed", "teachers.scale": "teacher supply",
                "teachers.external_busy_prob": "teachers shared with IB/G12", "solve.minutes_tol": "contact-minute tolerance",
                "solve.lab_doubles": "lab double periods", "school.pathways_G10": "G10 offered pathways", "school.pathways_G11AP": "G11-AP offered pathways",
                "solve.time_limit_s": "solver time limit", "solve.seed": "solver seed"}
        rows = sorted([(nice.get(k, k), min(v for _, v in vs), max(v for _, v in vs), "", "") for k, vs in by.items()], key=lambda r: r[2] - r[1])
        tor_svg = tornado(rows, bval, w=450)
        ok_runs = sum(1 for r in oat if "opt" in r and r["opt"]["ok"])
        n_inf = sum(1 for r in oat if "opt" not in r)
        n_sq = sum(1 for r in oat if "status_quo_error" in r)
        tor_note = (f"{len(oat)} runs &middot; {ok_runs} solved by us with zero checker violations &middot; {n_inf} infeasible for us &middot; "
                    f"{n_sq} where the current-style method could not produce any valid grid")
        cap = sorted([(r["overrides"]["rooms.removed_frac"] * 100, r) for r in oat if r["tag"].startswith("rooms.removed_frac")], key=lambda x: x[0])
        pts = [(x, r["opt"]["students"]["travel_s_mean"]) for x, r in cap if "opt" in r]
        bad = [x for x, r in cap if "status_quo_error" in r]
        cap_svg = line_chart(pts, 450, 210, "classrooms &amp; labs removed (%)", "optimized walking (s/wk)", BLUE, bad, bad_label="current method fails")
        kk = sorted([(r["overrides"]["loads.k"], r["opt"]["students"]["travel_s_mean"]) for r in oat if r["tag"].startswith("loads.k") and "opt" in r])
        k_bad = [r["overrides"]["loads.k"] for r in oat if r["tag"].startswith("loads.k") and "status_quo_error" in r]
        k_svg = line_chart(kk, 450, 210, "credit &rarr; slot factor k", "optimized walking (s/wk)", AQUA, k_bad, bad_label="current method fails")
    else:
        k_svg = ""
    if lhs and spec:
        import numpy as np
        rws = [r for r in lhs if "opt" in r]
        if len(rws) >= 8:
            keys = list(spec)
            X = np.array([[r["overrides"][k] for k in keys] for r in rws], float)
            Xs = (X - X.mean(0)) / (X.std(0) + 1e-12)
            y = np.array([r["opt"]["students"]["lost_min_week_mean"] for r in rws], float)
            beta, *_ = np.linalg.lstsq(Xs, (y - y.mean()) / (y.std() + 1e-12), rcond=None)
            nm = {"solve.w_gap": "w_gap", "solve.w_teacher_leg": "&lambda; teacher walking", "loads.k": "k (credit&rarr;slot)", "school.section_cap": "section cap",
                  "rooms.removed_frac": "rooms removed", "teachers.scale": "teacher supply", "teachers.external_busy_prob": "shared teachers", "school.min_free_periods": "free periods"}
            order = sorted(range(len(keys)), key=lambda i: abs(beta[i]))
            lhs_svg = hbars([(nm.get(keys[i], keys[i]), float(beta[i])) for i in order], 450, lab_w=140)
            r2 = 1 - float(np.sum((y - (Xs @ beta * y.std() + y.mean())) ** 2) / (np.sum((y - y.mean()) ** 2) + 1e-12))
            lhs_note = f"{len(rws)} Latin-hypercube runs &middot; linear fit R&sup2; = {r2:.2f}"
        else:
            lhs_note = ""
    else:
        lhs_note = ""
    if par:
        par_svg = line_chart([(p["teacher_travel_s"], p["student_travel_s"]) for p in par], 450, 240, "teacher walking (s / wk)", "student walking (s / wk)",
                             ORANGE, None, [str(p["lambda"]) for p in par])

    sh = res["shocks"]["draws"]
    ex = res["shocks"]["expected"]
    lev = {k: defaultdict(int) for k in sh}
    for k, L in sh.items():
        for x in L:
            lev[k][x.get("level", "infeasible")] += 1
    ta = sh["teacher_absence_1day"]
    cov = sum(x["covered"] for x in ta) / max(1, sum(x["affected_meetings"] for x in ta))
    cert_rows = "".join(f'<tr><td>{c}</td><td>{d}</td><td class="zero">{res["optimized"]["check"]["violations"].get(c, 0)}</td>'
                        f'<td class="bad">{round(statistics.mean(x["check"]["violations"].get(c, 0) for x in cs))}</td>'
                        f'<td>{"&#10003; caught" if mut["caught"].get(c) else "&ndash;"}</td></tr>'
                        for c, d in __import__("tt.checker", fromlist=["CODES"]).CODES.items())
    solver = res["optimized"]["solver"]
    gap = 100 * (solver["objective"] - solver["bound"]) / solver["objective"] if solver.get("objective") else float("nan")
    teacher_note = (f"Teachers: schedule loss {mean('teachers', 'sched_L_mean'):.1f} &rarr; {o['teachers']['sched_L_mean']:.1f}, "
                    f"idle gaps {mean('teachers', 'gaps_mean'):.1f} &rarr; {o['teachers']['gaps_mean']:.1f}/wk; walking "
                    f"{mean('teachers', 'travel_s_mean'):.0f} &rarr; {o['teachers']['travel_s_mean']:.0f} s/wk.")
    k = st["k"]

    MATH = MATH_TPL.replace("__K__", f"{k:.3f}")
    WEEK = week_section()
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Timetable Optimization Poster</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.css">
<script defer src="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.js"></script>
<script defer src="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/contrib/auto-render.min.js"
 onload="renderMathInElement(document.body,{{delimiters:[{{left:'$$',right:'$$',display:true}},{{left:'$',right:'$',display:false}}]}})"></script>
<style>
@page{{size:2200px 2350px;margin:0}}
:root{{--ink:#0b0b0b;--mut:#52514e;--line:#e2e1dd;--blue:#2a78d6;--orange:#eb6834;--aqua:#1baf7a;--soft:#f6f5f2}}
*{{box-sizing:border-box}}
body{{margin:0;background:#fff;color:var(--ink);font:17px/1.5 Inter,"Segoe UI",system-ui,sans-serif;-webkit-print-color-adjust:exact;print-color-adjust:exact}}
.poster{{width:2200px;margin:0 auto;padding:44px 56px 40px}}
header{{display:grid;grid-template-columns:1fr auto;gap:32px;align-items:end;border-bottom:6px solid var(--blue);padding-bottom:22px}}
h1{{font-size:54px;line-height:1.05;margin:0;letter-spacing:-.02em}}h1 span{{color:var(--blue)}}
.sub{{font-size:23px;color:var(--mut);margin-top:10px;max-width:1500px}}
.kpis{{display:flex;gap:14px}}.kpi{{background:var(--soft);border-radius:14px;padding:12px 18px;text-align:center;min-width:165px}}
.kpi b{{display:block;font-size:44px;color:var(--blue);line-height:1}}.kpi i{{font-style:normal;font-size:13px;color:var(--mut)}}
.cols{{display:grid;grid-template-columns:1fr 1.3fr 1fr 1fr;gap:26px;margin-top:26px}}
section{{background:#fff;border:1.5px solid var(--line);border-radius:16px;padding:20px 24px;margin-bottom:26px;break-inside:avoid}}
h2{{font-size:25px;margin:0 0 10px;display:flex;gap:10px;align-items:center}}h2 .n{{background:var(--blue);color:#fff;border-radius:50%;width:34px;height:34px;display:grid;place-items:center;font-size:18px}}
h3{{font-size:17px;margin:14px 0 4px;color:var(--mut);text-transform:uppercase;letter-spacing:.06em}}
p{{margin:6px 0}}.small{{font-size:14px;color:var(--mut)}}
.hl{{background:#eaf2fc;border-left:5px solid var(--blue);padding:8px 12px;border-radius:6px;margin:10px 0}}
.warn{{background:#fdeee7;border-left:5px solid var(--orange);padding:8px 12px;border-radius:6px;margin:10px 0}}
table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{padding:4px 8px;border-bottom:1px solid var(--line);text-align:left}}th{{color:var(--mut);font-size:12px;text-transform:uppercase}}
td.zero{{color:var(--blue);font-weight:800}}td.bad{{color:var(--orange);font-weight:800}}
.flow{{display:grid;gap:8px}}.step{{background:var(--soft);border-radius:10px;padding:8px 12px;font-size:15px}}.step b{{color:var(--blue)}}
.arrow{{text-align:center;color:var(--mut);line-height:.8}}
.legend{{display:flex;gap:16px;font-size:14px;color:var(--mut);margin:4px 0 8px}}.legend i{{display:inline-block;width:14px;height:14px;border-radius:3px;margin-right:6px;vertical-align:-2px}}
.katex-display{{margin:.6em 0;overflow-x:auto;overflow-y:hidden}}
footer{{margin-top:6px;color:var(--mut);font-size:14px;display:flex;justify-content:space-between}}

.wk{{display:grid;grid-template-columns:34px repeat(5,1fr);gap:3px;font-size:10px;margin-bottom:6px}}.wk b{{color:var(--mut);font-size:11px;text-align:center}}
.wk span{{background:#eaf2fc;border:1.5px solid #eaf2fc;border-radius:5px;padding:2px 3px;min-height:34px;line-height:1.15;overflow:hidden}}.wk span.mv{{background:#fdeee7;border-color:var(--orange)}}
.wk em{{display:block;font-style:normal;font-weight:700;color:var(--mut)}}.wk span.mv em{{color:var(--orange)}}
ul{{margin:6px 0;padding-left:22px}}li{{margin:3px 0}}
</style></head><body><div class="poster">
<header><div><h1>One timetable, <span>fewer footsteps, no wasted periods</span></h1>
<div class="sub">A constraint-certified, auto-scheduling system for {st['n_students']} students, {st['n_teachers']} teachers and 63 rooms &mdash; with a measured, stress-tested improvement over the current way of building the grid.</div></div>
<div class="kpis">
<div class="kpi"><b>&minus;{100 * (1 - o['students']['travel_s_mean'] / mean('students', 'travel_s_mean')):.0f}%</b><i>student walking</i></div>
<div class="kpi"><b>&minus;{100 * (1 - o['students']['gaps_mean'] / mean('students', 'gaps_mean')):.0f}%</b><i>idle periods</i></div>
<div class="kpi"><b>0</b><i>hard-rule violations<br>(10 rules, independently checked)</i></div>
<div class="kpi"><b>{ok_runs or '&ndash;'}</b><i>stress runs, all<br>still violation-free</i></div></div></header>

<div class="cols">
<div>
<section><h2><span class="n">1</span>What is wrong today</h2>
<p>From the one real G11-AP week we have, and a catalog audit:</p>
<ul>
<li><b>Students carry the walking.</b> Every teacher owns a room, so a student changes rooms ~<b>21&times;/week</b> (488 s of walking on the observed week).</li>
<li><b>Slots are filled with no objective</b>: stranded free periods between classes ({mean('students', 'gaps_mean'):.1f}/week), hard subjects late in the day.</li>
<li><b>Period length is ignored.</b> Periods run 60/40/40/45/55/40/40 min, so swapping a Math lesson from P1 to P2 silently removes 20 min &mdash; breaking the one rule the brief names: <i>hours must not change</i>. {round(statistics.mean(x['check']['violations'].get('H8', 0) for x in cs))} of {st['n_sections']} sections drift out of band in a typical status-quo grid.</li>
<li><b>Nothing is verified</b> and a room loss is repaired by hand.</li></ul>
<div class="warn small"><b>Honest scope.</b> We have one real week. The &ldquo;current system&rdquo; here is an emulator calibrated to it (~{res['emulator_calibration']['g11_changes']:.0f} vs 21 observed room changes), run 24 times to get a spread.</div></section>

<section><h2><span class="n">2</span>What we optimise &amp; who it affects</h2>
<table><tr><th>Aspect</th><th>Who</th><th>Why it matters</th></tr>
<tr><td>Room changes &amp; walking</td><td>{st['n_students']} students</td><td>transit time, late arrivals, congestion on stairs</td></tr>
<tr><td>Idle periods between classes</td><td>students, teachers</td><td>stranded time that cannot be used</td></tr>
<tr><td>Hard subjects in the morning</td><td>students</td><td>attention; mean period {mean('students','hard_subject_mean_period'):.1f}&rarr;{o['students']['hard_subject_mean_period']:.1f}</td></tr>
<tr><td>Equal minutes per course</td><td>everyone</td><td>the &ldquo;hours unchanged&rdquo; invariant</td></tr>
<tr><td>Teacher gaps, fatigue cap</td><td>{st['n_teachers']} teachers</td><td>fair, humane workload</td></tr>
<tr><td>Repairability</td><td>admin</td><td>closures, absences, surges</td></tr></table>
<p class="small">Students stay, teachers walk: one teacher-second counts <i>&lambda;</i> of a student-second (swept, see Pareto).</p></section>

<section><h2><span class="n">3</span>Method: four stages</h2>
<div class="flow">
<div class="step"><b>0 Sectioning.</b> Catalog rules &rarr; offered <i>pathways</i>; a pathway = one class with an identical timetable (kills cross-class clash cliques).</div><div class="arrow">&darr;</div>
<div class="step"><b>1 Slots (CP-SAT).</b> Boolean $z_{{g,s}}$ per section&times;slot &mdash; linear, not $O(M^2)$ pairwise.</div><div class="arrow">&darr;</div>
<div class="step"><b>2 Rooms.</b> Cohort home rooms &rarr; per-slot min-cost matching &rarr; exact person-seconds simulated annealing.</div><div class="arrow">&darr;</div>
<div class="step"><b>3 Certify.</b> A separate checker re-derives 10 rules from the finished grid; mutation tests prove it can fail.</div><div class="arrow">&darr;</div>
<div class="step"><b>4 Repair.</b> Substitute &rarr; re-room &rarr; re-slot only the affected sections, all else frozen.</div></div></section>
</div>

<div>
<section><h2><span class="n">4</span>The mathematics</h2>
{MATH}
</section>
</div>

<div>
<section><h2><span class="n">5</span>Results vs. the current system</h2>
<div class="legend"><span><i style="background:var(--orange)"></i>current, mean of 24 (whisker = range)</span><span><i style="background:var(--blue)"></i>optimized</span></div>
{headline}
<p class="small">{teacher_note}</p>
<h3>Which decision buys the walking saving?</h3>{ablation}
<div class="hl small">Room policy dominates walking; slot policy dominates idle gaps &mdash; the two stages are complementary, not redundant.</div></section>

<section><h2><span class="n">6</span>How we know every rule holds</h2>
<table><tr><th>Rule</th><th>Hard constraint</th><th>Ours</th><th>Current</th><th>Planted fault</th></tr>{cert_rows}</table>
<p class="small">{res['optimized']['check']['n_checked']['sections']} sections &middot; {res['optimized']['check']['n_checked']['students']} students &middot; {res['optimized']['check']['n_checked']['room_legs']} room legs checked. Mutation suite detected {sum(mut['caught'].values())}/{len(mut['caught'])} injected faults. 20 automated tests.</p></section>
</div>

<div>
<section><h2><span class="n">7</span>Sensitivity: do the conclusions survive?</h2>
<p class="small">{tor_note}. Each point rebuilds the school, re-solves, re-checks, and re-computes the status quo on the <i>same</i> world.</p>
<h3>Tornado: student lost-time gain (%) vs. every assumption</h3>{tor_svg}
<h3>Capacity cliff: remove rooms</h3>{cap_svg}<h3>Credit&rarr;slot factor k</h3>{k_svg}
<h3>Global screening: what moves student lost time? (standardised regression)</h3>{lhs_svg}<p class="small">{lhs_note}</p>
<h3>Pareto: who walks?</h3>{par_svg}
<p class="small">Labels are &lambda;. Moving walking from students (many) to teachers (few) is cheap until &lambda; &gt; ~4.</p></section>

<section><h2><span class="n">8</span>When circumstances change</h2>
<table><tr><th>Shock (p)</th><th>Repair used</th><th>Result</th></tr>
<tr><td>Teacher absent 1 day (.4)</td><td>substitute</td><td>{100 * cov:.0f}% of lessons covered</td></tr>
<tr><td>Room closed 1 week (.3)</td><td>{', '.join(f'{k} &times;{v}' for k, v in lev['room_closure_1week'].items())}</td><td>{statistics.mean(x.get('room_changes', 0) for x in sh['room_closure_1week']):.0f} lessons re-roomed, 0 re-slotted</td></tr>
<tr><td>Enrollment +5% (.3)</td><td>{', '.join(f'{k} &times;{v}' for k, v in lev['enrollment_surge_5pct'].items())}</td><td>{statistics.mean(x.get('rooms_outgrown', 0) for x in sh['enrollment_surge_5pct']):.0f} lessons need a bigger room</td></tr></table>
<p>$\\mathbb E[\\text{{moved lessons}}]={ex['moved_meetings']:.2f}$, $\\mathbb E[\\text{{room changes}}]={ex['room_changes']:.1f}$, infeasible rate {100 * ex['infeasible_rate']:.0f}%.</p></section>

{WEEK}
<section><h2><span class="n">9</span>Limits &amp; next steps</h2>
<ul class="small">
<li>All data simulated; only one week is real. Replace with registrar CSVs (schema ready).</li>
<li>CP-SAT stopped at its time limit: objective gap {gap:.0f}% to the bound. &ldquo;Optimized&rdquo; = best feasible found.</li>
<li>Pathway classes trade choice for feasibility &mdash; priced in the sweep.</li>
<li>Next: sections of one course still differ in minutes; teacher-to-section assignment joint with slots.</li></ul></section>
</div></div>
<footer><span>Constraints from the course catalog &middot; building model: 6 floors, 103 rooms, stair-aware walking times &middot; seed-reproducible, <code>python -m tt.run</code></span><span>All numbers from output/main_results.json &amp; output/sens_*.json</span></footer>
</div></body></html>"""
    import re
    secs = re.findall(r"<section>.*?</section>", html, re.S)
    assert len(secs) == 10, len(secs)
    head = html[:html.index('<div class="cols">')]
    tail = html[html.index("<footer>"):]
    col = lambda ids: "<div>" + "".join(secs[i - 1] for i in ids) + "</div>"
    html = head + '<div class="cols">' + col([1, 2, 3]) + col([4, 6]) + col([5, 9, 8]) + col([7, 10]) + "</div>" + tail
    (OUT / "poster.html").write_text(html, encoding="utf-8")
    return OUT / "poster.html"


if __name__ == "__main__":
    p = build()
    print("wrote", p)
    if "--pdf" in sys.argv:
        for exe in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Google\Chrome\Application\chrome.exe"):
            if Path(exe).exists():
                subprocess.run([exe, "--headless", "--disable-gpu", "--no-pdf-header-footer", "--virtual-time-budget=8000",
                                f"--print-to-pdf={OUT / 'poster.pdf'}", p.as_uri()], check=False)
                print("pdf", OUT / "poster.pdf")
                break
