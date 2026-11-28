#!/usr/bin/env bash
# Scaffold an empty Harbor package for the creator to complete.
set -euo pipefail
out=${1:?Usage: new-task.sh NEW_TASK_DIR NAMESPACE/SLUG}
name=${2:?Supply the Harbor task name}
if [[ ! "$name" =~ ^[a-z0-9][a-z0-9-]*/[a-z0-9][a-z0-9-]*$ ]]; then
    echo "Use a lowercase namespace and slug with letters, digits and hyphens" >&2
    exit 1
fi
mkdir "$out"
mkdir "$out"/{environment,solution,tests}
cat > "$out/task.toml" <<TOML
schema_version = "1.4"
artifacts = []

[task]
name = "$name"
version = "1.0.0"

[metadata]
difficulty = "hard"

[verifier]
timeout_sec = 900.0

[agent]
timeout_sec = 5400.0

[environment]
network_mode = "no-network"
allow_internet = false
build_timeout_sec = 900.0
cpus = 2
memory_mb = 4096
TOML
cat > "$out/environment/Dockerfile" <<'DOCKER'
FROM python:3.12-slim-bookworm@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337
RUN apt-get update \
 && apt-get install -y tmux=3.3a-3 \
 && command -v tmux \
 && tmux -V \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
DOCKER
printf '# %s\n' "$name" > "$out/instruction.md"
{
    printf '# %s\n' "$name"
    for section in 'Summary' 'What the agent sees' 'What the agent must get right' 'What makes it hard' 'How the answers are produced' 'Checks run' 'Running it'; do
        printf '\n## %s\n\n' "$section"
    done
} > "$out/README.md"
for file in solution/solve.sh tests/test.sh; do
    printf '#!/bin/sh\nprintf "Complete %s before grading.\\n" >&2\nexit 1\n' "$file" > "$out/$file"
    chmod +x "$out/$file"
done
