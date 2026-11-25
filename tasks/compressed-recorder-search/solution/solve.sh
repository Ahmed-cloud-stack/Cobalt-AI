#!/bin/sh
set -eu
solution_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
install -m 644 "$solution_dir/reference.py" /app/tape_search.py
mkdir -p /app/output
python3 -I -S /app/tape_search.py /app/sample.json /app/output/sample.json
