# Repair the exact coating map renderer

This Harbor task exercises exact planar geometry and versioned state. The candidate receives a deployed Python renderer, two public inputs, and a 100-changed-line repair budget. The renderer must recover planar boundaries from overlapping and self-crossing paths, honor paint and winding changes along a branching history, and answer directed probes about individual closed walks.

The Docker environment uses only Python 3.12 and its standard library. Docker Compose disables networking. The verifier runs each drawing in a separate Python process under a 256 MiB address-space cap and a 20-second timeout. It checks both generated sample outputs and enforces the patch budget with a zero-context unified diff.

## Run with Harbor

From the checkout root, run these as separate jobs.

```sh
harbor run -p tasks/exact-coating-map -e docker -a oracle
harbor run -p tasks/exact-coating-map -e docker -a nop
```

The reference solution splits edges into an exact rational arrangement. It indexes winding queries, including summaries for long rays through nested layers. A depth-first traversal applies and rolls back each edit. Along that traversal, the renderer records when each boundary successor link is active. An interval tree and rollback union–find recover closed walks and their probe measurements without retracing every walk for every revision.

## Verifier data

The held-out drawings cover rational crossings, retraced and overlapping edges, coincident anchors, holes, branch rollback, repeated-material layers, and directed probes at high-degree vertices. The largest workloads reach 16,000 input segments, 6,000 revisions, and 24,000 probe pairs. Independent checks use vertical-band integration, analytical nested and translated fixtures, and direct traversal of canonical walks on small histories.

To regenerate the expected outputs with those checks, run `python3 tasks/exact-coating-map/tests/generate.py`.

## Calibration

Harbor Oracle earned reward 1 with 64 of 64 checks and a 100-line patch. Harbor NOP earned reward 0 with 7 of 64 checks. Five blind solvers received separate copies of the public files. Their frozen submissions scored 63, 62, 62, 61, and 62 out of 64 in separate offline containers. The full-suite pass rate was 0 of 5.

An additional reference smoke test verified 6,000 revisions that each report all 136 interface pairs under the 256 MiB limit.
