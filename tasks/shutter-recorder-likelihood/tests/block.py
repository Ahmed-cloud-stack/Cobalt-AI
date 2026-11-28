"""Independent conditional-block oracle with a global scalar calibration bias."""
from decimal import Decimal as D, localcontext

from dense import LOG_2PI, PARAMETERS, decimal, forecasts


def block_rows(templates, groups, params):
    local = params.copy()
    local[2] = D(0)
    table = []
    for template in templates:
        rows = template["rows"]
        shifted = [dict(row, offset=decimal(row["offset"]) + decimal(row["bias_loading"]))
                   for row in rows]

        def kernels(target):
            _, zero = forecasts(rows, local, target)
            _, unit = forecasts(shifted, local, target)
            return [(a["mean"], b["mean"] - a["mean"], a["variance"])
                    for a,b in zip(zero, unit)]

        coeff = kernels(None)
        held = {i: kernels(i)[i] for i, row in enumerate(rows) if row.get("audit")}
        order = sorted(range(len(rows)), key=lambda i: (rows[i]["end"], i))
        table.append((rows, coeff, held, order))

    forecasts_out = [None] * (len(table[0][0]) * groups)
    audit_coeff = {}
    precision, linear, likelihood = 1 / params[2], D(0), D(0)
    for group in range(groups):
        rows, coeff, held, order = table[group % len(table)]
        for index in order:
            row = rows[index]
            a, b, variance = coeff[index]
            mean, spread = a + b*linear/precision, variance + b*b/precision
            output_index = index*groups + groups - group - 1
            forecasts_out[output_index] = mean, spread
            if row["value"] is None:
                continue
            value = decimal(row["value"])
            likelihood -= (LOG_2PI + spread.ln() + (value-mean)**2/spread)/2
            precision += b*b/variance
            linear += b*(value-a)/variance
            if index in held:
                audit_coeff[output_index] = value, *held[index]

    audits = {}
    for i,(y,a,b,s) in audit_coeff.items():
        p, q = precision-b*b/s, linear-b*(y-a)/s
        audits[i] = a+b*q/p, s+b*b/p
    return likelihood, forecasts_out, audits


def mixed_answers(templates, groups, document):
    with localcontext() as context:
        context.prec = 64
        p = [decimal(document["parameters"][k]) for k in PARAMETERS]
        ll, values, audited = block_rows(templates, groups, p)
        rows = [dict(mean=float(a), variance=float(b)) for a,b in values]
        audits = {i: {"row":i,"mean":float(a),"variance":float(b)}
                  for i,(a,b) in audited.items()}
        sensitive = {i: data for i,data in enumerate(rows) if document["rows"][i].get("sensitivity")}
        for record in [*sensitive.values(), *audits.values()]:
            record["mean_gradient"] = {}
            record["log_variance_gradient"] = {}
        gradient = {}
        h = D("1e-24")
        for i, name in enumerate(PARAMETERS):
            plus, minus = p.copy(), p.copy()
            plus[i] *= h.exp()
            minus[i] *= (-h).exp()
            a, b, c = block_rows(templates, groups, plus)
            x, y, z = block_rows(templates, groups, minus)
            key = "log_" + name
            gradient[key] = float((a-x)/(2*h))
            for groups_of_rows, upper, lower, baseline in ((sensitive,b,y,values),(audits,c,z,audited)):
                for j,row in groups_of_rows.items():
                    row["mean_gradient"][key] = float((upper[j][0]-lower[j][0])/(2*h))
                    row["log_variance_gradient"][key] = float((upper[j][1]-lower[j][1])/(2*h*baseline[j][1]))
    return {"log_likelihood":float(ll), "forecasts":rows, "gradient":gradient,
            "audits":[audits[i] for i in sorted(audits)]}
