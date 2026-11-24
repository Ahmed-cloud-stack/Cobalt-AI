"""Run the submitted CLI against the same held-out suite for every trial."""
import gzip
from difflib import unified_diff
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import time

from cases import examples, stress, histories, history_stress, rail_with_probes, fan_stress, probe_histories, dense_edits, narrow_tiles, patch_cases, long_ray_cases, palette_nesting


HERE = Path(__file__).resolve().parent


def constrain():
    limit = 256 * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
    if os.getuid() == 0:
        os.setgroups([])
        os.setgid(65534)
        os.setuid(65534)


def equal_json(actual, expected):
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(
            equal_json(actual[key], value) for key, value in expected.items()
        )
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            equal_json(a, b) for a, b in zip(actual, expected)
        )
    return actual == expected


def check(program, name, drawing, expected):
    with tempfile.TemporaryDirectory(prefix="overlay-") as work:
        root = Path(work)
        root.chmod(0o755)
        source = root / "input.json"
        output = root / "output.json"
        source.write_text(json.dumps(drawing, separators=(",", ":")), encoding="utf-8")
        source.chmod(0o444)
        output.touch(mode=0o666)
        output.chmod(0o666)
        try:
            ran = subprocess.run(
                [sys.executable, "-I", "-S", str(program), str(source), str(output)],
                cwd=root, preexec_fn=constrain, timeout=20, capture_output=True, text=True,
            )
        except subprocess.TimeoutExpired:
            return "20-second limit exceeded"
        if ran.returncode:
            detail = ran.stderr.strip().splitlines()[-1:] or ["no stderr"]
            return f"exit {ran.returncode}: {detail[0][:240]}"
        try:
            actual = json.loads(output.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return f"missing or invalid JSON: {exc}"
        if not equal_json(actual, expected):
            return "incorrect coverage, rings, interfaces, or output structure"
    return None


def main():
    program = Path(sys.argv[1] if len(sys.argv) == 2 else "/app/overlay.py").resolve()
    with gzip.open(HERE / "expected.json.gz", "rt", encoding="utf-8") as handle:
        golden = json.load(handle)
    cases = list(examples()) + [("sparse-16000", stress())] + list(histories())
    cases.extend([("branching-6000", history_stress()), ("connected-6000", rail_with_probes()),
                  ("high-valence", fan_stress())])
    cases.extend(probe_histories())
    cases.append(('dense-rule-edits', dense_edits()))
    cases.append(('narrow-measurements', narrow_tiles()[0]))
    cases.extend(patch_cases())
    cases.extend(long_ray_cases())
    cases.append(('nested-palette', palette_nesting()))
    assert set(golden) == {name for name, _ in cases}
    before = (HERE / "original.py.txt").read_text(encoding="utf-8").splitlines()
    after = program.read_text(encoding="utf-8").splitlines()
    changes = sum(line[:1] in ("+", "-")
                  for line in list(unified_diff(before, after, n=0))[2:])
    limit_ok = changes <= 100
    print(f"patch budget: {'PASS' if limit_ok else 'FAIL'} ({changes}/100 lines)", flush=True)
    failures = int(not limit_ok)
    samples = json.loads((HERE / "samples_expected.json").read_text(encoding="utf-8"))
    for sample, expected_sample in samples.items():
        try:
            produced = json.loads((program.parent / "output" / sample).read_text(encoding="utf-8"))
            found = equal_json(produced, expected_sample)
        except (OSError, ValueError):
            found = False
        print(f"sample artifact {sample}: {'PASS' if found else 'FAIL'}", flush=True)
        failures += int(not found)
    for name, data in cases:
        started = time.monotonic()
        failure = check(program, name, data, golden[name])
        print(f"{name}: {failure or 'PASS'} ({time.monotonic() - started:.2f}s)", flush=True)
        failures += bool(failure)
    print(f"{len(cases) + 3 - failures}/{len(cases) + 3} checks passed", flush=True)
    return int(bool(failures))


if __name__ == "__main__":
    sys.exit(main())
