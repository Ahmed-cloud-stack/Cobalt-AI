from pathlib import Path
p=Path('/tmp/shutter-curves/tests/dense.py')
s=p.read_text()
a=s.index('        if a == b:')
b=s.index('    entries =',a)
s=s[:a]+'''        if a == b:
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

'''+s[b:]
a=s.index('    @lru_cache(')
b=s.index('    for i, (g,l,sd,pieces)',a)
s=s[:a]+'''    @lru_cache(maxsize=None)
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

'''+s[b:]
p.write_text(s)
