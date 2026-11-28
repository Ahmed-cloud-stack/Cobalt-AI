# Repair the shutter recorder's likelihood calculator

Repair `/app/shutter.py` for a sensor that records both instantaneous readings and averages over exposures. It must compute the conditional prediction for each reading, the log likelihood of the recorded values, and four derivatives used to fit the sensor model.

Run the CLI with `python3 -I -S /app/shutter.py INPUT OUTPUT`. Use Python 3.12, NumPy, and the standard library. The program runs offline with a 256 MiB address-space limit and a 20-second timeout per input. It may read INPUT and write OUTPUT. Keep the implementation in `/app/shutter.py`.

The deployment accepts at most **145 changed lines**. Count added and deleted lines in `difflib.unified_diff(old.splitlines(), new.splitlines(), n=0)`, excluding the two file headers. Run the repaired CLI on `/app/sample.json` and save the result at `/app/output/sample.json`. The verifier supplies its own temporary paths as CLI arguments.

## Model

The signal is a stationary, zero-mean Gaussian Ornstein–Uhlenbeck process X. Its covariance at ticks s and t is `signal_variance * exp(-rate * abs(s-t))`. Time is continuous between integer ticks. A second, independent zero-mean Gaussian variable B is constant over the entire input and has variance `bias_variance`.

For `start < end`, put `u = (t-start)/(end-start)`. Define A as the integral of `(1 + ramp*(2*u-1)) * X(t)` from start to end, divided by `end-start`. The optional `ramp` is between -1 and 1 and defaults to 0. The weight integrates to one after normalization. Positive ramps emphasize the late part of the exposure. For `start == end`, A is X at that tick. The reported reading is

```
Y = offset + gain * A + bias_loading * B + noise
```

The measurement noise is centered Gaussian with variance `noise_scale * sd**2`. Measurement noises are independent of the signal, B, and each other.

## Input and processing order

The input is a JSON object containing `parameters` and `rows`. Parameters are `rate` in [1e-18, 1000], `signal_variance` and `bias_variance` both in [1e-4, 10000], and `noise_scale` in [0.01, 100].

Each row has `start`, `end`, `gain`, `bias_loading`, `offset`, `sd`, and `value`. Ticks are integer JSON numbers between -10^18 and 10^18 inclusive, with start at or before end. Gain and bias loading are in [-4, 4] and can be zero. The offset and any observed value are finite in [-100, 100]. The standard deviation sd is in [1e-7, 100]. A null value asks for a forecast only. An optional boolean `sensitivity` defaults to false and requests forecast derivatives. The absolute residual of an observed row is at most 128 conditional standard deviations at the supplied parameters.

Rows may arrive in arbitrary order. Process them by increasing end tick, breaking ties by their original positions in the input. Predict each reading conditional on earlier non-null readings in that order. A null row receives a forecast but supplies no conditioning information. Overlapping exposures, including exact duplicates, are allowed. There are at most 16,000 rows and at most six nonzero-duration exposure intervals active at any time, counting each interval as half-open at its end.

## Output

Write one JSON object with keys `forecasts`, `log_likelihood`, and `gradient`.

- `forecasts` contains one object per input row in its original order, with numeric `mean` and `variance`. The variance is for the reported reading Y, including its measurement noise. When `sensitivity` is true, add two objects, `mean_gradient` and `log_variance_gradient`, using the same four keys as `gradient`. These differentiate the conditional forecast mean and the natural logarithm of the conditional forecast variance with respect to the log parameters. The forecast and its derivatives describe the state before assimilating that row, including when the row has a null value. Omit those two objects when `sensitivity` is false.
- `log_likelihood` is the sum of the conditional Gaussian log densities for the non-null readings, using natural logarithms and including the Gaussian normalization constant.
- `gradient` contains numeric values under `log_rate`, `log_signal_variance`, `log_bias_variance`, and `log_noise_scale`. These are derivatives of the total log likelihood with respect to the natural log of the specified parameter, holding all other inputs fixed. For example, the log-rate derivative is the rate times the derivative with respect to rate.

Use finite numbers. The verifier accepts absolute error up to `2e-8 + 2e-8 * abs(expected)` for mean and likelihood, `1e-24 + 2e-7 * abs(expected)` for variance, and `2e-6 + 3e-6 * abs(expected)` for each gradient. Empty or all-null inputs have likelihood and gradients equal to zero.
