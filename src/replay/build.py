"""Build output/replay.html. Run: PYTHONPATH=src python -m replay.build."""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

from config import ROOT
from viz import building, plan

FLOORS = ["B1", "1F", "2F", "3F", "4F"]
W = 300
SC = W / 41.0  # must match viz.plan transform (w=300, no title)


def xy(floor_id: str, room_id: str) -> tuple[float, float] | None:
    bm = building()
    f = next(x for x in bm["floors"] if x["id"] == floor_id)
    for r in f["rooms"]:
        if r["id"] == room_id:
            return (r["anchor"][0] * SC + 0.5 * SC, r["anchor"][1] * SC + 0.5 * SC)
    return None


def moves(sol: dict, rooms: dict, max_student_dots: int, seed: int) -> dict:
    """break_key -> {'teachers': [...], 'students': [...] sampled}. Each dot:
    [floor0, x0, y0, floor1, x1, y1]."""
    rng = random.Random(seed)
    ssec = sol["student_sections"]
    rm = sol["room"]
    sec_of = sol["sections"]
    slots = {s["idx"]: s for s in sol["slots"]}
    per_break = defaultdict(lambda: {"teachers": [], "students": []})
    # teachers: every consecutive same-day pair
    by_t = defaultdict(list)
    for g, sl in sol["slot_of"].items():
        for s in sl:
            by_t[sec_of[g]["teacher"]].append((s, g))
    for lst in by_t.values():
        lst.sort()
        for (s1, g1), (s2, g2) in zip(lst, lst[1:]):
            a, b = slots[s1], slots[s2]
            if a["day"] != b["day"] or b["period"] != a["period"] + 1:
                continue
            r1, r2 = rm[f"{g1}|{s1}"], rm[f"{g2}|{s2}"]
            if r1 == r2:
                continue
            p1 = xy(rooms[r1], r1)
            p2 = xy(rooms[r2], r2)
            if p1 and p2:
                per_break[f"{a['day']} P{a['period']}->{b['period']}"]["teachers"].append(
                    [rooms[r1], *p1, rooms[r2], *p2])
    # students: one entry per leg, then weighted sample
    legs = []
    for sid, lst in ssec.items():
        ms = sorted((s, g) for g in lst for s in sol["slot_of"][g])
        for (s1, g1), (s2, g2) in zip(ms, ms[1:]):
            a, b = slots[s1], slots[s2]
            if a["day"] != b["day"] or b["period"] != a["period"] + 1:
                continue
            r1, r2 = rm[f"{g1}|{s1}"], rm[f"{g2}|{s2}"]
            if r1 == r2:
                continue
            legs.append((f"{a['day']} P{a['period']}->{b['period']}", r1, r2))
    rng.shuffle(legs)
    quota = max(1, max_student_dots // max(1, len(per_break)))
    per_key_count = defaultdict(int)
    for key, r1, r2 in legs:
        if per_key_count[key] >= quota:
            continue
        p1, p2 = xy(rooms[r1], r1), xy(rooms[r2], r2)
        if p1 and p2:
            per_break[key]["students"].append([rooms[r1], *p1, rooms[r2], *p2])
            per_key_count[key] += 1
    return per_break


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the break-time dot replay.")
    ap.add_argument("solution", nargs="?", default=str(ROOT / "output/main_solution.json"))
    ap.add_argument("--dots", type=int, default=600)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default=str(ROOT / "output/replay.html"))
    a = ap.parse_args()
    sol = json.loads(Path(a.solution).read_text(encoding="utf-8"))
    rooms = sol_rooms_floor(sol)
    data = moves(sol, rooms, a.dots, a.seed)
    panels = {f: plan(f, w=W, show_ids=False) for f in FLOORS}
    sim = {}
    sim_path = ROOT / "output/elevator_sim.json"
    if sim_path.exists():
        sim = json.loads(sim_path.read_text(encoding="utf-8"))
    html = ["<!DOCTYPE html><html><head><meta charset='utf-8'><title>Break-time replay</title>",
            "<style>body{font-family:system-ui,sans-serif;background:#fbfaf6;color:#1b1b1b;max-width:1200px;margin:auto;padding:16px}"
            ".floors{display:flex;flex-wrap:wrap;gap:12px}.panel{position:relative}"
            ".panel svg{display:block}circle.dot{opacity:.85}"
            "#bar{display:flex;gap:8px;align-items:center;margin:12px 0}</style></head><body>",
            "<h1>Break-time replay (schematic)</h1>",
            "<div id='bar'><select id='brk'></select><button id='play'>Play</button>",
            "<span id='info'></span></div>",
            f"<div id='sim'>Elevator sim: {sim.get('total_lift_requests', 'not run')} requests, "
            f"peak {sim.get('peak_break', '—')}</div>",
            "<div class='floors'>"]
    for f in FLOORS:
        html.append(f"<div class='panel'><h3>{f}</h3><div id='p-{f}'>{panels[f]}</div></div>")
    html.append("</div>")
    html.append("<script>const DATA=" + json.dumps(data) + ";")
    html.append("""const FLOORS=["B1","1F","2F","3F","4F"];
const sel=document.getElementById('brk'), info=document.getElementById('info');
Object.keys(DATA).forEach(k=>{const o=document.createElement('option');o.value=k;o.textContent=k;sel.appendChild(o);});
function draw(key,t){
  FLOORS.forEach(f=>{document.querySelectorAll('#p-'+f+' circle.dot').forEach(e=>e.remove());});
  const d=DATA[key]; if(!d){info.textContent='no moves';return;}
  info.textContent=d.teachers.length+' teacher legs, '+d.students.length+' student dots (sampled)';
  const put=(m,color,r)=>{
    const outs={},ins={};
    // fade out at origin for cross-floor, glide within floor
    const g0=document.querySelector('#p-'+m[0]+' svg'), g1=document.querySelector('#p-'+m[3]+' svg');
    if(!g0||!g1) return;
    const NS='http://www.w3.org/2000/svg';
    const c=document.createElementNS(NS,'circle');
    c.setAttribute('class','dot');c.setAttribute('r',r);c.setAttribute('fill',color);
    if(m[0]===m[3]){c.setAttribute('cx',m[1]+(m[4]-m[1])*t);c.setAttribute('cy',m[2]+(m[5]-m[2])*t);c.setAttribute('opacity',0.85);g0.appendChild(c);}
    else{const c2=c.cloneNode();c.setAttribute('cx',m[1]);c.setAttribute('cy',m[2]);c.setAttribute('opacity',0.85*(1-t));g0.appendChild(c);c2.setAttribute('cx',m[4]);c2.setAttribute('cy',m[5]);c2.setAttribute('opacity',0.85*t);g1.appendChild(c2);}
  };
  d.students.forEach(m=>put(m,'#1f5fa8',2.2));
  d.teachers.forEach(m=>put(m,'#d4572c',3.0));
}
let timer=null;
document.getElementById('play').onclick=()=>{if(timer){clearInterval(timer);timer=null;return;}
  let t=0;timer=setInterval(()=>{t+=0.05;if(t>1){clearInterval(timer);timer=null;}draw(sel.value,Math.min(t,1));},80);};
sel.onchange=()=>draw(sel.value,1);draw(sel.value||Object.keys(DATA)[0],1);
</script></body></html>""")
    Path(a.out).write_text("\n".join(html), encoding="utf-8")
    print(f"wrote {a.out} with {len(data)} breaks")


def sol_rooms_floor(sol: dict) -> dict:
    return {rid: r["floor"] for rid, r in sol["rooms"].items()}


if __name__ == "__main__":
    main()
