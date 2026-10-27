"""3D break replay: floor plates stacked in CSS-3D space, dots walking to a
stair/lift shaft, traversing vertically, and continuing. Teachers assigned to
the lift (same share convention as elevator.sim) ride E1 grouped by
(pickup floor, drop floor) -- one car movement per group; students take the
stairs from their route's primary via stair. Schematic: uniform segment
timing, straight walk legs, per-floor stair landings give the dog-leg jog.

Run: PYTHONPATH=src python -m replay.build3d"""

from __future__ import annotations

import argparse
import csv
import json
import random
from collections import defaultdict
from pathlib import Path

from config import ROOT
from viz import plan

from .build import FLOORS, SC, sol_rooms_floor, stair_landmarks, xy

FLOOR_Z = {f: i * 170 for i, f in enumerate(FLOORS)}  # px depth per level


def load_via() -> dict:
    out = {}
    with open(ROOT / "schoolmap-1.0.0/output/routes.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["via"].strip():
                out[(r["from"], r["to"])] = r["via"].split()
    return out


def dots_3d(sol: dict, rooms: dict, via: dict, share: float, seed: int,
            max_dots: int) -> dict:
    """break -> list of dots. Dot: {pts:[[x,y,z]...], color, grp}.
    grp groups lift riders sharing one car movement (None = independent)."""
    rng = random.Random(seed)
    rm, sec = sol["room"], sol["sections"]
    slots = {s["idx"]: s for s in sol["slots"]}
    ssec = sol["student_sections"]
    marks = stair_landmarks()
    e1 = marks.get("E1", {})
    out = defaultdict(list)

    def land(stair: str, fl: str):
        m = marks.get(stair, {})
        return m.get(fl)

    def push(key: str, pts: list, color: str, grp):
        # drop None-coord waypoints (missing landing), keep endpoints
        pts = [p for p in pts if p[0] is not None]
        if len(pts) >= 2:
            out[key].append({"pts": pts, "color": color, "grp": grp})

    # students: stairs only
    legs = []
    for sid, lst in ssec.items():
        ms = sorted((s, g) for g in lst for s in sol["slot_of"][g])
        for (s1, g1), (s2, g2) in zip(ms, ms[1:]):
            a, b = slots[s1], slots[s2]
            if a["day"] != b["day"] or b["period"] != a["period"] + 1:
                continue
            r1, r2 = rm[f"{g1}|{s1}"], rm[f"{g2}|{s2}"]
            if r1 == r2 or rooms[r1] == rooms[r2]:
                continue
            legs.append((f"{a['day']} P{a['period']}->{b['period']}", r1, r2))
    rng.shuffle(legs)
    quota = max(1, max_dots // max(1, 30))
    per_key = defaultdict(int)
    for key, r1, r2 in legs:
        if per_key[key] >= quota:
            continue
        f0, f1 = rooms[r1], rooms[r2]
        p0, p3 = xy(f0, r1), xy(f1, r2)
        v = via.get((r1, r2), [])
        if not p0 or not p3 or not v:
            continue
        st = v[0]
        l0, l1 = land(st, f0), land(st, f1)
        if not l0 or not l1:
            continue
        push(key, [(p0[0], p0[1], FLOOR_Z[f0]), (l0[0], l0[1], FLOOR_Z[f0]),
                   (l1[0], l1[1], FLOOR_Z[f1]), (p3[0], p3[1], FLOOR_Z[f1])],
             "#1f5fa8", None)
        per_key[key] += 1
    # teachers: lift (grouped) or stairs
    by_t = defaultdict(list)
    for g, sl in sol["slot_of"].items():
        for s in sl:
            by_t[sec[g]["teacher"]].append((s, g))
    for lst in by_t.values():
        lst.sort()
        for (s1, g1), (s2, g2) in zip(lst, lst[1:]):
            a, b = slots[s1], slots[s2]
            if a["day"] != b["day"] or b["period"] != a["period"] + 1:
                continue
            r1, r2 = rm[f"{g1}|{s1}"], rm[f"{g2}|{s2}"]
            if r1 == r2:
                continue
            f0, f1 = rooms[r1], rooms[r2]
            key = f"{a['day']} P{a['period']}->{b['period']}"
            p0, p3 = xy(f0, r1), xy(f1, r2)
            if not p0 or not p3:
                continue
            if f0 == f1:
                push(key, [(p0[0], p0[1], FLOOR_Z[f0]), (p3[0], p3[1], FLOOR_Z[f1])],
                     "#d4572c", None)
            elif rng.random() > share:
                v = via.get((r1, r2), [])
                st = v[0] if v else "S1"
                l0, l1 = land(st, f0), land(st, f1)
                if not l0 or not l1:
                    continue
                push(key, [(p0[0], p0[1], FLOOR_Z[f0]), (l0[0], l0[1], FLOOR_Z[f0]),
                           (l1[0], l1[1], FLOOR_Z[f1]), (p3[0], p3[1], FLOOR_Z[f1])],
                     "#d4572c", None)
            else:
                l0, l1 = (e1.get(f0), e1.get(f1)) if e1 else (None, None)
                if not l0 or not l1:
                    continue
                grp = f"E1:{f0}>{f1}"
                push(key, [(p0[0], p0[1], FLOOR_Z[f0]), (l0[0], l0[1], FLOOR_Z[f0]),
                           (l1[0], l1[1], FLOOR_Z[f1]), (p3[0], p3[1], FLOOR_Z[f1])],
                     "#c99a2e", grp)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the 3D break replay.")
    ap.add_argument("solution", nargs="?", default=str(ROOT / "output/main_solution.json"))
    ap.add_argument("--share", type=float, default=0.85)
    ap.add_argument("--dots", type=int, default=600)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default=str(ROOT / "output/replay3d.html"))
    a = ap.parse_args()
    sol = json.loads(Path(a.solution).read_text(encoding="utf-8"))
    rooms = sol_rooms_floor(sol)
    data = dots_3d(sol, rooms, load_via(), a.share, a.seed, a.dots)
    panels = {f: plan(f, w=300, show_ids=False) for f in FLOORS}
    zmax = max(FLOOR_Z.values())
    h = ["<!DOCTYPE html><html><head><meta charset='utf-8'><title>3D break replay</title>",
         "<style>body{font-family:system-ui,sans-serif;background:#101318;color:#e8e4da;max-width:1200px;margin:auto;padding:16px}"
         "#bar{display:flex;gap:8px;align-items:center;margin:12px 0;color:#e8e4da}"
         "#stage{width:100%;height:740px;perspective:1500px;position:relative;overflow:hidden;background:#171b22;border-radius:8px}"
         "#scene{position:absolute;left:50%;top:62%;transform-style:preserve-3d;transform:rotateX(52deg) rotateZ(38deg) scale(.86);transition:opacity .25s}"
         ".plate{position:absolute;transform-style:preserve-3d;border:1px solid #3a4150}"
         ".plate svg{display:block;background:#fbfaf6}"
         ".dot{position:absolute;width:7px;height:7px;border-radius:50%;margin:-3.5px;box-shadow:0 0 4px #000}"
         ".car{position:absolute;border:2px solid #c99a2e;border-radius:4px;background:rgba(201,153,46,.18);font-size:9px;color:#c99a2e}"
         "select,button{font-size:14px}</style></head><body>",
         "<h1>3D break replay (schematic)</h1>",
         "<div id='bar'><select id='brk'></select><button id='play'>Play</button>",
         "<button id='playall'>Play week</button>",
         "<label>speed <input id='spd' type='range' min='1' max='8' value='3'></label>",
         "<span id='info'></span></div>",
         "<div id='stage'><div id='scene'></div></div>",
         "<p style='font-size:12px;color:#9aa'>Blue students take the stairs (primary via stair, per-floor landings). "
         "Gold teachers ride E1 grouped by pickup&gt;drop floors — one car movement per group. "
         "Straight walk legs; uniform segment timing.</p>",
         "<script>const DATA=" + json.dumps(data) + ";",
         "const FLOORS=" + json.dumps(FLOORS) + ";const Z=" + json.dumps(FLOOR_Z) + ";",
         "const PLATES={" + ",".join(f'"{f}":' + json.dumps(panels[f]) for f in FLOORS) + "};",
         "const scene=document.getElementById('scene'),sel=document.getElementById('brk'),info=document.getElementById('info');",
         """Object.keys(DATA).forEach(k=>{const o=document.createElement('option');o.value=k;o.textContent=k;sel.appendChild(o);});
const PW=300, PH=300*52/41.0;
FLOORS.forEach(f=>{const d=document.createElement('div');d.className='plate';d.id='pl-'+f;
d.style.width=PW+'px';d.style.height=PH+'px';d.style.left=(-PW/2)+'px';d.style.top=(-PH/2)+'px';
d.style.transform='translateZ('+Z[f]+'px)';d.innerHTML=PLATES[f];scene.appendChild(d);});
let dots=[], timer=null;
function segLen(a,b){return Math.hypot(b[0]-a[0],b[1]-a[1],(b[2]-a[2])*0.35);}
function draw(key,t){
  dots.forEach(e=>e.el.remove()); dots=[];
  document.querySelectorAll('.car').forEach(e=>e.remove());
  const arr=DATA[key]||[]; const groups={};
  arr.forEach((m,i)=>{
    const el=document.createElement('div');el.className='dot';el.style.background=m.color;scene.appendChild(el);
    const segs=[];let tot=0;
    for(let j=0;j<m.pts.length-1;j++){const L=segLen(m.pts[j],m.pts[j+1]);segs.push(L);tot+=L;}
    const e={el,m,segs,tot};dots.push(e);
    if(m.grp){(groups[m.grp]=groups[m.grp]||[]).push(e);}});
  info.textContent=arr.length+' dots · gold groups ride E1 together';
  Object.entries(groups).forEach(([g,es])=>{
    const box=document.createElement('div');box.className='car';box.dataset.grp=g;box.textContent='E1';
    scene.appendChild(box);});
  render(t);
}
function render(t){
  dots.forEach(e=>{
    let d=t*e.tot, j=0;
    while(j<e.segs.length-1&&d>e.segs[j]){d-=e.segs[j];j++;}
    const a=e.m.pts[j],b=e.m.pts[j+1],f=e.segs[j]||1,k=Math.min(d/f,1);
    const x=a[0]+(b[0]-a[0])*k-PW/2, y=a[1]+(b[1]-a[1])*k-PH/2, z=a[2]+(b[2]-a[2])*k;
    e.el.style.transform='translate3d('+x+'px,'+y+'px,'+z+'px)';});
  document.querySelectorAll('.car').forEach(box=>{
    const es=dots.filter(e=>e.m.grp===box.dataset.grp); if(!es.length){box.remove();return;}
    let x=0,y=0,z=0;es.forEach(e=>{const m=e.el.style.transform.match(/translate3d\\((.*)px,(.*)px,(.*)px\\)/);x+=+m[1];y+=+m[2];z+=+m[3];});
    x/=es.length;y/=es.length;z/=es.length;
    box.style.transform='translate3d('+(x-14)+'px,'+(y-14)+'px,'+z+'px)';box.style.width='28px';box.style.height='28px';});
}
document.getElementById('play').onclick=()=>{if(timer){clearInterval(timer);timer=null;return;}
  let t=0;const sp=+document.getElementById('spd').value;
  timer=setInterval(()=>{t+=0.01*sp;if(t>1){clearInterval(timer);timer=null;}render(Math.min(t,1));},50);};
const DAY={Mon:0,Tue:1,Wed:2,Thu:3,Fri:4};
const KEYS=Object.keys(DATA).sort((a,b)=>{const pa=a.match(/(...) P(\d+)/),pb=b.match(/(...) P(\d+)/);
  return (DAY[pa[1]]-DAY[pb[1]])||(+pa[2]-+pb[2]);});
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
let playingAll=false;
function fadeTo(key){
  scene.style.opacity=0;
  return sleep(260).then(()=>{sel.value=key;draw(key,0);scene.style.opacity=1;return sleep(260);});
}
document.getElementById('playall').onclick=async()=>{
  if(playingAll){playingAll=false;return;}
  playingAll=true;
  for(const key of KEYS){
    if(!playingAll) break;
    await fadeTo(key);
    const sp=+document.getElementById('spd').value;
    let t=0;
    await new Promise(done=>{const iv=setInterval(()=>{if(!playingAll){clearInterval(iv);done();return;}
      t+=0.008*sp;if(t>=1){clearInterval(iv);done();return;}render(Math.min(t,1));},40);});
    await sleep(350);
  }
  playingAll=false;};
sel.onchange=()=>draw(sel.value,1);draw(sel.value||KEYS[0],1);
</script></body></html>"""]
    Path(a.out).write_text("\n".join(h), encoding="utf-8")
    print(f"wrote {a.out} with {len(data)} breaks, "
          f"{sum(len(v) for v in data.values())} dots")


if __name__ == "__main__":
    main()
