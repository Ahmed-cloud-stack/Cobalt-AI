#!/usr/bin/env bash
set -euo pipefail
task=$(realpath "${1:?Usage: public-snapshot.sh TASK_DIR NEW_OUTPUT_DIR}")
out=$(realpath -m "${2:?Supply a new output directory}")
if [[ "$out/" == "$task/"* ]]; then
    echo "Keep the public snapshot outside the private task tree" >&2
    exit 1
fi
mkdir "$out"
cp "$task/instruction.md" "$out/"
cp -a "$task/environment" "$out/"
echo "$out"
