"""Check forecasts, score, sample, and resource use."""
from difflib import unified_diff
import json
import math
import os
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import time

from cases import bias_answers, bias_clock, contrast, independent_batches, small_cases, ramps, profiled_batches, scaled_batches, audit_batches, audit_cases, audit_bias_answers, mixed_audit_batches, measured_profiles, measured_batches, panel_cases, panel_batches, curved_weights, curved_batches
from dense import dense
from block import mixed_answers

BUDGET = 282
APPLICATION = Path("/app/shutter.py")
HERE = Path(__file__).resolve().parent


def constrain():
    limit = 256 * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
    if os.getuid() == 0:
        os.setgroups([])
        os.setgid(65534)
        os.setuid(65534)


def comparison(answer, expected):
    def equal(x, y, absolute, relative):
        return type(x) in (int, float) and math.isfinite(x) and abs(x-y) <= absolute + relative * abs(y)

    if not isinstance(answer, dict) or answer.keys() != expected.keys():
        return "incorrect answer structure"
    if not equal(answer["log_likelihood"], expected["log_likelihood"], 2e-8, 2e-8):
        return "incorrect log likelihood"
    gradient = answer["gradient"]
    if not isinstance(gradient, dict) or gradient.keys() != expected["gradient"].keys():
        return "incorrect gradient structure"
    for key, value in expected["gradient"].items():
        if not equal(gradient[key], value, 2e-6, 3e-6):
            return f"incorrect {key} derivative"
    for label in ("forecasts", "audits"):
        rows = answer[label]
        if not isinstance(rows, list) or len(rows) != len(expected[label]):
            return f"incorrect {label} count"
        for i, (own, ref) in enumerate(zip(rows, expected[label])):
            if not isinstance(own, dict) or own.keys() != ref.keys():
                return f"incorrect {label} structure at item {i}"
            if label == "audits" and (type(own["row"]) is not int or own["row"] != ref["row"]):
                return f"incorrect audit index at item {i}"
            if not equal(own["mean"], ref["mean"], 2e-8, 2e-8):
                return f"incorrect {label} mean at item {i}"
            if not equal(own["variance"], ref["variance"], 1e-24, 2e-7):
                return f"incorrect {label} variance at item {i}"
            for key in ("mean_gradient", "log_variance_gradient"):
                if key not in ref:
                    continue
                data = own[key]
                if not isinstance(data, dict) or data.keys() != ref[key].keys():
                    return f"incorrect {label} {key} structure at item {i}"
                for name, value in ref[key].items():
                    if not equal(data[name], value, 2e-6, 3e-6):
                        return f"incorrect {label} {key}/{name} derivative at item {i}"
    return None


def check(document, expected):
    with tempfile.TemporaryDirectory(prefix="shutter-") as folder:
        root = Path(folder)
        root.chmod(0o755)
        original, output = root / "input.json", root / "output.json"
        original.write_text(json.dumps(document, separators=(",", ":")), encoding="utf-8")
        original.chmod(0o444)
        output.touch()
        output.chmod(0o666)
        try:
            process = subprocess.run(
                [sys.executable, "-I", "-S", str(APPLICATION), str(original), str(output)],
                cwd=root, preexec_fn=constrain, timeout=20, capture_output=True, text=True,
            )
        except subprocess.TimeoutExpired:
            return "20-second limit exceeded"
        if process.returncode:
            detail = process.stderr.strip().splitlines()[-1:] or ["no stderr"]
            return f"exit {process.returncode}: {detail[0][:200]}"
        try:
            answer = json.loads(output.read_text(encoding="utf-8"))
            return comparison(answer, expected)
        except (OSError, ValueError, OverflowError) as exc:
            return f"missing or invalid JSON: {exc}"


def suite():
    for name, document in small_cases():
        yield name, document, dense(document)
    document = contrast()
    yield "small-contrast", document, dense(document)

    for name, document in ramps():
        yield name, document, dense(document)

    for name, document in measured_profiles():
        yield name, document, dense(document)

    for name, document in curved_weights():
        yield name, document, dense(document)

    for name, document in panel_cases():
        yield name, document, dense(document)

    for name, document in audit_cases():
        yield name, document, dense(document)

    for label, factory in (("six-overlapping-16000", independent_batches),
                           ("six-profiled-16000", profiled_batches),
                           ("short-segments-16000", scaled_batches),
                           ("audited-overlap-16000", audit_batches),
                           ("panel-audits-16000", panel_batches)):
        document, templates, groups = factory()
        answers = [dense(template) for template in templates]
        expected = {
            "forecasts": [answers[group % len(templates)]["forecasts"][slot]
                          for slot in range(len(templates[0]["rows"]))
                          for group in range(groups - 1, -1, -1)],
            "log_likelihood": math.fsum(answers[group % len(templates)]["log_likelihood"]
                                       for group in range(groups)),
            "gradient": {name: math.fsum(answers[group % len(templates)]["gradient"][name]
                                         for group in range(groups))
                         for name in answers[0]["gradient"]},
        }
        audits = [dict(a, row=a["row"]*groups + groups - group - 1)
                  for group in range(groups) for a in answers[group % len(templates)]["audits"]]
        expected["audits"] = sorted(audits, key=lambda a: a["row"])
        yield label, document, expected
    document = bias_clock()
    expected = bias_answers(document)
    expected["audits"] = []
    yield "bias-clock-16000", document, expected

    document = bias_clock()
    for row in document["rows"]:
        row["audit"] = row["value"] is not None
    yield "bias-audits-16000", document, audit_bias_answers(document)


    document, templates, groups = mixed_audit_batches()
    yield "shared-bias-audits-16000", document, mixed_answers(templates, groups, document)

    document, templates, groups = measured_batches()
    yield "measured-profile-audits-16000", document, mixed_answers(templates, groups, document)

    document, templates, groups = curved_batches()
    yield "curved-shared-bias-audits-16000", document, mixed_answers(templates, groups, document)


def main():
    original = (HERE / "original.py.txt").read_text(encoding="utf-8").splitlines()
    replacement = APPLICATION.read_text(encoding="utf-8").splitlines()
    patch = list(unified_diff(original, replacement, n=0))[2:]
    lines = sum(row.startswith(("+", "-")) for row in patch)
    sample = json.loads(Path("/app/sample.json").read_text(encoding="utf-8"))
    try:
        answer = json.loads(Path("/app/output/sample.json").read_text(encoding="utf-8"))
        sample_issue = comparison(answer, dense(sample))
    except (OSError, ValueError, OverflowError):
        sample_issue = "missing or invalid sample output"
    checks = [("patch budget", None if lines <= BUDGET else f"{lines}/{BUDGET} lines"),
              ("sample output", sample_issue)]
    for name, issue in checks:
        print(f"{name}: {issue or 'PASS'}", flush=True)
    for name, document, expected in suite():
        started = time.monotonic()
        issue = check(document, expected)
        checks.append((name, issue))
        print(f"{name}: {issue or 'PASS'} ({time.monotonic() - started:.2f}s)", flush=True)
    passed = sum(issue is None for _, issue in checks)
    print(f"{passed}/{len(checks)} checks passed", flush=True)
    return int(passed != len(checks))


if __name__ == "__main__":
    sys.exit(main())
