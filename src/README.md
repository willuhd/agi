# `src/` — code source: configs, model, optimizers, simulation

Everything configurable lives in `config/*.toml` (never in code).
Python here is deliberately stdlib-only (tomllib/csv/random/dataclasses).

```
src/
├── config/
│   ├── periods.toml     # 7 periods, unequal minutes, gaps, Fri-off, parity rule
│   ├── buildings.toml   # ZX/XM zones, schoolmap paths, cross-building multiplier
│   ├── knobs.toml       # alpha/beta/eta/delta/theta, CVaR q, shock scenarios
│   ├── population.toml  # headcounts (PLACEHOLDERS), tracks, levels, archetypes
│   ├── courses.toml     # per-course loads WITH source+confidence provenance
│   └── selection.toml   # module choice rules + >5 floor + shared slots (hard)
├── data/                # run outputs: populations, demand, assignments (gitignored later)
├── sched/
│   ├── config_loader.py # load_all/validate/parity_weight/UNIT_EQUIV
│   ├── model/
│   │   └── formulation.py  # J(x) terms: mean, CVaR, group, slack, repair, churn
│   ├── optimizers/
│   │   └── baseline.py     # largest-first greedy; CP-SAT plugs in behind solve()
│   └── simulation/
│       └── population.py   # seeded teachers/students -> section demand
```

Smoke test (from repo root):

```
./.venv/bin/python -c "
import sys; sys.path.insert(0, 'src')
from sched import config_loader as C
cfg = C.load_all(); print('validate:', C.validate(cfg))
from sched.simulation import population as P
pop, sel = cfg['population'], cfg['selection']
teachers = P.generate_teachers(pop); students = P.generate_students(pop, sel)
print('teachers', len(teachers), 'students', len(students))
print('demand sections:', len(P.aggregate_demand(students, sel['floor']['min_students_to_run'])))
"
```

Data flow: `catalog_extract.md` (root) -> `courses.toml`/`selection.toml`
> `population.py` -> demand -> `optimizers/*` -> assignment -> J(x) scoring.
