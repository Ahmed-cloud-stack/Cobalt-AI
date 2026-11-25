# Vacuum manifold insert

FreeCAD benchmark for routing eighteen vacuum circuits through a three-layer insert and building a solid model from the routing schedule. The brief is in [agent/PROMPT.md](agent/PROMPT.md).

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

At least two of five agents passed the first layout, which had twelve circuits and no bend targets. The layout in this package has eighteen circuits with fixed bend counts and uses 557 of the 564 available stations. In a fresh round, five agents each had six minutes and separate working directories. They received the brief and handout before the oracle was written to disk. None delivered a valid submission. Four agents reported individually valid routes for every circuit, but their routes still shared stations.
