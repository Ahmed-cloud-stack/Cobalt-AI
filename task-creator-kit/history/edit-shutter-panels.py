from pathlib import Path
p=Path('/tmp/shutter-panels/solution/reference.py')
s=p.read_text()
s=s.replace('target = (index, value) if row.get("audit") else None','target = (index, value, row.get("panel")) if row.get("audit") else None')
s=s.replace('def audits(self):','def audits(self, panels):').replace('        results = {}\n        for operation','        results = {}\n        pending = {}\n        for operation')
s=s.replace('                information = information[:, :-1]','                information = information[:, :-1]\n                pending = {i: cross[:, :-1] for i, cross in pending.items()}')
s=s.replace('                information = np.insert(information, state, 0, axis=1)','                information = np.insert(information, state, 0, axis=1)\n                pending = {i: np.insert(cross, state, 0, axis=1) for i, cross in pending.items()}')
s=s.replace('                information[:, 0] = np.sum(column[:, :, None] * information, axis=1)','                information[:, 0] = np.sum(column[:, :, None] * information, axis=1)\n                for cross in pending.values():\n                    cross[:, 0] = np.sum(column * cross, axis=1)')
start=s.index('                if target is not None:',s.index('    def audits('))
end=s.index('                mean_score = mean_score -',start)
s=s[:start]+'''                if target is not None:
                    index, value, panel = target
                    if panel is None:
                        results[index] = value + score / precision, 1 / precision
                    else:
                        members, scores, entries = panels[panel]
                        scores[index] = value, score
                        entries[index, index] = precision
                        for other, cross in pending.items():
                            entries[index, other] = entries[other, index] = np.sum(gain * cross, axis=1)
                        if len(scores) == len(members):
                            matrix = np.array([[entries[i, j] for j in members] for i in members],
                                              dtype=complex).transpose(2, 0, 1)
                            covariance = np.linalg.inv(matrix)
                            residuals = np.array([scores[i][1] for i in members], dtype=complex).T
                            means = (covariance @ residuals[:, :, None])[:, :, 0]
                            for i, axis in zip(members, range(len(members))):
                                results[i] = scores[i][0] + means[:, axis], covariance[:, axis, axis]
                            pending.clear()
                            del panels[panel]
                for cross in pending.values():
                    cross -= np.sum(cross * gain, axis=1)[:, None] * projection
                if target is not None and target[2] in panels:
                    pending[index] = np.sum(information * j_gain[:, None, :], axis=2) - precision[:, None] * projection
'''+s[end:]
s=s.replace('        return [{"row": key, **results[key]} for key in sorted(results)]','''        return [{"row": index, "mean": float(center[0].real), "variance": float(uncertainty[0].real),
                 "mean_gradient": {f"log_{key}": float(center[i + 1].imag / STEP)
                                   for i, key in enumerate(PARAMETERS)},
                 "log_variance_gradient": {f"log_{key}": float(uncertainty[i + 1].imag / STEP / uncertainty[0].real)
                                            for i, key in enumerate(PARAMETERS)}}
                for index, (center, uncertainty) in sorted(results.items())]''')
s=s.replace('    likelihood = model.log_likelihood','''    panels = {}
    for index, row in enumerate(rows):
        if "panel" in row:
            panels.setdefault(row["panel"], ([], {}, {}))[0].append(index)
    likelihood = model.log_likelihood''')
s=s.replace('model.audits()', 'model.audits(panels)')
p.write_text(s)
p=Path('/tmp/shutter-panels/tests/dense.py')
s=p.read_text().replace('    ordered = sorted(enumerate(rows), key=lambda pair: (pair[0] == audit, pair[1]["end"], pair[0]))','    excluded = audit if isinstance(audit, tuple) else (audit,)\n    ordered = sorted(enumerate(rows), key=lambda pair: (pair[0] in excluded, pair[1]["end"], pair[0]))')
s=s.replace('        if y is None:', '        if y is None or index in excluded:')
s=s.replace('        audits = []\n','''        panels = {}
        for j, row in enumerate(rows):
            if "panel" in row:
                panels.setdefault(row["panel"], []).append(j)
        exclusions = [tuple(panels[row["panel"]]) if "panel" in row else (j,)
                      for j, row in enumerate(rows)]
        audits = []
''')
s=s.replace('forecasts(rows, p, j)', 'forecasts(rows, p, exclusions[j])').replace('forecasts(rows, plus, j)', 'forecasts(rows, plus, exclusions[j])').replace('forecasts(rows, minus, j)', 'forecasts(rows, minus, exclusions[j])')
p.write_text(s)
