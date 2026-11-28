"""Independent high-precision Gaussian kernel calculations for small inputs."""
from decimal import Decimal as D, localcontext
from functools import lru_cache

PARAMETERS = ("rate", "signal_variance", "bias_variance", "noise_scale")
LOG_2PI = D("1.8378770664093454835606594728112352797227949472755668256343030809655313918545")


def decimal(number):
    return D(str(number))


def forecasts(rows, parameters):
    rate, signal, bias, noise = parameters
    ordered = sorted(enumerate(rows), key=lambda pair: (pair[1]["end"], pair[0]))
    entries = [(r["start"], r["end"], decimal(r["gain"]), decimal(r["bias_loading"]),
                decimal(r["sd"]), decimal(r.get("ramp", 0))) for _, r in ordered]
    centers = [decimal(row["offset"]) for _, row in ordered]
    n = len(entries)
    covariance = [[D(0)] * n for _ in range(n)]

    @lru_cache(maxsize=None)
    def primitives(distance):
        x = rate * abs(distance)
        sign = 1 if distance >= 0 else -1
        e = (-x).exp()
        return (sign * (1-e) / rate, (e + x - 1) / rate**2,
                sign * (1-e-x+x*x/2) / rate**3,
                (e-1+x-x*x/2+x**3/6) / rate**4)

    def point_window(tick, start, stop, ramp):
        h, k = primitives(tick - start)[:2]
        u, v = primitives(tick - stop)[:2]
        slope = 2 * ramp / (stop - start)
        return ((1-ramp)*h - (1+ramp)*u + slope*(k-v)) / (stop-start)

    for i, (a, b, g, l, sd, ramp) in enumerate(entries):
        for j in range(i, n):
            c, d, h, k, _, other = entries[j]
            if g == 0 or h == 0:
                kernel = D(0)
            elif a == b and c == d:
                kernel = (-rate * abs(a - c)).exp()
            elif a == b:
                kernel = point_window(a, c, d, other)
            elif c == d:
                kernel = point_window(c, a, b, ramp)
            else:
                p, q = 2*ramp/(b-a), 2*other/(d-c)
                kernel = D(0)
                for t, sign_t in ((a, -1), (b, 1)):
                    for u, sign_u in ((c, -1), (d, 1)):
                        w, v = 1+sign_t*ramp, 1+sign_u*other
                        _, h2, h3, h4 = primitives(t-u)
                        kernel += sign_t*sign_u*(-w*v*h2 + (p*v-w*q)*h3 + p*q*h4)
                kernel /= (b-a)*(d-c)
            entry = signal * g * h * kernel + bias * l * k
            if i == j:
                entry += noise * sd * sd
            covariance[i][j] = covariance[j][i] = entry

    answer = [None] * n
    likelihood = D(0)
    for i, (index, row) in enumerate(ordered):
        y = row["value"]
        s = covariance[i][i]
        answer[index] = {"mean": centers[i], "variance": s}
        if y is None:
            continue
        residual = decimal(y) - centers[i]
        likelihood -= (LOG_2PI + s.ln() + residual**2 / s) / 2
        for j in range(i + 1, n):
            gain = covariance[j][i] / s
            centers[j] += gain * residual
            for k in range(j, n):
                entry = covariance[j][k] - gain * covariance[i][k]
                covariance[j][k] = covariance[k][j] = entry
    return likelihood, answer


def dense(request):
    with localcontext() as context:
        context.prec = 145
        rows = request["rows"]
        p = [decimal(request["parameters"][name]) for name in PARAMETERS]
        ll, predicted = forecasts(rows, p)
        step = D("1e-25")
        gradient = {}
        extra = {}
        for j, row in enumerate(rows):
            if row.get("sensitivity"):
                extra[j] = {"mean_gradient": {}, "log_variance_gradient": {}}
        for i, name in enumerate(PARAMETERS):
            plus, minus = p.copy(), p.copy()
            plus[i] *= step.exp()
            minus[i] *= (-step).exp()
            upper, upper_forecasts = forecasts(rows, plus)
            lower, lower_forecasts = forecasts(rows, minus)
            for j, data in extra.items():
                pmean, pvar = upper_forecasts[j]["mean"], upper_forecasts[j]["variance"]
                mmean, mvar = lower_forecasts[j]["mean"], lower_forecasts[j]["variance"]
                data["mean_gradient"]["log_" + name] = float((pmean - mmean) / (2 * step))
                data["log_variance_gradient"]["log_" + name] = float((pvar.ln() - mvar.ln()) / (2 * step))
            gradient["log_" + name] = float((upper - lower) / (2 * step))
    ready = [dict({key: float(v) for key, v in row.items()}, **extra.get(i, {}))
             for i, row in enumerate(predicted)]
    return {"log_likelihood": float(ll), "forecasts": ready, "gradient": gradient}
