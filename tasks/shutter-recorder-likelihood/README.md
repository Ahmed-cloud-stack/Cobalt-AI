# Repair the shutter recorder’s likelihood calculator

## Summary

Repair a scientific sensor’s Gaussian likelihood calculator. It predicts point readings and weighted exposure averages from a continuous-time signal model with a shared calibration bias.

## What the agent sees

Harbor supplies the instructions. The Python 3.12 Bookworm image contains NumPy 2.3.5, tmux 3.3a, the deployed `/app/shutter.py`, and `/app/sample.json`. Dependency installation happens during the image build.

## What the agent must get right

Within the 145-line repair budget, preserve the CLI and generate `/app/output/sample.json`. Forecast every reading conditional on the observed prefix, process tied end ticks in input order, and return the likelihood and log-parameter derivatives. Requested forecast derivatives include both the mean and the log variance. Inputs can contain 16,000 rows and must finish within 20 seconds and 256 MiB.

## What makes it hard

The signal is partially observed through up to six simultaneous exposure accumulators. A nonuniform shutter introduces an additional time moment. Small decay arguments cause cancellation in the process covariance, and nearly noiseless readings can make direct covariance downdates lose precision. An indexed event sweep keeps the cost bounded on long inputs. Integer tick differences preserve timing near the ends of the clock range.

## How the answers are produced

The reference transports a square-root covariance through the exposure and conditioning steps. It propagates each log-parameter perturbation through the same algebra. The test oracle constructs a joint Gaussian directly. It integrates the covariance kernel using high-precision antiderivatives and differentiates with high-precision central differences. For long cases, isolated exposure blocks or a scalar bias posterior provide independent expected forecasts, likelihoods, and derivatives.

## Checks run

The verifier checks the line budget and public output, then evaluates small and large inputs numerically. The cases cover endpoint ties, null readings, short exposures, extended tick ranges, and overlapping ramps with nearly noiseless observations.

Oracle passed all 48 checks and earned reward 1. NOP passed 2 of 48 and earned reward 0. The five blind submissions scored 46, 43, 40, 42, and 45 out of 48. All five produced non-finite outputs on at least one valid input. Independent preflight checks confirmed that the held-out inputs meet the documented bounds.

The local image build used a temporary trusted CA mount, and the local Harbor controls used an external offline Docker override. The package records its runtime network policy in `task.toml`.

## Running it

Use a Harbor provider that supports the `no-network` policy.

```sh
harbor run -p tasks/shutter-recorder-likelihood -e docker -a oracle
harbor run -p tasks/shutter-recorder-likelihood -e docker -a nop
```
