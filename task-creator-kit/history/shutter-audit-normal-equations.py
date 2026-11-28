#!/usr/bin/env python3
"""Likelihood and one-step forecasts for the shutter recorder."""
from collections import defaultdict
import json
import math
import sys
import sysconfig

sys.path.append(sysconfig.get_path("purelib"))

import numpy as np


PARAMETERS = ("rate", "signal_variance", "bias_variance", "noise_scale")
STEP = 1e-24
LANES = len(PARAMETERS) + 1
LOG_2PI = math.log(2.0 * math.pi)
NODES, WEIGHTS = np.polynomial.legendre.leggauss(12)
NODES, WEIGHTS = (1 + NODES[:, None]) / 2, WEIGHTS[:, None] / 2


def models(config):
    settings = np.tile([config[name] for name in PARAMETERS], (LANES, 1)).astype(complex)
    # Each imaginary perturbation is in a separate log-parameter direction.
    for col in range(len(PARAMETERS)):
        settings[col + 1, col] *= 1.0 + STEP * 1j
    return settings.T


def schedules(rows):
    opening, closing = defaultdict(list), defaultdict(list)
    for i, row in enumerate(rows):
        start, end = row["start"], row["end"]
        if start < end:
            opening[start].append(i)
        closing[end].append(i)
    for tick in sorted(opening.keys() | closing.keys()):
        yield tick, closing.get(tick, ()), opening.get(tick, ())


def coefficients(z):
    """Transition of X and the time average on a segment of length z/rate."""
    decay = np.exp(-z)
    change = -np.expm1(-z)
    average = change / z
    xx = -np.expm1(-2 * z)
    xa = change * average
    # The numerator vanishes to third order. Expand the quotient near zero.
    aa = np.empty_like(z)
    small = z.real < 0.04
    x = z[small]
    polynomial = np.zeros_like(x)
    for degree in range(12, 2, -1):
        term = (-1)**degree * (4 - 2**degree) / math.factorial(degree)
        polynomial = polynomial * x + term
    aa[small] = x * polynomial
    x, change_large = z[~small], change[~small]
    aa[~small] = (2 * (x - change_large) - change_large * change_large) / (x * x)
    return decay, average, xx, xa, aa


def ramp_coefficients(z, decay, average, xa, aa):
    """Extra mean coefficient and covariances of the first time moment."""
    first, x_first, avg_first, first_first = (np.empty_like(z) for _ in range(4))
    small = z.real < 0.5
    r = z[~small]
    first[~small] = first_large = (average[~small] - decay[~small]) / r
    multiplier = 1 + 1 / r
    slope_integral = (0.5 - first_large) / r
    x_first[~small] = multiplier * xa[~small] - 2 * first_large
    avg_first[~small] = multiplier * aa[~small] - 2 * slope_integral
    first_first[~small] = multiplier**2 * aa[~small] - 4 * multiplier * slope_integral + 2 / (3 * r)

    if np.any(small):
        r = z[small]
        width = -r * NODES
        weighted_noise = np.zeros_like(width)
        moment = np.zeros_like(r)
        for k in range(13, -1, -1):
            weighted_noise = weighted_noise * width + (
                NODES / math.factorial(k + 1) - NODES * NODES / math.factorial(k + 2)
            )
            moment = moment * (-r) + 1 / (math.factorial(k) * (k + 2))
        first[small] = moment
        x_noise = np.exp(width)
        mean_noise = -np.expm1(width) / r
        mass = 2 * r * WEIGHTS * weighted_noise
        x_first[small] = np.sum(mass * x_noise, axis=0)
        avg_first[small] = np.sum(mass * mean_noise, axis=0)
        first_first[small] = np.sum(mass * weighted_noise, axis=0)
    return first, x_first, avg_first, first_first


def turn(matrix, row, left, right):
    """Orthogonally eliminate one entry using algebraic transpose."""
    x, y = matrix[:, row, left], matrix[:, row, right]
    if np.all(y == 0):
        return
    radius = np.sqrt(x * x + y * y)
    nonzero = radius != 0
    safe = np.where(nonzero, radius, 1)
    c = np.where(nonzero, x / safe, 1)[:, None]
    s = (y / safe)[:, None]
    a, b = matrix[:, row:, left].copy(), matrix[:, row:, right].copy()
    matrix[:, row:, left] = c * a + s * b
    matrix[:, row:, right] = c * b - s * a
    matrix[:, row, right] = 0


class Filter:
    def __init__(self, config, auditing):
        self.history = [] if auditing else None
        self.rate, self.signal, self.bias, self.noise = models(config)
        self.time = None
        self.active = []
        self.mean = np.zeros((LANES, 2), dtype=complex)
        self.factor = np.zeros((LANES, 2, 2), dtype=complex)
        self.factor[:, 0, 0] = np.sqrt(self.signal)
        self.factor[:, 1, 1] = np.sqrt(self.bias)
        self.log_likelihood = np.zeros(LANES, dtype=complex)
        self.error = np.zeros(LANES, dtype=complex)
        self.transitions = {}

    def open(self, index, row):
        if self.history is not None:
            self.history.append(("open",))
        self.active.append((index, row["start"], row["end"] - row["start"], row.get("ramp", 0)))
        self.mean = np.pad(self.mean, ((0, 0), (0, 1)))
        self.factor = np.pad(self.factor, ((0, 0), (0, 1), (0, 1)))

    def close(self, state):
        if self.history is not None:
            self.history.append(("close", state))
        self.active.pop(state - 2)
        self.mean = np.delete(self.mean, state, axis=1)
        factor = np.delete(self.factor, state, axis=1)
        for row in range(state, factor.shape[1]):
            turn(factor, row, row, row + 1)
        self.factor = factor[:, :, :-1].copy()

    def advance(self, tick):
        previous, self.time = self.time, tick
        if previous is None or tick == previous:
            return
        duration = tick - previous
        ramps = any(active[3] for active in self.active)
        key = (duration, ramps)
        if key not in self.transitions:
            z = self.rate * duration
            decay, average, xx, xa, aa = coefficients(z)
            nx = np.sqrt(self.signal * xx)
            na = self.signal * xa / nx
            independent = np.sqrt(self.signal * aa - na * na)
            ramp = None
            if ramps:
                first, xf, af, ff = ramp_coefficients(z, decay, average, xa, aa)
                kx = self.signal * xf / nx
                ka = (self.signal * af - kx * na) / independent
                kf = np.sqrt(self.signal * ff - kx * kx - ka * ka)
                ramp = (first, kx, ka, kf)
            if len(self.transitions) == 4096:
                self.transitions.clear()
            self.transitions[key] = (decay, average, nx, na, independent, ramp)
        decay, average, nx, na, independent, ramp = self.transitions[key]

        m = self.mean
        f = self.factor
        dim = m.shape[1]
        has_exposure = bool(self.active)
        added = 3 if ramps else 2 if has_exposure else 1
        extended = np.zeros((LANES, dim, dim + added), dtype=f.dtype)
        extended[:, :, :dim] = f
        extended[:, 0, :dim] *= decay[:, None]
        extended[:, 0, dim] = nx
        if has_exposure:
            fractions = np.array([duration / span for _, _, span, _ in self.active])
            alpha = fractions
            if ramps:
                slopes = np.array([rate for _, _, _, rate in self.active])
                elapsed = np.array([(previous - start) / span for _, start, span, _ in self.active])
                remaining = np.array([(start + span - previous) / span for _, start, span, _ in self.active])
                alpha = fractions * np.where(slopes >= 0, (1 - slopes) + 2 * slopes * elapsed,
                                             (1 + slopes) - 2 * slopes * remaining)
                beta = 2 * slopes * fractions**2
            weight = average[:, None] * alpha
            extended[:, 2:, dim] = na[:, None] * alpha
            extended[:, 2:, dim + 1] = independent[:, None] * alpha
            if ramps:
                first, kx, ka, kf = ramp
                weight += first[:, None] * beta
                extended[:, 2:, dim] += kx[:, None] * beta
                extended[:, 2:, dim + 1] += ka[:, None] * beta
                extended[:, 2:, dim + 2] = kf[:, None] * beta
            m[:, 2:] += weight * m[:, :1]
            extended[:, 2:, :dim] += weight[:, :, None] * f[:, :1]
        if self.history is not None:
            column = np.zeros(m.shape, dtype=complex)
            column[:, 0] = decay
            if has_exposure:
                column[:, 2:] = weight
            self.history.append(("step", column))
        m[:, 0] *= decay
        for row in range(dim):
            for extra in range(dim, dim + added):
                turn(extended, row, row, extra)
        self.factor = extended[:, :, :dim].copy()

    def observe(self, index, row):
        state = 0
        for slot, (active, _, _, _) in enumerate(self.active, 2):
            if index == active:
                state = slot
                break
        gain, loading = row["gain"], row["bias_loading"]
        predicted = gain * self.mean[:, state] + loading * self.mean[:, 1] + row["offset"]
        f = self.factor
        innovations = gain * f[:, state] + loading * f[:, 1]
        noise = np.sqrt(self.noise) * row["sd"]
        variance = noise * noise + np.sum(innovations * innovations, axis=1)
        value = row["value"]
        if value is not None:
            residual = value - predicted
            contribution = -0.5 * (LOG_2PI + np.log(variance) + residual * residual / variance)
            # Compensated accumulation for the score and its four derivatives.
            increment = contribution - self.error
            total = self.log_likelihood + increment
            self.error = (total - self.log_likelihood) - increment
            self.log_likelihood = total

            # Start with the measurement row, followed by the state.
            # Eliminating its coefficients from right to left retains a lower factor.
            dim = f.shape[1]
            precision = np.clongdouble if row["sd"] < 1e-4 else f.dtype
            joint = np.zeros((LANES, dim + 1, dim + 1), dtype=precision)
            joint[:, 0, 0] = noise
            joint[:, 0, 1:] = innovations
            joint[:, 1:, 1:] = f
            for col in range(dim, 0, -1):
                turn(joint, 0, 0, col)
            self.mean = self.mean + joint[:, 1:, 0] * (residual / joint[:, 0, 0])[:, None]
            if self.history is not None:
                projection = np.zeros(dim)
                projection[state], projection[1] = gain, loading
                kalman_gain = joint[:, 1:, 0] / joint[:, :1, 0]
                target = (index, value) if row.get("audit") else None
                self.history.append(("reading", projection, kalman_gain, residual, variance, target))
            self.factor = joint[:, 1:, 1:].copy()
        if state:
            self.close(state)
        result = {"mean": float(predicted[0].real), "variance": float(variance[0].real)}
        if row.get("sensitivity"):
            result["mean_gradient"] = {f"log_{key}": float(predicted[i + 1].imag / STEP)
                                       for i, key in enumerate(PARAMETERS)}
            result["log_variance_gradient"] = {f"log_{key}": float(variance[i + 1].imag / STEP / variance[0].real)
                                               for i, key in enumerate(PARAMETERS)}
        return result


    def audits(self):
        mean_score = np.zeros_like(self.mean)
        information = np.zeros_like(self.factor)
        results = {}
        for operation, *data in reversed(self.history or ()):
            if operation == "open":
                mean_score = mean_score[:, :-1]
                information = information[:, :-1, :-1]
            elif operation == "close":
                state, = data
                mean_score = np.insert(mean_score, state, 0, axis=1)
                information = np.insert(np.insert(information, state, 0, axis=1), state, 0, axis=2)
            elif operation == "step":
                column, = data
                transition = np.broadcast_to(np.eye(column.shape[1]), information.shape).astype(complex)
                transition[:, :, 0] = column
                transpose = transition.transpose(0, 2, 1)
                mean_score = (transpose @ mean_score[:, :, None])[:, :, 0]
                information = transpose @ information @ transition
            else:
                projection, gain, residual, variance, target = data
                j_gain = (information @ gain[:, :, None])[:, :, 0]
                score = np.sum(mean_score * gain, axis=1) - residual / variance
                precision = 1 / variance + np.sum(gain * j_gain, axis=1)
                if target is not None:
                    index, value = target
                    center, uncertainty = value + score / precision, 1 / precision
                    results[index] = {
                        "mean": float(center[0].real),
                        "variance": float(uncertainty[0].real),
                        "mean_gradient": {f"log_{key}": float(center[i + 1].imag / STEP)
                                          for i, key in enumerate(PARAMETERS)},
                        "log_variance_gradient": {
                            f"log_{key}": float(uncertainty[i + 1].imag / STEP / uncertainty[0].real)
                            for i, key in enumerate(PARAMETERS)},
                    }
                change = np.eye(len(projection)) - gain[:, :, None] * projection
                transpose = change.transpose(0, 2, 1)
                mean_score = mean_score - score[:, None] * projection
                information = transpose @ information @ change + np.outer(projection, projection) / variance[:, None, None]
        return [{"row": key, **results[key]} for key in sorted(results)]


def render(request):
    rows = request["rows"]
    model = Filter(request["parameters"], any(row.get("audit") for row in rows))
    predictions = [None] * len(rows)
    for tick, closing, opening in schedules(rows):
        model.advance(tick)
        for index in closing:
            predictions[index] = model.observe(index, rows[index])
        for index in opening:
            model.open(index, rows[index])
    likelihood = model.log_likelihood
    return {"log_likelihood": float(likelihood[0].real),
            "gradient": {f"log_{key}": float(likelihood[i + 1].imag / STEP)
                         for i, key in enumerate(PARAMETERS)}, "forecasts": predictions, "audits": model.audits()}


def main():
    with open(sys.argv[1], encoding="utf-8") as source:
        result = render(json.load(source))
    with open(sys.argv[2], "w", encoding="utf-8") as output:
        json.dump(result, output, allow_nan=False, separators=(",", ":"))


if __name__ == "__main__":
    main()
