#!/bin/sh
set -eu
/bin/mkdir -p /logs/verifier
printf '0\n' > /logs/verifier/reward.txt
/bin/chmod 700 /tests
if /usr/local/bin/python3 -I -S -c 'import runpy, sys; sys.path.insert(0, "/tests"); runpy.run_path("/tests/verify.py", run_name="__main__")'; then
    printf '1\n' > /logs/verifier/reward.txt
fi
