"""Figures (PNG + one PDF) and the interactive HTML dashboard, built from output/*.json.
Run: python -m tt.report   (after tt.run and tt.sensitivity)
Palette: validated reference palette (blue / orange / aqua = first three slots, safe all-pairs).
"""
from __future__ import annotations

import base64
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from . import checker, config, metrics, mutations, world
from .config import ROOT

OUT = ROOT / "output"
FIG = OUT / "figures"
BLUE, ORANGE, AQUA, GREY = "#2a78d6", "#eb6834", "#1baf7a", "#8a8985"
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e2e1dd"
plt.rcParams.update({"font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": MUTED, "xtick.color": MUTED,
                     "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "figure.dpi": 150,
                     "savefig.facecolor": "white", "axes.titlesize": 11, "axes.titleweight": "bold"})


def jl(name):
    p = OUT / name
    return json.loads(p.read_text()) if p.exists() else None


def pct(a, b):
    return 100 * (1 - a / b) if b else 0


def save(fig, name, pdf):
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / f"{name}.png", bbox_inches="tight")
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def load_world():
    cfg = config.load()
    w = world.build(cfg)
    sol = json.loads((OUT / "main_solution.json").read_text())
    unk = lambda d: {(k.split("|")[0], int(k.split("|")[1])): v for k, v in d.items()}
    opt = ({g: v for g, v in sol["slot_of"].items()}, unk(sol["room"]))
    emu = ({g: v for g, v in sol["emu0"]["slot_of"].items()}, unk(sol["emu0"]["room"]))
    return w, opt, emu, sol


# ------------------------------------------------------------------------------ figures -----
def fig_headline(res, pdf):
    cs = res["current_system"]
    o = res["optimized"]["metrics"]["students"]
    keys = [("travel_s_mean", "Walking per student\n(seconds / week)"), ("room_changes_mean", "Room changes\nper student / week"),
            ("gaps_mean", "Idle periods between\nclasses / week"), ("lost_min_week_mean", "Lost time per student\n(min / week)")]
    fig, axs = plt.subplots(1, 4, figsize=(12, 3.4))
    for ax, (k, lab) in zip(axs, keys):
        vals = [c["metrics"]["students"][k] for c in cs]
        m, lo, hi = statistics.mean(vals), min(vals), max(vals)
        ax.bar([0], [m], color=ORANGE, width=0.55)
        ax.errorbar([0], [m], yerr=[[m - lo], [hi - m]], color=INK, capsize=4, lw=1)
        ax.bar([1], [o[k]], color=BLUE, width=0.55)
        ax.set_xticks([0, 1], [f"Current\n(n={len(cs)})", "Optimized"])
        ax.set_title(lab, fontsize=9)
        ax.text(1, o[k], f"{o[k]:.0f}" if o[k] > 20 else f"{o[k]:.1f}", ha="center", va="bottom", color=INK, fontsize=9)
        ax.text(0, hi, f"{m:.0f}" if m > 20 else f"{m:.1f}", ha="center", va="bottom", color=INK, fontsize=9)
        ax.set_ylim(0, hi * 1.2)
        ax.text(0.5, 0.88, f"-{pct(o[k], m):.0f}%", transform=ax.transAxes, ha="center", color=BLUE, fontweight="bold")
        ax.grid(axis="x", visible=False)
    fig.suptitle("Students: current-system emulator vs optimized timetable (same school, same loads)", y=1.04, fontsize=11)
    save(fig, "01_headline", pdf)


def fig_distribution(w, opt, emu, pdf):
    mo = metrics.evaluate(w, *opt)["per_student"]
    me = metrics.evaluate(w, *emu)["per_student"]
    fig, axs = plt.subplots(1, 2, figsize=(11, 3.6))
    for ax, key, lab in zip(axs, ("travel_s", "gaps"), ("Walking (s / week)", "Idle periods / week")):
        for i, (m, c, n) in enumerate([(me, ORANGE, "Current"), (mo, BLUE, "Optimized")]):
            by_g = defaultdict(list)
            for sid, p in m.items():
                by_g[sid.split("-")[0]].append(p[key])
        data = [[p[key] for p in me.values()], [p[key] for p in mo.values()]]
        parts = ax.violinplot(data, showmedians=True, widths=0.8)
        for pc, c in zip(parts["bodies"], (ORANGE, BLUE)):
            pc.set_facecolor(c); pc.set_alpha(0.75); pc.set_edgecolor("white")
        for k in ("cbars", "cmins", "cmaxes", "cmedians"):
            parts[k].set_color(INK); parts[k].set_linewidth(0.8)
        ax.set_xticks([1, 2], ["Current", "Optimized"]); ax.set_ylabel(lab)
        ax.grid(axis="x", visible=False)
    axs[0].set_title("Every student, not just the average")
    axs[1].set_title("Gaps: free periods stranded between classes")
    save(fig, "02_distribution", pdf)


def fig_ablation(res, pdf):
    cs = res["current_system"]
    cur = statistics.mean(c["metrics"]["students"]["travel_s_mean"] for c in cs)
    curg = statistics.mean(c["metrics"]["students"]["gaps_mean"] for c in cs)
    ab = res["ablation"]
    rows = [("Current\n(blind slots +\nteacher-owned rooms)", cur, curg, ORANGE),
            ("Blind slots +\noptimized rooms", ab["blind_slots+opt_rooms"]["metrics"]["students"]["travel_s_mean"],
             ab["blind_slots+opt_rooms"]["metrics"]["students"]["gaps_mean"], AQUA),
            ("Optimized slots +\nteacher-owned rooms", ab["opt_slots+owned_rooms"]["metrics"]["students"]["travel_s_mean"],
             ab["opt_slots+owned_rooms"]["metrics"]["students"]["gaps_mean"], AQUA),
            ("Optimized\n(both)", res["optimized"]["metrics"]["students"]["travel_s_mean"],
             res["optimized"]["metrics"]["students"]["gaps_mean"], BLUE)]
    fig, axs = plt.subplots(1, 2, figsize=(11, 3.6))
    for ax, i, lab in zip(axs, (1, 2), ("Walking (s / student / week)", "Idle periods / student / week")):
        ax.bar(range(4), [r[i] for r in rows], color=[r[3] for r in rows], width=0.6)
        for x, r in enumerate(rows):
            ax.text(x, r[i], f"{r[i]:.0f}" if r[i] > 20 else f"{r[i]:.1f}", ha="center", va="bottom", fontsize=9)
        ax.set_xticks(range(4), [r[0] for r in rows], fontsize=8); ax.set_ylabel(lab)
        ax.grid(axis="x", visible=False)
    axs[0].set_title("Which decision buys the walking saving? (room policy vs slot policy)")
    axs[1].set_title("Which decision buys the gap saving?")
    save(fig, "03_ablation", pdf)


def fig_certificate(res, mut, pdf):
    codes = list(checker.CODES)
    cur = res["current_system"][0]["check"]["violations"]
    opt = res["optimized"]["check"]["violations"]
    fig, ax = plt.subplots(figsize=(11, 4.4))
    ax.axis("off")
    rows = []
    for c in codes:
        rows.append([c, checker.CODES[c], str(cur.get(c, 0)), str(opt.get(c, 0)), "caught" if mut["caught"].get(c) else "-"])
    t = ax.table(cellText=rows, colLabels=["Rule", "Hard constraint", "Current: violations", "Optimized: violations",
                                           "Planted fault detected"], loc="center", cellLoc="left",
                 colWidths=[0.05, 0.5, 0.14, 0.15, 0.16])
    t.auto_set_font_size(False); t.set_fontsize(8.5); t.scale(1, 1.5)
    for (r, c), cell in t.get_celld().items():
        cell.set_edgecolor(GRID)
        if r == 0:
            cell.set_facecolor("#f0efec"); cell.set_text_props(fontweight="bold")
        elif c == 2 and rows[r - 1][2] != "0":
            cell.set_text_props(color=ORANGE, fontweight="bold")
        elif c == 3:
            cell.set_text_props(color=BLUE if rows[r - 1][3] == "0" else ORANGE, fontweight="bold")
    n = res["optimized"]["check"]["n_checked"]
    ax.set_title(f"Constraint certificate: independent checker re-derived all 10 rules from the finished grid "
                 f"({n['sections']} sections, {n['students']} students, {n['teachers']} teachers, {n['room_legs']} room legs)\n"
                 f"Mutation test: {sum(mut['caught'].values())}/{len(mut['caught'])} planted faults detected", fontsize=10)
    save(fig, "04_certificate", pdf)


def week_grid(ax, w, sid, slot_of, room, title, lit):
    ss = w.student_sections()[sid]
    cell = {}
    for g in ss:
        for s in slot_of[g]:
            cell[s] = (w.sections[g].course, room[(g, s)])
    days = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    ax.set_xlim(0, 5); ax.set_ylim(7, 0); ax.set_xticks([i + .5 for i in range(5)], days)
    ax.set_yticks([i + .5 for i in range(7)], [f"P{i+1}" for i in range(7)]); ax.grid(False)
    ax.xaxis.tick_top()
    prev = {}
    for s in w.slots:
        x, y = days.index(s["day"]), s["period"] - 1
        if s["idx"] in cell:
            c, r = cell[s["idx"]]
            moved = (x in prev and prev[x][1] != r and prev[x][0] == y - 1)
            ax.add_patch(plt.Rectangle((x + .03, y + .03), .94, .94, color="#fbe4d9" if moved else "#dbe9f8", lw=0))
            ax.text(x + .5, y + .38, c.split("#")[0], ha="center", va="center", fontsize=7, color=INK)
            ax.text(x + .5, y + .70, r, ha="center", va="center", fontsize=7.5, color=ORANGE if moved else MUTED,
                    fontweight="bold" if moved else None)
            prev[x] = (y, r)
        elif s["idx"] in w.pe_slots:
            ax.add_patch(plt.Rectangle((x + .03, y + .03), .94, .94, color="#ececea", lw=0))
            ax.text(x + .5, y + .5, "PE", ha="center", va="center", fontsize=7, color=MUTED)
    ax.set_title(title, fontsize=9)


def fig_timetable(w, opt, emu, pdf):
    sid = next(s for s in w.students if s.startswith("G11AP"))
    fig, axs = plt.subplots(1, 2, figsize=(12, 4.6))
    mo = metrics.evaluate(w, *opt)["per_student"][sid]
    me = metrics.evaluate(w, *emu)["per_student"][sid]
    week_grid(axs[0], w, sid, *emu, f"Current  -  {me['changes']} room changes, {me['travel_s']:.0f} s walking, {me['gaps']} idle", 0)
    week_grid(axs[1], w, sid, *opt, f"Optimized  -  {mo['changes']} room changes, {mo['travel_s']:.0f} s walking, {mo['gaps']} idle", 1)
    fig.suptitle(f"One G11-AP student's week ({sid}); orange = had to change rooms since the previous period", y=1.0, fontsize=10)
    save(fig, "05_timetable", pdf)


def fig_building(w, opt, emu, pdf):
    xy = {}
    with open(ROOT / "data/building/rooms.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            xy[r["id"]] = (r["floor"], float(r["anchor_x_m"]), float(r["anchor_y_m"]))
    from . import model
    def traffic(slot_of, room):
        L = model.legs(w, slot_of) if False else None
        t = defaultdict(float)
        ssec = w.student_sections()
        for sid, lst in ssec.items():
            by_day = defaultdict(list)
            for g in lst:
                for s in slot_of[g]:
                    by_day[w.slots[s]["day"]].append((s, g))
            for items in by_day.values():
                items.sort()
                for (s1, g1), (s2, g2) in zip(items, items[1:]):
                    a, b = room[(g1, s1)], room[(g2, s2)]
                    if a != b:
                        t[a] += 1; t[b] += 1
        return t
    floors = ["B2", "B1", "1F", "2F", "3F", "4F"]
    fig, axs = plt.subplots(2, 6, figsize=(14, 5), sharex=True, sharey=True)
    tt = [traffic(*emu), traffic(*opt)]
    mx = max(max(t.values()) for t in tt)
    for row, (t, name, col) in enumerate(zip(tt, ("Current", "Optimized"), (ORANGE, BLUE))):
        for j, fl in enumerate(floors):
            ax = axs[row][j]
            for rid, (f_, x, y) in xy.items():
                if f_ == fl:
                    ax.scatter(x, y, s=8, color=GRID, zorder=1)
                    if t.get(rid):
                        ax.scatter(x, y, s=10 + 260 * t[rid] / mx, color=col, alpha=0.7, zorder=2, edgecolor="white", lw=.5)
            ax.set_title(fl if row == 0 else "", fontsize=9); ax.set_aspect("equal"); ax.grid(False)
            ax.set_xticks([]); ax.set_yticks([])
        axs[row][0].set_ylabel(name)
    fig.suptitle("Where students change rooms: dot area = room-changes/week touching that room, by floor "
                 f"(same area scale; peak {mx:.0f})", y=1.0, fontsize=10)
    save(fig, "06_building", pdf)


def fig_pareto(par, pdf):
    if not par:
        return
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    ax.plot([p["teacher_travel_s"] for p in par], [p["student_travel_s"] for p in par], "-o", color=BLUE, lw=2)
    for p in par:
        ax.annotate(f"{p['lambda']}", (p["teacher_travel_s"], p["student_travel_s"]), textcoords="offset points",
                    xytext=(5, 5), fontsize=8, color=MUTED)
    ax.set_xlabel("Teacher walking (s / teacher / week)"); ax.set_ylabel("Student walking (s / student / week)")
    ax.set_title("Pareto: who walks?  (labels = weight of a teacher-second vs a student-second)")
    save(fig, "07_pareto", pdf)


def fig_tornado(oat, pdf):
    if not oat:
        return
    base = next((r for r in oat if r["tag"] == "base" and "improvement" in r), None)
    if not base:
        return
    b = base["improvement"]["lost_min_pct"]
    by = defaultdict(list)
    for r in oat:
        if r["tag"] == "base" or "improvement" not in r:
            continue
        by[r["tag"].split("=")[0]].append((r["tag"].split("=", 1)[1], r["improvement"]["lost_min_pct"]))
    rows = [(k, min(v for _, v in vs), max(v for _, v in vs)) for k, vs in by.items()]
    rows.sort(key=lambda x: x[2] - x[1])
    fig, ax = plt.subplots(figsize=(8.5, 0.34 * len(rows) + 1.2))
    for i, (k, lo, hi) in enumerate(rows):
        ax.barh(i, hi - lo, left=lo, color=BLUE, height=0.55)
    ax.axvline(b, color=INK, lw=1)
    ax.set_yticks(range(len(rows)), [r[0] for r in rows], fontsize=8)
    ax.set_xlabel("Student lost-time reduction vs current system (%); line = baseline setting")
    ax.set_title("Tornado: how far does each assumption move the headline gain?")
    ax.grid(axis="y", visible=False)
    save(fig, "08_tornado", pdf)


def fig_capacity(oat, pdf):
    pts = [(r["overrides"].get("rooms.removed_frac"), r) for r in (oat or []) if r["tag"].startswith("rooms.removed_frac")]
    pts = sorted([(x, r) for x, r in pts if x is not None])
    if not pts:
        return
    fig, ax = plt.subplots(figsize=(6.4, 4))
    xs = [100 * x for x, r in pts if "improvement" in r]
    ax.plot(xs, [r["improvement"]["lost_min_pct"] for x, r in pts if "improvement" in r], "-o", color=BLUE, lw=2)
    for x, r in pts:
        if "improvement" not in r:
            ax.axvline(100 * x, color=ORANGE, ls="--"); ax.text(100 * x, 5, f" infeasible: {r.get('status')[:18]}", rotation=90, color=ORANGE, fontsize=8)
    ax.set_xlabel("Classrooms/labs removed (%)"); ax.set_ylabel("Lost-time reduction vs current (%)")
    ax.set_title("Capacity cliff: how much building can we lose?")
    save(fig, "09_capacity", pdf)


def fig_lhs(lhs, spec, pdf):
    import numpy as np
    rows = [r for r in (lhs or []) if "improvement" in r]
    if len(rows) < 8:
        return
    keys = list(spec)
    X = np.array([[r["overrides"][k] for k in keys] for r in rows], float)
    Xs = (X - X.mean(0)) / (X.std(0) + 1e-12)
    outs = {"Student lost-time gain (%)": [r["improvement"]["lost_min_pct"] for r in rows],
            "Student walking (s/week)": [r["opt"]["students"]["travel_s_mean"] for r in rows],
            "Teacher schedule loss": [r["opt"]["teachers"]["sched_L_mean"] for r in rows]}
    fig, axs = plt.subplots(1, 3, figsize=(13, 3.8), sharey=True)
    for ax, (name, y) in zip(axs, outs.items()):
        y = np.array(y, float)
        ys = (y - y.mean()) / (y.std() + 1e-12)
        beta, *_ = np.linalg.lstsq(Xs, ys, rcond=None)
        order = np.argsort(np.abs(beta))
        ax.barh(range(len(keys)), beta[order], color=[BLUE if b > 0 else ORANGE for b in beta[order]], height=0.6)
        ax.set_yticks(range(len(keys)), [keys[i] for i in order], fontsize=8)
        ax.set_title(name, fontsize=9); ax.axvline(0, color=INK, lw=.8); ax.grid(axis="y", visible=False)
    fig.suptitle(f"Global screening: standardized regression coefficients over {len(rows)} Latin-hypercube runs "
                 "(blue +, orange -)", y=1.02, fontsize=10)
    save(fig, "10_lhs", pdf)


def fig_shocks(res, pdf):
    sh = res["shocks"]["draws"]
    fig, axs = plt.subplots(1, 3, figsize=(12, 3.5))
    for ax, k, title in zip(axs, ("teacher_absence_1day", "room_closure_1week", "enrollment_surge_5pct"),
                            ("Teacher absent 1 day", "Room closed 1 week", "Enrollment +5%")):
        L = sh[k]
        lev = defaultdict(int)
        for x in L:
            lev[x.get("level", "infeasible")] += 1
        ax.bar(list(lev), list(lev.values()), color=BLUE, width=0.5)
        extra = ""
        if k == "teacher_absence_1day":
            extra = f"covered {sum(x['covered'] for x in L)}/{sum(x['affected_meetings'] for x in L)} lessons"
        else:
            extra = f"mean meetings re-roomed {statistics.mean(x.get('room_changes', 0) for x in L):.0f}, re-slotted {statistics.mean(x.get('moved_meetings', 0) for x in L):.1f}"
        ax.set_title(title, fontsize=9); ax.set_xlabel(extra, fontsize=8); ax.set_ylabel("draws (of %d)" % len(L))
        ax.grid(axis="x", visible=False)
    e = res["shocks"]["expected"]
    fig.suptitle(f"Repair ladder (cheapest sufficient fix). E[moved lessons]={e['moved_meetings']:.2f}, "
                 f"E[room changes]={e['room_changes']:.1f}, infeasible rate={e['infeasible_rate']:.0%}", y=1.03, fontsize=10)
    save(fig, "11_shocks", pdf)


# -------------------------------------------------------------------------------- dashboard ---
def b64(name):
    return base64.b64encode((FIG / name).read_bytes()).decode()


def build_dashboard(res, w, opt, emu, sol, mut, oat, lhs, par):
    cs = res["current_system"]
    o = res["optimized"]["metrics"]
    cur = lambda sec, k: statistics.mean(c["metrics"][sec][k] for c in cs)
    cards = [
        ("Walking per student", f"{cur('students','travel_s_mean'):.0f}s", f"{o['students']['travel_s_mean']:.0f}s", pct(o['students']['travel_s_mean'], cur('students', 'travel_s_mean'))),
        ("Room changes / week", f"{cur('students','room_changes_mean'):.1f}", f"{o['students']['room_changes_mean']:.1f}", pct(o['students']['room_changes_mean'], cur('students', 'room_changes_mean'))),
        ("Idle periods / week", f"{cur('students','gaps_mean'):.2f}", f"{o['students']['gaps_mean']:.2f}", pct(o['students']['gaps_mean'], cur('students', 'gaps_mean'))),
        ("Worst-20% student walking", f"{cur('students','travel_s_cvar80'):.0f}s", f"{o['students']['travel_s_cvar80']:.0f}s", pct(o['students']['travel_s_cvar80'], cur('students', 'travel_s_cvar80'))),
        ("Contact-minute violations", f"{statistics.mean(c['check']['violations'].get('H8',0) for c in cs):.0f} sections", "0", 100),
    ]
    # per-student interactive data (sample)
    ssec = sol["student_sections"]
    pick = [s for s in sorted(ssec) if s.startswith("G11AP")][:12] + [s for s in sorted(ssec) if s.startswith("G10")][:12] + \
           [s for s in sorted(ssec) if s.startswith("G9")][:12]
    data = {}
    for sid in pick:
        for nm, (so, rm) in (("cur", emu), ("opt", opt)):
            cells = {}
            for g in ssec[sid]:
                for s in so[g]:
                    sl = w.slots[s]
                    cells[f"{sl['day']}{sl['period']}"] = [w.sections[g].course, rm[(g, s)]]
            data.setdefault(sid, {})[nm] = cells
    sens_rows = ""
    for r in (oat or []):
        imp = r.get("improvement")
        sens_rows += (f"<tr><td>{r['tag']}</td><td>{r.get('status')}</td>"
                      f"<td>{imp['lost_min_pct']:.1f}</td><td>{imp['travel_pct']:.1f}</td><td>{imp['gaps_pct']:.1f}</td>"
                      f"<td>{r['opt']['students']['travel_s_mean']:.0f}</td><td>{r['opt']['teachers']['sched_L_mean']:.1f}</td>"
                      f"<td>{'OK' if r['opt']['ok'] else sum(r['opt']['viol'].values())}</td></tr>") if imp else \
                     f"<tr><td>{r['tag']}</td><td>{r.get('status')}</td><td colspan=6>n/a</td></tr>"
    figs = [("01_headline.png", "Headline"), ("02_distribution.png", "Distribution"), ("03_ablation.png", "What buys the gain"),
            ("04_certificate.png", "Constraint certificate"), ("05_timetable.png", "One week"), ("06_building.png", "Building"),
            ("07_pareto.png", "Pareto"), ("08_tornado.png", "Tornado"), ("09_capacity.png", "Capacity"),
            ("10_lhs.png", "Global screening"), ("11_shocks.png", "Shocks")]
    figs = [(f, t) for f, t in figs if (FIG / f).exists()]
    st = res["stats"]
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Timetable Optimizer Results</title>
<style>
:root{{--bg:#fcfcfb;--ink:#0b0b0b;--mut:#52514e;--line:#e2e1dd;--blue:#2a78d6;--orange:#eb6834;--card:#fff}}
@media (prefers-color-scheme:dark){{:root:not([data-theme=light]){{--bg:#1a1a19;--ink:#f0efec;--mut:#c3c2b7;--line:#34332f;--blue:#3987e5;--orange:#d95926;--card:#222220}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,Segoe UI,sans-serif}}
main{{max-width:1100px;margin:0 auto;padding:24px 16px 64px}}
h1{{font-size:26px;margin:0 0 4px}}h2{{font-size:18px;margin:36px 0 8px}}p.sub{{color:var(--mut);margin:0 0 20px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}}
.card{{border:1px solid var(--line);border-radius:10px;padding:12px;background:var(--card)}}
.card .l{{color:var(--mut);font-size:12px}}.card .v{{font-size:22px;font-weight:700}}.card .c{{color:var(--orange);text-decoration:line-through;font-size:13px}}
.card .d{{color:var(--blue);font-weight:700}}
.tabs{{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0}}.tabs button{{border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:999px;padding:6px 12px;cursor:pointer}}
.tabs button.on{{background:var(--blue);color:#fff;border-color:var(--blue)}}
img{{max-width:100%;border:1px solid var(--line);border-radius:8px;background:#fff}}
table{{border-collapse:collapse;width:100%;font-size:13px}}th,td{{border-bottom:1px solid var(--line);padding:4px 8px;text-align:left}}th{{color:var(--mut)}}
.grid{{display:grid;grid-template-columns:60px repeat(5,1fr);gap:3px;font-size:11px}}
.grid div{{padding:4px;border-radius:4px;min-height:34px;background:var(--card);border:1px solid var(--line)}}
.grid .h{{font-weight:700;background:none;border:none}}.moved{{border-color:var(--orange)!important}}.moved b{{color:var(--orange)}}
.two{{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:16px}}
select{{padding:6px;border-radius:6px;border:1px solid var(--line);background:var(--card);color:var(--ink)}}
details{{border:1px solid var(--line);border-radius:8px;padding:8px 12px;margin:8px 0}}
.note{{color:var(--mut);font-size:13px}}
</style></head><body><main>
<h1>Full-school timetable optimizer</h1>
<p class="sub">{st['n_students']} students (G9, G10, G11-AP) &middot; {st['n_sections']} sections &middot; {st['n_meetings']} weekly lessons &middot; {st['n_teachers']} teachers &middot; 63 teaching rooms. Simulated data; loads from the catalog calibrated on the observed week (k={st['k']:.3f}).</p>
<div class="cards">
{''.join(f'<div class="card"><div class="l">{a}</div><div class="v">{c if False else d}</div><div class="c">now {b}</div><div class="d">-{p:.0f}%</div></div>' for a,b,d,p in cards)}
</div>
<h2>Pick a student</h2>
<p class="note">Same courses, same teachers, same loads. Orange border = changed rooms since the previous period.</p>
<select id="sid"></select>
<div class="two" style="margin-top:12px"><div><h3>Current system (emulated)</h3><div id="cur" class="grid"></div></div>
<div><h3>Optimized</h3><div id="opt" class="grid"></div></div></div>
<h2>Results</h2>
<div class="tabs" id="tabs"></div><div id="fig"></div>
<h2>Sensitivity: one-at-a-time</h2>
<p class="note">Columns: lost-time / walking / idle-gap reduction vs the status quo of the same world (%), optimized walking (s), teacher schedule loss, violations (OK = zero).</p>
<details><summary>{len(oat or [])} runs</summary><table><tr><th>setting</th><th>solver</th><th>lost-time %</th><th>walking %</th><th>gaps %</th><th>walk s</th><th>teacher L</th><th>checks</th></tr>{sens_rows}</table></details>
<h2>Honest caveats</h2>
<ul class="note"><li>Everything is simulated; the only real timetable data is one observed G11-AP week. The "current system" is an emulator calibrated to that week (room changes and teacher-owned rooms), clearly not the school's real grid.</li>
<li>Loads come from the catalog/GPA credits via a fitted factor (k={st['k']:.3f}); the sensitivity runs sweep it from 0.83 to 1.0.</li>
<li>Pathway-class sectioning for G10/G11-AP is a design choice, not a given: it removes cross-class elective clashes at the price of smaller classes. Its effect is quantified in the staffing sweep.</li></ul>
</main>
<script>
const D={json.dumps(data)};const figs={json.dumps([(f,t) for f,t in figs])};const IMG={{{','.join(f'"{f}":"{b64(f)}"' for f,_ in figs)}}};
const days=['Mon','Tue','Wed','Thu','Fri'];
const sel=document.getElementById('sid');Object.keys(D).forEach(s=>{{const o=document.createElement('option');o.value=o.textContent=s;sel.appendChild(o)}});
function draw(id,cells){{const g=document.getElementById(id);g.innerHTML='<div class="h"></div>'+days.map(d=>'<div class="h">'+d+'</div>').join('');
for(let p=1;p<=7;p++){{g.innerHTML+='<div class="h">P'+p+'</div>';let prev={{}};
days.forEach(d=>{{const c=cells[d+p];if(!c){{g.innerHTML+='<div></div>';return}}
g.innerHTML+='<div><b>'+c[0].split('#')[0]+'</b><br>'+c[1]+'</div>'}})}}}}
function drawAll(){{const s=D[sel.value];['cur','opt'].forEach(k=>{{const g=document.getElementById(k);const cells=s[k];
let h='<div class="h"></div>'+days.map(d=>'<div class="h">'+d+'</div>').join('');
for(let p=1;p<=7;p++){{h+='<div class="h">P'+p+'</div>';days.forEach(d=>{{const c=cells[d+p];const q=cells[d+(p-1)];
if(!c){{h+='<div></div>';return}}const mv=q&&q[1]!==c[1];h+='<div class="'+(mv?'moved':'')+'">'+(mv?'<b>':'')+c[0]+'<br>'+c[1]+(mv?'</b>':'')+'</div>'}})}}
g.innerHTML=h}})}}
sel.onchange=drawAll;drawAll();
const tabs=document.getElementById('tabs'),fig=document.getElementById('fig');
figs.forEach(([f,t],i)=>{{const b=document.createElement('button');b.textContent=t;b.onclick=()=>{{[...tabs.children].forEach(x=>x.classList.remove('on'));b.classList.add('on');fig.innerHTML='<img alt="'+t+'" src="data:image/png;base64,'+IMG[f]+'">'}};tabs.appendChild(b);if(i==0)b.click()}});
</script></body></html>"""
    (OUT / "dashboard.html").write_text(html, encoding="utf-8")


def main():
    res = jl("main_results.json")
    oat, lhs, par = jl("sens_oat.json"), jl("sens_lhs.json"), jl("sens_pareto.json")
    spec = jl("sens_lhs_spec.json")
    w, opt, emu, sol = load_world()
    mut = mutations.run_suite(w, *opt)
    (OUT / "mutation_suite.json").write_text(json.dumps(mut))
    FIG.mkdir(parents=True, exist_ok=True)
    with PdfPages(OUT / "report_figures.pdf") as pdf:
        fig_headline(res, pdf); fig_distribution(w, opt, emu, pdf); fig_ablation(res, pdf)
        fig_certificate(res, mut, pdf); fig_timetable(w, opt, emu, pdf); fig_building(w, opt, emu, pdf)
        fig_pareto(par, pdf); fig_tornado(oat, pdf); fig_capacity(oat, pdf)
        if lhs and spec:
            fig_lhs(lhs, spec, pdf)
        fig_shocks(res, pdf)
    build_dashboard(res, w, opt, emu, sol, mut, oat, lhs, par)
    print("wrote", OUT / "dashboard.html")


if __name__ == "__main__":
    main()
