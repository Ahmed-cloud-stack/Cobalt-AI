"""Regenerate goldens after checking the reference with independent invariants."""
import json
import sys
from fractions import Fraction as Q
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "solution"))
from reference import render
from answer_digest import answer_digest
from cases import drawing, examples, rect, independent_measurements, layer, stress, tile_paths, histories, history_stress, rail_stress, rail_limits, rail_transform, fan_stress, RAIL_LENGTH, probe_histories, rail_with_probes, dense_edits, dense_markers, dense_tile, DENSE_TILES, narrow_tiles, patch_cases, long_ray_cases, palette_nesting


def measurements(answer):
    return {name: (data["area"], data["centroid"])
            for name, data in answer["materials"].items()}


def independent_goldens():
    square = [["0", "0"], ["2", "0"], ["2", "2"], ["0", "2"]]
    contact = [["2", "2"], ["4", "2"], ["4", "4"], ["2", "4"]]
    pointed_hole = [["0", "0"], ["8", "0"], ["8", "8"], ["0", "8"], ["0", "4"],
                    ["3", "6"], ["5", "4"], ["3", "2"], ["0", "4"]]
    return {
        "empty": {"materials": {}, "interfaces": []},
        "point-contact": {
            "materials": {"red": {"area": "8", "centroid": ["2", "2"],
                                  "rings": [square, contact]}},
            "interfaces": [{"pair": [None, "red"], "length": "16"}],
        },
        "touching-hole": {
            "materials": {"red": {"area": "54", "centroid": ["344/81", "4"],
                                  "rings": [pointed_hole]}},
            "interfaces": [{"pair": [None, "red"], "length": "50"}],
        },
    }


def audit_small_history(source, answer):
    plain = source["layers"]
    versions = [[item["material"] for item in plain]]
    assert len(answer["revisions"]) == len(source["revisions"])
    for revision, actual in zip(source["revisions"], answer["revisions"]):
        paints = versions[revision["parent"]].copy()
        paints[revision["layer"]] = revision["paint"]
        versions.append(paints)
        static = drawing(*(dict(item, material=p) for item, p in zip(plain, paints)
                           if p is not False))
        expected = render(static)
        for details in expected["materials"].values():
            details["ring_count"] = len(details.pop("rings"))
        assert actual == expected, (revision, actual, expected)


def audit_large_history(source, answer):
    rng = len(source["layers"]) // 4
    shapes = tile_paths(0, 0)
    base = ("z", "a", None, "z")

    @lru_cache(maxsize=None)
    def tile_result(paints):
        template = tuple(layer(p, path, rule=rule)
                         for p, path, rule in zip(paints, shapes,
                             ("nonzero", "evenodd", "nonzero", "nonzero"))
                         if p is not False)
        sample = drawing(*template)
        known = render(sample)
        assert measurements(known) == independent_measurements(sample)
        return known

    def apply(paints, tile, sign, masses, lengths):
        sampled = tile_result(paints)
        for name, data in sampled["materials"].items():
            area = Q(data["area"]) * sign
            x, y = map(Q, data["centroid"])
            ma, mx, my, count = masses.get(name, (0, 0, 0, 0))
            masses[name] = (ma + area, mx + area * (x + 11 * tile),
                            my + area * (y + 13 * tile), count + sign * len(data["rings"]))
        for entry in sampled["interfaces"]:
            key = tuple(entry["pair"])
            lengths[key] = lengths.get(key, 0) + sign * Q(entry["length"])

    masses, lengths = {}, {}
    for tile in range(rng):
        apply(base, tile, 1, masses, lengths)
    states, totals = [[base] * rng], [(masses, lengths)]
    for edit, actual in zip(source["revisions"], answer["revisions"], strict=True):
        tile, local = divmod(edit["layer"], 4)
        paints = states[edit["parent"]].copy()
        masses, lengths = (m.copy() for m in totals[edit["parent"]])
        previous = paints[tile]
        changed = list(previous)
        changed[local] = edit["paint"]
        paints[tile] = tuple(changed)
        apply(previous, tile, -1, masses, lengths)
        apply(paints[tile], tile, 1, masses, lengths)
        states.append(paints)
        totals.append((masses, lengths))
        expected = {
            "materials": {
                name: {"area": str(area), "centroid": [str(x / area), str(y / area)], "ring_count": count}
                for name, (area, x, y, count) in masses.items() if area
            },
            "interfaces": [{"pair": list(key), "length": str(lengths[key])}
                           for key in sorted(lengths, key=lambda p: tuple(x or "" for x in p))
                           if lengths[key]],
        }
        assert actual == expected, (edit, actual, expected)


def audit_rail(source, answer):
    area = 25 * RAIL_LENGTH
    xc, yc = rail_transform(Q(RAIL_LENGTH, 2), Q(5, 2))
    initial = [area, area * xc, area * yc, 1, 0, 0, 0, 0,
               2 * (7 * RAIL_LENGTH + 15), 0, 0]

    def apply(stats, patch, paint, factor):
        if paint is False or paint == "a":
            return
        lo, hi = rail_limits(patch)
        h = hi - lo
        area = 5 * h
        x, y = rail_transform(Q(6 * patch + 3, 2), Q(lo + hi, 2))
        exposed = 7 * ((lo == 0) + (hi == 5))
        interior = 2 * (7 + 3 * h) - exposed
        vector = [-area, -area * x, -area * y, int(exposed != 7),
                  0, 0, 0, 0, -exposed, 0, 0]
        if paint == "b":
            vector[4:8] = [area, area * x, area * y, 1]
            vector[9:11] = [exposed, interior]
        else:
            vector[8] += interior
        for i, value in enumerate(vector):
            stats[i] += factor * value

    def summarize(stats):
        materials = {}
        for paint, offset in (("a", 0), ("b", 4)):
            area, x, y, count = stats[offset:offset + 4]
            if area:
                materials[paint] = {"area": str(area), "centroid": [str(Q(x, area)), str(Q(y, area))],
                                    "ring_count": count}
        pairs = ((None, "a"), (None, "b"), ("a", "b"))
        return {"materials": materials,
                "interfaces": [{"pair": list(pair), "length": str(length)}
                               for pair, length in zip(pairs, stats[8:]) if length]}

    paints = [item["material"] for item in source["layers"][1:]]
    for patch, paint in enumerate(paints):
        apply(initial, patch, paint, 1)
    base = {"materials": {name: dict({k: v for k, v in record.items() if k != "rings"},
                                    ring_count=len(record["rings"]))
                         for name, record in answer["materials"].items()},
            "interfaces": answer["interfaces"]}
    assert summarize(initial) == base
    histories = [(paints, initial)]
    for edit, got in zip(source["revisions"], answer["revisions"], strict=True):
        paints, stats = (data.copy() for data in histories[edit["parent"]])
        patch = edit["layer"] - 1
        apply(stats, patch, paints[patch], -1)
        paints[patch] = edit["paint"]
        apply(stats, patch, paints[patch], 1)
        histories.append((paints, stats))
        expected = summarize(stats)
        if "queries" in edit:
            expected["queries"] = check_rail_queries(paints, edit["queries"])
        assert expected == got, (edit, expected, got)


def audit_fan(source, answer):
    points = [item["paths"][0][1] for item in source["layers"]]
    n = len(points)
    original = [item["material"] for item in source["layers"]]
    versions = [original]
    inner_lengths = [abs(x) + abs(y) for x, y in points]
    centers = [(x + points[(i + 1) % n][0], y + points[(i + 1) % n][1])
               for i, (x, y) in enumerate(points)]

    def summarize(paints):
        sums = {}
        lengths = {}
        for i, paint in enumerate(paints):
            other = paints[i - 1]
            if paint is not None:
                count, x, y, runs = sums.get(paint, (0, 0, 0, 0))
                a, b = centers[i]
                sums[paint] = count + 1, x + a, y + b, runs + (other != paint)
                lengths[None, paint] = lengths.get((None, paint), 0) + 1
            if paint != other:
                pair = tuple(sorted((paint, other), key=lambda p: p or ""))
                lengths[pair] = lengths.get(pair, 0) + inner_lengths[i]
        return {"materials": {
                paint: {"area": str(50 * count), "centroid": [str(Q(x, 3 * count)), str(Q(y, 3 * count))],
                        "ring_count": max(1, runs)}
                for paint, (count, x, y, runs) in sums.items()},
                "interfaces": [{"pair": list(pair), "length": str(lengths[pair])}
                               for pair in sorted(lengths, key=lambda p: tuple(x or "" for x in p))]}

    base = {"materials": {name: dict({k: v for k, v in record.items() if k != "rings"},
                                    ring_count=len(record["rings"]))
                         for name, record in answer["materials"].items()},
            "interfaces": answer["interfaces"]}
    assert summarize(original) == base
    for edit, got in zip(source["revisions"], answer["revisions"], strict=True):
        paints = versions[edit["parent"]].copy()
        paints[edit["layer"]] = edit["paint"] or None
        versions.append(paints)
        assert summarize(paints) == got, (edit, summarize(paints), got)


def audit_probe_queries(source, answer):
    versions = [[(item["material"], item["rule"]) for item in source["layers"]]]
    for edit, actual in zip(source["revisions"], answer["revisions"], strict=True):
        version = versions[edit["parent"]].copy()
        k = edit["layer"]
        version[k] = edit["paint"], edit.get("rule", version[k][1])
        versions.append(version)
        static = render(drawing(*(dict(item, material=paint, rule=rule)
                                 for item, (paint, rule) in zip(source["layers"], version)
                                 if paint is not False)))
        marks = [query_walk(static, marker) for marker in source["probes"]]
        expected = [report_pair(marks[a], marks[b]) for a, b in edit["queries"]]
        for entry in static["materials"].values():
            entry["ring_count"] = len(entry.pop("rings"))
        static["queries"] = expected
        assert static == actual, (edit, static, actual)


def query_walk(drawing, marker):
    p = tuple(map(Q, marker["point"]))
    dx, dy = marker["heading"]
    for name, data in drawing["materials"].items():
        for i, raw in enumerate(data["rings"]):
            points = [tuple(map(Q, vertex)) for vertex in raw]
            edges = list(zip(points, points[1:] + points[:1]))
            for (x, y), (u, v) in edges:
                a, b = u - x, v - y
                if a * dy != b * dx or a * dx + b * dy <= 0:
                    continue
                s, t = p[0] - x, p[1] - y
                if a * t != b * s or not 0 <= a * s + b * t < a * a + b * b:
                    continue
                area = sum(x * v - y * u for (x, y), (u, v) in edges) / 2
                length = sum(abs(u - x) + abs(v - y) for (x, y), (u, v) in edges)
                return (name, i), {"material": name, "signed_area": str(area), "length": str(length),
                                   "anchor": raw[0]}
    return None, None


def report_pair(first, second):
    return {"first": first[1], "second": second[1],
            "same_walk": first[0] is not None and first[0] == second[0]}


def check_rail_queries(paints, queries):
    import bisect
    from itertools import accumulate

    cuts = [i for i in range(0, len(paints), 4) if paints[i] not in ("a", False)]
    prefixes = list(accumulate((i % 4 in (2, 3) and paint not in ("a", False)
                                for i, paint in enumerate(paints)), initial=0))

    @lru_cache(maxsize=None)
    def resolve(index):
        patch, direction = divmod(index, 5)
        lo, hi = rail_limits(patch)
        left = 3 * patch + 1
        paint = paints[patch]
        if direction == 4:
            if paint != "b":
                return None, None
            key, material, area, length, anchor = ("b", patch), "b", 5 * (hi - lo), \
                2 * (7 + 3 * (hi - lo)), rail_transform(left, lo)
        elif direction in (2, 3) and paint in (False, "a"):
            return None, None
        elif direction in (2, 3) and 0 < lo < hi < 5:
            key, material, area, length, anchor = ("hole", patch), "a", -5 * (hi - lo), \
                2 * (7 + 3 * (hi - lo)), rail_transform(left, lo)
        else:
            i = (bisect.bisect_right if direction in (1, 3) else bisect.bisect_left)(cuts, patch)
            previous = cuts[i - 1] if i else -1
            following = cuts[i] if i < len(cuts) else len(paints)
            start = (3 * previous + 2) if i else 0
            end = (3 * following + 1) if i < len(cuts) else RAIL_LENGTH
            notches = prefixes[following] - prefixes[previous + 1]
            key, material = ("outer", i), "a"
            area = 25 * (end - start) - 20 * notches
            length = 2 * (7 * (end - start) + 15) + 24 * notches
            anchor = rail_transform(start, 0)
        return key, {"material": material, "signed_area": str(area), "length": str(length),
                     "anchor": list(map(str, anchor))}

    return [report_pair(resolve(a), resolve(b)) for a, b in queries]


def audit_dense_edits(source, answer):
    sample = dense_tile(0, 0)
    markers = dense_markers(0, 0)
    initial = "mask", "evenodd"

    @lru_cache(maxsize=None)
    def local(state):
        paint, rule = state
        layers = sample[:-1] + ([dict(sample[-1], material=paint, rule=rule)]
                                if paint is not False else [])
        tile = drawing(*layers)
        rendered = render(tile)
        assert measurements(rendered) == independent_measurements(tile)
        return rendered, [query_walk(rendered, marker) for marker in markers]

    def apply(totals, tile, state, sign):
        masses, interfaces = totals
        rendered, _ = local(state)
        for paint, data in rendered["materials"].items():
            area = sign * Q(data["area"])
            x, y = map(Q, data["centroid"])
            count, mass, mx, my = masses.get(paint, (0, 0, 0, 0))
            masses[paint] = (count + sign * len(data["rings"]), mass + area,
                             mx + area * (x + 23 * tile), my + area * (y + 27 * tile))
        for item in rendered["interfaces"]:
            pair = tuple(item["pair"])
            interfaces[pair] = interfaces.get(pair, 0) + sign * Q(item["length"])

    def base_summary(totals):
        masses, interfaces = totals
        return {"materials": {
                    paint: {"area": str(area), "centroid": [str(mx / area), str(my / area)],
                            "ring_count": count}
                    for paint, (count, area, mx, my) in masses.items() if area
                },
                "interfaces": [{"pair": list(pair), "length": str(interfaces[pair])}
                               for pair in sorted(interfaces, key=lambda p: tuple(x or "" for x in p))
                               if interfaces[pair]]}

    def mark(states, i):
        tile, offset = divmod(i, 4)
        identity, data = local(states[tile])[1][offset]
        if data is None:
            return None, None
        x, y = map(Q, data["anchor"])
        return (tile, identity), dict(data, anchor=[str(x + 23 * tile), str(y + 27 * tile)])

    base = {}, {}
    for tile in range(DENSE_TILES):
        apply(base, tile, initial, 1)
    base_answer = {"materials": {name: dict({k: v for k, v in record.items() if k != "rings"},
                                          ring_count=len(record["rings"]))
                               for name, record in answer["materials"].items()},
                   "interfaces": answer["interfaces"]}
    assert base_summary(base) == base_answer
    versions = [([initial] * DENSE_TILES, base)]
    for edit, actual in zip(source["revisions"], answer["revisions"], strict=True):
        parent, old_totals = versions[edit["parent"]]
        states = parent.copy()
        totals = tuple(item.copy() for item in old_totals)
        tile = edit["layer"] // 7
        old = states[tile]
        states[tile] = edit["paint"], edit.get("rule", old[1])
        apply(totals, tile, old, -1)
        apply(totals, tile, states[tile], 1)
        versions.append((states, totals))
        expected = base_summary(totals)
        expected["queries"] = [report_pair(mark(states, a), mark(states, b)) for a, b in edit["queries"]]
        assert expected == actual, (edit, expected, actual)


def run():
    sys.set_int_max_str_digits(0)
    expected = {}
    fixed = independent_goldens()
    for name, data in examples():
        answer = render(data)
        assert measurements(answer) == independent_measurements(data), name
        if name in fixed:
            assert answer == fixed[name], (name, answer)
        reversed_paths = drawing(*[
            layer(item["material"], *(p[::-1] for p in reversed(item["paths"])), rule=item["rule"])
            for item in data["layers"]
        ])
        assert render(reversed_paths) == answer, name
        expected[name] = answer

    tile = tile_paths(0, 0)
    one = drawing(layer("z", tile[0]), layer("a", tile[1], rule="evenodd"),
                  layer(None, tile[2]), layer("z", tile[3]))
    one_answer = render(one)
    assert measurements(one_answer) == independent_measurements(one)
    big = render(stress())
    for name, data in one_answer["materials"].items():
        actual = big["materials"][name]
        assert Q(actual["area"]) == 1000 * Q(data["area"])
        assert list(map(Q, actual["centroid"])) == [
            Q(data["centroid"][0]) + Q(11 * 999, 2), Q(data["centroid"][1]) + Q(13 * 999, 2)
        ]
        assert len(actual["rings"]) == 1000 * len(data["rings"])
    for a, b in zip(big["interfaces"], one_answer["interfaces"], strict=True):
        assert a["pair"] == b["pair"] and Q(a["length"]) == 1000 * Q(b["length"])
    expected["sparse-16000"] = big
    for name, data in histories():
        answer = render(data)
        audit_small_history(data, answer)
        expected[name] = answer
    edited = history_stress()
    answer = render(edited)
    audit_large_history(edited, answer)
    assert {k: v for k, v in answer.items() if k != "revisions"} == big
    expected["branching-6000"] = answer
    rail = rail_with_probes()
    answer = render(rail)
    audit_rail(rail, answer)
    expected["connected-6000"] = answer
    fan = fan_stress()
    answer = render(fan)
    audit_fan(fan, answer)
    expected["high-valence"] = answer
    for name, data in probe_histories():
        answer = render(data)
        audit_probe_queries(data, answer)
        expected[name] = answer
    edited = dense_edits()
    answer = render(edited)
    audit_dense_edits(edited, answer)
    expected["dense-rule-edits"] = answer
    slender, tiles = narrow_tiles()
    answer = render(slender)
    pieces = [Q(1, 2 * width) for _, _, width in tiles]
    area = sum(pieces)
    x = sum(piece * (x + Q(2, 3)) for piece, (x, _, _) in zip(pieces, tiles)) / area
    y = sum(piece * (y + Q(1, 3 * width)) for piece, (_, y, width) in zip(pieces, tiles)) / area
    rings = [[[str(x), str(y)], [str(x + 1), str(y)],
              [str(x + 1), str(y + Q(1, width))]] for x, y, width in tiles]
    assert answer == {
        "materials": {"ink": {"area": str(area), "centroid": [str(x), str(y)], "rings": rings}},
        "interfaces": [{"pair": [None, "ink"], "length": str(2 * len(tiles) + 4 * area)}],
    }
    expected["narrow-measurements"] = answer
    for name, data in patch_cases():
        result = render(data)
        assert measurements(result) == independent_measurements(data)
        if "revisions" in data:
            audit_probe_queries(data, result)
        else:
            for details in result["materials"].values():
                for ring in details["rings"]:
                    raw = [tuple(map(Q, point)) for point in ring]
                    assert raw == min(raw[k:] + raw[:k] for k in range(len(raw)))
        expected[name] = result
    for name, data in long_ray_cases():
        result = render(data)
        if name == "aligned-16000":
            area, center, length = 24000, [str(Q(5 * 3999, 2) + 1), "3/2"], 40000
            rings = [rect(5 * k, 0, 2, 3) for k in range(4000)]
        else:
            radii = range(4000, 0, -1)
            area = sum((1 if r % 2 == 0 else -1) * (2 * r) ** 2 for r in radii)
            center, length = ["0", "0"], sum(8 * r for r in radii)
            rings = [rect(-r, -r, 2 * r, 2 * r) for r in radii]
            rings = [ring if i % 2 == 0 else ring[:1] + ring[:0:-1]
                     for i, ring in enumerate(rings)]
        formatted = [[[str(x), str(y)] for x, y in ring] for ring in rings]
        assert result == {
            "materials": {"ink": {"area": str(area), "centroid": center, "rings": formatted}},
            "interfaces": [{"pair": [None, "ink"], "length": str(length)}],
        }, name
        expected[name] = result
    palette = palette_nesting()
    result = render(palette)
    materials, interfaces = {}, {}
    inside = [False] * 8
    exterior = None
    for radius in range(4000, 0, -1):
        layer_index = (radius - 1) % 8
        inside[layer_index] = not inside[layer_index]
        last = next((i for i in range(7, -1, -1) if inside[i]), None)
        interior = palette["layers"][last]["material"] if last is not None else None
        if exterior != interior:
            pair = tuple(sorted((exterior, interior), key=lambda p: p or ""))
            interfaces[pair] = interfaces.get(pair, 0) + 8 * radius
            ring = rect(-radius, -radius, 2 * radius, 2 * radius)
            for material, sign in ((interior, 1), (exterior, -1)):
                if material is not None:
                    record = materials.setdefault(material, {"area": 0, "centroid": ["0", "0"],
                                                               "rings": []})
                    record["area"] += sign * (2 * radius) ** 2
                    points = ring if sign > 0 else ring[:1] + ring[:0:-1]
                    record["rings"].append([list(map(str, p)) for p in points])
        exterior = interior
    for record in materials.values():
        record["area"] = str(record["area"])
    assert result == {"materials": materials, "interfaces": [
        {"pair": list(pair), "length": str(interfaces[pair])}
        for pair in sorted(interfaces, key=lambda p: tuple(x or "" for x in p))
    ]}
    expected["nested-palette"] = result
    output = Path(__file__).with_name("expected_sha256.json")
    files = output.parents[1] / "environment"
    sample_answers = {name: render(json.loads((files / name).read_text(encoding="utf-8")))
                      for name in ("sample.json", "sample_history.json")}
    example = sample_answers["sample_history.json"]["revisions"]
    assert example[0]["queries"] == [{"first": None, "second": None, "same_walk": False}]
    probe = {"material": "ink", "signed_area": "2", "length": "6", "anchor": ["0", "0"]}
    assert example[1]["queries"] == [{"first": probe, "second": probe, "same_walk": True}]
    output.with_name("samples_expected.json").write_text(json.dumps(sample_answers, indent=2) + "\n",
                                                        encoding="utf-8")
    digests = {name: answer_digest(answer) for name, answer in expected.items()}
    output.write_text(json.dumps(digests, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    run()
