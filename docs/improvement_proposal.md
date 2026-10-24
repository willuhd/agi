# Improvement proposal + sensitivity / test / visualization plan

Scope: `willuhd/agi` (cloned to `agi/`), judged against `Question.txt` (the 7 evaluation bullets).
Evidence below was read from code and re-run on 2026-10-24; items marked **[verified]** were executed, not inferred.
`docs/audit-track1.md` is stale: CP-SAT, repair and the scorers now exist.

---

## 1. What the algorithms actually do today

| Piece | What it does | Limit |
|---|---|---|
| `selection/evaluator.py` | Validates a student's module choices against `Courses.gpa` rules | Hardcoded `/Volumes/thinkplus/...` path; file not in repo, so it cannot run here |
| `simulation/population.py` | Seeded teachers (103) / students (925) -> sections | See findings F1, F2 |
| `graph/conflicts.py` | Conflict graph, greedy clique (lower bound) vs greedy colouring (upper bound) | Greedy clique is a weak bound; nothing consumes it in the solve |
| `optimizers/baseline.py` | Largest-first greedy, round-robin teachers | A strawman. It ignores eligibility, capacity and reachability (`tau_violations = 0` is hardcoded) |
| `optimizers/cpsat.py` | One cohort set; teacher given; minimises distinct (cohort, day, room) triples | Pairwise reified constraints are O(M^2); only a single cohort has ever been solved |
| `optimizers/repair.py` | Frozen re-solve for "teacher quits" and "student AP->IB" | The three shocks declared in `knobs.toml` (absence, room closure, surge) are not the two implemented |
| `analysis/score_*.py` | Scores the grid / solution on J(x) terms | Group terms, repair and churn are zero; the old-vs-new run is n = 1 student |

## 2. Findings that change the plan

- **F1 [verified] Only ~20% of the timetable exists.** `aggregate_demand` yields 74 sections. G9/G10 core courses are `courses = []`, so English, Math, Chinese, Physics and the like are never scheduled. 18 "pooled" electives (e.g. G10 Chemistry, 169 students; AP CSA, 17) are listed as unknown and never become sections.
- **F2 Cohort = homeroom is a hidden feasibility error.** Electives and AP sections mix homerooms, so a conflict-free homeroom grid can still double-book real students. Sections are also tiny (AP Chem about 8 students against a stated class size of about 21).
- **F3 Contact hours are counted in slots, not minutes. No code reads `minutes`.** Periods are 60/40/40/45/55/40/40. Swapping Math from P1 to P2 loses 20 minutes a week, which breaks the one invariant the problem names ("hours spent on math should not change").
- **F4 The observed baseline is one student.** "21 room changes" has no variance, so it cannot be generalised, and a judge will ask.
- **F5 The load table and the owner ruling conflict.** The ruling says `.gpa` weights are not time, but 165 of 230 catalog rows have only a `.gpa` weight. **Calibration check [verified]:** the observed student totals exactly 33.0 slots, which equals the grid capacity (35 - 2 Friday-off). `.gpa` credits for the same courses are Calc 6 / Phys 6 / Eng 6 / Chinese 3 against observed 5 / 5 / 6 / 2.5. So credits track slots with a ratio of roughly 0.83-1.0. That supports a *calibrated proxy with an uncertainty band*, not a silent conversion.
- **F6 Broken data paths.** `rooms_csv`/`travel_time_s.csv` point at `schoolmap-1.0.0/output/`, which is not in the repo (it exists in `building_model/output/` here). The `.gpa` path is machine-specific. `score_grid`, `travel` and the CP-SAT demo cannot run as shipped.
- **F7 Inconsistent price of teacher movement.** `knobs.toml` sets `teacher_move_price = 0`, but `teachers.toml` prices teacher walking at 0.02/s.
- **F8 Over-blocking.** Fixed blocks (PE, IB optional, AP optional) are blocked for every cohort, which wastes capacity for cohorts that do not have them.

## 3. Improvements, by aspect

Priority: P0 = needed for the claim to be true, P1 = clearly strengthens judging, P2 = depth.
"Question.txt" = the evaluation bullet it serves.

### A. Problem definition and data
| # | Improvement | Why / who benefits | Bullet |
|---|---|---|---|
| A1 P0 | **Load ladder**: run everything under 3 load regimes: (a) stated loads only, (b) `.gpa` credits x calibrated factor with a band, (c) registrar-confirmed (plug-in). Report which conclusions survive all three | Resolves F5 without inventing numbers; conclusions become robust to the open question | 1, 4 |
| A2 P0 | Make the full school schedulable: G9/G10 cores from the ladder, pooled electives turned into sections | F1 | 2, 4 |
| A3 P0 | **Student-level sectioning layer** (students -> sections of about 21, min 6, planning cap as a knob). Conflicts are weighted by shared students, not homeroom | F2: real feasibility | 5 |
| A4 P0 | Fix paths: ship the matrix, read `GPA_FILE` from env, add a data-doctor script | F6 | 5 |
| A5 P1 | CSV import schema so registrar data replaces simulation | Real-world adoptability | 6 |

### B. Model and constraints
| # | Improvement | Why / who benefits | Bullet |
|---|---|---|---|
| B1 P0 | **Minute-based contact invariant**: weekly minutes per course are checked against the baseline within a tolerance, with long periods (P1, P5) used for lab doubles | F3. Students and teachers; the "hours unchanged" rule | 5 |
| B2 P0 | Add the missing hard constraints: teacher eligibility and availability, room kind and area-based capacity (`area_m2` is in `rooms.csv`), reachability tau along every student and teacher sequence | The checker can then certify, not assert | 5 |
| B3 P1 | **Double periods** for labs (observed grid: Physics Mon3-4, Chem Wed3-4) | Real constraint present in the data | 5 |
| B4 P1 | Scope fixed blocks per cohort (F8) | Frees capacity | 2 |
| B5 P1 | Linked/shared sections across grades (Business Mgmt G11+G12, Chinese levels) | Catalog rule E31, currently prose | 5 |
| B6 P1 | **Student-side objectives** (all fairness is on teachers today): idle gaps, daily-minute balance, subject spread across the week, hard subjects in the morning, PE not right after lunch | Students are 900+ of the people affected | 2, 3 |
| B7 P1 | Richer teacher loss: first-to-last span, free-period placement, same-prep adjacency, minutes-based load; resolve F7 with one consistent walking price | Teachers | 2, 3 |
| B8 P1 | Joint teacher-section assignment (balance load, max preps) instead of dept round-robin | Fairness among teachers | 2 |
| B9 P2 | Cross-building: model IBD/XMT as external busy slots for shared staff | Realistic, and the 20 x 60 s assumption becomes a swept parameter | 5, 6 |

### C. Algorithms
| # | Improvement | Why | Bullet |
|---|---|---|---|
| C1 P0 | **Three staged baselines** so "better" is honest: observed grid, naive-feasible greedy, strong heuristic (greedy + SA/hill-climb). Plus a CP-SAT bound for an optimality gap | A strawman win is not a win | 4 |
| C2 P0 | **Decomposition**: sectioning -> home-room assignment -> slots -> rooms -> LNS polish. Home rooms mean students stay and teachers move, as the knowledge report observes | CP-SAT is O(M^2) as written; this is what makes full-school scale solvable | 2, 6 |
| C3 P0 | Replace pairwise reified constraints with `NoOverlap` / `AddAllDifferent` on Boolean `x[m,s,r]`; greedy solution as hint; fixed seed and worker count for reproducibility | Speed and determinism | 5 |
| C4 P1 | Student cost as **person-seconds** (size x tau(r_i, r_i+1), plus stairs and "late-risk" legs where tau > gap), not a room-count | The metric now means something to a student | 2, 3 |
| C5 P1 | Epsilon-constraint **Pareto front** (the doc's plan): efficiency, fairness, robustness. Weights justified in one currency (person-minutes per week) | Judges ask why those weights | 2, 4 |
| C6 P1 | Infeasibility **explanations** (unsat core in plain language), exact clique / LP / per-period room-capacity and teacher-load bounds in place of greedy clique | "Why" is part of the evaluation | 5 |

### D. Robustness and change
| # | Improvement | Why | Bullet |
|---|---|---|---|
| D1 P0 | Implement the 3 declared shocks (absence 1 day, room closure 1 week, surge +5%) plus the two existing repairs; compute E[Delta] and churn for real | Bullet 6 is currently only config | 6 |
| D2 P1 | **Robust-by-design** score: fraction of single-point failures repairable within k moves (Monte Carlo), and spare-slack reservation as a knob | Cope with change before it happens | 6 |
| D3 P2 | Rolling re-optimisation mid-term with a stability weight theta | Churn has no x_prev; simulate last year by perturbation | 6 |

### E. Measurement and verification
| # | Improvement | Why | Bullet |
|---|---|---|---|
| E1 P0 | **Independent checker** that re-validates every hard constraint from the output grid alone, plus a mutation test (inject a violation, checker must flag it) | The answer to "how do you confirm" | 5 |
| E2 P0 | **Current-system emulator** calibrated to the observed grid (rooms change about 4x on Monday, teacher-first placement), run for n = 200 timetables with CIs. The observed grid stays as the anchor point | Fixes F4 honestly: stated as an emulator, not as the real school | 4 |
| E3 P1 | Equity metrics: Jain / Gini across students and teachers; per-stakeholder impact table in person-minutes | "Who is affected, how much" | 3 |
| E4 P1 | Reproducibility: config hash in every output, one `make all` | Presentation / audit | 4 |
| E5 P2 | Delete or quarantine dead config (Dirichlet electives, `load_band` groups) until used | Dead knobs read as hand-waving | 2 |

## 4. Simulated data design

All seeded; every distribution parameter lives in TOML and is swept in section 5.
1. **School**: G9 250 / G10 250 / G11 AP 126 / G11 IB 84 (XMT ledger) / G12 215 (XMT ledger); 103 teachers; the real 63 classroom/lab/arts/sport rooms (areas and floors from `rooms.csv`).
2. **Choices**: students sample modules through `selection.toml` rules; the evaluator is the gate (zero illegal selections generated, asserted in tests).
3. **Teachers**: eligibility sets with Zipf-like breadth, availability masks (part-timers), 3 archetypes with preferences.
4. **Loads**: regimes (a), (b), (c) from A1. Regime (b) factor is fitted on the 10 observed courses and carries its fit residual as a band.
5. **Current-system emulator** (E2): teacher-first sequential placement with a room-after-the-fact rule, tuned so the observed statistics are inside the emulator's 90% interval.
6. **Shock generator**: absences, closures, surges, drawn from the declared scenario probabilities.

## 5. Sensitivity analysis

Method: one-at-a-time sweeps (tornado) on every knob, then a Sobol / Morris screening on the top 8 with a combined-factor run. Each point = 5 seeds, mean and 95% CI. Output metric set M = {student person-seconds, teacher L mean and CVaR, equity index, slack, repair cost, checker violations (must stay 0)}.

| Group | Parameters | Question it answers |
|---|---|---|
| Objective | alpha, beta, beta', eta, delta, theta (x0.25..x4); CVaR q 0.7..0.95; CVaR vs range | Is the ranking of solutions stable to the weights we chose? |
| Data uncertainty | load regime and factor band; headcounts +-10%; min-to-run 4..8; planning cap 20..28; AP/IB split 45..65% | Do conclusions survive the unconfirmed assumptions? |
| Physical | cross-building multiplier 1..40; walk speed 0.8..1.6 m/s; stair cost; period gaps 5..15 min | Does the building model drive the gain? |
| Structure | rooms available -5..-30%; teacher count -10%; fixed-block variants | Where does it break? Breakpoint = capacity cliff |
| Solver | time limit 10..300 s; seed; workers; LNS neighbourhood size | How much is solver luck vs. model? |
| Shocks | probability and severity of each scenario; repair neighbourhood size | Price of robustness; repair cost vs. churn |

Deliverables: tornado chart, 2-D weight heatmaps, Pareto front with the knee marked, breakpoint curve (rooms vs. slack), rank-stability table.

## 6. Full test plan

1. **Unit**: each formulation term against hand-computed values; parity weights; minute accounting; tau lookups.
2. **Property-based** (hypothesis-style, seeded): any generated selection passes the evaluator; any solver output passes the independent checker; the contact-minute invariant holds under every random swap.
3. **Mutation tests**: 20 injected violations (double-booked room/teacher/cohort, missing hour, tau breach, ineligible teacher, over capacity, off-slot use). The checker must flag all of them.
4. **Integration**: full pipeline end to end on 3 seeds; reproducibility (same seed + config hash = same output).
5. **Metamorphic**: remove a room -> objective never improves; double the time limit -> never worse; relabel rooms -> same objective.
6. **Repair**: each shock yields a feasible grid; frozen entries unchanged; churn <= bound.
7. **Scale**: runtime vs. problem size (1 cohort -> grade -> school); gap-to-bound reported.
8. **Regression**: golden-file metrics for the observed grid (21 changes, 488 s).

## 7. Visualization (HTML dashboard + static PNG/PDF)

1. Before/after timetable grids for a sample student and teacher, with room-change arcs.
2. Building floor-plan overlay (from `schoolmap` renders) showing student paths: observed vs. optimised, per-floor heat of traffic.
3. Old-vs-new distributions (emulator n = 200 violin/box + observed anchor) per metric.
4. Per-stakeholder impact table and equity curves.
5. Pareto front with knee, and weight-sweep heatmaps.
6. Tornado + Sobol bars + breakpoint curve.
7. Constraint certificate panel: every hard rule, count checked, count violated (0), and mutation-test catch rate.
8. Shock replay: pick a shock, see the diff of moved meetings and the cost.

Static versions are matplotlib PNG and a combined PDF for slides.

## 8. Phasing

| Phase | Output | Gate |
|---|---|---|
| 0 | Data doctor, paths fixed, ortools env, regression of 21 / 488 s | Existing pipeline runs on a clean machine |
| 1 | Full-school demand, sectioning, load ladder, checker + mutation tests | Zero violations on every seed |
| 2 | Decomposed solver, baselines, person-seconds objective | Better than all 3 baselines with a stated gap |
| 3 | Shocks + repair + robust score | E[Delta] computed |
| 4 | Sensitivity + Pareto | Rank stability reported |
| 5 | Dashboard + PDF | Reproducible `make all` |
