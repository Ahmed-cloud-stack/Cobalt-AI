#!/bin/sh
set -eu
mkdir -p /logs/verifier
printf '0\n' > /logs/verifier/reward.txt
chmod 700 /tests
if python3 /tests/verify.py; then
    printf '1\n' > /logs/verifier/reward.txt
fi
