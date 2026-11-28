# Extend the shutter recorder’s likelihood calculator

## Summary

Add retrospective audits to a Gaussian likelihood calculator. An audit predicts an observed sensor reading from all the other observations, including later ones, and reports how the result changes with the model parameters. Measured shutter profiles can change slope inside an exposure. Curved profiles use a separate quadratic weight on each segment.

## What the agent sees

Harbor supplies the instructions. The image contains Python 3.12, NumPy 2.3.5, tmux 3.3a, a working forward calculator at `/app/shutter.py`, and a small input at `/app/sample.json`. The starter returns an empty audit list.

## What the agent must get right

Extend the calculator within 282 changed lines, support linear and quadratic shutter profiles, and generate `/app/output/sample.json`. Individual audits exclude their own observation. Panel audits exclude all the panel’s observations, even when the members end at different ticks. Each predicted variance includes measurement noise. Return each audited row’s conditional mean, variance, and log-parameter derivatives. Preserve the forward outputs. A 16,000-row input can audit every observed row and must finish within 20 seconds and 256 MiB.

## What makes it hard

Leaving out every reading separately repeats the work of integrating overlapping exposures. The event sweep must also integrate linear and quadratic weight changes at internal knots without losing accuracy over the supported range of event gaps. Retrospective information crosses changes in the state dimension whenever exposures open or close. In nearly noiseless cases, directly propagating an information matrix can lose precision when projecting onto a nearly unidentified direction. Panel audits also need the off-diagonal precision between panel members. Gradients pass through the retrospective calculation and each small panel solve.

## How the answers are produced

The reference computes conditional means and a process-noise factor for the endpoint and the first three exposure moments. It records the linear parts of the forward updates and transports a factor of the future information backward through those updates. It evaluates each audited reading’s marginal score and precision while passing its four parameter perturbations through the same operations.

The independent oracle constructs a joint Gaussian by integrating the covariance kernel at high precision. It delays the readings under audit until all retained readings are conditioned on and reads off their conditional marginals. The large cases use repeated exposure blocks and scalar calibration-bias calculations. A separate block oracle integrates out a common bias across 1,000 groups. Inputs and expected answers are generated inside the verifier.

## Checks run

The verifier checks the patch budget and sample, then compares numerical results for 88 held-out inputs. It exercises all-audited streams, overlapping curved exposures, tied observations, nearly noiseless readings, overlapping panels, and a common bias that persists across exposure groups.

The local Oracle run passed all 90 checks on rerun. NOP passed 47 and earned zero. Five blind repairs were graded on the same fixtures and limits. Each had at least one numerical failure and earned zero. These are local results.

## Running it

Use a Harbor provider that supports the `no-network` policy.

```sh
harbor run -p tasks/shutter-recorder-likelihood -e docker -a oracle
harbor run -p tasks/shutter-recorder-likelihood -e docker -a nop
```
