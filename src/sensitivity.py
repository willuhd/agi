"""Sensitivity analysis: one-at-a-time tornado, Latin-hypercube global screening (standardized regression
coefficients), room-stage Pareto (students vs teachers) and the capacity cliff.

Every point rebuilds the world, re-solves, re-checks (checker must stay at 0 violations) and re-computes
the status-quo emulator on the SAME world so the reported improvement is like-for-like.
Run: python -m sensitivity [oat|lhs|pareto|all]
"""
from __future__ import annotations

import json
import multiprocessing as mp
import random
import sys
import time
from pathlib import Path

import checker, config, emulator, metrics, model, world

OUT = Path(__file__).resolve().parent.parent / "output"
P_OWN = 0.6          # calibrated in run.main (G11-AP: ~20 vs observed 21 room changes)
BASE_TL = 45

OAT = {
    # objective weights
    "solve.w_gap": [0, 1, 3, 6, 12],
    "solve.w_spread": [0, 2, 8],
    "solve.w_morning": [0, 0.15, 1.0],
    "solve.w_tgap": [0, 0.3, 1.0],
    "solve.w_teacher_leg": [0, 0.5, 1, 3],
    # data uncertainty
    "loads.k": [0.83, 0.8725, 0.95, 1.0],
    "school.section_cap": [20, 24, 28],
    "school.section_floor": [4, 6, 10],
    "school.min_free_periods": [1, 2, 4],
    "school.headcount": [0.9, 1.0, 1.1],
    # structure / capacity
    "rooms.removed_frac": [0.0, 0.2, 0.4, 0.55],
    "teachers.scale": [0.8, 1.0, 1.25],
    "teachers.external_busy_prob": [0.0, 0.3, 0.6],
    "solve.minutes_tol": [0.04, 0.08, 0.15],
    "solve.lab_doubles": [False, True],
    "school.pathways_G10": [6, 11, 16],
    "school.pathways_G11AP": [6, 10, 14],
    # solver
    "solve.time_limit_s": [20, 45, 120],
    "solve.seed": [1, 2, 3],
}


def _overrides(param, val):
    if param == "school.headcount":
        return {"school.G9": int(250 * val), "school.G10": int(250 * val), "school.G11AP": int(126 * val)}
    if param.startswith("school.pathways_"):
        g = param.split("_")[1]
        base = {"G10": 11, "G11AP": 10}
        base[g] = val
        return {"school.pathways": base}
    return {param: val}


def run_point(args):
    tag, ov = args
    t0 = time.time()
    ov = {"solve.time_limit_s": BASE_TL, "solve.workers": 4, "solve.room_polish_iters": 20000, **ov}
    rec = {"tag": tag, "overrides": ov}
    try:
        cfg = config.load(ov)
        w = world.build(cfg)
        rec["stats"] = w.stats
        # status quo on the same world (it may fail to produce a grid at all: that is a result too)
        mb = None
        try:
            sb = emulator.blind_slots(w, 0, 25)
            rb = emulator.teacher_owned_rooms(w, sb, 0, P_OWN)
            mb = metrics.evaluate(w, sb, rb)
            rec["status_quo"] = {"students": mb["students"], "teachers": mb["teachers"],
                                 "viol": checker.check(w, sb, rb)["violations"], "J": metrics.objective(mb, cfg)}
        except Exception as e:
            rec["status_quo_error"] = f"{type(e).__name__}: {str(e)[:100]}"
        r = model.solve_slots(w, time_limit=cfg["solve"]["time_limit_s"])
        rec["status"] = r["status"]
        if r["assignment"]:
            so = r["assignment"]
            rm, info = model.assign_rooms(w, so)
            m = metrics.evaluate(w, so, rm)
            c = checker.check(w, so, rm)
            rec["opt"] = {"students": m["students"], "teachers": m["teachers"], "contact": m["contact"],
                          "viol": c["violations"], "ok": c["ok"], "J": metrics.objective(m, cfg),
                          "objective": r["objective"], "bound": r["bound"]}
            if mb is not None:
              rec["improvement"] = {
                  "travel_pct": 100 * (1 - m["students"]["travel_s_mean"] / max(1e-9, mb["students"]["travel_s_mean"])),
                  "gaps_pct": 100 * (1 - m["students"]["gaps_mean"] / max(1e-9, mb["students"]["gaps_mean"])),
                  "lost_min_pct": 100 * (1 - m["students"]["lost_min_week_mean"] / max(1e-9, mb["students"]["lost_min_week_mean"])),
                  "J_pct": 100 * (1 - rec["opt"]["J"] / max(1e-9, rec["status_quo"]["J"])),
              }
    except Exception as e:   # infeasible build / room matching etc. is a result, not a crash
        rec["status"] = f"ERROR: {type(e).__name__}: {str(e)[:120]}"
    rec["wall_s"] = round(time.time() - t0, 1)
    return rec


def oat_jobs():
    jobs = [("base", {})]
    for p, vals in OAT.items():
        for v in vals:
            jobs.append((f"{p}={v}", _overrides(p, v)))
    return jobs


def lhs_jobs(n=24, seed=7):
    rng = random.Random(seed)
    spec = {   # (low, high, integer?)
        "solve.w_gap": (0.5, 10, False), "solve.w_teacher_leg": (0, 4, False), "loads.k": (0.83, 0.93, False),
        "school.section_cap": (20, 28, True), "rooms.removed_frac": (0.0, 0.3, False),
        "teachers.scale": (0.8, 1.25, False), "teachers.external_busy_prob": (0.0, 0.6, False),
        "school.min_free_periods": (1, 4, True),
    }
    keys = list(spec)
    cols = {}
    for k in keys:
        idx = list(range(n))
        rng.shuffle(idx)
        cols[k] = [(i + rng.random()) / n for i in idx]
    jobs = []
    for i in range(n):
        ov = {}
        for k in keys:
            lo, hi, isint = spec[k]
            x = lo + cols[k][i] * (hi - lo)
            ov[k] = int(round(x)) if isint else round(x, 4)
        jobs.append((f"lhs{i:02d}", ov))
    return jobs, spec


def run_jobs(jobs, path, procs=3, merge=False):
    OUT.mkdir(exist_ok=True)
    done = json.loads(Path(path).read_text()) if merge and Path(path).exists() else []
    with mp.Pool(procs) as pool:
        for rec in pool.imap_unordered(run_point, jobs):
            done = [d for d in done if d["tag"] != rec["tag"]] + [rec]
            Path(path).write_text(json.dumps(done, default=str))
            print(f"{rec['tag']:<34} {rec.get('status','?'):<10} {rec['wall_s']}s "
                  f"{rec.get('improvement', {}).get('lost_min_pct', float('nan')):.1f}%", flush=True)
    return done


def pareto(path):
    """Room-stage Pareto: one slot grid, sweep how much a teacher's walking second counts vs a student's."""
    cfg = config.load({"solve.time_limit_s": 90, "solve.room_polish_iters": 30000})
    w = world.build(cfg)
    r = model.solve_slots(w, time_limit=90)
    so = r["assignment"]
    pts = []
    for lam in (0, 0.25, 0.5, 1, 2, 4, 8, 16, 32):
        w2 = world.World(**{**w.__dict__, "cfg": config.clone(cfg, {"solve.w_teacher_leg": lam})})
        rm, _ = model.assign_rooms(w2, so, seed=1)
        m = metrics.evaluate(w, so, rm)
        pts.append({"lambda": lam, "student_travel_s": m["students"]["travel_s_mean"],
                    "student_travel_h": m["students"]["travel_total_person_hours"],
                    "teacher_travel_s": m["teachers"]["travel_s_mean"],
                    "teacher_L": m["teachers"]["sched_L_mean"], "teacher_L_cvar": m["teachers"]["sched_L_cvar80"],
                    "ok": checker.check(w, so, rm)["ok"]})
        print("pareto", pts[-1], flush=True)
    Path(path).write_text(json.dumps(pts))
    return pts


def failed_tags(path):
    d = json.loads(Path(path).read_text())
    return {r["tag"] for r in d if "opt" not in r or "improvement" not in r}


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what == "retry":   # re-run only points that failed (e.g. the status-quo emulator, not us, failed)
        bad = failed_tags(OUT / "sens_oat.json")
        todo = [j for j in oat_jobs() if j[0] in bad or j[0].startswith(("solve.time_limit_s", "solve.seed"))]
        run_jobs(todo, OUT / "sens_oat.json", merge=True)
        jobs, spec = lhs_jobs()
        have = {r["tag"] for r in json.loads((OUT / "sens_lhs.json").read_text()) if "opt" in r and "improvement" in r}
        run_jobs([j for j in jobs if j[0] not in have], OUT / "sens_lhs.json", merge=True)
        (OUT / "sens_lhs_spec.json").write_text(json.dumps(spec))
        pareto(OUT / "sens_pareto.json")
        sys.exit()
    if what in ("oat", "all"):
        run_jobs(oat_jobs(), OUT / "sens_oat.json")
    if what in ("lhs", "all"):
        jobs, spec = lhs_jobs()
        run_jobs(jobs, OUT / "sens_lhs.json")
        (OUT / "sens_lhs_spec.json").write_text(json.dumps(spec))
    if what in ("pareto", "all"):
        pareto(OUT / "sens_pareto.json")
