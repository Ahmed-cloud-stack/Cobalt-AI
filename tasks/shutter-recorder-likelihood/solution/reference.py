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
NODES, WEIGHTS = np.polynomial.legendre.leggauss(16)
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
    knots = {mark[0] for row in rows for mark in row.get("curve", row.get("profile", ()))[1:-1]}
    for tick in sorted(opening.keys() | closing.keys() | knots):
        yield tick, closing.get(tick, ()), opening.get(tick, ())


def coefficients(z):
    """Mean and process-noise factors for the endpoint and three weighted moments."""
    shape = z.shape
    z = z.ravel()
    decay = np.exp(-z)
    means = np.zeros((len(z), 3), dtype=complex)
    gram = np.zeros((len(z), 4, 4), dtype=complex)
    small = z.real < 4
    if small.any():
        r = z[small]
        u = NODES[:, 0]
        weight = WEIGHTS[:, 0]
        inner = u[:, None] + (1-u)[:, None] * u
        exp_inner = np.exp(-((1-u)[:, None] * u)[..., None] * r)
        basis = np.stack((np.ones_like(inner), inner, inner**2), axis=2)
        integrated = np.einsum("j,ijm,ijn->imn", weight, basis, exp_inner) * (1-u)[:, None, None]
        kernels = np.concatenate((np.exp(-(1-u[:, None])*r)[:, None], integrated), axis=1)
        gram[small] = 2*r[:, None, None] * np.einsum("i,imn,ikn->nmk", weight, kernels, kernels)
        means[small] = np.array([np.sum(weight[:, None] * u[:, None]**j * np.exp(-u[:, None]*r), axis=0)
                                 for j in range(3)]).T
    if (~small).any():
        r, end = z[~small], decay[~small]
        inv = 1/r
        e0 = -np.expm1(-r)*inv
        e1 = (1-e0)*inv
        e2 = (1-2*e1)*inv
        means[~small] = np.stack((e0, (e0-end)*inv, ((2*(e0-end)*inv)-end)*inv), axis=1)
        polynomial = np.zeros((len(r), 4, 3), dtype=complex)
        polynomial[:, 1, 0] = inv
        polynomial[:, 2, :2] = np.stack((inv**2, inv), axis=1)
        polynomial[:, 3] = np.stack((2*inv**3, 2*inv**2, inv), axis=1)
        expo = -polynomial.sum(axis=2)
        expo[:, 0] = 1
        moment = polynomial @ np.stack((e0,e1,e2), axis=1)[:, :, None]
        hilbert = 1 / (1 + np.arange(3)[:, None] + np.arange(3))
        gram[~small] = (2*r[:, None, None] * (polynomial @ hilbert @ polynomial.transpose(0, 2, 1)
                         + moment * expo[:, None, :] + expo[:, :, None] * moment.transpose(0, 2, 1))
                         - np.expm1(-2*r)[:, None, None] * expo[:, :, None] * expo[:, None, :])
    factor = np.zeros_like(gram)
    for k in range(4):
        remaining = gram[:, k:, k] - np.sum(factor[:, k:, :k] * factor[:, k:k+1, :k], axis=2)
        factor[:, k:, k] = remaining / np.sqrt(remaining[:, :1])
    return decay.reshape(shape), means.reshape(*shape, 3), factor.reshape(*shape, 4, 4)


def compress(factor):
    # A real orthogonal basis retains every direction present in the base factor.
    # Discarded columns are therefore second order in the imaginary perturbation.
    basis, triangular = np.linalg.qr(factor[0].real.astype(float).T, mode="reduced")
    compressed = factor @ basis
    compressed.real = triangular.T
    return compressed


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
        ramp = row.get("ramp", 0)
        profile = row.get("profile", ((row["start"], 1 - ramp), (row["end"], 1 + ramp)))
        if "curve" in row:
            marks = row["curve"]
            pieces = [(a,b,u,w,v) for (a,u,w),(b,v,*_) in zip(marks,marks[1:])]
        else:
            pieces = [(a,b,u,(u+v)/2,v) for (a,u),(b,v) in zip(profile,profile[1:])]
        area = math.fsum((b-a)*(u+w+v)/3 for a,b,u,w,v in pieces)
        self.active.append((index, [(a,b,u/area,w/area,v/area) for a,b,u,w,v in pieces]))
        self.mean = np.pad(self.mean, ((0, 0), (0, 1)))
        self.factor = np.pad(self.factor, ((0, 0), (0, 1), (0, 1)))

    def close(self, state):
        if self.history is not None:
            self.history.append(("close", state))
        self.active.pop(state - 2)
        self.mean = np.delete(self.mean, state, axis=1)
        factor = np.delete(self.factor, state, axis=1)
        self.factor = compress(factor)

    def advance(self, tick):
        previous, self.time = self.time, tick
        if previous is None or tick == previous:
            return
        duration = tick - previous
        weights = []
        for _, pieces in self.active:
            left, right, lower, middle, upper = next(piece for piece in pieces if piece[1] > previous)
            fraction = duration / (right - left)
            u, v = (previous-left)/(right-left), (right-previous)/(right-left)
            weights.append((duration * (v*v*lower + 2*u*v*middle + u*u*upper),
                            2*duration*fraction * (v*(middle-lower) + u*(upper-middle)),
                            duration*fraction**2 * ((lower-middle)+(upper-middle))))
        if duration not in self.transitions:
            spans = next(self.batches)
            decay, moments, factor = coefficients(self.rate[:, None] * spans)
            factor *= np.sqrt(self.signal)[:, None, None, None]
            self.transitions = {span: (decay[:, j], moments[:, j], factor[:, j])
                                for j, span in enumerate(spans)}
        decay, moments, noise_factor = self.transitions[duration]

        m = self.mean
        f = self.factor
        dim = m.shape[1]
        has_exposure = bool(self.active)
        added = 4 if has_exposure else 1
        extended = np.zeros((LANES, dim, dim + added), dtype=f.dtype)
        extended[:, :, :dim] = f
        extended[:, 0, :dim] *= decay[:, None]
        extended[:, 0, dim] = noise_factor[:, 0, 0]
        if has_exposure:
            weights = np.asarray(weights)
            weight = moments @ weights.T
            extended[:, 2:, dim:] = weights @ noise_factor[:, 1:]
            m[:, 2:] += weight * m[:, :1]
            extended[:, 2:, :dim] += weight[:, :, None] * f[:, :1]
        if self.history is not None:
            column = np.zeros(m.shape, dtype=complex)
            column[:, 0] = decay
            if has_exposure:
                column[:, 2:] = weight
            self.history.append(("step", column))
        m[:, 0] *= decay
        self.factor = compress(extended)

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
            precision = np.clongdouble if row["sd"] < 1e-4 or "panel" in row else f.dtype
            joint = np.zeros((LANES, dim + 1, dim + 1), dtype=precision)
            joint[:, 0, 0] = noise
            joint[:, 0, 1:] = innovations
            joint[:, 1:, 1:] = f
            # Reflect the measurement vector onto its first column.
            length = np.sqrt(np.sum(joint[:, 0] * joint[:, 0], axis=1))
            reflection = joint[:, 0].copy()
            reflection[:, 0] += length
            projected = np.sum(joint * reflection[:, None], axis=2)
            joint -= (projected / (length * reflection[:, 0])[:, None])[:, :, None] * reflection[:, None]
            joint[:, 0, 0] = -length
            self.mean = self.mean + joint[:, 1:, 0] * (residual / joint[:, 0, 0])[:, None]
            if self.history is not None:
                projection = np.zeros(dim)
                projection[state], projection[1] = gain, loading
                kalman_gain = joint[:, 1:, 0] / joint[:, :1, 0]
                target = (index, value, row.get("panel")) if row.get("audit") else None
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


    def audits(self, panels):
        mean_score = np.zeros_like(self.mean)
        information = self.factor[:, :, :0].copy()
        results = {}
        pending, cross_information = [], information.copy()
        while self.history:
            operation, *data = self.history.pop()
            if operation == "open":
                mean_score = mean_score[:, :-1]
                information = information[:, :-1]
                cross_information = cross_information[:, :-1]
            elif operation == "close":
                state, = data
                mean_score = np.insert(mean_score, state, 0, axis=1)
                information = np.insert(information, state, 0, axis=1)
                cross_information = np.insert(cross_information, state, 0, axis=1)
            elif operation == "step":
                column, = data
                mean_score[:, 0] = np.sum(column * mean_score, axis=1)
                information[:, 0] = np.sum(column[:, :, None] * information, axis=1)
                cross_information[:, 0] = np.sum(column[:, :, None] * cross_information, axis=1)
            else:
                projection, gain, residual, variance, target = data
                j_gain = np.sum(gain[:, :, None] * information, axis=1)
                score = np.sum(mean_score * gain, axis=1) - residual / variance
                precision = 1 / variance + np.sum(j_gain * j_gain, axis=1)
                if target is not None:
                    index, value, panel = target
                    if panel is None:
                        results[index] = value + score / precision, 1 / precision
                    else:
                        members, scores, entries = panels[panel]
                        scores[index] = value, score
                        entries[index, index] = precision
                        for other in members:
                            if other in pending:
                                cross = cross_information[:, :, pending.index(other)]
                                entries[index, other] = entries[other, index] = np.sum(gain * cross, axis=1)
                        if len(scores) == len(members):
                            matrix = np.array([[entries[i, j] for j in members] for i in members]).transpose(2, 0, 1)
                            residuals = np.array([scores[i][1] for i in members]).T
                            inverse = np.broadcast_to(np.eye(len(members)), matrix.shape)
                            solved = np.concatenate((inverse, residuals[:, :, None]), axis=2)
                            for j in range(len(members)):
                                diagonal = matrix[:, j:j+1, j:j+1].copy()
                                multiplier = matrix[:, :, j:j+1] / diagonal
                                multiplier[:, j] = 0
                                solved -= multiplier * solved[:, j:j+1]
                                matrix -= multiplier * matrix[:, j:j+1]
                                solved[:, j:j+1] /= diagonal
                                matrix[:, j:j+1] /= diagonal
                            means, covariance = solved[:, :, -1], solved[:, :, :-1]
                            for i, axis in zip(members, range(len(members))):
                                results[i] = scores[i][0] + means[:, axis], covariance[:, axis, axis]
                            retained = [j for j, other in enumerate(pending) if other not in members]
                            pending, cross_information = [pending[j] for j in retained], cross_information[:, :, retained]
                            del panels[panel]
                if pending:
                    cross_information -= projection[None, :, None] * np.sum(cross_information * gain[:, :, None], axis=1)[:, None]
                if target is not None and target[2] in panels:
                    cross = np.sum(information * j_gain[:, None, :], axis=2) - precision[:, None] * projection
                    pending.append(index)
                    cross_information = np.concatenate((cross_information, cross[:, :, None]), axis=2)
                mean_score = mean_score - score[:, None] * projection
                information = np.concatenate((information - projection[None, :, None] * j_gain[:, None, :],
                                              projection[None, :, None] / np.sqrt(variance)[:, None, None]), axis=2)
                width = len(projection)
                if information.shape[2] >= 4 * width + 24:
                    information = compress(information)
        return [{"row": index, "mean": float(center[0].real), "variance": float(uncertainty[0].real),
                 "mean_gradient": {f"log_{key}": float(center[i + 1].imag / STEP)
                                   for i, key in enumerate(PARAMETERS)},
                 "log_variance_gradient": {f"log_{key}": float(uncertainty[i + 1].imag / STEP / uncertainty[0].real)
                                            for i, key in enumerate(PARAMETERS)}}
                for index, (center, uncertainty) in sorted(results.items())]


def render(request):
    rows = request["rows"]
    model = Filter(request["parameters"], any(row.get("audit") for row in rows))
    predictions = [None] * len(rows)
    events = list(schedules(rows))
    for pos, (tick, closing, opening) in enumerate(events):
        if pos % 256 == 0:
            batch = events[max(0, pos - 1):pos + 256]
            model.batches = iter((tuple({b[0] - a[0] for a, b in zip(batch, batch[1:])}),))
            model.transitions.clear()
        model.advance(tick)
        for index in closing:
            predictions[index] = model.observe(index, rows[index])
        for index in opening:
            model.open(index, rows[index])
    panels = {}
    for index, row in enumerate(rows):
        if "panel" in row:
            panels.setdefault(row["panel"], ([], {}, {}))[0].append(index)
    likelihood = model.log_likelihood
    return {"log_likelihood": float(likelihood[0].real),
            "gradient": {f"log_{key}": float(likelihood[i + 1].imag / STEP)
                         for i, key in enumerate(PARAMETERS)}, "forecasts": predictions, "audits": model.audits(panels)}


def main():
    with open(sys.argv[1], encoding="utf-8") as source:
        result = render(json.load(source))
    with open(sys.argv[2], "w", encoding="utf-8") as output:
        json.dump(result, output, allow_nan=False, separators=(",", ":"))


if __name__ == "__main__":
    main()
