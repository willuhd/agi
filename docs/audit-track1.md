# Track 1 Audit — Current Project State vs `problems/Track 1 Problem Statement.pdf`

Method: statement read with pypdf (2 pages, 7 evaluation bullets); repo walked and
smoke-tested live with `./.venv/bin/python` on 2026-10-24. No git repo present.
Blunt version: the math vocabulary exists, the system does not run.

## Verdicts per statement bullet

### 1. "What problems in the current timetable system did you identify?" — PARTIAL
- Evidence: `docs/knowledge-report.md` §2 (movement model from `apschedule.png`:
  teachers move every period, sample AP student changes rooms 4× Monday →
  `teacher_move_price = 0`, student moves priced); §1 unit-identity mess
  (periods / teaching periods / credit hr / observed slots never equated);
  catalog-vs-render conflicts (§5: Sociology M3, Drawing/3D/Micro M4-vs-M2).
- Gap: no standalone written problem diagnosis. Findings are scattered tacit
  notes, not a "current system works like X, fails at Y" section a judge can read.
- File: `docs/knowledge-report.md` (59 lines, internal notes, not submission prose).

### 2. "Which aspects did you choose to optimize? How?" — PARTIAL, mostly stubbed
| Aspect | State | Evidence |
|---|---|---|
| Student stickiness (cohort moves) | function exists, **never called** | `src/sched/model/formulation.py:62-69` (`cohort_moves`, `stickiness_cost`); `knobs.toml [stickiness]`; zero callers |
| Teacher preference loss L_i | function exists, **orphan** | `src/sched/simulation/staffing.py:57` (`preference_loss`); zero callers |
| Fairness CVaR / group terms | pure functions, **unwired** | `formulation.py:13-31`; `knobs.toml [fairness]`; no sweep runner |
| Robustness E[Δ], churn | defined, **dead** | `formulation.py:39-42`; `knobs.toml [robustness]` scenarios; no repair operator |
| Greedy scheduler | exists, **places 0/24** | `src/sched/optimizers/baseline.py solve()` — see §4 |
| Conflict-graph + CP-SAT | **DOES NOT EXIST** | `src/sched/optimizers/` holds only `baseline.py`; `src/model/`, `src/optimizers/`, `src/simulation/` are empty dirs |

### 3. "Who do these aspects affect, and how much?" — PARTIAL
- Teachers: quantified in code — 3 archetypes with shares (`population.toml`),
  `generate_teachers()` yields 93 staff (33 homeroom + 60 subject), L_i breakdown
  (load/travel/colocation). Students: 610 generated (250 G9 + 250 G10 + 110 G11).
- Gap: no "who benefits how much" statement anywhere — no per-stakeholder impact
  numbers, no why-it-matters argument. The 4-moves-Monday figure is flagged as
  "the demo number" in knowledge-report §7 but never computed by code.

### 4. "Compared with current timetable, how much improvement? How measured?" — MISSING
- The only "current timetable" artifact is `apschedule.png` (one G11-AP student's
  observed grid). Nothing in `src/` loads it, scores it, or diffs against it.
- Live test: `baseline.solve()` on real simulated demand → **placed 0, unplaced 24**,
  every section `reason: "no stated load"`. Root cause: `population.py`
  `aggregate_demand()` emits names (`Biology`, `G9 core`, `Arts`…) that match
  **zero** keys in `courses.toml` (which holds `AP Macroeconomics`, `OBS …` names).
  The pipeline is broken end-to-end; there is no J(x) number for old *or* new.
- `knobs.toml [report] pareto_points = 11` is config with no runner.

### 5. "How do you confirm every constraint is satisfied?" — PARTIAL, weak
- Real: `config_loader.validate()` (7 periods, knob presence, share sums — passes);
  `selection/evaluator.py` (module limits, exclusions, dynamic/conditional rules;
  solid, 176 lines, but reads `Courses.gpa` from a hardcoded **absolute path**
  `/Volumes/thinkplus/Code/CourseResources/Courses.gpa` — fragile, machine-specific).
- Weak/fake: `baseline.solve()` claims "hard feasibility" but (a) teacher is
  `auto-NNN` round-robin — eligibility `q(t,c)`/availability never checked;
  (b) room capacity `E(c) ≤ cap(r)` never checked (no cap data anywhere);
  (c) `tau_violations` is **hardcoded 0**, reachability never evaluated despite
  the docstring claiming it; (d) `contact_ok()` (`formulation.py:54`) never called.
- So: selection legality is checkable; schedule feasibility is asserted, not proven.

### 6. "Can your system cope when circumstances change?" — MISSING (stubbed)
- `knobs.toml [[robustness.scenario]]` (3 shocks, probs sum to 1),
  `expected_repair()`, `churn_l1()` all exist with zero callers.
- No repair operator, no LNS, no re-solve demo. README's "greedy (bound + repair
  primitive)" is aspirational — greedy has no repair path. `x_prev` (last-year grid)
  acknowledged missing in knowledge-report §7, so churn term has no data.

### 7. "Explain why better + presentation readiness" — MISSING
- No slides, no submission report, no results table/figure generator.
  `docs/` contains only `knowledge-report.md` (internal). `src/data/` (run outputs)
  is empty apart from README. Nothing a judge can look at exists.

## Scope creep (in repo, NOT asked for by the statement)
1. `electives.popularity` + `dirichlet_concentration` (`population.toml`) — **dead
   config**: `population.py` uses uniform `rng.choice`, never reads them.
2. `groups.load_band` + `weights.group` machinery — no grouping code consumes it.
3. `schoolmap` 3D renders/viewer (`output/renders/`, `viewer.html`) — venue for
   travel matrix is justified; the gallery is demo ornament.
4. XM-building/IBD independent-schedule modeling + IB-only-homeroom edge case
   (`teachers.toml [edge_cases]`) — deep work on the explicitly out-of-scope zone.
5. Strategy-proofness token/veto sketch, GPA-credit firewall docs — correct instinct,
   but prose volume exceeds what the statement rewards; none of it runs.
6. Absolute-path dependency on external `Courses.gpa` — not creep but fragility;
   breaks reproducibility on any other machine.

## Statement requirements with zero coverage
- An automatically produced timetable (pipeline outputs nothing placeable).
- Any measured old-vs-new comparison number.
- Any presentation artifact.
- Conflict-graph / CP-SAT optimizer (in progress elsewhere — not in tree at audit time).

## Prioritized gap list (do first → last)
1. **P0 — Fix the demand→courses name join.** `aggregate_demand()` output keys must
   resolve in `courses.toml`, or `solve()` needs a stated-load fallback. Until this
   works, every downstream claim (J(x), Pareto, "better") is fiction. (0/24 placed.)
2. **P0 — Real teacher assignment + real feasibility check.** Replace `auto-NNN`
   with eligibility/availability matching against `generate_teachers()`; compute
   `tau_violations` from the schoolmap matrix instead of hardcoding 0; enforce or
   explicitly slack capacity. Feasibility is a judging bullet — it must be computed.
3. **P1 — One comparison harness.** Score `apschedule.png` (hand-encode the one grid)
   with the same J-terms as the optimizer output; print old-vs-new table. This single
   script answers bullets 4 and 7's quantitative half.
4. **P1 — Write the problem diagnosis (one page).** Promote knowledge-report §1–§2
   into "current system: X; measured defects: Y (4 moves Monday, unit confusion,
   no feasibility proof)". Bullet 1 is the cheapest point on the board.
5. **P2 — Wire ONE objective path end-to-end** (mean-L + stickiness + slack) from
   demand → greedy → J(x) → validator, deleting or quarantining dead knobs
   (Dirichlet, load_band, repair scenarios) until CP-SAT lands. Dead config that
   never executes reads as hand-waving to judges.
6. **P3 — Repair demo** (one shock: 1-day teacher absence → re-solve diff + Δ cost).
   Bullet 6's minimal credible answer; needs `x_prev`-shaped output first.
7. **P3 — Presentation artifact.** Results table + one movement figure + Pareto stub
   (even 3 greedy points). Nothing exists; judges score what they see.
