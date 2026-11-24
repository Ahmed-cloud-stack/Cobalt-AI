#!/bin/sh
set -eu
solution_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
install -m 644 "$solution_dir/reference.py" /app/overlay.py
mkdir -p /app/output
python3 -I -S /app/overlay.py /app/sample.json /app/output/sample.json
python3 -I -S /app/overlay.py /app/sample_history.json /app/output/sample_history.json
