"""Deterministic held-out drawings and an independent measurement check."""
import itertools
import random
from fractions import Fraction as Q


def layer(material, *paths, rule="nonzero"):
    return {"material": material, "rule": rule, "paths": paths}


def drawing(*layers):
    return {"layers": layers}


def rect(x, y, w, h):
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


def examples():
    yield "empty", drawing(layer("red", [], [(1, 2)], [(1, 0), (0, 0)]))
    yield "shared-edge", drawing(layer("red", rect(0, 0, 2, 2)),
                                 layer("blue", rect(2, 0, 1, 2)))
    yield "point-contact", drawing(layer("red", rect(0, 0, 2, 2), rect(2, 2, 2, 2)))
    yield "touching-hole", drawing(layer("red", rect(0, 0, 8, 8)),
                                   layer(None, [(0, 4), (3, 2), (5, 4), (3, 6)]))
    yield "bow-tie", drawing(layer("red", [(0, 0), (5, 4), (0, 4), (4, 0)]))
    twice = rect(1, 1, 2, 2)
    yield "winding", drawing(layer("gold", rect(-1, -1, 8, 8)),
                             layer("coal", twice, twice, rect(2, 0, 2, 5), rule="evenodd"),
                             layer(None, rect(0, 2, 5, 2), rect(0, 3, 5, 2)[::-1]),
                             layer("gold", rect(0, 0, 1, 8)))
    yield "seams", drawing(layer("eel", rect(0, 0, 6, 3)),
                           layer("ant", rect(0, 3, 2, 1), rect(4, 3, 2, 1)),
                           layer("bee", rect(2, 3, 2, 1)),
                           layer("eel", rect(5, 1, 1, 2)))
    yield "overlap-retracing", drawing(
        layer("o", [(0, 0), (9, 0), (5, 0), (9, 0), (9, 5), (0, 5), (0, 0), (0, 0)]),
        layer("a", [(2, 1), (4, 3), (6, 5), (8, 4)], [(3, 2), (5, 4), (1, 4)]),
        layer("o", [(3, 2), (4, 3), (5, 4), (5, 5), (3, 5)]))
    n = 10**9 - 5
    yield "near-coincident", drawing(
        layer("lower", [(0, 0), (n, n - 1), (n, n)]),
        layer("upper", [(0, 0), (n - 1, n - 2), (n, n - 2), (n, n - 1)]),
        layer(None, [(1, 0), (n, n - 2), (n - 1, n - 1)]))
    yield "material-stack", drawing(
        layer("a", rect(-20, -20, 40, 40)),
        layer("b", rect(-15, -15, 30, 30)),
        layer(None, rect(-12, -12, 24, 24), rect(-6, -6, 12, 12), rule="evenodd"),
        layer("a", rect(-13, -2, 26, 4)),
        layer("b", rect(-8, -1, 16, 2)),
        layer("c", rect(-1, -18, 2, 36)),
        layer(None, rect(-2, -4, 4, 8)),
        layer("a", rect(-3, -3, 6, 6)))
    yield "layer-reversal", drawing(
        layer("a", [(1, 3), (9, 3), (3, -3), (3, 8), (7, 0), (-4, 0)]),
        layer("b", [(-1, 2), (7, 3), (0, 0), (8, -9), (8, 8)], rule="evenodd"),
        layer("a", [(3, 0), (3, 8), (3, -3)]))
    rng = random.Random(719044)
    for i in range(20):
        layers = []
        for _ in range(rng.randint(1, 5)):
            paths = []
            for _ in range(rng.randint(1, 3)):
                if rng.randrange(3) == 0:
                    path = rect(rng.randrange(-6, 5), rng.randrange(-6, 5),
                                rng.randrange(1, 8), rng.randrange(1, 8))
                else:
                    path = [(rng.randrange(-7, 8), rng.randrange(-7, 8))
                            for _ in range(rng.randrange(3, 9))]
                paths.append(path if rng.randrange(2) else path[::-1])
                if rng.randrange(8) == 0:
                    paths.append(paths[-1])
            layers.append(layer(rng.choice(["a", "b", "a", "c", None]), *paths,
                                rule=rng.choice(["evenodd", "nonzero"])))
        yield f"mixed-{i:02}", drawing(*layers)


def stress():
    # 16,000 segments. Tiles are separated on both axes, but each presents
    # overlaps, winding, erasure, reappearance of a material, and point contacts.
    groups = [[], [], [], []]
    for k in range(1000):
        x, y = 11 * k, 13 * k
        for group, path in zip(groups, tile_paths(x, y)):
            group.append(path)
    return drawing(layer("z", *groups[0]), layer("a", *groups[1], rule="evenodd"),
                   layer(None, *groups[2]), layer("z", *groups[3]))


def tile_paths(x, y):
    return (rect(x, y, 7, 7), rect(x + 2, y + 2, 4, 4),
            [(x + 3, y + 1), (x + 6, y + 3), (x + 2, y + 6), (x + 1, y + 3)],
            rect(x + 5, y + 5, 3, 2))


def independent_measurements(data):
    """Integrate affine vertical bands; no segment arrangement or face walks."""
    lines = []
    cuts = set()
    for k, item in enumerate(data["layers"]):
        for path in item["paths"]:
            for (x, y), (u, v) in zip(path, path[1:] + path[:1]):
                cuts.update((x, u))
                if u != x:
                    slope = Q(v - y, u - x)
                    lines.append((min(x, u), max(x, u), slope, y - slope * x,
                                  k, 1 if u > x else -1))
    for first, second in itertools.combinations(lines, 2):
        a, b, m, n, _, _ = first
        c, d, p, q, _, _ = second
        if m != p:
            x = (q - n) / (m - p)
            if max(a, c) < x < min(b, d):
                cuts.add(x)
    totals = {}

    def integrate(lo, hi, coefficients):
        return sum(c * (hi ** (i + 1) - lo ** (i + 1)) / (i + 1)
                   for i, c in enumerate(coefficients))

    ordered = sorted(cuts)
    for lo, hi in zip(ordered, ordered[1:]):
        lo, hi = Q(lo), Q(hi)
        mid = (lo + hi) / 2
        bands = {}
        for a, b, m, n, k, sign in lines:
            if a < mid < b:
                bands.setdefault((m * mid + n, m, n), []).append((k, sign))
        winding = [0] * len(data["layers"])
        previous = None
        for current, changes in sorted(bands.items()):
            if previous is not None:
                for k in range(len(winding) - 1, -1, -1):
                    item = data["layers"][k]
                    count = winding[k] if item["rule"] == "nonzero" else winding[k] % 2
                    if count:
                        if item["material"] is not None:
                            _, a, b = previous
                            _, c, d = current
                            measurements = totals.setdefault(item["material"], [0, 0, 0])
                            measurements[0] += integrate(lo, hi, [d - b, c - a])
                            measurements[1] += integrate(lo, hi, [0, d - b, c - a])
                            measurements[2] += integrate(lo, hi,
                                [d*d - b*b, 2*(c*d - a*b), c*c - a*a]) / 2
                        break
            previous = current
            for k, sign in changes:
                winding[k] += sign
    return {name: (str(area), [str(mx / area), str(my / area)])
            for name, (area, mx, my) in totals.items()}



def histories():
    yield "empty-history", {"layers": [], "revisions": []}
    yield "no-footprint", {"layers": [layer("a", [])], "revisions": [
        {"parent": 0, "layer": 0, "paint": False},
        {"parent": 0, "layer": 0, "paint": None},
        {"parent": 1, "layer": 0, "paint": "c"},
    ]}
    layers = [
        layer("a", rect(0, 0, 10, 10)),
        layer(None, rect(3, 2, 8, 7)),
        layer("b", [(1, 1), (3, 9), (8, 3), (8, 8), (9, 2)], rule="evenodd"),
        layer("a", rect(4, 1, 2, 9)),
    ]
    actions = [(0, 1, False), (0, 1, "a"), (1, 1, None), (2, 3, "c"),
               (3, 0, None), (1, 1, False), (4, 2, False), (2, 1, "d"),
               (5, 2, "c"), (7, 3, False), (0, 0, "a"), (10, 3, None)]
    yield "branch-rollback", {"layers": layers, "revisions": [
        {"parent": p, "layer": k, "paint": m} for p, k, m in actions
    ]}
    rng = random.Random(6509321)
    for name, base in itertools.islice(examples(), 10, 17):
        history = []
        for i in range(25):
            history.append({"parent": rng.randrange(i + 1),
                            "layer": rng.randrange(len(base["layers"])),
                            "paint": rng.choice([False, None, "a", "b", "extra"])})
        yield "edit-" + name, dict(base, revisions=history)


def history_stress():
    layers = []
    for tile in range(1000):
        for paint, path, rule in zip(("z", "a", None, "z"), tile_paths(11 * tile, 13 * tile),
                                     ("nonzero", "evenodd", "nonzero", "nonzero")):
            layers.append(layer(paint, path, rule=rule))
    rng = random.Random(37477880)
    history = []
    for i in range(6000):
        parent = i if i < 1500 or i % 5 == 1 else rng.randrange(i + 1)
        index = rng.randrange(4000)
        history.append({"parent": parent, "layer": index,
                        "paint": rng.choice([False, None, "z", "a", "b", "c"])})
    return dict(drawing(*layers), revisions=history)


RAIL_LENGTH = 4500
RAIL_PATCHES = 1500


def rail_transform(s, t):
    return 4 * s + t, 3 * s + 2 * t


def rail_limits(patch):
    return ((0, 5), (1, 4), (0, 4), (1, 5))[patch % 4]


def rail_stress():
    def shape(s, t, width, height):
        return [rail_transform(x, y) for x, y in rect(s, t, width, height)]

    layers = [layer("a", shape(0, 0, RAIL_LENGTH, 5))]
    for patch in range(RAIL_PATCHES):
        lo, hi = rail_limits(patch)
        paint = (None, None, "b", "a")[patch % 4]
        layers.append(layer(paint, shape(3 * patch + 1, lo, 1, hi - lo)))
    rng = random.Random(71802023)
    revisions = [
        {"parent": i if i < 1800 or i % 5 == 0 else rng.randrange(i + 1),
         "layer": 1 + rng.randrange(RAIL_PATCHES),
         "paint": rng.choice([None, False, "a", "b"])}
        for i in range(6000)
    ]
    return dict(drawing(*layers), revisions=revisions)


def fan_stress():
    radius = 100
    corners = list(range(-radius, radius))
    ring = ([(x, -radius) for x in corners] + [(radius, y) for y in corners] +
            [(-x, radius) for x in corners] + [(-radius, -y) for y in corners])
    layers = [layer(("a", "a", "b", None, "c", "a", "b")[i % 7], [(0, 0), p, ring[(i + 1) % len(ring)]])
              for i, p in enumerate(ring)]
    rng = random.Random(690400024)
    edits = [{"parent": i if i < 500 else rng.randrange(i + 1), "layer": rng.randrange(len(ring)),
              "paint": rng.choice([False, None, "a", "b", "c"])}
             for i in range(1000)]
    return dict(drawing(*layers), revisions=edits)


def landmark(point, heading):
    return {"point": tuple(map(str, point)), "heading": heading}


def probe_histories():
    ra = rect(0, 0, 8, 8)
    inner = rect(2, 2, 4, 4)
    layers = [layer("base", ra),
              layer("red", inner, inner, rect(2, 2, 1, 1), rule="evenodd"),
              layer(None, rect(3, 3, 2, 2), rect(3, 3, 2, 2))]
    probes = [landmark((0, Q(3, 2)), (0, -1)), landmark((3, 0), (1, 0)),
              landmark((2, 2), (1, 0)), landmark((2, 2), (0, 1)),
              landmark((3, 3), (1, 0)), landmark((3, 3), (0, 1)),
              landmark((6, 6), (0, 1)), landmark((2, 2), (1, 1)),
              landmark((Q(5, 2), 2), (-1, 0)), landmark((2, 6), (1, 0))]
    definitions = [
        (0, 1, False, "nonzero"), (1, 1, "red", None), (0, 1, "red", None),
        (0, 2, None, "evenodd"), (2, 2, None, "evenodd"), (5, 2, "red", "nonzero"),
        (5, 1, None, "evenodd"), (6, 1, "green", "evenodd"), (3, 0, False, None),
        (7, 0, None, None), (6, 2, False, "evenodd"), (11, 2, "blue", None),
        (11, 2, "blue", "nonzero"), (13, 0, "blue", None),
    ]
    queries = [(0, 1), (2, 3), (4, 5), (5, 2), (6, 7), (7, 7), (8, 9), (3, 9)]
    revisions = [dict({"parent": p, "layer": k, "paint": m, "queries": queries},
                      **({"rule": r} if r is not None else {})) for p, k, m, r in definitions]
    revisions.append({"parent": 0, "layer": 0, "paint": "base", "queries": []})
    yield "rule-inheritance", dict(drawing(*layers), probes=probes, revisions=revisions)

    paths = [[(0, 0), (5, 4), (0, 4), (4, 0)]]
    cuts = [(Q(20, 9), Q(16, 9)), (Q(5, 2), 2), (0, 0), (0, 4)]
    rays = [(5, 4), (-5, -4), (1, -1), (-1, 1), (1, 0), (0, 1)]
    probes = [landmark(point, heading) for point in cuts for heading in rays]
    queries = [(i, j) for i in range(len(probes)) for j in (0, i, (i + 5) % len(probes))]
    edits = [{"parent": 0, "layer": 1, "paint": False, "queries": queries},
             {"parent": 0, "layer": 1, "paint": None, "queries": queries},
             {"parent": 2, "layer": 1, "paint": "ink", "queries": queries},
             {"parent": 3, "layer": 0, "paint": "upper", "queries": queries}]
    yield "fractional-probes", dict(drawing(layer("ink", *paths),
                                          layer(None, rect(2, 1, 1, 2))),
                                   probes=probes, revisions=edits)
    yield "probes-on-empty", dict(drawing(layer("a", [])),
                                  probes=[landmark((0, 0), (1, 0))],
                                  revisions=[{"parent": 0, "layer": 0, "paint": "a",
                                              "queries": [(0, 0)]}])


def rail_with_probes():
    data = rail_stress()
    marks = []
    for patch in range(RAIL_PATCHES):
        lo, hi = rail_limits(patch)
        s = 3 * patch + 1
        t = Q(lo + hi, 2)
        marks.extend([
            landmark(rail_transform(s - Q(1, 2), 0), (4, 3)),
            landmark(rail_transform(s + Q(3, 2), 0), (4, 3)),
            landmark(rail_transform(s, t), (1, 2)),
            landmark(rail_transform(s + 1, t), (-1, -2)),
            landmark(rail_transform(s, t), (-1, -2)),
        ])
    data["probes"] = marks
    rng = random.Random(962054)
    for edit in data["revisions"]:
        k = 5 * (edit["layer"] - 1)
        target = 5 * rng.randrange(RAIL_PATCHES)
        edit["queries"] = [(k, k + 1), (k + 2, k + 3), (k + 4, target + 4),
                           (k + rng.randrange(5), target + rng.randrange(5))]
    return data


DENSE_TILES = 350


def dense_tile(x, y):
    base = rect(x, y, 14, 14)
    return [
        layer("a", base),
        *(layer("b", rect(x + offset, y + 1, 1, 12)) for offset in (2, 5, 8)),
        layer(None, rect(x + 1, y + 3, 12, 1)),
        layer("c", rect(x + 1, y + 7, 12, 1)),
        layer("mask", base, base, rule="evenodd"),
    ]


def dense_markers(x, y):
    return [
        landmark((x, y + 1), (0, -1)),
        landmark((x + 7, y), (1, 0)),
        landmark((x + 2, y + 3), (0, 1)),
        landmark((x + 2, y + 3), (1, 0)),
    ]


def dense_edits():
    layers = []
    probes = []
    for tile in range(DENSE_TILES):
        x, y = 23 * tile, 27 * tile
        layers.extend(dense_tile(x, y))
        probes.extend(dense_markers(x, y))
    rng = random.Random(10058440)
    revisions = []
    for i in range(4100):
        tile = rng.randrange(DENSE_TILES)
        other = rng.randrange(DENSE_TILES)
        parent = i if i < 1300 or i % 3 == 1 else rng.randrange(i + 1)
        edit = {"parent": parent, "layer": 7 * tile + 6,
                "paint": rng.choice(["a", "mask", None, False]),
                "queries": [(4 * tile, 4 * tile + 1), (4 * tile + 2, 4 * tile + 3),
                            (4 * tile + 2, 4 * other + 3)]}
        if i % 7:
            edit["rule"] = rng.choice(["nonzero", "evenodd"])
        revisions.append(edit)
    return dict(drawing(*layers), probes=probes, revisions=revisions)


def narrow_tiles():
    from math import isqrt

    def prime(n):
        return not any(n % d == 0 for d in range(2, isqrt(n) + 1))

    widths = itertools.islice((p for p in range(100001, 120001, 2) if prime(p)), 740)
    base, masks, tile_data = [], [], []
    for k, width in enumerate(widths):
        x, y = 140003 * k, 140009 * k
        base.append([(x, y), (x + width, y), (x + width, y + 1)])
        masks.append(rect(x + 1, y - 1, width + 1, 3))
        tile_data.append((x, y, width))
    assert len(tile_data) == 740
    return drawing(layer("ink", *base), layer(None, *masks)), tile_data


def patch_cases():
    outer = [(0, 0), (8, -5), (8, 7)]
    cut = [(0, 0), (5, -1), (4, 2)]
    for i, (dx, dy) in enumerate(((0, 0), (-19, 6), (37, -21), (-9, -31))):
        a = [(x + dx, y + dy) for x, y in outer]
        b = [(x + dx, y + dy) for x, y in cut]
        yield f"pinched-anchor-{i}", drawing(layer("ink", a), layer(None, b))

    # The two walks have the same anchor and leave it on different rays.
    shapes = [[(0, 0), (8, 1), (6, 4)], [(0, 0), (2, 7), (1, 9)]]
    probes = [landmark((0, 0), (8, 1)), landmark((0, 0), (2, 7)),
              landmark((1, 1), (6, 4)), landmark((0, 0), (1, 9)),
              landmark((2, 7), (-2, -7)), landmark((Q(5, 2), Q(8, 3)), (6, 4)),
              landmark((4, Q(3, 4)), (8, 1))]
    pairs = [(0, 1), (0, 5), (2, 3), (3, 4), (1, 1), (0, 3), (6, 0)]
    edits = [{"parent": 0, "layer": 1, "paint": "ink", "queries": pairs},
             {"parent": 1, "layer": 1, "paint": "yellow", "queries": pairs},
             {"parent": 1, "layer": 1, "paint": "ink", "queries": pairs},
             {"parent": 0, "layer": 0, "paint": None, "queries": pairs}]
    yield "coincident-anchors", dict(drawing(layer("ink", shapes[0]), layer("ink", shapes[1])),
                                    probes=probes, revisions=edits)
    yield "numeric-coordinate-order", drawing(layer("a", rect(9, 0, 1, 1), rect(100, 0, 1, 1),
                             rect(-11, 0, 1, 1), rect(-2, 0, 1, 1), rect(0, -100, 1, 1), rect(0, -9, 1, 1)))


    # A zero-winding trace still contributes both overlap endpoints to the arrangement.
    yield "collinear-trace", drawing(layer("a", rect(0, 0, 12, 4)),
                                     layer(None, [(2, 0), (6, 0), (2, 0)]),
                                     layer("a", [(4, 4), (10, 4)]))

    shapes = [layer("tan", rect(0, 0, 50, 5))]
    shapes.extend(layer("tan", rect(x, 0, 1, 5)) for x in range(3, 48, 4))
    marks = [landmark((x, 0), (1, 0)) for x in range(1, 50, 4)]
    rng = random.Random(748515)
    revisions = []
    for i in range(48):
        queries = [(j, len(marks) - j - 1) for j in range(len(marks))]
        revisions.append({"parent": i if i < 15 else rng.randrange(i + 1),
                          "layer": rng.randrange(1, len(shapes)),
                          "paint": rng.choice([None, None, "tan", False]),
                          "queries": queries})
    yield "split-anchors", dict(drawing(*shapes), probes=marks, revisions=revisions)


def long_ray_cases():
    yield "aligned-16000", drawing(layer("ink", *(rect(5 * k, 0, 2, 3) for k in range(4000))))
    yield "nested-16000", drawing(layer("ink", *(rect(-r, -r, 2 * r, 2 * r)
                                               for r in range(1, 4001)), rule="evenodd"))


def palette_nesting():
    layers = []
    for k, paint in enumerate(("gold", "red", "blue", "red", "gold", "green", "blue", None)):
        paths = []
        for r in range(k + 1, 4001, 8):
            ring = rect(-r, -r, 2 * r, 2 * r)
            paths.append(ring if (r - 1) // 8 % 2 == 0 else ring[::-1])
        layers.append(layer(paint, *paths, rule=("nonzero" if k % 2 else "evenodd")))
    return drawing(*layers)
