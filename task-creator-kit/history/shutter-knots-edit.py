from pathlib import Path
from difflib import unified_diff
root=Path('/tmp/shutter-knots'); p=root/'solution/reference.py'
s=p.read_text()
s=s.replace('    for tick in sorted(opening.keys() | closing.keys()):','''    knots = {tick for row in rows for tick, _ in row.get("profile", ())[1:-1]}
    for tick in sorted(opening.keys() | closing.keys() | knots):''')
s=s.replace('    def open(self, index, row):','''    def open(self, index, row):''')
s=s.replace('        self.active.append((index, row["start"], row["end"] - row["start"], row.get("ramp", 0)))','''        ramp = row.get("ramp", 0)
        profile = row.get("profile", ((row["start"], 1 - ramp), (row["end"], 1 + ramp)))
        adjacent = list(zip(profile, profile[1:]))
        area = math.fsum((b-a)*(lo+hi)/2 for (a,lo),(b,hi) in adjacent)
        self.active.append((index, [(a,b,lo/area,hi/area) for (a,lo),(b,hi) in adjacent]))''')
s=s.replace('        ramps = any(active[3] for active in self.active)','''        weights = []
        for _, pieces in self.active:
            left, right, lower, upper = next(piece for piece in pieces if piece[1] > previous)
            fraction = duration / (right - left)
            weights.append((fraction * ((right-previous)*lower + (previous-left)*upper),
                            duration * fraction * (upper-lower)))
        ramps = any(slope for _, slope in weights)''')
a=s.index('            fractions = np.array')
b=s.index('            weight = average[:, None] * alpha',a)
s=s[:a]+'''            alpha, beta = np.asarray(weights).T
'''+s[b:]
s=s.replace('for slot, (active, _, _, _) in enumerate(self.active, 2):','for slot, (active, _) in enumerate(self.active, 2):')
p.write_text(s)
old=(root/'tests/original.py.txt').read_text().splitlines()
diff=list(unified_diff(old,s.splitlines(),n=0))[2:]
print(sum(l.startswith(("+","-")) for l in diff))
