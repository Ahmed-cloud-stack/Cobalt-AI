"""Independent high-precision Gaussian kernel calculations for small inputs."""
from decimal import Decimal as D, localcontext
from functools import lru_cache

PARAMETERS = ("rate", "signal_variance", "bias_variance", "noise_scale")
LOG_2PI = D("1.8378770664093454835606594728112352797227949472755668256343030809655313918545")


def decimal(number):
    return D(str(number))


def forecasts(rows, parameters, audit=None):
    rate, signal, bias, noise = parameters
    excluded = audit if isinstance(audit, tuple) else (audit,)
    ordered = sorted(enumerate(rows), key=lambda pair: (pair[0] in excluded, pair[1]["end"], pair[0]))
    def sections(row):
        a, b = row["start"], row["end"]
        if a == b:
            return [(a, b, (D(1),), (D(1),))]
        ramp = decimal(row.get("ramp", 0))
        profile = [(tick, decimal(weight)) for tick, weight in
                   row.get("profile", ((a, 1-ramp), (b, 1+ramp)))]
        if "curve" in row:
            marks = row["curve"]
            pieces = [(a,b,decimal(u),decimal(w),decimal(v))
                      for (a,u,w),(b,v,*_) in zip(marks,marks[1:])]
        else:
            pieces = [(a,b,u,(u+v)/2,v) for (a,u),(b,v) in zip(profile,profile[1:])]
        area = sum((b-a)*(u+w+v)/3 for a,b,u,w,v in pieces)
        result = []
        for a,b,u,w,v in pieces:
            width = b-a
            second = 2*(u-2*w+v)/width**2
            slopes = (2*(w-u)/width, 2*(v-w)/width)
            result.append((a,b,(u/area,slopes[0]/area,second/area),
                              (v/area,slopes[1]/area,second/area)))
        return result

    entries = [(decimal(r["gain"]), decimal(r["bias_loading"]),
                decimal(r["sd"]), sections(r)) for _, r in ordered]
    centers = [decimal(row["offset"]) for _, row in ordered]
    n = len(entries)
    covariance = [[D(0)] * n for _ in range(n)]

    @lru_cache(maxsize=None)
    def primitives(distance):
        x = rate * abs(distance)
        remainder, term, divisor = (-x).exp(), D(1), D(1)
        result = []
        for degree in range(1, 7):
            remainder -= term
            term *= -x/degree
            divisor *= rate
            sign = -1 if degree % 2 and distance >= 0 else 1
            result.append(sign * remainder / divisor)
        return result

    def point_window(tick, section):
        a,b,lower,upper = section
        return sum(sign*sum(w*k for w,k in zip(weights,primitives(tick-t)))
                   for t,weights,sign in ((a,lower,1),(b,upper,-1)))

    def pair(first, second):
        a,b,lower,upper = first
        c,d,low,high = second
        if a == b:
            if c == d:
                return (-rate * abs(a-c)).exp()
            return point_window(a,second)
        if c == d:
            return point_window(c,first)
        total = D(0)
        for t, wt, left_sign in ((a,lower,-1),(b,upper,1)):
            for u, wu, right_sign in ((c,low,-1),(d,high,1)):
                antiderivatives = primitives(t-u)
                total += left_sign*right_sign*sum((-1)**(i+1)*w*v*antiderivatives[i+j+1]
                    for i,w in enumerate(wt) for j,v in enumerate(wu))
        return total

    for i, (g,l,sd,pieces) in enumerate(entries):
        for j in range(i,n):
            h,k,_,other = entries[j]
            kernel = sum(pair(first,second) for first in pieces for second in other) if g and h else D(0)
            entry = signal*g*h*kernel + bias*l*k
            if i == j:
                entry += noise*sd*sd
            covariance[i][j] = covariance[j][i] = entry

    answer = [None] * n
    likelihood = D(0)
    for i, (index, row) in enumerate(ordered):
        y = row["value"]
        s = covariance[i][i]
        answer[index] = {"mean": centers[i], "variance": s}
        if y is None or index in excluded:
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
        panels = {}
        for j, row in enumerate(rows):
            if "panel" in row:
                panels.setdefault(row["panel"], []).append(j)
        exclusions = [tuple(panels[row["panel"]]) if "panel" in row else (j,)
                      for j, row in enumerate(rows)]
        audits = []
        for j, row in enumerate(rows):
            if row.get("audit"):
                _, last = forecasts(rows, p, exclusions[j])
                audits.append(dict({k: float(v) for k, v in last[j].items()}, row=j,
                                   mean_gradient={}, log_variance_gradient={}))
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
            for entry in audits:
                j = entry["row"]
                _, upper_audit = forecasts(rows, plus, exclusions[j])
                _, lower_audit = forecasts(rows, minus, exclusions[j])
                a, b = upper_audit[j], lower_audit[j]
                entry["mean_gradient"]["log_" + name] = float((a["mean"] - b["mean"]) / (2 * step))
                entry["log_variance_gradient"]["log_" + name] = float(
                    (a["variance"].ln() - b["variance"].ln()) / (2 * step))
            gradient["log_" + name] = float((upper - lower) / (2 * step))
    ready = [dict({key: float(v) for key, v in row.items()}, **extra.get(i, {}))
             for i, row in enumerate(predicted)]
    return {"log_likelihood": float(ll), "forecasts": ready, "gradient": gradient, "audits": audits}
