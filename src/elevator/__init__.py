"""Lift-queue simulation for teacher vertical movement.

Additive analysis only: reads a finished timetable plus the building spec and
reports elevator waits. Changes no solver, checker or metric code.

Demand model (documented assumptions, all swept from the CLI):
  * every teacher leg between consecutive same-day periods whose rooms are on
    different floors uses the lift with probability ``share`` (default 0.85);
    same-floor legs always walk;
  * arrivals are batched at the bell plus a seeded 0-45 s walk-to-landing
    stagger (the room->E1 walk has no matrix entry, so this is explicit);
  * end-of-day office returns are NOT modelled (off-grid, unbounded).

Supply model (E1 north-core pair, B2-4F landings per building_spec.yaml):
  * 2 cars, capacity ``capacity`` (default 8, assumed), pooled FIFO queue;
  * ride timing read live from data/building/building_model.json
    (door_s + per_floor_s; the spec wait_s is the static default this
    simulation replaces -- none of these numbers are measurements);
  * cars start at ``rest`` floors (default 1F+3F spread) and rest at their
    last drop afterwards.
"""
