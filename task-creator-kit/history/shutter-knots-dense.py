from pathlib import Path
root=Path('/tmp/shutter-knots')
p=root/'tests/dense.py'
s=p.read_text()
a=s.index('    entries ='); b=s.index('    answer =',a)
s=s[:a]+'''    def sections(row):
        a, b = row["start"], row["end"]
        if a == b:
            return [(a, b, D(1), D(1))]
        ramp = decimal(row.get("ramp", 0))
        profile = [(tick, decimal(weight)) for tick, weight in
                   row.get("profile", ((a, 1-ramp), (b, 1+ramp)))]
        pieces = [(a,b,u,v) for (a,u),(b,v) in zip(profile,profile[1:])]
        area = sum((b-a)*(u+v)/2 for a,b,u,v in pieces)
        return [(a,b,u/area,v/area) for a,b,u,v in pieces]

    entries = [(decimal(r["gain"]), decimal(r["bias_loading"]),
                decimal(r["sd"]), sections(r)) for _, r in ordered]
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

    def point_window(tick, left, right, lo, hi):
        h, k = primitives(tick-left)[:2]
        u, v = primitives(tick-right)[:2]
        return lo*h - hi*u + (hi-lo)/(right-left)*(k-v)

    def pair(first, second):
        a,b,lo,hi = first
        c,d,low,high = second
        if a == b:
            if c == d:
                return (-rate * abs(a-c)).exp()
            return point_window(a,c,d,low,high)
        if c == d:
            return point_window(c,a,b,lo,hi)
        p,q = (hi-lo)/(b-a),(high-low)/(d-c)
        total = D(0)
        for t, w, left_sign in ((a,lo,-1),(b,hi,1)):
            for u, v, right_sign in ((c,low,-1),(d,high,1)):
                _, h2, h3, h4 = primitives(t-u)
                total += left_sign*right_sign*(-w*v*h2 + (p*v-w*q)*h3 + p*q*h4)
        return total

    for i, (g,l,sd,pieces) in enumerate(entries):
        for j in range(i,n):
            h,k,_,other = entries[j]
            kernel = sum(pair(first,second) for first in pieces for second in other) if g and h else D(0)
            entry = signal*g*h*kernel + bias*l*k
            if i == j:
                entry += noise*sd*sd
            covariance[i][j] = covariance[j][i] = entry

'''+s[b:]
p.write_text(s)
