# Vacuum manifold insert

FreeCAD benchmark for routing twelve vacuum circuits through a three-layer insert and building a solid model from the routing schedule. The brief is in [agent/PROMPT.md](agent/PROMPT.md).

For an agent run, give the solver the brief and mount only `environment/data/task/` at `/app/data/task/`. Use a fresh writable `/app/` for each submission. Keep the reference and verifier outside the solver environment.

The verifier reads the original handout from the task package and checks the submitted routes and native FreeCAD solid. Any routing that meets the handout and matches the solid earns full credit.

## Local verification

Run with a Python interpreter that can import FreeCAD and Part. On a Debian FreeCAD installation:

```bash
PYTHONPATH=/usr/lib/freecad/lib ./tools/run_verify.sh
```

The script builds and grades the oracle, then grades an empty submission. It requires rewards of 1.00 and 0.00 respectively. Set `FREECAD_PYTHON` to override the default interpreter, `/usr/bin/python3`.

To grade an existing submission:

```bash
PYTHONPATH=/usr/lib/freecad/lib /usr/bin/python3 verifier/grade.py \
  --submission /path/to/submission --output /path/to/report
```

The grader writes `reward.json` and `report.json` in the output directory.

## Difficulty check

The final layout uses 343 of 351 available stations. V07 also has a fixed bend count.

Five agents received the same brief and handout in separate working directories. None finished both deliverables in five minutes, so every run received the same four-minute continuation. One of the five submissions passed at the cutoff.

| Run | At the cutoff |
| --- | --- |
| 1 | Valid routes and FreeCAD solid |
| 2 | Valid routes; CAD build unfinished |
| 3 | One shared station in the best candidate |
| 4 | Valid routes; CAD build unfinished |
| 5 | Valid routes; FreeCAD file saved after the cutoff |

The pass count measures the complete routing and CAD submission under this time budget. The oracle was held back until the runs ended.
