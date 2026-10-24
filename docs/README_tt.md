# Full-school timetable pipeline (`src/tt`)

Simulated school (G9, G10, G11-AP; 626 students, 54 teachers, 63 rooms) scheduled by a staged CP-SAT +
annealing pipeline, independently checked, stress-tested and compared with an emulator of the current system.
Proposal and rationale: `docs/improvement_proposal.md`. Prompt: `docs/Question.txt`.

```
python -m venv .venv && .venv/Scripts/pip install ortools numpy matplotlib pytest   # Windows
cd src
PYTHONPATH=. python -m tt.run 24 150          # main run -> output/main_*.json
PYTHONPATH=. python -m tt.sensitivity all     # sweeps   -> output/sens_*.json  (heavy: ~40 min, 12 cores)
PYTHONPATH=. python -m tt.poster2             # poster   -> output/poster_large.html
cd .. && python -m pytest tests/test_tt.py    # 20 tests incl. mutation suite
```
Committed results: `output/main_results.json`, `main_solution.json`, `sens_*.json`, `poster_large.{html,png,pdf}`.
