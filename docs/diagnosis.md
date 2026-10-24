# Current-system diagnosis (judge-readable)

## What the current timetable gets wrong
1. **Students carry the movement burden.** One real G11-AP week: **21 room
   changes, 488 seconds of inter-room travel** per two-week mean (scored from
   the hand-encoded grid in `src/data/current_grid.toml` via the schoolmap
   walk matrix). Teachers move every period by design; students absorb it.
2. **Rooms are not sticky.** The same cohort re-seats nearly every period
   (Monday: 114→103→108→108→106→106→103). Nothing in the current system
   prices staying put.
3. **Contact loads are unverifiable.** Catalog states loads for ~20 entries;
   the rest is Duration-only; `.gpa` weights are grade-point credits, not
   time. No current process distinguishes these — our pipeline refuses to
   schedule load-silent courses instead of inventing numbers.
4. **Repairs are manual.** A room loss (e.g. construction noise) reshuffles
   by hand today; the pipeline re-solves the shocked subset with everything
   else frozen (large-neighbourhood repair — in build).

## What we optimize, and the measured gap
- Objective: distinct (cohort, day, room) triples → 0 moves/day ideal.
- Current grid: 21 changes. CP-SAT on one cohort: **OPTIMAL at 5 triples =
  one room per day, zero within-day moves.** Same solver, same constraints.
- Feasibility is certified first (conflict-graph clique bound), then solved;
  the certificate caught a real over-allocation (slack −3) before any solve.
