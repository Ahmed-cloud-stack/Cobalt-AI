from pathlib import Path
p=Path('/tmp/shutter-curves/solution/reference.py')
s=p.read_text()
s=s.replace('    knots = {tick for row in rows for tick, _ in row.get("profile", ())[1:-1]}','    knots = {mark[0] for row in rows for mark in row.get("curve", row.get("profile", ()))[1:-1]}')
a=s.index('def coefficients(')
b=s.index('def compress(',a)
s=s[:a]+'''def coefficients(z):
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


'''+s[b:]
s=s.replace('leggauss(12)','leggauss(16)')
a=s.index('        adjacent =',s.index('    def open('))
b=s.index('        self.mean =',a)
s=s[:a]+'''        if "curve" in row:
            marks = row["curve"]
            pieces = [(a,b,u,w,v) for (a,u,w),(b,v,*_) in zip(marks,marks[1:])]
        else:
            pieces = [(a,b,u,(u+v)/2,v) for (a,u),(b,v) in zip(profile,profile[1:])]
        area = math.fsum((b-a)*(u+w+v)/3 for a,b,u,w,v in pieces)
        self.active.append((index, [(a,b,u/area,w/area,v/area) for a,b,u,w,v in pieces]))
'''+s[b:]
a=s.index('        weights = []',s.index('    def advance('))
b=s.index('        m = self.mean',a)
s=s[:a]+'''        weights = []
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

'''+s[b:]
a=s.index('        added =',s.index('    def advance('))
b=s.index('            m[:, 2:] +=',a)
s=s[:a]+'''        added = 4 if has_exposure else 1
        extended = np.zeros((LANES, dim, dim + added), dtype=f.dtype)
        extended[:, :, :dim] = f
        extended[:, 0, :dim] *= decay[:, None]
        extended[:, 0, dim] = noise_factor[:, 0, 0]
        if has_exposure:
            weights = np.asarray(weights)
            weight = moments @ weights.T
            extended[:, 2:, dim:] = weights @ noise_factor[:, 1:]
'''+s[b:]
p.write_text(s)
