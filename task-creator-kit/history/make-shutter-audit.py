from pathlib import Path
from difflib import unified_diff
root=Path("/tmp/shutter-audit")
p=root/"solution/reference.py"
s=p.read_text()
s=s.replace('    def __init__(self, config):','    def __init__(self, config, auditing):\n        self.history = [] if auditing else None')
s=s.replace('    def open(self, index, row):','    def open(self, index, row):\n        if self.history is not None:\n            self.history.append(("open",))')
s=s.replace('    def close(self, state):','    def close(self, state):\n        if self.history is not None:\n            self.history.append(("close", state))')
s=s.replace('        m[:, 0] *= decay','''        if self.history is not None:
            column = np.zeros(m.shape, dtype=complex)
            column[:, 0] = decay
            if has_exposure:
                column[:, 2:] = weight
            self.history.append(("step", column))
        m[:, 0] *= decay''')
src='            self.mean = self.mean + joint[:, 1:, 0] * (residual / joint[:, 0, 0])[:, None]'
s=s.replace(src,src+'''
            if self.history is not None:
                projection = np.zeros(dim)
                projection[state], projection[1] = gain, loading
                kalman_gain = joint[:, 1:, 0] / joint[:, :1, 0]
                target = (index, value) if row.get("audit") else None
                self.history.append(("reading", projection, kalman_gain, residual, variance, target))''')
s=s.replace('\n\ndef render(request):','''

    def audits(self):
        mean_score = np.zeros_like(self.mean)
        information = np.zeros_like(self.factor)
        results = {}
        for operation, *data in reversed(self.history or ()):
            if operation == "open":
                mean_score = mean_score[:, :-1]
                information = information[:, :-1, :-1]
            elif operation == "close":
                state, = data
                mean_score = np.insert(mean_score, state, 0, axis=1)
                information = np.insert(np.insert(information, state, 0, axis=1), state, 0, axis=2)
            elif operation == "step":
                column, = data
                transition = np.broadcast_to(np.eye(column.shape[1]), information.shape).astype(complex)
                transition[:, :, 0] = column
                transpose = transition.transpose(0, 2, 1)
                mean_score = (transpose @ mean_score[:, :, None])[:, :, 0]
                information = transpose @ information @ transition
            else:
                projection, gain, residual, variance, target = data
                j_gain = (information @ gain[:, :, None])[:, :, 0]
                score = np.sum(mean_score * gain, axis=1) - residual / variance
                precision = 1 / variance + np.sum(gain * j_gain, axis=1)
                if target is not None:
                    index, value = target
                    center, uncertainty = value + score / precision, 1 / precision
                    results[index] = {
                        "mean": float(center[0].real),
                        "variance": float(uncertainty[0].real),
                        "mean_gradient": {f"log_{key}": float(center[i + 1].imag / STEP)
                                          for i, key in enumerate(PARAMETERS)},
                        "log_variance_gradient": {
                            f"log_{key}": float(uncertainty[i + 1].imag / STEP / uncertainty[0].real)
                            for i, key in enumerate(PARAMETERS)},
                    }
                change = np.eye(len(projection)) - gain[:, :, None] * projection
                transpose = change.transpose(0, 2, 1)
                mean_score = mean_score - score[:, None] * projection
                information = transpose @ information @ change + np.outer(projection, projection) / variance[:, None, None]
        return [{"row": key, **results[key]} for key in sorted(results)]


def render(request):''')
s=s.replace('model = Filter(request["parameters"])','model = Filter(request["parameters"], any(row.get("audit") for row in rows))')
s=s.replace('for i, key in enumerate(PARAMETERS)}, "forecasts": predictions}','for i, key in enumerate(PARAMETERS)}, "forecasts": predictions, "audits": model.audits()}')
p.write_text(s)
old=(root/"tests/original.py.txt").read_text()
diff=list(unified_diff(old.splitlines(),s.splitlines(),n=0))[2:]
print(sum(row.startswith(("+","-")) for row in diff))
