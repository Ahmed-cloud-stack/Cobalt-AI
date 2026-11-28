#!/bin/sh
set -eu
source_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
install -m 644 "$source_dir/reference.py" /app/shutter.py
mkdir -p /app/output
python3 -I -S /app/shutter.py /app/sample.json /app/output/sample.json
