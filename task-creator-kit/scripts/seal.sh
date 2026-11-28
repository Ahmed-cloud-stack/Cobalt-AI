#!/usr/bin/env bash
set -euo pipefail
source=$(realpath "${1:?Usage: seal.sh APP_OVERLAY NEW_SEAL_DIR}")
out=$(realpath -m "${2:?Supply a new seal directory}")
test -d "$source"
if [[ "$out/" == "$source/"* ]]; then
    echo "Keep the seal outside the submission tree" >&2
    exit 1
fi
if find "$source" ! -type f ! -type d -print -quit | read -r ignored; then
    echo "Submission must contain regular files and directories" >&2
    exit 1
fi
mkdir "$out"
mkdir "$out/app"
cp -R "$source/." "$out/app/"
(
    cd "$out/app"
    find . -type f -print0 | LC_ALL=C sort -z | xargs -0 -r sha256sum
) > "$out/SHA256SUMS"
test -s "$out/SHA256SUMS"
chmod -R a-w "$out"
printf '%s\n' "$out/app"
