"""Deterministic inputs and the assembly of independently solved long cases."""
import math
import random


def params(rate=0.31, signal=2.8, bias=1.3, noise=0.74):
    return dict(rate=rate, signal_variance=signal, bias_variance=bias, noise_scale=noise)


def row(start, end, gain=1, bias=1, offset=0, sd=0.5, value=0):
    return dict(start=start, end=end, gain=gain, bias_loading=bias, offset=offset, sd=sd, value=value)


def tape(parameters, rows):
    return dict(parameters=parameters, rows=rows)


def small_cases():
    yield "empty", tape(params(), [])
    yield "all-forecast", tape(params(), [
        row(33, 40, sd=0.03, value=None), row(0, 13, sd=0.8, value=None),
        row(8, 8, gain=-2, bias=3, sd=0.4, value=None),
        row(6, 37, gain=1.5, bias=-0.5, value=None), row(10, 10, value=None),
    ])
    yield "simultaneous-order", tape(params(0.19, 0.07, 1.2, 3.0), [
        row(8, 12, 2, -1, 0.1, 0.08, 0.4), row(1, 12, -1, 1, 0.3, 0.1, 0),
        row(12, 12, 1, 1, -0.15, 0.12, -0.8), row(-9, 12, -0.5, 2, 0.5, 0.2, None),
        row(12, 20, 3, -1, 0.7, 0.08, None), row(12, 12, -1, 2, 0.6, 0.14, 0.3),
        row(20, 20, 1, -1, 0.07, 0.5, 0.0),
    ])
    yield "epoch-translation", tape(params(0.15, 1.4, 0.2, 3.7), [
        row(10**18 - 50 + start, 10**18 - 50 + stop, gain, bias, 0.03, 0.13, value)
        for start, stop, gain, bias, value in (
            (5, 9, 1, -1, 0.2), (6, 6, -1, 2, 0), (1, 7, -1, 1, 0.05),
            (6, 13, 2, -1, None), (9, 9, 3, 1, -0.1), (13, 13, 1, 0, 0.5))
    ])
    for rate in (1e-18, 1e-10, 1e-7, 4e-6, 0.03999999, 0.04000001, 12.0, 1000):
        yield "rate-" + str(rate), tape(params(rate, 0.2, 0.09, 0.02), [
            row(0, 0, bias=0, sd=1e-7, value=0.2),
            row(0, 1, bias=0, sd=1e-7, value=0.20000003),
            row(0, 3, bias=0, sd=1e-7, value=None),
            row(1, 2, bias=0, sd=3e-7, value=0.19999995),
            row(1, 3, bias=0, sd=2e-7, value=0.200000004),
            row(3, 4, bias=0, sd=1e-7, value=0.20000002),
            row(5, 5, bias=0, sd=2e-7, value=0.2),
            row(0, 1, bias=0, sd=2e-7, value=None),
        ])
    yield "duplicate-exposures", tape(params(1e-17, 0.4, 5, 0.04), [
        row(1, 11, 1, 1, 0, 1e-7, 0.2), row(1, 11, -1, -1, 0, 1e-7, -0.2),
        row(1, 11, 2, 2, 0, 1e-7, None), row(2, 13, 1, 1, 0, 2e-7, 0.2000001),
        row(11, 11, 1, 1, 0, 2e-7, 0.20000001),
        row(0, 0, 0, 1, 0, 0.2, -0.1), row(11, 12, -1, 1, 0.2, 0.25, 0.2),
        row(11, 12, 1, -1, 0.2, 1e-7, None),
        row(13, 14, 1, 1, 0, 1e-7, 0.2),
    ])
    yield "clock-span", tape(params(rate=1e-18), [
        row(-10**18, 10**18, 1.2, 0.9, 0, 0.2, -0.1),
        row(-10**18, -10**18, 0.8, -0.2, 0.4, 0.4, 0.3),
        row(10**18 - 1, 10**18, 1, 1, 0.15, 0.2, None),
        row(0, 0, 1, 1, 0.2, 0.15, 0), row(-10**18 + 1, -1, 0.6, 1, 0, 0.3, 0.6),
        row(10**18, 10**18, 1, -1, 0.2, 0.2, 0.9),
    ])
    for seed in range(14):
        rng = random.Random(50888 + seed)
        spans = [(0, 17), (1, 9), (3, 19), (0, 17), (3, 10), (4, 31),
                 (7, 7), (9, 10), (10, 16), (13, 26), (17, 17), (19, 23), (24, 24)]
        spans.extend((rng.randrange(31),) * 2 for _ in range(6))
        rows = [row(a, b, rng.choice((-2.5, -0.4, 0, 0.1, 1.7)),
                    rng.choice((-1.2, -0.5, 0, 0.8, 2.9)), rng.uniform(-2, 2),
                    rng.uniform(0.015, 2.0),
                    None if rng.randrange(5) == 0 else rng.choice((0, rng.uniform(-3, 3))))
                for a, b in spans]
        rng.shuffle(rows)
        yield f"overlap-{seed:02}", tape(params(rng.choice((2e-5, 0.012, 0.26, 1.1, 6.2)),
                    10**rng.uniform(-1, 1), 10**rng.uniform(-1, 1), 10**rng.uniform(-1, 1)), rows)


def independent_batches():
    parameters = params(0.37, 1.2, 1.4, 0.71)
    spans = [(0, 17), (1, 9), (3, 19), (0, 17), (3, 10), (4, 31),
             (7, 7), (9, 10), (10, 16), (13, 26), (17, 17), (19, 23),
             (24, 24), (26, 28), (31, 32), (31, 31)]
    pattern = [tape(parameters, [
        row(start, end, (-1)**i * (0.8 + i/63), 0, (i % 5 - 2)/11,
            (i % 7 + 1)/21, None if (i+j)%8==0 else (i%6 - 3 + j)/6)
        for i, (start, end) in enumerate(spans)
    ]) for j in range(4)]
    chunks = 1000
    # Interleave the time blocks without changing the relative input rank within one block.
    rows = []
    for slot in range(len(spans)):
        for group in range(chunks - 1, -1, -1):
            source = pattern[group % len(pattern)]["rows"][slot]
            base = 10**18 - 6000 * (chunks - group)
            rows.append(dict(source, start=base + source["start"], end=base + source["end"]))
    return tape(parameters, rows), pattern, chunks


def bias_clock():
    rng = random.Random(292982)
    parameters = params(rate=1.0, signal=0.8, bias=3.0, noise=0.24)
    rows = []
    tick = -10**18
    for i in range(16000):
        tick += i + rng.randrange(1, 53)
        rows.append(row(tick, tick, 0, (i % 11 - 5.0)/5, (i % 6 - 3.0)/7,
                        (i % 5 + 1.0)/9, None if i % 11 == 3 else (i % 23 - 11.0)/37))
    rng.shuffle(rows)
    return tape(parameters, rows)


def bias_answers(request):
    params = request["parameters"]
    prior = params["bias_variance"]
    scale = params["noise_scale"]
    # Keep the information form posterior and differentiate its closed form.
    curvature = weighted = 0.0
    predicted = [None] * len(request["rows"])
    ll, gb, gn = [], [], []
    for i in sorted(range(len(predicted)), key=lambda k: request["rows"][k]["end"]):
        q = request["rows"][i]
        l, sd, offset, y = q["bias_loading"], q["sd"], q["offset"], q["value"]
        variance = 1 / (1 / prior + curvature / scale)
        mean = variance * weighted / scale
        mu = offset + l * mean
        s = l*l * variance + scale * sd**2
        predicted[i] = {"mean": mu, "variance": s}
        if y is None:
            continue
        residual = y - mu
        ll.append(-0.5 * (math.log(2*math.pi*s) + residual**2 / s))
        bv = variance**2 / prior
        nv = variance**2 * curvature / scale
        variance_score = (residual**2 / s - 1) / (2*s)
        mean_score = residual / s
        gb.append(variance_score*l*l*bv + mean_score*l*bv*weighted/scale)
        gn.append(variance_score*(l*l*nv + scale*sd**2) + mean_score*l*(nv*weighted/scale-mean))
        curvature += (l/sd)**2
        weighted += l*(y-offset)/sd**2
    return {"forecasts": predicted, "log_likelihood": math.fsum(ll),
            "gradient": {"log_rate": 0.0, "log_signal_variance": 0.0,
                         "log_bias_variance": math.fsum(gb), "log_noise_scale": math.fsum(gn)}}


def contrast():
    values = []
    rng = random.Random(194)
    for i in range(16):
        gain = 3.135 + i % 3 * 1e-8
        loading = 2.763 - i % 3 * 1e-8
        values.append(row(i, i, gain, loading, sd=1e-7,
                          value=0.02*gain - 0.036*loading + rng.randrange(-5, 6)*1e-9))
        values.append(row(i, i, -2.763, 3.135, sd=1e-7, value=None))
    return tape(params(1e-18, 100, 100, 0.014), values)


def ramps():
    for rate in (1e-18, 1e-10, 4e-5, 0.035, 0.49999999, 0.50000001, 8.0, 1000):
        rows = [
            row(2, 14, 1.2, 1, 0.01, 0.07, 0.1),
            row(0, 6, -1.7, 1.6, -0.02, 0.05, -0.3),
            row(1, 8, 2, -1, 0.03, 0.1, None),
            row(2, 14, -1.2, -1, -0.01, 0.07, None),
            row(3, 11, 0.4, 1.7, 0.1, 0.08, 0),
            row(4, 5, 0.8, -1.2, 0.1, 0.04, 0.2),
            row(3, 3, 1.4, -2, 0.3, 0.05, -0.25),
            row(5, 5, 0.9, -0.02, 0.33, 0.05, 0.05),
            row(6, 8, -1, 1.1, 0.2, 0.1, None),
            row(11, 11, 3.2, 2, -0.05, 0.15, 0.46),
            row(11, 16, 0, 1, -0.07, 0.1, 0.11),
            row(13, 14, 1.09, 1, 0.01, 0.05, None),
            row(14, 14, 1.8, -1, 0.3, 0.07, None),
        ]
        for j, item in enumerate(rows):
            item["ramp"] = (1, -1, 0.37, -0.6, 0, 1, -1)[j % 7]
            if j != 4:
                item["sensitivity"] = True
        yield f"ramped-segments-{rate}", tape(params(rate, 0.73, 0.22, 2.46), rows)

    cases = dict(small_cases())
    for name in ("clock-span", "rate-1e-18", "duplicate-exposures", "all-forecast"):
        case = cases[name]
        for j, entry in enumerate(case["rows"]):
            entry.update(ramp=(j%5-2)/2, sensitivity=True)
        yield "profiled-" + name, case

    values = []
    rng = random.Random(28719)
    for j in range(13):
        loading = 2.23 + (j % 3 - 1) * 8e-7
        gain = -2.75 + (j % 5 - 2) * 4e-7
        source = 0.012 * gain + 0.026 * loading
        look = row(j, j+3, gain, loading, sd=3e-7,
                   value=source + rng.randrange(-5, 6)*1.3e-8)
        values.append(dict(look, ramp=(-1, 0.23, 1, 0)[j%4], sensitivity=True))
        values.append(dict(row(j+3, j+3, -2.23, -2.75, sd=1e-7, value=None),
                           sensitivity=True))
    yield "weighted-low-noise-design", tape(params(1e-18, 19, 24, 0.02), values)


def profiled_batches():
    source, templates, groups = independent_batches()
    for template in templates:
        for index, item in enumerate(template["rows"]):
            item["ramp"] = (1, -1, 0.625, -0.12, 0, 0.33)[index % 6]
            item["sensitivity"] = index % 4 != 0
    for i, row in enumerate(source["rows"]):
        local = i // groups
        row["ramp"] = (1, -1, 0.625, -0.12, 0, 0.33)[local % 6]
        row["sensitivity"] = local % 4 != 0
    return source, templates, groups


def scaled_batches():
    _, originals, groups = profiled_batches()
    settings = params(0.00008, 1.2, 2, 0.3)
    templates = []
    for j in range(96):
        factor = 23 + 3*j
        rows = [dict(row, start=row["start"]*factor, end=row["end"]*factor)
                for row in originals[j % len(originals)]["rows"]]
        templates.append(tape(settings, rows))
    rows = []
    for slot in range(len(templates[0]["rows"])):
        for group in range(groups - 1, -1, -1):
            source = templates[group % len(templates)]["rows"][slot]
            base = -10**18 + (group + 1) * 100_000_000
            rows.append(dict(source, start=base + source["start"], end=base + source["end"]))
    return tape(settings, rows), templates, groups
