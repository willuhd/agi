# Tacit knowledge report — things established in discussion, not yet (or not fully) in code

## 1. Quantity identities (the_macro_lesson)
- `.gpa` weight (AP 6.0 / school 4.5) = GPA credit multiplier. Never time.
- Catalog "periods" / "teaching periods" / "credit hr" = three distinct stated
  units with no given conversion. Observed grid slots = a fourth quantity.
- AP Macro exists in three irreconcilable numbers: 4.5 catalog periods,
  3.5 observed slots, 6.0 GPA weight. Registrar call required.
- Rule: code records, never converts. `slot_map.toml` holds the provisional
  1:1 factors, every one flagged ASSUMPTION, so the optimizer can run while
  the question is open.

## 2. Movement model (observed, from apschedule.png)
- Teachers move every period (new student wave each slot, no owned room).
- Students should not move: the sample AP student changes rooms 4x Monday.
- Hence: teacher_move_price = 0, student cohort swaps priced. Stickiness
  attaches to cohort consecutive slots, never to teachers.

## 3. Buildings and zoning
- ZX (Zhong Xing) 1F-4F + B1/B2 fully modeled (schoolmap 1.0.0, 103 rooms).
  110=G11 homeroom office, 210=G10, 406=G9; 3F teaching + 3A/3B/3C offices.
- XM building has NO metric model: cross-legs priced 20x60s, both ASSUMPTIONs.
- IB = XMT-only, AP (+G9/G10) = ZXB-only. IBD runs an independent schedule;
  transfers school<->IBD unsupported (catalog policy).
- Edge case: IB-only G11 homeroom teacher stays pinned to 110; optimizer
  day-clusters their XMT lessons, never re-offices them.

## 4. Fixed weekly structure (user rulings, not inferred)
- 7 periods, unequal minutes (60/40/40/45/55/40/40), lunch after P4.
- Friday P6-P7 off. Even/Odd parity averaged over two weeks (0.5 weight).
- PE = Mon+Thu P5 (banding split between grade bands unconfirmed).
- IB Tue-P5 optional; AP/A-level Wed P6P7 biweekly + Thu P6P7 weekly.
- G9 M2/M3 choice rules, G10 combo+M2 rules, G11 module web — in selection.toml.

## 5. Source hierarchy (explicit)
1. User rulings > 2. catalog raw PDF (structure/rules/venues; loads only
   where stated) > 3. observed grid (one G11-AP student) > 4. .gpa (selection
   rules ONLY) > 5. synthetic simulation (clearly marked).
- Catalog-vs-render conflicts: Sociology in G11-M3 (.gpa yes, render no);
  Drawing/3D/Micro M4-vs-M2 inter-form conflict (.gpa sides with G10->11 form).
- G12 has no .gpa band (25 rows n/s); XMT-only so out of ZX scope.

## 6. Scale (user figures, Oct 2026)
- G9 250 (12 homerooms), G10 250 (11), G11+G12 215 combined, 10 homerooms
  across G11-12. Class size ~21 everywhere (cross-checks).
- G11/G12 split 110/105 and 5/5 homerooms are ASSUMPTIONS. Subject-teacher
  headcount (60) is ASSUMPTION. AP/IB split 55/45 provisional.

## 7. Design positions (pitch)
- Baseline assumption: every team builds a working selector. Novelty =
  teacher appetite pricing, student stickiness, repairability, year-over-year
  familiarity (churn vs x_prev — needs last-year grid, still missing).
- Venues bind before periods (lab practical mandates, no max caps, >5 floor).
- Student preferences modeled but acknowledged gameable; strategy-proofness
  via token/veto sketch, not implemented.
- Solver stack: greedy (bound + repair primitive) -> CP-SAT core ->
  large-neighbourhood repair. Calculus only in the outer sweep (response
  surface is piecewise-constant; finite differences, not derivatives).
- Room-stickiness figure: sample student moves 4x Monday — the demo number.
