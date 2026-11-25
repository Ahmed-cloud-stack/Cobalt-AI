#!/usr/bin/env bash
set -euo pipefail

task_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
python=${FREECAD_PYTHON:-/usr/bin/python3}
scratch=$(mktemp -d)
trap 'rm -rf -- "$scratch"' EXIT
mkdir "$scratch/nop"

"$python" "$task_dir/references/gold.py" "$scratch/oracle"
for trial in oracle nop; do
    "$python" "$task_dir/verifier/grade.py" \
        --submission "$scratch/$trial" --output "$scratch/$trial-report"
done

"$python" - "$scratch" <<'PY'
import json
import sys
from pathlib import Path

scratch = Path(sys.argv[1])
for name, expected in [("oracle", 1.0), ("nop", 0.0)]:
    reward = json.loads((scratch / f"{name}-report/reward.json").read_text())["reward"]
    if reward != expected:
        raise SystemExit(f"{name}: got {reward}, expected {expected}")
    print(f"{name}: {reward:.2f}")
PY
