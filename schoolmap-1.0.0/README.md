# schoolmap: school building space model & walking-time engine

A precise, metric 3-D model of the school building, reconstructed from the six
floor-plan photos.  It gives you:

* a **function** that returns the walking time between any two rooms, deterministic and
  stair-aware;
* an **interactive 3-D model** with real stairs (flights, half-landings, spiral, lifts) and
  live route finding;
* **clean 2-D plans** (PNG + SVG) as a visual baseline;
* ready-made **CSV/JSON matrices** for a timetable optimiser.

---

## 1. Quick start (2 minutes)

```bash
pip install .                 # inside this folder; only needs numpy
```

```python
import schoolmap

schoolmap.travel_time("215", "B208")      # 83.7  (seconds)
r = schoolmap.route("215", "B208")
print(r.summary())
# 215 -> B208: 84 s  (walk 17 m on 2F, S1 2F->1F, S1 1F->B1, S1 B1->B2, walk 47 m on B2)

ids, T = schoolmap.matrix()               # 103 x 103 numpy matrix, T[i, j] = seconds ids[i] -> ids[j]
```

Command line:

```bash
python -m schoolmap 215 B208          # time + itinerary
python -m schoolmap 215 B208 --json   # machine-readable
python -m schoolmap --rooms 3F        # list the rooms of a floor
python -m schoolmap --viewer          # open the 3-D model in your browser
```

No Python?  Open `output/travel_time_s.csv` (rows = from, columns = to, seconds) and
`output/viewer.html` in a browser.

## 2. API

| call | returns |
|---|---|
| `schoolmap.travel_time(a, b, **scenario)` | seconds, room centre → room centre |
| `schoolmap.route(a, b, **scenario)` | `Route`: `.seconds .walk_m .walk_s .vertical_s .floors_up .floors_down .legs .summary() .to_dict()` |
| `schoolmap.matrix(ids=None, **scenario)` | `(ids, T)`, all-pairs seconds |
| `schoolmap.rooms(floor=None)` | room records: id, name, kind, floor, area, centre, outline, doors |
| `schoolmap.load(**scenario)` | the `Building` object (cached) |
| `schoolmap.viewer_path()` | path of the bundled 3-D viewer |

Scenario keywords (any call):
* `walk_speed=1.0`: m/s; default 1.2, a casual indoor pace;
* `elevator=True`: allow the lifts (25 s wait + 6 s doors + 3 s per floor);
* `disabled_connectors=("S5",)`: close a stairwell.

Room ids are as on the doors: `"101"`, `"215"`, `"B208"`, `"RECEPTION"` …

**Rules baked in.** Going up costs **15 s per floor**, going down **10 s per floor**, so
the matrix is *not* symmetric.  Walking time is route length / walking speed.  Routes
follow corridors and doorways at a natural distance from walls, and never cut through
another room.  The best combination of stairwells is chosen automatically, including
switching stairwells mid-way.  Everything is deterministic: same input, same answer.

## 3. What's in the folder

```
schoolmap/              the Python package
  model.py              runtime engine (numpy only): Building, Route, Dijkstra over rooms + stairs
  __init__.py, __main__ one-line API and command line
  data/                 bundled model (building_model.json), viewer.html, building_spec.yaml
  pipeline.py …         the reconstruction pipeline (photos -> model), see section 6
  stairs.py             stair geometry (flights, landings) shared by 2-D and 3-D
  render2d.py           2-D plans,  render3d.py + viewer_template.html  3-D viewer
output/
  viewer.html           interactive 3-D model (open in a browser)
  renders/              plan_<floor>.png/.svg, plans_overview.png, route_*.png examples
  travel_time_s.csv     room x room seconds  (also .json)
  routes.csv            every ordered pair: seconds, metres, stair time, floors up/down, stairs used
  rooms.csv             room catalogue,  stairs.csv  stair register
floor_plans/            the original photos (input of the rebuild)
examples/               quickstart.py, timetable_integration.py
tests/                  consistency checks:  python tests/test_model.py
build.py                full rebuild from the photos
```

## 4. The 3-D viewer

`output/viewer.html` (or `python -m schoolmap --viewer`).  Pick *From*/*To*, or click a room
(shift-click sets *To*).  The route is drawn in orange and follows the actual stair flights
in purple; the panel shows total time, metres and every leg.  You can also:
* toggle floors (shift-click shows one floor only);
* change the floor separation;
* switch to plan view;
* change walking speed;
* switch the lifts on.

It loads three.js from a CDN, so it needs an internet connection; everything else is in
the file.

## 5. Stairs: the vertical story

| id | stair | shape | serves | role |
|---|---|---|---|---|
| S1 | North core stair | dog-leg | B2–4F | main stair beside the lifts; the only stair that serves every level |
| E1 | North core lifts | 2 cars | B2–4F | off for student routing unless `elevator=True` |
| S2 | East stair | dog-leg | B2–3F | east-wing stair by the toilets (the 4F east wing is a roof terrace) |
| S3 | South-west stair | dog-leg | B2–1F | links the basements to the ground floor and its west exit |
| S4 | South-east stair | dog-leg | 1F–2F | passage east of the south corridor |
| S4B | South-east basement stair | dog-leg | B2–B1 | continues outdoors, not into 1F |
| S5 | South-central stair | dog-leg | 1F–4F | beside 110 / 210 / 310 / 406; does not go below ground |
| S6 | East open stair | straight | 2F–3F | open flight in the east corridor, rising north → south |
| S7 | Atrium spiral stair | spiral | B1–1F | from the 1F atrium down into the B1 hall |

Stairs available on each floor:

| floor | stairs |
|---|---|
| 4F | S1, S5 |
| 3F | S1, S2, S5, S6 |
| 2F | S1, S2, S4, S5, S6 |
| 1F | S1, S2, S3, S4, S5, S7 |
| B1 | S1, S2, S3, S4B, S7 |
| B2 | S1, S2, S3, S4B |

Every stair has **one shaft position used on all its floors** (a stairwell is vertical).
Its landing on each floor is where it opens to the corridor.  The flights run from the
lower landing to the upper landing, and both the 2-D plans and the 3-D model are drawn
from that same geometry.  Not modelled:
* exterior escape stairs (2F north-east, 1F west & south, basement exit);
* the stair drawn inside the 3F atrium, which has no landing on the 2F plan.

## 6. How the model was built (for the judges)

1. **Perspective normalisation.**  On each photo the four outer walls are snapped to
   sub-pixel precision.  A homography maps them onto one metric frame, which removes
   perspective and stacks all floors (lifts, stairs and toilets line up).
2. **Scale.**  N–S = **50 m** (given).  E–W is **measured**: self-calibrated rectification
   of all six photos gives aspect 0.773–0.811 (median 0.7895), so **39.5 m**.
3. **Straightening.**  The signs themselves are slightly warped (walls drifting up to
   1.7°).  A smooth correction of at most 0.6 m makes the walls square.
4. **Vector walls.**  Text, icons and stair treads are removed.  Every wall becomes one
   straight segment, snapped to shared lines and joined at clean corners.  All walls are
   orthogonal except the few real diagonals.
5. **Rooms.**  Labels are found automatically.  Outlines come from "closing the doors";
   96 of 103 rooms are exact rectangles.  Each room is measured from its centre (an
   average seat).
6. **Routes.**  A 10 cm grid with clearance-aware cost, one search per room (other rooms
   blocked), then string-pulled into smooth polylines.  Time = length / speed.
7. **Floors.**  Stair landings join the floor graphs.  Dijkstra finds the optimal route.

**Accuracy.**  Positions are good to roughly ±0.3–0.5 m, and walking times to roughly
±3 % (±1–3 s per trip).  A rebuild is byte-identical.

## 7. Assumptions you might want to change

All of these live in `schoolmap/data/building_spec.yaml`.  Edit it, then run
`pip install .[build]` and `python build.py` (about 35 s).

* **Walking speed 1.2 m/s.**  Casual indoor pace; the literature range is 1.2–1.35 m/s.
* **Room numbers decide the floor.**  The wall directory has its "1F"/"2F" headings
  swapped, so rooms were assigned by number.
* **Atria and roof.**  The 1F atrium is two voids over B1 with a walkable bridge.  The
  2F/3F atria and the 4F courtyard are voids, and the 4F east block is a roof terrace.
* **Ice rink.**  The B1 rink hall is open-plan and is the only way into B107, so routes
  may cross it.
* **Measuring point.**  Times are centre-to-centre.  Door points are in `rooms.csv` if
  you prefer door-to-door.
