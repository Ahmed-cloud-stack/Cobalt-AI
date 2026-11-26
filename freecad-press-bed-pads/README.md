# Press-bed pads

Lay out 58 stock pads on a 30 × 24 cell press bed, then build a FreeCAD fit-check model with one solid per pad. The stock covers all 690 usable cells. See [the brief](agent/PROMPT.md) for the rotation convention, edge clearance, and blind pockets.

In a solver environment, give the agent the brief and mount `environment/data/task/` at `/app/data/task/`. Use a fresh writable submission directory for each run. Keep `references/` and the verifier outside that environment.

The grader accepts any complete placement whose solid model matches the positioned stock. It checks every pad by label and compares its geometry with the prescribed cell prisms and pocket.

## Local verification

Use Python with FreeCAD and Part available. On Debian:

```bash
PYTHONPATH=/usr/lib/freecad/lib ./tools/run_verify.sh
```

The script builds and grades the reference submission, then grades an empty directory. It requires oracle 1.00 and no-op 0.00. Set `FREECAD_PYTHON` if your FreeCAD installation uses a different interpreter.

To grade a submission directly:

```bash
PYTHONPATH=/usr/lib/freecad/lib /usr/bin/python3 verifier/grade.py \
  --submission /path/to/submission --output /path/to/report
```

The grader writes `reward.json` and `report.json`.

## Blind trial

Five agents received the brief and stock file in separate working directories.
They had approximately six minutes to submit both files. A service interruption
paused their agent turns, and the runs resumed against the original cutoff.
None found a complete tiling before the cutoff, so the final score was 0 of 5.
Several agents independently built all 58 stock solids for mock layouts.
