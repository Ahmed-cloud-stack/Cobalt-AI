#!/usr/bin/env bash
set -euo pipefail
task=$(realpath "${1:?Usage: controls.sh TASK_DIR JOBS_DIR}")
jobs=$(realpath -m "${2:?Supply a new jobs directory}")
mkdir "$jobs"
for agent in oracle nop; do
    harbor run -p "$task" -e docker -a "$agent" --jobs-dir "$jobs" --job-name "$agent"
done
python3 "$(dirname "$0")/gate.py" "$jobs/oracle" "$jobs/nop"
