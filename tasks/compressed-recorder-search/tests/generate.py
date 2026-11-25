"""Regenerate fingerprints and compare the reference with independent answers."""
import json
from pathlib import Path
import sys

from answers import expanded, flat_stress, periodic, repeated_mixture, shared_head_answers, replay_answers
from cases import held_out
from fingerprint import fingerprint

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "solution"))
from reference import render


def validate(document):
    catalog, queries, patterns = (document[key] for key in ("catalog", "queries", "patterns"))
    assert len(catalog) <= 16000 and len(queries) <= 12000
    assert sum(len(row["data"]) for row in catalog if row["op"] == "literal") <= 128000
    assert len({(row["pattern"], row["stride"]) for row in queries}) <= 16
    assert all(1 <= len(p) <= 64 and all(0 < mask < 65536 for mask in p) for p in patterns)
    lengths, views = [], []
    repeats = slice_operands = 0
    for row in catalog:
        op = row["op"]
        if op == "literal":
            length = len(row["data"])
            assert length <= 512
        elif op == "concat":
            a, b = row["left"], row["right"]
            slice_operands += views[a] + views[b]
            length = lengths[a] + lengths[b]
        else:
            source = row["source"]
            length = lengths[source]
            if op == "repeat":
                slice_operands += views[source]
                times = int(row["times"])
                repeats += times.bit_length()
                length *= times
            elif op == "slice":
                lo, hi = int(row["start"]), int(row["stop"])
                assert 0 <= lo <= hi <= length
                length = hi - lo
        assert 0 <= length <= 10**30
        lengths.append(length)
        views.append(op == "slice" or op == "reverse" and views[row["source"]])
    assert repeats <= 12000 and slice_operands <= 256
    for row in queries:
        assert 0 <= int(row["start"]) <= int(row["stop"]) <= lengths[row["node"]]
        assert len(row["ranks"]) <= 4 and all(1 <= int(rank) <= 10**30 for rank in row["ranks"])


def main():
    expected = {}
    sample = json.loads((ROOT / "environment/sample.json").read_text(encoding="utf-8"))
    for name, document in [("public-sample", sample), *held_out()]:
        validate(document)
        if name in {"wide-coordinates", "dense-virtual-tape", "dense-stride-one", "many-ranged-views"}:
            independent = periodic(document)
        elif name == "broad-replay":
            independent = replay_answers(document)
        elif name in {"shared-giant-head", "doubled-giant-head"}:
            independent = shared_head_answers(document)
        elif name == "mixed-periods":
            independent = repeated_mixture(document)
        elif name == "deep-catalog":
            independent = flat_stress(document)
        else:
            independent = expanded(document)
        answer = render(document)
        assert answer == independent, name
        expected[name] = fingerprint(independent)
        print(f"{name}: matched independent answers", flush=True)
    out = ROOT / "tests/expected_sha256.json"
    out.write_text(json.dumps(expected, sort_keys=True, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
