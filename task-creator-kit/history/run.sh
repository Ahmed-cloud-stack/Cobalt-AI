#!/bin/bash
set -euo pipefail
base=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
stage="$base/frozen-task"
tag=$(cat "$base/image")
for mode in "$@"; do
  extras=()
  if [[ $mode == oracle ]]; then
    extras=(-v "$stage/solution:/solution:ro")
  elif [[ $mode != nop ]]; then
    extras=(-v "$base/sealed/$mode:/submission:ro")
  fi
  docker run --rm --network none --cpus 2 --memory 4096m \
    -v "$stage/tests:/fixture:ro" "${extras[@]}" \
    "$tag" sh -ec '
      cp -r /fixture /tests
      if [ "$1" = oracle ]; then
        /solution/solve.sh
      elif [ "$1" != nop ]; then
        install -m 644 /submission/shutter.py /app/shutter.py
        install -m 644 /submission/sample.json /app/output/sample.json
      fi
      /tests/test.sh
      printf "reward="; cat /logs/verifier/reward.txt
    ' sh "$mode" > "$base/$mode.log" 2>&1
  printf '%s\n' "$mode"
  if [[ $mode == nop ]]; then
    tail -2 "$base/$mode.log"
  else
    rg -v ': PASS' "$base/$mode.log"
  fi
done
