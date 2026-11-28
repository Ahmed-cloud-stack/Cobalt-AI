# Repair the shutter recorder's likelihood calculator

Extend the likelihood calculator in `/app/shutter.py` for a sensor that records both instantaneous readings and averages over exposures. The deployed code handles forward forecasts for a point reading or a single linear ramp. Extend it to support measured shutter profiles, curved shutter weights, and retrospective audits of individual readings and calibration panels.

Run the CLI with `python3 -I -S /app/shutter.py INPUT OUTPUT`. Use Python 3.12, NumPy, and the standard library. The program runs offline with a 256 MiB address-space limit and a 20-second timeout per input. It may read INPUT and write OUTPUT. Keep the implementation in `/app/shutter.py`.

The deployment accepts at most **282 changed lines**. Count added and deleted lines in `difflib.unified_diff(old.splitlines(), new.splitlines(), n=0)`, excluding the two file headers. Run the repaired CLI on `/app/sample.json` and save the result at `/app/output/sample.json`. The verifier supplies its own temporary paths as CLI arguments.

## Model

The signal is a stationary, zero-mean Gaussian Ornstein–Uhlenbeck process X. Its covariance at ticks s and t is `signal_variance * exp(-rate * abs(s-t))`. Time is continuous between integer ticks. A second, independent zero-mean Gaussian variable B is constant over the entire input and has variance `bias_variance`.

For `start < end`, put `u = (t-start)/(end-start)`. Define A as the integral of `(1 + ramp*(2*u-1)) * X(t)` from start to end, divided by `end-start`. The optional `ramp` is between -1 and 1 and defaults to 0. The weight integrates to one after normalization. Positive ramps emphasize the late part of the exposure. For `start == end`, A is X at that tick. The reported reading is

```
Y = offset + gain * A + bias_loading * B + noise
```

The measurement noise is centered Gaussian with variance `noise_scale * sd**2`. Measurement noises are independent of the signal, B, and each other.

## Input and processing order

The input is a JSON object containing `parameters` and `rows`. Parameters are `rate` in [1e-18, 1000], `signal_variance` and `bias_variance` both in [1e-4, 10000], and `noise_scale` in [0.01, 100].

Each row has `start`, `end`, `gain`, `bias_loading`, `offset`, `sd`, and `value`. Ticks are integer JSON numbers between -10^18 and 10^18 inclusive, with start at or before end. Gain and bias loading are in [-4, 4] and can be zero. The offset and any observed value are finite in [-100, 100]. The standard deviation sd is in [1e-7, 100]. A null value asks for a forecast only. An optional boolean `sensitivity` defaults to false and requests forecast derivatives. An optional boolean `audit` also defaults to false. It may be true only on a row with a non-null value. The absolute residual of an observed row is at most 128 conditional standard deviations at the supplied parameters.

Rows may arrive in arbitrary order. Process them by increasing end tick, breaking ties by their original positions in the input. Predict each reading conditional on earlier non-null readings in that order. A null row receives a forecast but supplies no conditioning information. Overlapping exposures, including exact duplicates, are allowed. There are at most 16,000 rows and at most six nonzero-duration exposure intervals active at any time, counting each interval as half-open at its end.

## Output

Write one JSON object with keys `forecasts`, `log_likelihood`, `gradient`, and `audits`.

- `forecasts` contains one object per input row in its original order, with numeric `mean` and `variance`. The variance is for the reported reading Y, including its measurement noise. When `sensitivity` is true, add two objects, `mean_gradient` and `log_variance_gradient`, using the same four keys as `gradient`. These differentiate the conditional forecast mean and the natural logarithm of the conditional forecast variance with respect to the log parameters. The forecast and its derivatives describe the state before assimilating that row, including when the row has a null value. Omit those two objects when `sensitivity` is false.
- `log_likelihood` is the sum of the conditional Gaussian log densities for the non-null readings, using natural logarithms and including the Gaussian normalization constant.
- `gradient` contains numeric values under `log_rate`, `log_signal_variance`, `log_bias_variance`, and `log_noise_scale`. These are derivatives of the total log likelihood with respect to the natural log of the specified parameter, holding all other inputs fixed. For example, the log-rate derivative is the rate times the derivative with respect to rate.

Use finite numbers. The verifier accepts absolute error up to `2e-8 + 2e-8 * abs(expected)` for mean and likelihood, `1e-24 + 2e-7 * abs(expected)` for variance, and `2e-6 + 3e-6 * abs(expected)` for each gradient. Empty or all-null inputs have likelihood and gradients equal to zero.


## Retrospective audits

For every row with `audit: true`, calculate the conditional Gaussian distribution of that row's reported reading Y given **all the other non-null readings in the same input**, including later ones and readings that end at the same tick. Exclude its own value from the conditioning set, along with any other members of its panel as specified below. Its measurement noise is part of the quantity being predicted. Auditing a row leaves the forward forecasts, likelihood, and other audits as defined above. An audited row without a panel independently excludes exactly its own row.

Return `audits` as a list ordered by original input position. Each entry has `row` (the zero-based input row index), `mean`, `variance`, `mean_gradient`, and `log_variance_gradient`. The two gradient objects use the same keys and log-parameter convention as the forward sensitivities, even when the audited row has `sensitivity: false`. The output tolerances above apply. Return an empty list when there are no audited rows.

Any number of observed rows may request an audit, including every row in a 16,000-row input. The existing memory and per-input time limits include the audits.


## Measured shutter profiles

An exposure may specify `profile` instead of `ramp`. This is an array of two to five `[tick, weight]` pairs with strictly increasing integer ticks. The first tick is the row’s start, and the last is its end. The shutter weight is linearly interpolated between consecutive pairs. A weight is zero or a finite number in [1e-5, 4], and the profile has positive integral. For a profile, A is the integral of X(t) times the shutter weight divided by the integral of the shutter weight alone. A profile applies only to a nonzero-duration row. There are at most 10,000 interior profile knots summed across all rows.

An internal knot changes the weight at that tick and supplies no measurement. End tick ordering and conditioning use the same rules for profiles and ramps. The model parameters do not change the profile.

## Measurement panels

A calibration panel identifies readings recorded in the same calibration sequence. Rows can carry a nonempty string `panel` in addition to `audit: true`. Each panel identifier occurs on two to four observed rows, which may end at different ticks. Other panels, unrelated observations, and null forecasts may occur between members. At any point in processing order, at most four panels have some members already processed and others still to come. The standard deviation of each panel member is at least 1.

For the audit of a panel member, exclude the observed values of **every** member of that panel. Condition on all remaining observations, including members of other panels. Report only the same marginal mean, variance, and gradients for each member in the existing `audits` list. Panel membership has no effect on the forward forecasts or likelihood.

## Curved shutter weights

A nonzero-duration exposure can specify `curve` in place of both `profile` and `ramp`. A curve contains two to five marks at strictly increasing integer ticks, starting at `start` and ending at `end`. Every mark except the last has the form `[tick, weight, control]`. The last has the form `[tick, weight]`. Between consecutive marks at a and b, let u = (t-a)/(b-a), let w0 and w1 be their endpoint weights, and let c be the first mark's control value. The shutter weight at t is

```
(1-u)^2 * w0 + 2*u*(1-u)*c + u^2*w1
```

Weights and controls are zero or finite numbers in [1e-5, 4]. The full curve has positive integral. Normalize the entire exposure by that integral. Individual segments can have zero weight. Both linear profile and curve knots count toward the existing 10,000-interior-knot limit. A curve's internal marks change the shutter weight function and supply no measurement. Apply the existing ordering and conditioning rules to curved exposures.
