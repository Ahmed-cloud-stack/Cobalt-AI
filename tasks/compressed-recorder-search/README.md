# Repair compressed recorder searches

## Summary

This task asks for a small repair to a Python telemetry tape searcher. A recorder can describe a tape much larger than physical storage by reusing catalog blocks. A search must count masked matches and recover their positions and a positional checksum from the compressed catalog.

## What the agent sees

Harbor supplies the task instructions. The Python 3.12 Bookworm image contains the starter `/app/tape_search.py`, `/app/sample.json`, an output directory, and tmux 3.3a. The task runs offline.

## What the agent must get right

Repair the CLI within 150 added or deleted lines, and use it to generate the requested sample output. Catalog concatenations, repeats, reversals, and slices must agree with their logical tapes. Preserve overlapping matches and rank order, apply stride filtering to absolute coordinates in the queried tape, and compute the full count and checksum. Each input must finish within 20 seconds and 128 MiB.

## What makes it hard

Logical lengths reach 10^30 symbols. Even when each query has a compact description, constructing a separate tree for every wide slice or scanning every candidate start can exhaust the resource limits. Reversal changes boundary windows and the placement of slice coordinates. A match spanning a join must count once, in between any matches wholly within the children. Translating a summary affects its start residues and both moments used for the checksum.

## How the answers are produced

The reference uses balanced concatenations, retains slice and reverse entries as views, and caches bounded boundary scans for masked matches. Each query subtracts two prefix summaries and selects by descending over counts. Independent test oracles use direct expansion for small tapes, binary search over flat match lists for the deep catalog, and arithmetic progressions for huge repeats and splices. A nested repeat case uses whole-cycle sums and handles starts that straddle the two different periods.

Inputs are generated from fixed seeds. The verifier compares canonical JSON fingerprints, keeping the submission compact.

## Checks run

The verifier checks the patch budget and public output, then runs 36 held-out inputs. They exercise overlap, 64-symbol seam matches, reversed slices, exact coordinates beyond 64 bits, a deep catalog, and dense histories of wide queries over shared blocks.

Oracle passed all 38 checks and earned reward 1. NOP passed 1 of 38 checks and earned reward 0. Five independent blind submissions scored 35, 37, 35, 37, and 34 out of 38. Three exceeded the memory cap. The other two timed out on dense stride-one searches, and the timeout on the fourth submission reproduced in an isolated rerun. The local Harbor provider required an external Docker networking override for the control runs.

## Running it

Use a Harbor environment that supports the `no-network` policy.

```sh
harbor run -p tasks/compressed-recorder-search -e docker -a oracle
harbor run -p tasks/compressed-recorder-search -e docker -a nop
```

Regenerate and cross-check the answer fingerprints with `python3 tasks/compressed-recorder-search/tests/generate.py`.
