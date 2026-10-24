"""End-to-end pipeline: world -> baselines -> optimized grid -> checks -> metrics."""
from __future__ import annotations

import json
import time
from pathlib import Path

from . import checker, config, emulator, metrics, model, world

OUT = Path(__file__).resolve().parent.parent.parent / "output"


def summarize(w, slot_of, room, label):
    m = metrics.evaluate(w, slot_of, room)
    c = checker.check(w, slot_of, room)
    slim = {k: v for k, v in m.items() if k not in ("per_student", "per_teacher")}
    return {"label": label, "metrics": slim, "check": c, "J": metrics.objective(m, w.cfg)}, m


def run_optimizer(w, hint=None, time_limit=None, seed=0, verbose=False):
    t0 = time.time()
    r = model.solve_slots(w, time_limit=time_limit, hint=hint)
    t1 = time.time()
    if not r["assignment"]:
        return None, r
    slot_of = r["assignment"]
    room, info = model.assign_rooms(w, slot_of, seed=seed)
    return (slot_of, room), {**{k: v for k, v in r.items() if k != "assignment"}, "room_info": {
        k: v for k, v in info.items() if k != "homes"}, "t_slots": t1 - t0, "t_rooms": time.time() - t1}


def pipeline(cfg=None, overrides=None, emu_seeds=(0,), time_limit=None, save=None):
    cfg = cfg or config.load(overrides)
    w = world.build(cfg)
    res = {"stats": w.stats, "baselines": {}}
    for sd in emu_seeds:
        so, rm = emulator.emulate(w, seed=sd, p_own=_p_own(cfg))
        res["baselines"][f"emulator_{sd}"], _ = summarize(w, so, rm, f"current-system emulator #{sd}")
    # hint from emulator #0 (valid except it ignores minute bands) just to warm start
    sol, info = run_optimizer(w, time_limit=time_limit)
    if sol is None:
        res["optimized"] = {"status": info["status"]}
        return w, res, None
    res["optimized"], m = summarize(w, sol[0], sol[1], "optimized")
    res["optimized"]["solver"] = info
    if save:
        OUT.mkdir(exist_ok=True)
        Path(save).write_text(json.dumps(res, default=str, indent=1))
    return w, res, sol


def _p_own(cfg):
    p = cfg["emulator"]["p_stay"]
    return 1.0 if p == "auto" else float(p)


# ------------------------------------------------------------------------------------ main --------

def _g11_changes(m):
    v = [p["changes"] for s, p in m["per_student"].items() if s.startswith("G11")]
    return sum(v) / len(v)


def calibrate_p_own(w, slot_of, target):
    best = (9e9, 1.0)
    for p in (1.0, 0.95, 0.9, 0.85, 0.8, 0.7, 0.6):
        rm = emulator.teacher_owned_rooms(w, slot_of, seed=0, p_own=p)
        m = metrics.evaluate(w, slot_of, rm)
        d = abs(_g11_changes(m) - target)
        if d < best[0]:
            best = (d, p, _g11_changes(m))
    return best


_W = {}


def _emu_job(args):
    seed, overrides, p_own, tl = args
    cfg = config.load(overrides)
    key = tuple(sorted((overrides or {}).items(), key=str))
    if key not in _W:
        _W.clear()
        _W[key] = world.build(cfg)
    w = _W[key]
    slot_of = emulator.blind_slots(w, seed, time_limit=tl)
    room = emulator.teacher_owned_rooms(w, slot_of, seed, p_own)
    s, m = summarize(w, slot_of, room, f"emulator {seed}")
    return seed, s, ({"slot_of": slot_of, "room": {f"{g}|{sl}": r for (g, sl), r in room.items()}} if seed == 0 else None)


def main(n_emu=24, solve_time=150, n_shocks=12, out=None):
    out = str(out or OUT / "main")
    import multiprocessing as mp
    t0 = time.time()
    OUT.mkdir(exist_ok=True)
    cfg = config.load({"solve.time_limit_s": solve_time})
    w = world.build(cfg)
    print("world", w.stats, flush=True)
    res = {"stats": w.stats, "config": {k: cfg[k] for k in ("loads", "school", "solve", "teachers", "rooms")}}
    # current-system emulator, calibrated to the observed week (G11-AP: 21 room changes)
    so0 = emulator.blind_slots(w, 0, 20)
    d, p_own, chg = calibrate_p_own(w, so0, cfg["emulator"]["target_changes"])
    print(f"calibrated p_own={p_own} (G11AP changes {chg:.1f} vs observed 21)", flush=True)
    res["emulator_calibration"] = {"p_own": p_own, "g11_changes": chg, "target": 21.0}
    with mp.Pool(6) as pool:
        jobs = [(sd, {"solve.time_limit_s": solve_time, "solve.workers": 2}, p_own, 15) for sd in range(n_emu)]
        out_emu = pool.map(_emu_job, jobs)
    res["current_system"] = [s for _, s, _ in out_emu]
    emu0 = next(x for sd, _, x in out_emu if x is not None)
    print("emulators done", round(time.time() - t0), flush=True)
    # optimized
    sol, info = run_optimizer(w, time_limit=solve_time)
    slot_of, room = sol
    res["optimized"], mo = summarize(w, slot_of, room, "optimized")
    res["optimized"]["solver"] = info
    print("optimized", info["status"], info.get("objective"), info.get("bound"), round(time.time() - t0), flush=True)
    # ablation: blind slots + optimized rooms ; optimized slots + owned rooms
    so_b = emu0["slot_of"]
    room_b, _ = model.assign_rooms(w, so_b)
    res["ablation"] = {}
    res["ablation"]["blind_slots+opt_rooms"], _ = summarize(w, so_b, room_b, "blind slots + optimized rooms")
    room_c = emulator.teacher_owned_rooms(w, slot_of, 0, p_own)
    res["ablation"]["opt_slots+owned_rooms"], _ = summarize(w, slot_of, room_c, "optimized slots + owned rooms")
    # shocks
    from . import shocks
    sh = shocks.run_scenarios(w, slot_of, room, n_draws=n_shocks)
    res["shocks"] = {"draws": sh, "expected": shocks.expected_delta(sh)}
    print("shocks", res["shocks"]["expected"], round(time.time() - t0), flush=True)
    # persist
    sol_json = {"slot_of": slot_of, "room": {f"{g}|{s}": r for (g, s), r in room.items()},
                "emu0": emu0,
                "sections": {g: {"course": s.course, "teacher": s.teacher, "size": s.size, "kind": s.kind,
                                 "homerooms": s.homerooms, "n": s.n} for g, s in w.sections.items()},
                "slots": w.slots, "students": {sid: {"grade": st["grade"], "homeroom": st["homeroom"],
                                                     "courses": st["courses"]} for sid, st in w.students.items()},
                "student_sections": w.student_sections(),
                "rooms": {r.id: {"kind": r.kind, "floor": r.floor, "area": r.area} for r in w.rooms.values()},
                "courses": {k: {"label": c.label, "credit": c.credit, "slots": c.slots, "src": c.credit_src}
                            for k, c in w.courses.items()}}
    Path(out + "_solution.json").write_text(json.dumps(sol_json))
    Path(out + "_results.json").write_text(json.dumps(res, default=str, indent=1))
    print("done", round(time.time() - t0), flush=True)


if __name__ == "__main__":
    import sys
    main(n_emu=int(sys.argv[1]) if len(sys.argv) > 1 else 24, solve_time=int(sys.argv[2]) if len(sys.argv) > 2 else 150)
