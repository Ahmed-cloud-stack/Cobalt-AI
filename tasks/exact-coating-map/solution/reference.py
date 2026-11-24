#!/usr/bin/env python3
"""Offline coating map renderer."""
import bisect
import json
import sys
from collections import defaultdict
from fractions import Fraction as Q
from functools import cmp_to_key


def sub(a, b):
    return a[0] - b[0], a[1] - b[1]


def cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def bounds(a, b):
    return min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])


def overlaps(a, b):
    return a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]


class Index:
    """Bounding-box hierarchy shared by segment and ray queries."""

    def __init__(self, boxes, ids):
        self.boxes = boxes
        self.box = (
            min(boxes[i][0] for i in ids), min(boxes[i][1] for i in ids),
            max(boxes[i][2] for i in ids), max(boxes[i][3] for i in ids),
        )
        self.ids = ids
        self.children = ()
        if len(ids) > 8:
            centers = [[boxes[i][a] + boxes[i][a + 2] for i in ids] for a in (0, 1)]
            spread = [max(values) - min(values) for values in centers]
            axis = int(spread[1] > spread[0])
            ids.sort(key=lambda i: boxes[i][axis] + boxes[i][axis + 2])
            middle = len(ids) // 2
            self.children = Index(boxes, ids[:middle]), Index(boxes, ids[middle:])
            self.ids = ()

    def query(self, box):
        pending = [self]
        while pending:
            node = pending.pop()
            if overlaps(node.box, box):
                pending.extend(node.children)
                for i in node.ids:
                    if overlaps(self.boxes[i], box):
                        yield i


    def ray(self, x, y, east):
        xn, xd = x.numerator, x.denominator
        yn, yd = y.numerator, y.denominator
        pending = [self]
        while pending:
            node = pending.pop()
            _, bottom, right, top = node.box
            if right * xd >= xn and bottom * yd <= yn <= top * yd:
                if node.box[0] * xd > xn and hasattr(node, "winding"):
                    for layer, (cuts, counts) in node.winding.items():
                        east[layer] += counts[bisect.bisect_right(cuts, y)]
                    continue
                pending.extend(node.children)
                for i in node.ids:
                    _, bottom, right, top = self.boxes[i]
                    if right * xd >= xn and bottom * yd <= yn <= top * yd:
                        yield i

def winding_index(edges, weights, rotated, summarize_small):
    segments = [(rotate(a), rotate(b)) if rotated else (a, b) for a, b in edges]
    ids = [i for i, (a, b) in enumerate(segments) if a[1] != b[1]]
    if not ids:
        return None
    index = Index([bounds(a, b) for a, b in segments], ids)

    def summarize(node):
        events = defaultdict(int)
        for child in node.children:
            for y, delta in summarize(child).items():
                events[y] += delta
        for i in node.ids:
            a, b = segments[i]
            for layer, weight in weights[i].items():
                events[layer, a[1]] += weight
                events[layer, b[1]] -= weight
        groups = {}
        for (layer, y), delta in sorted(events.items()):
            if delta:
                cuts, counts = groups.setdefault(layer, ([], [0]))
                cuts.append(y)
                counts.append(counts[-1] + delta)
        node.winding = groups
        return events

    if summarize_small:
        summarize(index)
    return index


def coordinate(numerator, denominator):
    value, remainder = divmod(numerator, denominator)
    return Q(numerator, denominator) if remainder else value


def split_points(a, b, c, d):
    r, s = sub(b, a), sub(d, c)
    offset = sub(c, a)
    determinant = cross(r, s)
    if determinant:
        t, u = cross(offset, s), cross(offset, r)
        if determinant < 0:
            determinant, t, u = -determinant, -t, -u
        if 0 <= t <= determinant and 0 <= u <= determinant:
            if t == 0:
                yield a
            elif t == determinant:
                yield b
            elif u == 0:
                yield c
            elif u == determinant:
                yield d
            else:
                yield (coordinate(a[0] * determinant + t * r[0], determinant),
                       coordinate(a[1] * determinant + t * r[1], determinant))
    elif cross(offset, r) == 0:
        # Endpoints of the common interval, ordered along the same line.
        low, high = max(a, c), min(b, d)
        if low <= high:
            yield low
            yield high


def rotate(point):
    return point[1], -point[0]


def stack_for(winding):
    return tuple(i + 1 if winding[i] % 2 else -i - 1
                 for i in sorted(winding, reverse=True) if winding[i])


def visible(stack, paints, rules):
    for token in stack:
        layer = abs(token) - 1
        if paints[layer] is not False and (token > 0 or rules[layer] == "nonzero"):
            return paints[layer]
    return None


def material_key(material):
    return material is not None, material or ""


def edge_sides(a, b, edges, weights, index, rotated):
    x, y = Q(a[0] + b[0], 2), Q(a[1] + b[1], 2)
    east, crossing = defaultdict(int), defaultdict(int)
    xn, xd = x.numerator, x.denominator
    yn, yd = y.numerator, y.denominator
    for i in index.ray(x, y, east):
        c, d = edges[i]
        if rotated:
            c, d = rotate(c), rotate(d)
        cy, dy = c[1] * yd, d[1] * yd
        if cy <= yn < dy:
            sign = 1
        elif dy <= yn < cy:
            sign = -1
        else:
            continue
        # Test which side of the ray origin this integer segment crosses.
        side = ((d[0] - c[0]) * (yn - cy) * xd - (dy - cy) * (xn - c[0] * xd)) * sign
        if side < 0:
            continue
        counts = crossing if side == 0 else east
        for layer, weight in weights[i].items():
            counts[layer] += sign * weight
    right_of_ray = stack_for(east)
    for layer, weight in crossing.items():
        east[layer] += weight
    left_of_ray = stack_for(east)
    if b[1] > a[1]:
        return left_of_ray, right_of_ray
    return right_of_ray, left_of_ray


def angle_compare(a, b):
    def half(v):
        return v[1] < 0 or (v[1] == 0 and v[0] < 0)

    first, second = half(a), half(b)
    if first != second:
        return first - second
    determinant = cross(a, b)
    return (determinant < 0) - (determinant > 0)


angle_key = cmp_to_key(angle_compare)


def least_rotation(sequence):
    # Two candidates for the least rotation. A mismatch rules out all
    # starts in the losing matched prefix, including repeated vertices.
    n = len(sequence)
    i, j, k = 0, 1, 0
    while i < n and j < n and k < n:
        a, b = sequence[(i + k) % n], sequence[(j + k) % n]
        if a == b:
            k += 1
            continue
        if a > b:
            i += k + 1
            if i == j:
                i += 1
        else:
            j += k + 1
            if j == i:
                j += 1
        k = 0
    start = min(i, j)
    return sequence[start:] + sequence[:start]


def rings_for(boundary):
    outgoing = defaultdict(list)
    for a, b in boundary:
        outgoing[a].append((angle_key(sub(b, a)), b))
    for arcs in outgoing.values():
        arcs.sort()
    remaining = set(boundary)
    rings = []
    while remaining:
        start = next(iter(remaining))
        a, b = start
        points = []
        while True:
            remaining.remove((a, b))
            points.append(a)
            arcs = outgoing[b]
            i = bisect.bisect_left(arcs, (angle_key(sub(a, b)),))
            a, b = b, arcs[i - 1][1]
            if (a, b) == start:
                break
        simplified = []
        for i, point in enumerate(points):
            enter = sub(point, points[i - 1])
            leave = sub(points[(i + 1) % len(points)], point)
            if cross(enter, leave) or (enter[0] * leave[0] + enter[1] * leave[1]) <= 0:
                simplified.append(point)
        rings.append(least_rotation(simplified))
    return sorted(rings)


def describe(boundary):
    rings = rings_for(boundary)
    twice_area = mx = my = 0
    for ring in rings:
        for a, b in zip(ring, ring[1:] + ring[:1]):
            determinant = cross(a, b)
            twice_area += determinant
            mx += (a[0] + b[0]) * determinant
            my += (a[1] + b[1]) * determinant
    return {
        "area": str(Q(twice_area, 2)),
        "centroid": [str(Q(moment, 3 * twice_area)) for moment in (mx, my)],
        "rings": [[[str(x), str(y)] for x, y in ring] for ring in rings],
    }


def locate_probes(geometry, probes):
    if not probes:
        return []
    if not geometry:
        return [None] * len(probes)
    boxes = [bounds(a, b) for a, b in geometry]
    index = Index(boxes, list(range(len(geometry))))
    located = []
    for probe in probes:
        p = tuple(map(Q, probe["point"]))
        heading = tuple(probe["heading"])
        forward = heading > (0, 0)
        found = None
        for i in index.query((*p, *p)):
            a, b = geometry[i]
            direction = sub(b, a)
            if (b == p if forward else a == p):
                continue
            if cross(direction, heading) == 0 and cross(direction, sub(p, a)) == 0:
                found = 2 * i + (not forward)
                break
        located.append(found)
    return located


class Topology:
    """Version intervals for the permutation links at boundary vertices."""

    def __init__(self, edges, states, paints, history):
        self.states = states
        self.labels = {p: i for i, p in enumerate(sorted(
            {p for p in paints if p is not None} |
            {edit["paint"] for edit in history if isinstance(edit["paint"], str)}))}
        self.endpoints = []
        vertices = {}
        rays = []
        for i, (a, b) in enumerate(edges):
            ends = []
            for side, (p, q) in enumerate(((a, b), (b, a))):
                if p not in vertices:
                    vertices[p] = len(rays)
                    rays.append([])
                v = vertices[p]
                rays[v].append((angle_key(sub(q, p)), 2 * i + side))
                ends.append(v)
            self.endpoints.append(tuple(ends))
        self.rays = [tuple(ray for _, ray in sorted(angles)) for angles in rays]
        self.live = [{link: 0 for link in self.links(v)} for v in range(len(rays))]
        self.intervals = []
        self.time = 0

    def links(self, vertex):
        rays = self.rays[vertex]
        clockwise = {}
        for ray in rays:
            paint = self.states[ray // 2][ray % 2]
            other = self.states[ray // 2][1 - ray % 2]
            if paint is not None and paint != other:
                clockwise[paint] = ray
        for ray in rays:
            paint = self.states[ray // 2][ray % 2]
            other = self.states[ray // 2][1 - ray % 2]
            if paint == other:
                continue
            if other is not None:
                yield self.labels[other], ray ^ 1, clockwise[other]
            if paint is not None:
                clockwise[paint] = ray

    def refresh(self, vertices):
        for v in vertices:
            live = self.live[v]
            current = {}
            for link in self.links(v):
                current[link] = live.pop(link, self.time)
            for link, start in live.items():
                if start < self.time:
                    self.intervals.append((start, self.time, link))
            self.live[v] = current

    def finish(self, snapshots, probes, geometry):
        for live in self.live:
            for link, start in live.items():
                if start < self.time:
                    self.intervals.append((start, self.time, link))
        leaves = 1 << (self.time - 1).bit_length()
        tree = [[] for _ in range(2 * leaves)]
        nodes = {}
        for start, end, (material, a, b) in self.intervals:
            a = nodes.setdefault((material, a), len(nodes))
            b = nodes.setdefault((material, b), len(nodes))
            edge = material, a, b
            start += leaves
            end += leaves
            while start < end:
                if start % 2:
                    tree[start].append(edge)
                    start += 1
                if end % 2:
                    end -= 1
                    tree[end].append(edge)
                start //= 2
                end //= 2

        aggregate = None
        if any(probes):
            aggregate = [None] * len(nodes)
            for (_, arc), node in nodes.items():
                a, b = geometry[arc // 2]
                if arc % 2:
                    a, b = b, a
                aggregate[node] = (cross(a, b), abs(b[0] - a[0]) + abs(b[1] - a[1]), a)

        parent = list(range(len(nodes)))
        size = [1] * len(nodes)
        cycles = [0] * len(self.labels)

        def root(i):
            while i != parent[i]:
                i = parent[i]
            return i

        def visit(node):
            undone = []
            for material, a, b in tree[node]:
                a, b = root(a), root(b)
                if a == b:
                    cycles[material] += 1
                    undone.append((material, -1, None))
                else:
                    if size[a] < size[b]:
                        a, b = b, a
                    parent[b] = a
                    size[a] += size[b]
                    previous = None
                    if aggregate is not None:
                        previous = aggregate[a]
                        area, length, anchor = aggregate[b]
                        p_area, p_length, p_anchor = previous
                        aggregate[a] = (p_area + area, p_length + length, min(p_anchor, anchor))
                    undone.append((a, b, previous))
            if node < leaves:
                visit(2 * node)
                visit(2 * node + 1)
            elif node - leaves < len(snapshots):
                version = node - leaves
                answer = snapshots[version]
                for material, details in answer["materials"].items():
                    details["ring_count"] = cycles[self.labels[material]]
                if probes[version] is not None:
                    def resolve(mark):
                        if mark is None:
                            return None, None
                        material, arc = mark
                        leader = root(nodes[self.labels[material], arc])
                        area, length, anchor = aggregate[leader]
                        return leader, {"material": material, "signed_area": str(Q(area, 2)),
                                        "length": str(length), "anchor": list(map(str, anchor))}

                    answers = []
                    for first, second in probes[version]:
                        a, data_a = resolve(first)
                        b, data_b = resolve(second)
                        answers.append({"first": data_a, "second": data_b,
                                        "same_walk": a is not None and a == b})
                    answer["queries"] = answers
            for a, b, previous in reversed(undone):
                if b < 0:
                    cycles[a] -= 1
                else:
                    size[a] -= size[b]
                    parent[b] = b
                    if aggregate is not None:
                        aggregate[a] = previous

        visit(1)


def history_snapshots(history, paints, rules, geometry, probes):
    if not history:
        return []

    paints, rules = list(paints), list(rules)
    stacks, endpoints, edges = [], [], []
    incident = defaultdict(list)
    measurements = defaultdict(lambda: [0, 0, 0])
    interfaces = defaultdict(int)
    interface_rows = {}
    states = []

    def update_metrics(i, left, right, direction):
        if left == right:
            return
        area, mx, my, length = endpoints[i]
        for material, sign in ((left, direction), (right, -direction)):
            if material is not None:
                sums = measurements[material]
                sums[0] += sign * area
                sums[1] += sign * mx
                sums[2] += sign * my
        pair = tuple(sorted((left, right), key=material_key))
        interfaces[pair] += direction * length

    edited = {revision["layer"] for revision in history}
    for a, b, left, right in geometry:
        if left == right:
            continue
        i = len(stacks)
        stacks.append((left, right))
        edges.append((a, b))
        area = cross(a, b)
        endpoints.append((area, (a[0] + b[0]) * area, (a[1] + b[1]) * area,
                          abs(b[0] - a[0]) + abs(b[1] - a[1])))
        for layer in {abs(token) - 1 for token in left + right} & edited:
            incident[layer].append(i)
        pair = visible(left, paints, rules), visible(right, paints, rules)
        states.append(pair)
        update_metrics(i, *pair, 1)

    topology = Topology(edges, states, paints, history)
    locations = locate_probes(edges, probes)

    def repaint(layer, paint, rule):
        previous = paints[layer], rules[layer]
        if previous == (paint, rule):
            return previous
        paints[layer], rules[layer] = paint, rule
        dirty = set()
        for i in incident[layer]:
            left, right = stacks[i]
            pair = visible(left, paints, rules), visible(right, paints, rules)
            if states[i] != pair:
                update_metrics(i, *states[i], -1)
                update_metrics(i, *pair, 1)
                states[i] = pair
                dirty.update(topology.endpoints[i])
        topology.refresh(dirty)
        return previous

    def snapshot():
        return {
            "materials": {
                material: {"area": str(Q(area, 2)),
                           "centroid": [str(Q(moment, 3 * area)) for moment in (mx, my)]}
                for material, (area, mx, my) in measurements.items() if area
            },
            "interfaces": [
                interface_rows.setdefault((pair, interfaces[pair]), {"pair": list(pair), "length": str(interfaces[pair])})
                for pair in sorted(interfaces, key=lambda p: tuple(map(material_key, p)))
                if interfaces[pair]
            ],
        }

    children = [[] for _ in range(len(history) + 1)]
    for i, revision in enumerate(history, 1):
        children[revision["parent"]].append(i)
    results = [None] * len(history)
    preorder = []
    probe_order = []

    def active_probe(index):
        arc = locations[index]
        if arc is None:
            return None
        left, right = states[arc // 2]
        if arc % 2:
            left, right = right, left
        return (left, arc) if left is not None and left != right else None
    # Enter a revision, record it, traverse its children, then undo the paint.
    pending = [(i, None, None) for i in reversed(children[0])]
    while pending:
        i, layer, previous = pending.pop()
        if layer is not None:
            repaint(layer, *previous)
        else:
            revision = history[i - 1]
            layer = revision["layer"]
            previous = repaint(layer, revision["paint"], revision.get("rule", rules[layer]))
            results[i - 1] = snapshot()
            preorder.append(results[i - 1])
            probe_order.append([(active_probe(a), active_probe(b)) for a, b in revision["queries"]]
                               if "queries" in revision else None)
            topology.time += 1
            pending.append((i, layer, previous))
            pending.extend((child, None, None) for child in reversed(children[i]))
    topology.finish(preorder, probe_order, edges)
    return results


def render(drawing):
    rules, materials = [], []
    segments = defaultdict(lambda: defaultdict(int))
    for layer, data in enumerate(drawing["layers"]):
        rules.append(data["rule"])
        materials.append(data["material"])
        for path in data["paths"]:
            points = list(map(tuple, path))
            for a, b in zip(points, points[1:] + points[:1]):
                if a < b:
                    segments[a, b][layer] += 1
                elif b < a:
                    segments[b, a][layer] -= 1
    if not segments:
        empty = {"materials": {}, "interfaces": []}
        if "revisions" in drawing:
            empty["revisions"] = [
                {"materials": {}, "interfaces": [],
                 **({"queries": [{"first": None, "second": None, "same_walk": False}
                                 for _ in revision["queries"]]} if "queries" in revision else {})}
                for revision in drawing["revisions"]
            ]
        return empty

    edges = list(segments)
    weights = list(segments.values())
    boxes = [bounds(a, b) for a, b in edges]
    main = Index(boxes, list(range(len(edges))))
    winding = winding_index(edges, weights, False, len(rules) <= 16)
    swapped = winding_index(edges, weights, True, len(rules) <= 16)
    splits = [set(edge) for edge in edges]
    for i, (a, b) in enumerate(edges):
        for j in main.query(boxes[i]):
            if j > i:
                for point in split_points(a, b, *edges[j]):
                    splits[i].add(point)
                    splits[j].add(point)
    atomic = set()
    for points in splits:
        ordered = sorted(points)
        atomic.update(zip(ordered, ordered[1:]))

    boundary = defaultdict(list)
    interfaces = defaultdict(int)

    history = drawing.get("revisions")
    history_edges = []
    for a, b in atomic:
        if a[1] == b[1]:
            left, right = edge_sides(rotate(a), rotate(b), edges, weights, swapped,
                                     True)
        else:
            left, right = edge_sides(a, b, edges, weights, winding, False)
        if history:
            history_edges.append((a, b, left, right))
        left, right = visible(left, materials, rules), visible(right, materials, rules)
        if left == right:
            continue
        if left is not None:
            boundary[left].append((a, b))
        if right is not None:
            boundary[right].append((b, a))
        pair = tuple(sorted((left, right), key=material_key))
        interfaces[pair] += abs(b[0] - a[0]) + abs(b[1] - a[1])
    result = {
        "materials": {material: describe(arcs) for material, arcs in boundary.items()},
        "interfaces": [{"pair": list(pair), "length": str(interfaces[pair])}
                       for pair in sorted(interfaces, key=lambda p: tuple(map(material_key, p)))],
    }
    if history is not None:
        result["revisions"] = history_snapshots(history, materials, rules, history_edges, drawing.get("probes", ()))
    return result


if __name__ == "__main__":
    sys.set_int_max_str_digits(0)
    with open(sys.argv[1], encoding="utf-8") as source:
        result = render(json.load(source))
    with open(sys.argv[2], "w", encoding="utf-8") as destination:
        json.dump(result, destination)
