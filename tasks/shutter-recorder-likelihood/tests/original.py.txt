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


def models(config):
    settings = np.tile([config[name] for name in PARAMETERS], (LANES, 1)).astype(complex)
    # Each imaginary perturbation is in a separate log-parameter direction.
    for col in range(len(PARAMETERS)):
        settings[col + 1, col] += STEP * 1j
    return settings.T


def schedules(rows):
    ticks = {row[key] for row in rows for key in ("start", "end")}
    for tick in sorted(ticks):
        closing = [i for i, row in enumerate(rows) if row["end"] == tick]
        closing.sort(key=lambda i: rows[i]["start"])
        opening = [i for i, row in enumerate(rows) if row["start"] == tick < row["end"]]
        yield tick, closing, opening


def coefficients(z):
    """Transition of X and the time average on a segment of length z/rate."""
    decay = np.exp(-z)
    change = -np.expm1(-z)
    average = change / z
    xx = 1 - decay * decay
    xa = change * average * decay
    # The numerator vanishes to third order. Expand the quotient near zero.
    aa = np.empty_like(z)
    small = z.real < 1e-8
    x = z[small]
    polynomial = np.zeros_like(x)
    for degree in range(12, 3, -1):
        term = (-1)**degree * (4 - 2**degree) / math.factorial(degree)
        polynomial = polynomial * x + term
    aa[small] = x * polynomial
    x, change_large = z[~small], change[~small]
    aa[~small] = (2 * (x - change_large) - change_large * change_large) / (x * x)
    return decay, average, xx, xa, aa


def turn(matrix, row, left, right):
    """Orthogonally eliminate one entry using algebraic transpose."""
    x, y = matrix[:, row, left], matrix[:, row, right]
    if np.all(y == 0):
        return
    radius = np.sqrt(x * x.conjugate() + y * y.conjugate())
    nonzero = radius != 0
    safe = np.where(nonzero, radius, 1)
    c = np.where(nonzero, x / safe, 1)[:, None]
    s = (y / safe)[:, None]
    a, b = matrix[:, row:, left].copy(), matrix[:, row:, right].copy()
    matrix[:, row:, left] = c * a + s * b
    matrix[:, row:, right] = c * b - s * a
    matrix[:, row, right] = 0


class Filter:
    def __init__(self, config):
        self.rate, self.signal, self.bias, self.noise = models(config)
        self.time = None
        self.active = []
        self.mean = np.zeros((LANES, 2), dtype=complex)
        self.factor = np.zeros((LANES, 2, 2), dtype=complex)
        self.factor[:, 0, 0] = np.sqrt(self.signal)
        self.factor[:, 1, 1] = np.sqrt(self.bias * self.noise)
        self.log_likelihood = np.zeros(LANES, dtype=complex)
        self.error = np.zeros(LANES, dtype=complex)
        self.transitions = {}

    def open(self, index, duration):
        self.active.append((index, duration))
        self.mean = np.pad(self.mean, ((0, 0), (0, 1)))
        self.factor = np.pad(self.factor, ((0, 0), (0, 1), (0, 1)))

    def close(self, state):
        self.active.pop(state - 2)
        self.mean = np.delete(self.mean, state, axis=1)
        factor = np.delete(self.factor, state, axis=1)
        for row in range(state + 1, factor.shape[1]):
            turn(factor, row, row, row + 1)
        self.factor = factor[:, :, :-1].copy()

    def advance(self, tick):
        previous, self.time = self.time, tick
        if previous is None or tick == previous:
            return
        duration = float(tick) - float(previous)
        if duration not in self.transitions:
            decay, average, xx, xa, aa = coefficients(self.rate * duration)
            nx = np.sqrt(self.signal * xx)
            na = self.signal * xa / nx
            independent = np.sqrt(self.signal * aa - na * na)
            if len(self.transitions) == 4096:
                self.transitions.clear()
            self.transitions[duration] = (decay, average, nx, na, independent)
        decay, average, nx, na, independent = self.transitions[duration]

        m = self.mean
        f = self.factor
        dim = m.shape[1]
        has_exposure = bool(self.active)
        added = 2 if has_exposure else 1
        extended = np.zeros((LANES, dim, dim + added), dtype=complex)
        extended[:, :, :dim] = f
        extended[:, 0, :dim] *= decay[:, None]
        extended[:, 0, dim] = nx
        if has_exposure:
            fractions = np.array([duration / (span + 1) for _, span in self.active])
            weight = average[:, None] * fractions
            m[:, 2:] += weight * m[:, :1]
            extended[:, 2:, :dim] += weight[:, :, None] * extended[:, :1, :dim]
            extended[:, 2:, dim] = na[:, None] * fractions
            extended[:, 2:, dim + 1] = independent[:, None] * fractions
        m[:, 0] *= decay
        for row in range(dim):
            for extra in range(dim, dim + 1):
                turn(extended, row, row, extra)
        self.factor = extended[:, :, :dim].copy()

    def observe(self, index, row):
        state = 0
        for slot, (active, _) in enumerate(self.active, 2):
            if index == active:
                state = slot
                break
        gain, loading = row["gain"], row["bias_loading"]
        predicted = gain * self.mean[:, state] + loading * self.mean[:, 1] + row["offset"]
        f = self.factor
        innovations = gain * f[:, state] + loading * f[:, 1]
        noise = self.noise * row["sd"]
        variance = noise * noise + np.sum(innovations * innovations, axis=1)
        value = row["value"]
        if value:
            residual = value - predicted
            contribution = -0.5 * (LOG_2PI + np.log(variance.real) + residual * residual / variance)
            # Compensated accumulation for the score and its four derivatives.
            increment = contribution - self.error
            total = self.log_likelihood + increment
            self.error = (total - self.log_likelihood) - increment
            self.log_likelihood = total

            # Start with the measurement row, followed by the state.
            # Eliminating its coefficients from right to left retains a lower factor.
            dim = f.shape[1]
            joint = np.zeros((LANES, dim + 1, dim + 1), dtype=complex)
            joint[:, 0, 0] = noise
            joint[:, 0, 1:] = innovations
            joint[:, 1:, 1:] = f
            for col in range(1, dim + 1):
                turn(joint, 0, 0, col)
            self.mean += joint[:, 1:, 0] * (residual / joint[:, 0, 0])[:, None]
            self.factor = joint[:, 1:, 1:].copy()
        if state and value is not None:
            self.close(state)
        return {"mean": float(predicted[0].real), "variance": float(variance[0].real)}


def render(request):
    rows = request["rows"]
    model = Filter(request["parameters"])
    predictions = [None] * len(rows)
    for tick, closing, opening in schedules(rows):
        model.advance(tick)
        for index in closing:
            predictions[index] = model.observe(index, rows[index])
        for index in opening:
            model.open(index, rows[index]["end"] - tick)
    likelihood = model.log_likelihood
    return {"log_likelihood": float(likelihood[0].real),
            "gradient": {f"log_{key}": float(likelihood[i + 1].imag / STEP)
                         for i, key in enumerate(PARAMETERS)}, "forecasts": predictions}


def main():
    with open(sys.argv[1], encoding="utf-8") as source:
        result = render(json.load(source))
    with open(sys.argv[2], "w", encoding="utf-8") as output:
        json.dump(result, output, allow_nan=False, separators=(",", ":"))


if __name__ == "__main__":
    main()
