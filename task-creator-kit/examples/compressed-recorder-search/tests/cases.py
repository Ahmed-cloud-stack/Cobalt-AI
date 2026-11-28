"""Deterministic public-format inputs for the held-out suite."""
import random

ALPHABET = "0123456789ABCDEF"
ANY = 65535


def literal(value):
    return {"op": "literal", "data": value}


def concat(left, right):
    return {"op": "concat", "left": left, "right": right}


def repeat(source, times):
    return {"op": "repeat", "source": source, "times": str(times)}


def reverse(source):
    return {"op": "reverse", "source": source}


def cut(source, start, stop):
    return {"op": "slice", "source": source, "start": str(start), "stop": str(stop)}


def query(node, pattern, start, stop, stride=1, phase=0, ranks=(1,)):
    return dict(node=node, pattern=pattern, start=str(start), stop=str(stop),
                stride=stride, phase=phase, ranks=list(map(str, ranks)))


def masks(word):
    return [ANY if c == "?" else 1 << ALPHABET.index(c) for c in word]


def document(catalog, patterns, queries):
    return dict(catalog=catalog, patterns=patterns, queries=queries)


def short_cases():
    catalog = [literal(""), literal("0A0A0"), repeat(1, 0), concat(0, 1), reverse(3),
               cut(4, 2, 2), concat(5, 2), repeat(6, 11), cut(3, 1, 3),
               literal("1B32DC000012"), concat(1, 9), reverse(10), cut(11, 2, 16),
               reverse(12), concat(12, 13)]
    yield "identity-and-cuts", document(catalog, [masks("???"), masks("0?0"), masks("A0"), masks("?")], [
        query(node, pat, start, end, 3, phase, (2, 1, 3, 1))
        for node, length in enumerate((0, 5, 0, 5, 5, 0, 0, 0, 2, 12, 17, 17, 14, 14, 28))
        for pat in range(4)
        for start, end in {(0, length), (max(0, length - 5), length), (0, max(0, length - 1))}
        for phase in range(3)
    ])
    seed = "A" * 73 + "0" + "B" * 81
    catalog = [literal(seed[:62]), literal(seed[62:63]), literal(seed[63:]),
               concat(0, 1), concat(3, 2), reverse(4), repeat(5, 3)]
    wide = [masks("A" * 64), masks("A" * 33 + "0" + "B" * 30),
            masks("B" * 63 + "0"), masks("?" * 64)]
    yield "sixty-four-symbol-seams", document(catalog, wide, [
        query(node, p, lo, hi, 5, r, (2, 1, 4, 3))
        for node, length in ((4, len(seed)), (5, len(seed)), (6, 3 * len(seed)))
        for lo, hi in ((0, length), (17, min(140, length)), (62, min(length, 126)), (63, 64))
        for p in range(len(wide)) for r in range(5)
    ])
    yield "overlap-and-rank", document([literal("B"), repeat(0, 75), literal("0B0B00"),
                                        concat(1, 2), reverse(3)], [masks("BBBBB"), masks("B?B"), masks("?")], [
        query(node, p, 4, 76, 7, r, (10, 1, 2, 1))
        for node in (3, 4) for p in range(3) for r in range(7)
    ])
    # Random grammars keep a separate small expansion for choosing legal ranges.
    for seed in range(24):
        rng = random.Random(619003 + seed)
        catalog = [literal(""), literal("B82B"), literal("AB01")]
        tapes = ["", "B82B", "AB01"]
        for _ in range(105):
            a = rng.randrange(len(tapes))
            b = rng.randrange(len(tapes))
            operation = rng.randrange(5)
            value = tapes[a]
            if operation == 1 and len(value) + len(tapes[b]) < 650:
                entry, value = concat(a, b), value + tapes[b]
            elif operation == 2:
                count = rng.randrange(min(7, 650 // max(1, len(value))) + 1)
                entry, value = repeat(a, count), value * count
            elif operation == 3:
                entry, value = reverse(a), value[::-1]
            elif operation == 4:
                lo = rng.randrange(len(value) + 1)
                hi = rng.randrange(lo, len(value) + 1)
                entry, value = cut(a, lo, hi), value[lo:hi]
            else:
                value = "".join(rng.choices("0AB128", k=rng.randrange(30)))
                entry = literal(value)
            catalog.append(entry)
            tapes.append(value)
        patterns = [masks("?"), masks("B?"), masks("?A?"), masks("AB") +
                    [rng.choice((1, 2, 65535)) for _ in range(4)]]
        queries = []
        for n in range(320):
            node = rng.randrange(len(tapes))
            length = len(tapes[node])
            lo = rng.randrange(length + 1)
            hi = rng.randrange(lo, length + 1)
            if n % 2 == 0:
                lo, hi = 0, length
            p, stride = rng.randrange(4), rng.choice((1, 2, 3, 5))
            queries.append(query(node, p, lo, hi, stride, rng.randrange(stride),
                                 (rng.randrange(1, 10), 1, length + 1, 1)))
        yield f"small-{seed:02}", document(catalog, patterns, queries)


def huge_splices():
    first = "F1095B1B011ADC70B"
    second = "0A00A0FF3FB"
    copies = 10**27 + 973
    left, right = copies * len(first), (copies + 17) * len(second)
    catalog = [literal(first), literal(second), repeat(0, copies), repeat(1, copies + 17),
               cut(2, 19, left - 31), reverse(4), concat(5, 3),
               cut(6, left - 97, left + 69), reverse(7), concat(8, 4)]
    seam = left - 50
    rng = random.Random(88057)
    p = [masks("??B?"), masks("0?0"), masks("?"), masks("?F??B"),
         masks("?" * 63 + "0"), [2 | 4 | 16] * 3]
    q = []
    for i in range(560):
        node, length = rng.choice(((2, left), (3, right), (4, seam), (5, seam),
                                  (6, seam + right), (8, 166), (9, 166 + seam)))
        lo = rng.choice((0, length // 2, max(0, length - 101), rng.randrange(length)))
        hi = rng.choice((length, min(length, lo + 200), rng.randrange(lo, length + 1)))
        pat = i % len(p)
        stride = (3, 5, 11, 16, 2, 7)[pat]
        q.append(query(node, pat, lo, hi, stride, rng.randrange(stride),
                       (1, 10**20, 3, max(1, (hi - lo) // (2 * stride)))))
    for r in range(7):
        q.append(query(6, 2, seam - 64, seam + 80, 7, r, (1, 19, 2, 20)))
    return document(catalog, p, q)


def dense_virtual():
    count = 10**28 + 111
    word = "000A00A0"
    size = len(word) * count
    catalog = [literal(word), repeat(0, count), cut(1, 3, size - 17), reverse(2)]
    p = [masks("?" * 64), masks("?" * 61 + "0??"), masks("0?A"),
         masks("??????"), masks("?0" * 17)]
    choices = [(i, stride) for i in range(len(p)) for stride in (3, 7, 16)]
    rng = random.Random(361701234)
    q = []
    for i in range(12000):
        node = 2 + (i & 1)
        total = size - 20
        lo = rng.randrange(total // 2)
        hi = rng.randrange(total // 2, total + 1)
        pat, stride = choices[i % len(choices)]
        q.append(query(node, pat, lo, hi, stride, i % stride,
                       (2, 10**23 + i, 10**25 - i, 10**30)))
    return document(catalog, p, q)


def deep_catalog():
    rng = random.Random(23279149)
    chunks = ["00B0", "0A00", "0000", "0001", "F000", "000B", "00B1", "A000"]
    catalog = [literal(chunk) for chunk in chunks]
    root = 0
    for i in range(15992):
        piece = rng.randrange(len(chunks))
        if i % 19 == 2:
            catalog.append(reverse(root))
        elif i & 1:
            catalog.append(concat(root, piece))
        else:
            catalog.append(concat(piece, root))
        root = len(catalog) - 1
    length = 4 * (1 + sum(i % 19 != 2 for i in range(15992)))
    p = [masks("?" * 64), masks("?00?00?"), masks("0000"), masks("0B?"), masks("?")]
    q = []
    for i in range(8500):
        lo = rng.randrange(length // 2)
        hi = rng.randrange(length // 2, length + 1)
        pat = i % len(p)
        stride = (3, 5, 7, 11, 16)[pat]
        q.append(query(root, pat, lo, hi, stride, rng.randrange(stride),
                       (1, max(1, (hi - lo) // 250), rng.randrange(1, 900), 10**30)))
    return document(catalog, p, q)


def held_out():
    yield from short_cases()
    yield "wide-coordinates", huge_splices()
    yield "dense-virtual-tape", dense_virtual()
    yield "dense-stride-one", dense_stride_one()
    yield "deep-catalog", deep_catalog()
    yield "many-ranged-views", many_views()
    yield "mixed-periods", mixed_periods()
    yield "shared-giant-head", shared_head()
    yield "doubled-giant-head", shared_head(doubled=True)
    yield "broad-replay", broad_replay()


def many_views():
    rng = random.Random(14700219)
    word = "1A1000010BAFA01"
    copies = 10**27 + 152
    total = copies * len(word)
    catalog = [literal(word), repeat(0, copies)]
    sizes = [len(word), total]
    for i in range(15998):
        parent = len(catalog) - 1
        if i % 5 == 1:
            catalog.append(reverse(parent))
            sizes.append(sizes[parent])
        elif i % 5 == 2:
            catalog.append(cut(parent, 13, sizes[parent] - 35))
            sizes.append(sizes[parent] - 48)
        else:
            lo = rng.randrange(total // 3)
            hi = rng.randrange(2 * total // 3, total)
            catalog.append(cut(1, lo, hi))
            sizes.append(hi - lo)
    patterns = [masks("1?0?"), masks("?" * 27 + "A" + "?" * 36),
                masks("0" + "?" * 49), masks("??????")]
    queries = []
    for i in range(11000):
        node = len(catalog) - 1 - i
        total = sizes[node]
        lo, hi = rng.randrange(total // 2), rng.randrange(total // 2, total)
        pattern = i % len(patterns)
        stride = (3, 7, 11, 16)[pattern]
        queries.append(query(node, pattern, lo, hi, stride, rng.randrange(stride),
                             (10**25, 1, 10**20, 10**30)))
    return document(catalog, patterns, queries)


def mixed_periods():
    first, second = "001A0000000", "000BA10"
    a, b, loops = 240240 * (10**9 + 103), 240240 * (10**9 + 771), 10**13 + 19
    catalog = [literal(first), literal(second), repeat(0, a), repeat(1, b),
               reverse(3), concat(2, 4), repeat(5, loops)]
    size = (len(first) * a + len(second) * b) * loops
    patterns = [masks("0" + "?" * 62 + "0"), masks("0?0?0?B?"),
                masks("?" * 17 + "1" + "?" * 16), masks("A" + "?" * 29 + "0")]
    rng = random.Random(2197979)
    query_list = []
    for i in range(2900):
        start = rng.randrange(size // 2)
        stop = rng.randrange(size // 2, size + 1)
        pattern = i % len(patterns)
        stride = (13, 11, 7, 16)[pattern]
        query_list.append(query(6, pattern, start, stop, stride, rng.randrange(stride),
                                (10**21 + i, 1, (stop - start) // 1000 + 1, 1)))
    return document(catalog, patterns, query_list)


def shared_head(doubled=False):
    base = "001A0000000"
    copies = 2**93 if doubled else 10**28 + 987
    prefix = len(base) * copies
    catalog = [literal(base)]
    if doubled:
        for node in range(93):
            catalog.append(concat(node, node))
    else:
        catalog.append(repeat(0, copies))
    root = len(catalog) - 1
    first_small = len(catalog)
    catalog.extend(map(literal, ("000A", "00B0", "000C", "B00B")))
    rng = random.Random(652021)
    for _ in range(16000 - len(catalog)):
        catalog.append(concat(root, first_small + rng.randrange(4)))
        root = len(catalog) - 1
    patterns = [masks("0?0"), masks("?" * 63 + "A"), masks("??B?000?"), masks("?")]
    queries = []
    for i in range(12000):
        pat = i % 4
        stride = (3, 7, 11, 16)[pat]
        delta = rng.randrange(-110, 70)
        start = prefix + delta
        stop = start + rng.randrange(1, 220)
        queries.append(query(root - i, pat, start, stop, stride, rng.randrange(stride),
                             (1, 10**25, 2, 1)))
    return document(catalog, patterns, queries)


def dense_stride_one():
    data = dense_virtual()
    data["patterns"] = [masks("?" * 64), masks("?" * 63 + "0")]
    for i, row in enumerate(data["queries"]):
        row.update(pattern=i % 2, stride=1, phase=0)
    return data


def broad_replay():
    data = deep_catalog()
    catalog = data["catalog"][:15998]
    # Calculate length through the retained append/reverse chain.
    length = 4 * (1 + sum(row["op"] == "concat" for row in catalog[8:]))
    length -= length % 16
    catalog.append(cut(len(catalog)-1, 0, length))
    copies = 10**24 + 1
    catalog.append(repeat(len(catalog)-1, copies))
    patterns = []
    for i in range(16):
        pattern = [ANY] * (61 + i % 4)
        pattern[0] = pattern[-1] = 1 | 2 | 1024
        pattern[2 + i] = 1 | 1024 | (1 << (i % 6))
        pattern[27 + i % 11] = 1 | 2 | 1024 | 2048
        patterns.append(pattern)
    rng = random.Random(8702263)
    total = length * copies
    selected = []
    for i in range(9000):
        lo = rng.randrange(total // 2)
        hi = rng.randrange(total // 2, total)
        selected.append(query(len(catalog) - 1, i % 16, lo, hi, 16, rng.randrange(16),
                              (1, 10**22, (hi-lo)//400, 10**30)))
    return document(catalog, patterns, selected)
