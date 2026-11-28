# Shutter Recorder Likelihood v1.0.6 local results

Commit [1b24b43](https://github.com/Ahmed-cloud-stack/Cobalt-AI/commit/1b24b43e5a1e929a4ed51c0aefe98a7d3d76f7ca). Full pass means all 90 checks pass.

| Trial | Checks passed | Reward |
|---|---:|---:|
| Harbor Oracle | 90 | 1 |
| Harbor NOP | 47 | 0 |
| Blind 1 | 89 | 0 |
| Blind 2 | 3 | 0 |
| Blind 3 | 89 | 0 |
| Blind 4 | 86 | 0 |
| Blind 5 | 87 | 0 |

Every blind submission had a numerical failure. One also timed out under concurrent load. The initial Oracle timed out on one case under concurrent load; both the rerun and the subsequent Harbor run passed. A separate 42,000-event check completed in 13.17 seconds under the 256 MiB limit after stale processes were cleared. These results are local.
