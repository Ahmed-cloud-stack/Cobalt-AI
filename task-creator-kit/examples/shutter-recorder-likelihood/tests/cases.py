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


def audit_cases():
    cases = dict(small_cases())
    cases.update(ramps())
    for name in ("simultaneous-order", "epoch-translation", "duplicate-exposures", "clock-span",
                 "overlap-00", "overlap-05", "overlap-11", "ramped-segments-0.49999999",
                 "ramped-segments-1e-18", "profiled-clock-span", "weighted-low-noise-design"):
        document = cases[name]
        for i, entry in enumerate(document["rows"]):
            entry["audit"] = entry["value"] is not None and i % 5 != 2
        yield "audit-" + name, document

    forecasts_only = [row(1, 4, 1, -1, 2, 0.25, None),
                      row(3, 3, 1, 2.35, 0, 0.25, None)]
    for number in (0.0, 3.0):
        audited = dict(row(2, 9, -1, 2, 0.3, 0.4, number), audit=True, ramp=1)
        yield f"sole-reading-{number}", tape(params(), [*forecasts_only, audited])


def audit_batches():
    document, templates, groups = profiled_batches()
    for rows in [document["rows"], *(t["rows"] for t in templates)]:
        for row in rows:
            row["audit"] = row["value"] is not None
    return document, templates, groups


def audit_bias_answers(document):
    base = bias_answers(document)
    bias = document["parameters"]["bias_variance"]
    scale = document["parameters"]["noise_scale"]
    rows = document["rows"]

    weighted = [(r["bias_loading"]/r["sd"])**2 if r["value"] is not None else 0
                for r in rows]
    moment = [r["bias_loading"]*(r["value"]-r["offset"])/r["sd"]**2
              if r["value"] is not None else 0 for r in rows]
    information, linear = math.fsum(weighted), math.fsum(moment)
    audited = []
    for i, r in enumerate(rows):
        if not r.get("audit"):
            continue
        l, sd = r["bias_loading"], r["sd"]
        other, total = information-weighted[i], linear-moment[i]
        var = 1/(1/bias + other/scale)
        m = var * total / scale
        y = r["offset"] + l*m
        err = l*l*var + scale*sd**2
        db, dn = var**2/bias, var**2*other/scale
        dm = l*db*total/scale
        en = l*l*dn + scale*sd**2
        audited.append({"row": i, "mean": y, "variance": err,
                        "mean_gradient": {"log_rate": 0, "log_signal_variance": 0,
                                          "log_bias_variance": dm,
                                          "log_noise_scale": l*(dn*total/scale-m)},
                        "log_variance_gradient": {"log_rate": 0, "log_signal_variance": 0,
                                                  "log_bias_variance": l*l*db/err,
                                                  "log_noise_scale": en/err}})
    return dict(base, audits=audited)


def mixed_audit_batches():
    document, templates, groups = audit_batches()
    for j, source in enumerate(templates):
        for i, row in enumerate(source["rows"]):
            row["bias_loading"] = (i % 9 - 4) * (0.2 + j/20)
    for j, row in enumerate(document["rows"]):
        local, slot = divmod(j, groups)
        group = groups-slot-1
        row["bias_loading"] = templates[group % len(templates)]["rows"][local]["bias_loading"]
    return document, templates, groups


def use_profile(row, variant):
    a, b = row["start"], row["end"]
    if b - a < 2:
        return
    ticks = sorted({a, a+(b-a)//4, a+(b-a)//2, a+3*(b-a)//4, b})
    weight = ((0, 0, 1.125, 4, 0), (3, 0.063, 0, 0, 2.4), (0.3, 2, 1e-5, 1, 0))
    row.pop("ramp", None)
    row["profile"] = [[t, weight[variant % 3][i]] for i, t in enumerate(ticks)]


def measured_profiles():
    templates = dict(audit_cases())
    for name in ("ramped-segments-1e-18", "ramped-segments-0.49999999",
                 "ramped-segments-4e-05", "profiled-clock-span", "weighted-low-noise-design",
                 "duplicate-exposures", "epoch-translation", "overlap-05",
                 "profiled-rate-1e-18", "profiled-all-forecast"):
        full = "audit-" + name
        document = templates.get(full)
        if document is None:
            options = dict(ramps())
            document = options[name]
            for entry in document["rows"]:
                entry["audit"] = entry["value"] is not None
        for j, entry in enumerate(document["rows"]):
            use_profile(entry, j)
            entry["sensitivity"] = True
        yield "profile-" + name, document

    rows = [
        dict(row(-10**18, -10**18+5, 1.2, 1.1, 0, .1, .2),
             profile=[[-10**18,0],[-10**18+1,0],[-10**18+3,0],[-10**18+4,3],[-10**18+5,0]],
             sensitivity=True, audit=True),
        dict(row(-10**18+1, -10**18+3, 1, -2, 0, .12, None),
             profile=[[-10**18+1,4],[-10**18+2,0],[-10**18+3,1]], sensitivity=True),
        dict(row(-10**18+3, -10**18+3, 1, 1, 0, .15, .6), audit=True),
        dict(row(-10**18+3, -10**18+6, 1.9, -1.1, .03, .4, 0),
             profile=[[-10**18+3,0],[-10**18+4,0],[-10**18+5,0],[-10**18+6,4]], audit=True),
        dict(row(-10**18+5,-10**18+5, 1, 0, 0, .25, .15), audit=True)
    ]
    yield "knot-at-other-reading", tape(params(.03999999995, 2.6, 1.8, .66), rows)


def measured_batches():
    document, templates, groups = mixed_audit_batches()
    for template in templates:
        for index in (0, 1, 3):
            use_profile(template["rows"][index], index)
    for i, row in enumerate(document["rows"]):
        local, slot = divmod(i, groups)
        if local not in (0, 1, 3):
            continue
        group = groups - slot - 1
        source = templates[group % len(templates)]["rows"][local]
        shift = row["start"] - source["start"]
        row.pop("ramp", None)
        row["profile"] = [[tick + shift, weight] for tick, weight in source["profile"]]
    return document, templates, groups


def panel_cases():
    rows = [
        dict(row(-2, 3, 1.4, -1.1, .02, 1.2, .14), panel="D", audit=True),
        dict(row(1, 6, -.8, .7, .01, 1.1, -.09), panel="C", audit=True),
        dict(row(-1, 1, .9, 1.3, -.03, 1.0, .08), panel="A", audit=True),
        dict(row(10, 10, .6, -.7, .09, 1.0, -.22), panel="D", audit=True),
        dict(row(2, 3, .3, .9, 0, .5, None), sensitivity=True),
        dict(row(0, 4, 1.7, -.2, .04, 1.6, .32), panel="A", audit=True, sensitivity=True),
        dict(row(6, 8, -.5, 1.4, 0, 1.3, .03), panel="A", audit=True),
        dict(row(4, 4, 1.2, 1.1, 0, 1.0, .07), panel="C", audit=True),
        dict(row(5, 11, 2.0, -.8, -.03, 1.0, -.12), panel="C", audit=True),
        dict(row(-2, 2, .5, -.4, 0, 1.4, .01), panel="B", audit=True),
        dict(row(3, 3, 1.2, -.9, .02, .4, .12), audit=True),
        dict(row(7, 7, .85, .9, 0, 1.0, .27), panel="B", audit=True),
        dict(row(8, 10, -1.3, .3, 0, 1.0, -.32), panel="C", audit=True),
        dict(row(3, 5, 1.2, 1.2, .07, .2, .08), audit=True, sensitivity=True),
    ]
    for i in (0, 1, 5, 8):
        use_profile(rows[i], i)
    for rate, name in ((.039, "interleaved"), (1e-18, "persistent"), (200, "decorrelated")):
        yield f"panels-{name}", tape(params(rate, 2.6, .9, .73), rows)
    rows = [dict(row(0, 0, 4, 4, 0.07, 1, .04 + i*.003), panel="same-tick", audit=True)
            for i in range(4)]
    rows.insert(1, dict(row(0, 0, 2, -3, 0, .001, None), sensitivity=True))
    yield "panel-high-dynamic-range", tape(params(.7, 10000, 10000, .01), rows)
    shifted = [dict(item, value=item["value"] + 90) if item["value"] is not None else item for item in rows]
    yield "panel-high-dynamic-range-offset", tape(params(.7, 10000, 10000, .01), shifted)


def panel_batches():
    templates = []
    groups = 4000
    for variant in range(3):
        rows = [dict(row(0, 3, 1.4, 0, .1, 1, .07), audit=True, panel="s"),
                dict(row(1, 4, -1.0, 0, -.04, 1.2, .24), audit=True, panel="s"),
                dict(row(2, 2, .7, 0, 0, .4, .06), audit=True, sensitivity=True),
                dict(row(4, 6, .2, 0, .03, 1.0, -.03), audit=True, panel="s")]
        rows[0]["profile"] = [[0, .2], [1 + variant % 2, 1.0 + variant], [3, .3]]
        templates.append(tape(params(.36, 1.7, .4, .73), rows))

    rows = []
    for slot in range(4):
        for group in range(groups - 1, -1, -1):
            item = templates[group % len(templates)]["rows"][slot].copy()
            shift = group * 8192
            item.update(start=item["start"] + shift, end=item["end"] + shift)
            if "profile" in item:
                item["profile"] = [[t + shift, w] for t, w in item["profile"]]
            if "panel" in item:
                item["panel"] = str(group)
            rows.append(item)
    return tape(templates[0]["parameters"], rows), templates, groups


def curve_from_profile(profile, variant):
    controls = (0, .015, 2.5, 1.0, 4.0)
    return [[tick, weight, controls[(i + variant) % len(controls)]]
            for i, (tick, weight) in enumerate(profile[:-1])] + [profile[-1]]


def curved_weights():
    start = -10**18
    for rate in (1e-18, 3.999999999, 4, 4.000000001, 1000):
        rows = [
            dict(row(start, start+5, 1.3, -.4, .04, 1, .11),
                 curve=[[start,0,3],[start+1,0,0],[start+3,0,1],[start+5,0]],
                 audit=True, panel="curved"),
            dict(row(start+1,start+5, -.55,1.1,.02,.7,None),
                 curve=[[start+1,4,0],[start+2,0,3],[start+5,0]], sensitivity=True),
            dict(row(start+3,start+3,1.6,-.2,.1,.4,.13), audit=True, sensitivity=True),
            dict(row(start+3,start+9, .9,.2,-.05,1.2,.07),
                 curve=[[start+3,0,4],[start+4,0,0],[start+7,0,0],[start+9,1e-5]],
                 audit=True, panel="curved"),
            dict(row(start+5,start+10, .7,-.8,0,.7,-.09), ramp=-.9, audit=True),
        ]
        yield f"curved-rate-{rate}", tape(params(rate, 1.8, .45, .8), rows)
    rows = [
        dict(row(-10**18,10**18,1,1,.02,1,.01), audit=True, panel="cross",
             curve=[[-10**18,0,0],[-10**18+1,0,1],[0,0,0],[10**18,1]]),
        dict(row(-10**18,10**18, -1, .5,-.03,.4,None), sensitivity=True,
             curve=[[-10**18,4,0],[-1,0,0],[0,0,1],[10**18,0]]),
        dict(row(-1,0,.2,1,.03,1,-.02), audit=True, panel="cross", curve=[[-1,0,4],[0,0]]),
        dict(row(0,0,1,-1,.03,.25,.1), sensitivity=True, audit=True),
    ]
    for rate in (1e-18, 1000):
        yield f"curved-full-clock-{rate}", tape(params(rate, 3.2, 1.5,.5), rows)


def curved_batches():
    document, templates, groups = measured_batches()
    for i, template in enumerate(templates):
        for slot in (0, 1, 3):
            item = template["rows"][slot]
            item["curve"] = curve_from_profile(item.pop("profile"), i + slot)
    for i, item in enumerate(document["rows"]):
        if "profile" in item:
            slot, pos = divmod(i, groups)
            group = groups - pos - 1
            item["curve"] = curve_from_profile(item.pop("profile"), group % len(templates) + slot)
    return document, templates, groups
