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


def stair_landmarks() -> dict:
    """stair id -> {floor: (px, py)} from the building model connectors."""
    bm = building()
    out = {}
    for c in bm.get("connectors", []):
        if c.get("type") not in ("stair", "elevator"):
            continue
        per = {}
        for fl, info in (c.get("floors") or {}).items():
            land = (info or {}).get("landing")
            if land and fl in FLOORS:
                per[fl] = [land[0] * SC + 0.5 * SC, land[1] * SC + 0.5 * SC]
        if per:
            out[c["id"]] = per
    return out


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
    marks = stair_landmarks()
    sim, crowd = {}, {}
    sim_path = ROOT / "output/elevator_sim.json"
    if sim_path.exists():
        sim = json.loads(sim_path.read_text(encoding="utf-8"))
    crowd_path = ROOT / "output/crowd.json"
    if crowd_path.exists():
        crowd = json.loads(crowd_path.read_text(encoding="utf-8"))
    slow, loads, rerouted, cars = {}, {}, {}, {}
    for k, v in (crowd.get("breaks") or {}).items():
        s = v.get("slowdown", {})
        slow[k] = max(s.values()) if s else 1.0
        loads[k] = v.get("stair_loads", {})
        rerouted[k] = v.get("rerouted", 0)
    for k, v in (sim.get("breaks") or {}).items():
        cars[k] = {"trips": v.get("trips", []), "gap": v.get("gap_s", 600),
                   "avoided": v.get("shared_avoided", 0),
                   "avg_wait": round(v.get("avg_wait_s", 0), 1)}
    html = ["<!DOCTYPE html><html><head><meta charset='utf-8'><title>Break-time replay</title>",
            "<style>body{font-family:system-ui,sans-serif;background:#fbfaf6;color:#1b1b1b;max-width:1200px;margin:auto;padding:16px}"
            ".floors{display:flex;flex-wrap:wrap;gap:12px}.panel{position:relative}"
            ".panel svg{display:block}circle.dot{opacity:.85}"
            "#bar{display:flex;gap:8px;align-items:center;margin:12px 0}</style></head><body>",
            "<h1>Break-time replay (schematic)</h1>",
            "<div id='bar'><select id='brk'></select><button id='play'>Play</button>",
            "<span id='info'></span></div>",
            f"<div id='sim'>Elevator: {sim.get('total_lift_requests', 'not run')} requests, "
            f"peak {sim.get('peak_break', '—')} (collective control, no double-dispatch) · "
            f"Crowd: stair capacity {crowd.get('stair_cap', '—')}/break, G9/G10 multi-floor scope</div>",
            "<div id='shaft'></div>",
            "<div class='floors'>"]
    for f in FLOORS:
        html.append(f"<div class='panel'><h3>{f}</h3><div id='p-{f}'>{panels[f]}</div></div>")
    html.append("</div>")
    html.append("<script>const DATA=" + json.dumps(data) + ";")
    html.append("const SLOW=" + json.dumps(slow) + ";const LOADS=" + json.dumps(loads)
                + ";const REROUTED=" + json.dumps(rerouted) + ";const CARS=" + json.dumps(cars)
                + ";const MARKS=" + json.dumps(marks) + ";")
    html.append("""const FLOORS=["B1","1F","2F","3F","4F"];
const sel=document.getElementById('brk'), info=document.getElementById('info'), shaft=document.getElementById('shaft');
Object.keys(DATA).forEach(k=>{const o=document.createElement('option');o.value=k;o.textContent=k;sel.appendChild(o);});
function badgeColor(load,cap){const r=load/cap;if(r>=1)return '#d4572c';if(r>=0.5)return '#c99a2e';return '#2a8f84';}
function draw(key,t){
  FLOORS.forEach(f=>{document.querySelectorAll('#p-'+f+' circle.dot,#p-'+f+' circle.badge').forEach(e=>e.remove());});
  const d=DATA[key]; const NS='http://www.w3.org/2000/svg';
  const slow=SLOW[key]||1, ld=LOADS[key]||{}, cap=%CAP%;
  for(const [s,fl] of Object.entries(MARKS)){for(const [f,p] of Object.entries(fl)){
    const g=document.querySelector('#p-'+f+' svg'); if(!g||ld[s]===undefined) continue;
    const b=document.createElementNS(NS,'circle');b.setAttribute('class','badge');
    b.setAttribute('cx',p[0]);b.setAttribute('cy',p[1]);b.setAttribute('r',7);
    b.setAttribute('fill',badgeColor(ld[s],cap));b.setAttribute('opacity',0.9);
    b.innerHTML='<title>'+s+': '+ld[s]+' persons</title>';g.appendChild(b);}}
  if(!d){info.textContent='no moves';return;}
  info.textContent=d.teachers.length+' teacher legs, '+d.students.length+' student dots (sampled)'
    +' · stair slowdown x'+slow.toFixed(2)+' · rerouted '+(REROUTED[key]||0)
    +' · lift avoided '+(CARS[key]?CARS[key].avoided:0)+' double-dispatches';
  const put=(m,color,r)=>{
    // cross-floor dots move slower on congested breaks (schematic: t/slow)
    const tt=(m[0]!==m[3])?Math.min(t*slow,1):t;
    const g0=document.querySelector('#p-'+m[0]+' svg'), g1=document.querySelector('#p-'+m[3]+' svg');
    if(!g0||!g1) return;
    const c=document.createElementNS(NS,'circle');
    c.setAttribute('class','dot');c.setAttribute('r',r);c.setAttribute('fill',color);
    if(m[0]===m[3]){c.setAttribute('cx',m[1]+(m[4]-m[1])*t);c.setAttribute('cy',m[2]+(m[5]-m[2])*t);c.setAttribute('opacity',0.85);g0.appendChild(c);}
    else{const c2=c.cloneNode();c.setAttribute('cx',m[1]);c.setAttribute('cy',m[2]);c.setAttribute('opacity',0.85*(1-tt));g0.appendChild(c);c2.setAttribute('cx',m[4]);c2.setAttribute('cy',m[5]);c2.setAttribute('opacity',0.85*tt);g1.appendChild(c2);}
  };
  d.students.forEach(m=>put(m,'#1f5fa8',2.2));
  d.teachers.forEach(m=>put(m,'#d4572c',3.0));
  // lift shaft strip: two car timelines for this break
  shaft.innerHTML='';
  const cb=CARS[key];
  if(cb&&cb.trips.length){
    const order={"B2":-2,"B1":-1,"1F":0,"2F":1,"3F":2,"4F":3};
    const s=document.createElementNS(NS,'svg');s.setAttribute('width','520');s.setAttribute('height','90');
    const X=t=>20+t/cb.gap*480, Y=f=>80-(f+2)*12;
    [0,1].forEach(car=>{
      const tr=cb.trips.filter(x=>x.car===car); if(!tr.length) return;
      let dAttr='M'+X(0)+' '+Y(tr[0].pickup);
      tr.forEach(x=>{dAttr+=' L'+X(x.t_board)+' '+Y(x.pickup)+' L'+X(x.t_free)+' '+Y(x.drop);});
      const p=document.createElementNS(NS,'path');p.setAttribute('d',dAttr);
      p.setAttribute('stroke',car?'#c99a2e':'#1f5fa8');p.setAttribute('fill','none');p.setAttribute('stroke-width','2');
      const t=document.createElementNS(NS,'text');t.setAttribute('x','2');t.setAttribute('y',Y(car?2:-1)+3);
      t.setAttribute('font-size','9');t.textContent='car'+car;s.appendChild(t);s.appendChild(p);});
    shaft.appendChild(s);
    const lab=document.createElement('div');lab.style.fontSize='12px';
    lab.textContent='E1 cars during this break ('+cb.trips.length+' trips, avg wait '+cb.avg_wait+'s)';shaft.appendChild(lab);
  }
}
let timer=null;
document.getElementById('play').onclick=()=>{if(timer){clearInterval(timer);timer=null;return;}
  let t=0;timer=setInterval(()=>{t+=0.05;if(t>1){clearInterval(timer);timer=null;}draw(sel.value,Math.min(t,1));},80);};
sel.onchange=()=>draw(sel.value,1);draw(sel.value||Object.keys(DATA)[0],1);
</script></body></html>""")
    Path(a.out).write_text("\n".join(html).replace("%CAP%", str(crowd.get("stair_cap", 150))), encoding="utf-8")
    print(f"wrote {a.out} with {len(data)} breaks")


def sol_rooms_floor(sol: dict) -> dict:
    return {rid: r["floor"] for rid, r in sol["rooms"].items()}


if __name__ == "__main__":
    main()
