#!/bin/bash
set -eu
base=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
for attempt in "$@"; do
    source="$base/../shutter-curves-blind-$attempt"
    dest="$base/sealed/$attempt"
    mkdir "$dest" -p
    install -m 644 "$source/shutter.py" "$dest/shutter.py"
    install -m 644 "$source/output/sample.json" "$dest/sample.json"
done
sha256sum "$base"/sealed/*/{shutter.py,sample.json} > "$base/submissions.sha256"
