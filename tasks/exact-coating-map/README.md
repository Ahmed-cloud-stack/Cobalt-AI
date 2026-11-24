# Repair the exact coating map renderer

## Summary

Repair a deployed Python renderer that computes visible regions, material interfaces, and boundary walks from overlapping paths and branching paint revisions.

## What the agent sees

Harbor supplies the task instructions. The Python 3.12 image includes tmux and three files in `/app`: `overlay.py`, `sample.json`, and `sample_history.json`. Harbor sets the task runtime to `no-network`.

## What the agent must get right

Repair `/app/overlay.py` within 100 changed lines and generate `/app/output/sample.json` and `/app/output/sample_history.json`. Preserve the CLI, use exact rational arithmetic, and honor the winding rules, paint precedence, branching history, and directed boundary probes. Each drawing has a 20-second timeout and a 256 MiB address-space cap.

## What makes it hard

Rational intersections, collinear overlaps, holes, and point contacts complicate boundary traversal and canonical ordering. Large workloads reach 16,000 segments, 6,000 revisions, and 24,000 probe pairs. Recomputing every drawing from scratch or scanning every segment for each winding query can exceed the time limit.

## How the answers are produced

The reference renderer splits edges into an exact rational arrangement and indexes winding queries. A depth-first traversal applies and rolls back edits. A segment tree over revision order and rollback union–find recover closed walks for the probes.

The verifier generates held-out inputs locally and compares complete, canonical JSON answers against SHA-256 fingerprints. The generator checks the reference using vertical-band integration, analytical fixtures, and direct traversal of canonical walks on small histories. The two public sample answers are stored separately as JSON.

## Checks run

The suite has 61 held-out drawings, two public output checks, and a patch-budget check. During calibration, Oracle passed 64 of 64 checks and earned reward 1. NOP passed 7 of 64 and earned reward 0. Five blind solvers scored 63, 62, 62, 61, and 62 of 64. A separate reference smoke test verified 6,000 revisions reporting all 136 interface pairs under the memory cap.

## Running it

From the checkout root, run the two controls in a Harbor environment with support for the `no-network` policy.

```sh
harbor run -p tasks/exact-coating-map -e docker -a oracle
harbor run -p tasks/exact-coating-map -e docker -a nop
```

Run `python3 tasks/exact-coating-map/tests/generate.py` to regenerate the fingerprints and sample answers.
