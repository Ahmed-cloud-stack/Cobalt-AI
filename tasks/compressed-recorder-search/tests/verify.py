"""Grade the CLI and its public output against the fixed input suite."""
from difflib import unified_diff
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import time

from cases import held_out
from fingerprint import fingerprint

HERE = Path(__file__).resolve().parent
BUDGET = 150


def constrain():
    ceiling = 128 * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (ceiling, ceiling))
    if os.getuid() == 0:
        os.setgroups([])
        os.setgid(65534)
        os.setuid(65534)


def attempt(program, data, expected):
    with tempfile.TemporaryDirectory(prefix="recorder-") as scratch:
        folder = Path(scratch)
        folder.chmod(0o755)
        source = folder / "input.json"
        source.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
        source.chmod(0o444)
        output = folder / "output.json"
        output.touch()
        output.chmod(0o666)
        try:
            outcome = subprocess.run(
                [sys.executable, "-I", "-S", str(program), str(source), str(output)],
                cwd=folder, preexec_fn=constrain, timeout=20, capture_output=True, text=True,
            )
        except subprocess.TimeoutExpired:
            return "20-second limit exceeded"
        if outcome.returncode:
            detail = outcome.stderr.strip().splitlines()[-1:] or ["no stderr"]
            return f"exit {outcome.returncode}: {detail[0][:240]}"
        try:
            answer = json.loads(output.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError) as exc:
            return f"missing or invalid JSON: {exc}"
        if fingerprint(answer) != expected:
            return "incorrect count, moment, selection, or output structure"
    return None


def main():
    program = Path("/app/tape_search.py")
    before = (HERE / "original.py.txt").read_text(encoding="utf-8").splitlines()
    after = program.read_text(encoding="utf-8").splitlines()
    patch = list(unified_diff(before, after, n=0))[2:]
    lines = sum(row.startswith(("+", "-")) for row in patch)
    expected = json.loads((HERE / "expected_sha256.json").read_text(encoding="utf-8"))
    sample = Path("/app/output/sample.json")
    try:
        actual = fingerprint(json.loads(sample.read_text(encoding="utf-8")))
        artifact = actual == expected.pop("public-sample")
    except (OSError, ValueError, UnicodeError):
        del expected["public-sample"]
        artifact = False
    outcomes = [
        ("patch budget", None if lines <= BUDGET else f"{lines}/{BUDGET} changed lines"),
        ("sample artifact", None if artifact else "missing or incorrect sample output"),
    ]
    for label, issue in outcomes:
        print(f"{label}: {issue or 'PASS'}", flush=True)
    cases = dict(held_out())
    assert cases.keys() == expected.keys()
    for label, data in cases.items():
        start = time.monotonic()
        issue = attempt(program, data, expected[label])
        outcomes.append((label, issue))
        print(f"{label}: {issue or 'PASS'} ({time.monotonic() - start:.2f}s)", flush=True)
    passed = sum(detail is None for _, detail in outcomes)
    print(f"{passed}/{len(outcomes)} checks passed", flush=True)
    return int(passed != len(outcomes))


if __name__ == "__main__":
    sys.exit(main())
