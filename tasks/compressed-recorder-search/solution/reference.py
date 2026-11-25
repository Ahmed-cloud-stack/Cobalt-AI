#!/usr/bin/env python3
"""Index and query a compressed recorder export."""
import json
import sys
from collections import defaultdict, namedtuple
from functools import lru_cache

SYMBOLS = "0123456789ABCDEF"
SLOTS = {letter: i for i, letter in enumerate(SYMBOLS)}
MASK = (1 << 64) - 1
WINDOW = 63

Node = namedtuple("Node", "size height left right text prefix suffix")
EMPTY = Node(0, 0, 0, 0, "", "", "")


class Tape:
    def __init__(self):
        self.nodes = [EMPTY]

    def size(self, root):
        return self.nodes[abs(root)].size

    def height(self, root):
        return self.nodes[abs(root)].height

    def children(self, root):
        row = self.nodes[abs(root)]
        if root < 0:
            return -row.right, -row.left
        return row.left, row.right

    def text(self, root):
        text = self.nodes[abs(root)].text
        return text[::-1] if root < 0 and text else text

    def prefix(self, root):
        node = self.nodes[abs(root)]
        return node.suffix[::-1] if root < 0 else node.prefix

    def suffix(self, root):
        node = self.nodes[abs(root)]
        return node.prefix[::-1] if root < 0 else node.suffix

    def leaf(self, text):
        if not text:
            return 0
        self.nodes.append(Node(len(text), 1, 0, 0, text, text[:WINDOW], text[-WINDOW:]))
        return len(self.nodes) - 1

    def branch(self, left, right):
        left_size, right_size = self.size(left), self.size(right)
        prefix = self.prefix(left)
        suffix = self.suffix(right)
        if left_size < WINDOW:
            prefix = (prefix + self.prefix(right))[:WINDOW]
        if right_size < WINDOW:
            suffix = (self.suffix(left) + suffix)[-WINDOW:]
        height = 1 + max(self.height(left), self.height(right))
        self.nodes.append(Node(left_size + right_size, height, left, right, None, prefix, suffix))
        return len(self.nodes) - 1

    def balance(self, left, right):
        if self.height(left) > self.height(right) + 1:
            a, b = self.children(left)
            if self.height(a) < self.height(b):
                b, pivot = self.children(b)
                a, right = self.branch(a, b), self.branch(pivot, right)
                return self.branch(a, right)
            return self.branch(a, self.branch(b, right))
        if self.height(right) > self.height(left) + 1:
            a, b = self.children(right)
            if self.height(a) > self.height(b):
                pivot, a = self.children(a)
                left, b = self.branch(left, pivot), self.branch(a, b)
                return self.branch(left, b)
            return self.branch(self.branch(left, a), b)
        return self.branch(left, right)

    def join(self, left, right):
        if not left or not right:
            return left or right
        if self.height(left) > self.height(right) + 1:
            a, b = self.children(left)
            return self.balance(a, self.join(b, right))
        if self.height(right) > self.height(left) + 1:
            a, b = self.children(right)
            return self.balance(self.join(left, a), b)
        return self.branch(left, right)

    def repeat(self, root, times):
        result = 0
        while times:
            if times & 1:
                result = self.join(result, root)
            times >>= 1
            if times:
                root = self.join(root, root)
        return result

    def cut(self, root, start, stop):
        if start == stop:
            return 0
        if start == 0 and stop == self.size(root):
            return root
        text = self.text(root)
        if text is not None:
            return self.leaf(text[start:stop])
        left, right = self.children(root)
        seam = self.size(left)
        if stop <= seam:
            return self.cut(left, start, stop)
        if start >= seam:
            return self.cut(right, start - seam, stop - seam)
        return self.join(self.cut(left, start, seam), self.cut(right, 0, stop - seam))

    def load(self, catalog):
        views = []

        def materialize(index):
            return self.cut(*views[index])

        for entry in catalog:
            kind = entry["op"]
            if kind == "literal":
                root = self.leaf(entry["data"])
            elif kind == "concat":
                root = self.join(materialize(entry["left"]), materialize(entry["right"]))
            elif kind == "repeat":
                root = self.repeat(materialize(entry["source"]), int(entry["times"]))
            else:
                root, start, stop = views[entry["source"]]
                if kind == "reverse":
                    size = self.size(root)
                    views.append((-root, size - stop, size - start))
                else:
                    views.append((root, start + int(entry["start"]), start + int(entry["stop"])))
                continue
            if self.height(root) >= 24 or kind == "repeat" and self.height(root) > 1:
                self.nodes.append(self.nodes[abs(root)]._replace(height=1))
                root = (len(self.nodes) - 1) * (1 if root > 0 else -1)
            views.append((root, 0, self.size(root)))
        return views


class Signature:
    def __init__(self, pattern):
        self.length = len(pattern)
        self.accept = 1 << (self.length - 1)
        self.transitions = [
            sum(1 << i for i, positions in enumerate(pattern) if positions & (1 << letter))
            for letter in range(len(SYMBOLS))
        ]

    def matches(self, text, origin=0):
        state = 0
        base = origin - self.length + 1
        for i, letter in enumerate(text):
            state = ((state << 1) | 1) & self.transitions[SLOTS[letter]]
            if state & self.accept:
                yield base + i

    @lru_cache(maxsize=2048)
    def boundary_hits(self, text, stride, phase):
        return tuple(start for start in self.matches(text) if start % stride == phase)

    def crossing(self, tape, left, right, stride=1, phase=0, raw=False):
        width = self.length - 1
        if not width:
            return (0, ()) if raw else ()
        suffix = tape.suffix(left)[-width:]
        prefix = tape.prefix(right)[:width]
        origin = tape.size(left) - len(suffix)
        hits = self.boundary_hits(suffix + prefix, stride, (phase - origin) % stride)
        return (origin, hits) if raw else (origin + local for local in hits)


ZERO = (0, 0, 0)


def add_hit(totals, start, stride):
    phase = start % stride
    count, linear, square = totals.get(phase, ZERO)
    totals[phase] = (count + 1, (linear + start) & MASK, (square + start * start) & MASK)


def append_totals(totals, right, offset, stride):
    for phase, (count, linear, square) in right.items():
        translated = (phase + offset) % stride
        old_count, old_linear, old_square = totals.get(translated, ZERO)
        totals[translated] = (
            old_count + count,
            (old_linear + linear + offset * count) & MASK,
            (old_square + square + 2 * offset * linear + offset * offset * count) & MASK,
        )


class Searches:
    def __init__(self, tape, pattern, stride):
        self.tape = tape
        self.signature = Signature(pattern)
        self.stride = stride
        self.saved = {}

    def totals(self, root):
        tape = self.tape
        signature = self.signature
        if tape.size(root) < signature.length:
            return {}
        cache = self.saved
        if root not in cache:
            text = tape.text(root)
            if text is not None:
                result = {}
                for start in signature.matches(text):
                    add_hit(result, start, self.stride)
            else:
                left, right = tape.children(root)
                result = self.totals(left).copy()
                for start in signature.crossing(tape, left, right):
                    add_hit(result, start, self.stride)
                append_totals(result, self.totals(right), tape.size(left), self.stride)
            cache[root] = result
        return cache[root]

    def select(self, root, phase, rank):
        tape = self.tape
        stride = self.stride
        origin = 0
        while True:
            text = tape.text(root)
            if text is not None:
                for start in self.signature.matches(text):
                    if start % stride == phase:
                        rank -= 1
                        if rank == 0:
                            return origin + start
                raise AssertionError("rank outside leaf")
            left, right = tape.children(root)
            count = self.totals(left).get(phase, ZERO)[0]
            if rank <= count:
                root = left
                continue
            rank -= count
            seam, hits = self.signature.crossing(tape, left, right, stride, phase, raw=True)
            if rank <= len(hits):
                return origin + seam + hits[rank - 1]
            rank -= len(hits)
            offset = tape.size(left)
            origin += offset
            phase = (phase - offset) % stride
            root = right

    @staticmethod
    @lru_cache(maxsize=2048)
    def hit_moments(hits, bound):
        starts = tuple(s for s in hits if s < bound)
        return len(starts), sum(starts), sum(s * s for s in starts)

    def before(self, root, phase, bound, shift):
        tape, stride = self.tape, self.stride
        length = self.signature.length
        count = moment = 0
        while bound > 0 and (maximum := tape.size(root) - length + 1) > 0:
            if bound >= maximum:
                n, linear, square = self.totals(root).get(phase, ZERO)
                return count + n, moment + square + 2 * shift * linear + shift * shift * n
            text = tape.text(root)
            if text is not None:
                for start in self.signature.matches(text):
                    if start >= bound:
                        break
                    if start % stride == phase:
                        count += 1
                        moment += (start + shift) ** 2
                break
            left, right = tape.children(root)
            seam = tape.size(left)
            if bound <= seam - length + 1:
                root = left
                continue
            n, linear, square = self.totals(left).get(phase, ZERO)
            count += n
            moment += square + 2 * shift * linear + shift * shift * n
            origin, hits = self.signature.crossing(tape, left, right, stride, phase, raw=True)
            n, linear, square = self.hit_moments(hits, min(bound - origin, WINDOW))
            count += n
            translated = shift + origin
            moment += square + 2 * translated * linear + translated * translated * n
            bound -= seam
            shift += seam
            phase = (phase - seam) % stride
            root = right
        return count, moment

    def query(self, view, query):
        root, origin, _ = view
        start, stop = int(query["start"]), int(query["stop"])
        phase = (query["phase"] + origin) % self.stride
        last = stop - self.signature.length + 1
        lower = upper = moment = 0
        if last > start:
            lower, earlier = self.before(root, phase, origin + start, 1 - origin)
            upper, later = self.before(root, phase, origin + last, 1 - origin)
            moment = (later - earlier) & MASK
        count = upper - lower
        selected = []
        for rank in map(int, query["ranks"]):
            selected.append(str(self.select(root, phase, lower + rank) - origin) if rank <= count else None)
        return {"count": str(count), "moment": str(moment), "selected": selected}


def render(document):
    tape = Tape()
    roots = tape.load(document["catalog"])
    groups = defaultdict(list)
    for i, query in enumerate(document["queries"]):
        groups[query["pattern"], query["stride"]].append((i, query))
    answers = [None] * len(document["queries"])
    for (pattern, stride), entries in groups.items():
        search = Searches(tape, document["patterns"][pattern], stride)
        for i, query in entries:
            answers[i] = search.query(roots[query["node"]], query)
    return {"answers": answers}


def main():
    with open(sys.argv[1], encoding="utf-8") as source:
        result = render(json.load(source))
    with open(sys.argv[2], "w", encoding="utf-8") as destination:
        json.dump(result, destination, separators=(",", ":"))


if __name__ == "__main__":
    main()
