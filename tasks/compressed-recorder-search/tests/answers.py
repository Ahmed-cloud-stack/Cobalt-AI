"""Independent answer producers for the benchmark fixtures."""
from bisect import bisect_left, bisect_right
from functools import lru_cache
from math import lcm

from cases import ALPHABET

BITS = {symbol: 1 << i for i, symbol in enumerate(ALPHABET)}
MODULO = 2**64


def pack(count, moment, picks):
    return {"count": str(count), "moment": str(moment % MODULO),
            "selected": [None if i is None else str(i) for i in picks]}


def plain_tapes(catalog):
    values = []
    for spec in catalog:
        operation = spec["op"]
        if operation == "literal":
            text = spec["data"]
        elif operation == "concat":
            text = values[spec["left"]] + values[spec["right"]]
        else:
            text = values[spec["source"]]
            if operation == "reverse":
                text = text[::-1]
            elif operation == "repeat":
                text = text * int(spec["times"])
            else:
                text = text[int(spec["start"]):int(spec["stop"])]
        values.append(text)
    return values


def expanded(document):
    texts = plain_tapes(document["catalog"])
    result = []
    for q in document["queries"]:
        masks = document["patterns"][q["pattern"]]
        tape = texts[q["node"]]
        begin, end = int(q["start"]), int(q["stop"])
        starts = [i for i in range(begin, end - len(masks) + 1)
                  if i % q["stride"] == q["phase"]
                  and all(BITS[c] & mask for c, mask in zip(tape[i:i + len(masks)], masks))]
        result.append(pack(len(starts), sum((i + 1)**2 for i in starts),
                           (starts[r - 1] if r <= len(starts) else None for r in map(int, q["ranks"]))))
    return {"answers": result}


def rotate(word, start):
    start %= len(word)
    return word[start:] + word[:start]


def run_slice(parts, start, stop):
    offset = 0
    result = []
    for word, count in parts:
        end = offset + count
        lo, hi = max(start, offset), min(stop, end)
        if lo < hi:
            result.append((rotate(word, lo - offset), hi - lo))
        offset = end
    return result


def periodic_tapes(catalog):
    tapes = []
    for spec in catalog:
        operation = spec["op"]
        if operation == "literal":
            word = spec["data"]
            parts = [(word, len(word))] if word else []
        elif operation == "concat":
            parts = tapes[spec["left"]] + tapes[spec["right"]]
        else:
            parts = tapes[spec["source"]]
            if operation == "reverse":
                parts = [(rotate(word, count)[::-1], count) for word, count in reversed(parts)]
            elif operation == "repeat":
                period, length = parts[0]
                assert len(parts) == 1 and length % len(period) == 0
                parts = [(period, length * int(spec["times"]))]
            else:
                parts = run_slice(parts, int(spec["start"]), int(spec["stop"]))
        tapes.append(parts)
    return tapes


@lru_cache(maxsize=4096)
def offsets(word, pattern, stride, phase):
    period = lcm(len(word), stride)
    accepted = [i for i in range(len(word))
                if all(BITS[word[(i + j) % len(word)]] & mask for j, mask in enumerate(pattern))]
    accepted = set(accepted)
    return period, [i for i in range(phase, period, stride) if i % len(word) in accepted]


def periodic_blocks(parts, pattern, q):
    lo, hi = int(q["start"]), int(q["stop"]) - len(pattern)
    stride, phase = q["stride"], q["phase"]
    coords = [0]
    for _, size in parts:
        coords.append(coords[-1] + size)

    def char(position):
        i = bisect_right(coords, position) - 1
        word = parts[i][0]
        return word[(position - coords[i]) % len(word)]

    # Each run has an interior periodic block followed by explicit seam starts.
    blocks = []
    linear = moment = 0
    for i, (word, size) in enumerate(parts):
        origin = coords[i]
        begin, end = max(lo, origin), min(hi, origin + size - len(pattern))
        if begin <= end:
            period, choices = offsets(rotate(word, begin - origin), pattern, stride,
                                      (phase - begin) % stride)
            total = 0
            for offset in choices:
                first = begin + offset + 1
                n = max(0, (end - first + 1) // period + 1)
                linear += n * first + period * (n - 1) * n // 2
                moment += (n * first**2 + first * period * (n - 1) * n
                           + period**2 * (n - 1) * n * (2*n - 1) // 6)
                total += n
            if total:
                blocks.append((total, begin, period, choices))
        seam = []
        if i + 1 < len(parts):
            for s in range(max(lo, origin, origin + size - len(pattern) + 1),
                           min(hi, origin + size - 1) + 1):
                if s % stride == phase and all(BITS[char(s + j)] & mask
                                               for j, mask in enumerate(pattern)):
                    seam.append(s)
                    linear += s + 1
                    moment += (s + 1)**2
        if seam:
            blocks.append((len(seam), 0, 0, seam))

    def pick(rank):
        for count, base, period, choices in blocks:
            if rank <= count:
                block, position = divmod(rank - 1, len(choices))
                return base + block * period + choices[position]
            rank -= count
        return None

    return sum(row[0] for row in blocks), linear, moment, pick


def periodic_query(parts, pattern, q):
    count, _, moment, pick = periodic_blocks(parts, pattern, q)
    return pack(count, moment, (pick(r) for r in map(int, q["ranks"])))


def periodic(document):
    tapes = periodic_tapes(document["catalog"])
    return {"answers": [periodic_query(tapes[q["node"]], tuple(document["patterns"][q["pattern"]]), q)
                        for q in document["queries"]]}


def flat_stress(document):
    data = document["catalog"]
    literals = [row["data"] for row in data[:8]]
    text = literals[0]
    for entry in data[8:]:
        if entry["op"] == "reverse":
            text = text[::-1]
        elif entry["left"] < 8:
            text = literals[entry["left"]] + text
        else:
            text += literals[entry["right"]]

    @lru_cache(maxsize=None)
    def index(p, stride):
        masks = document["patterns"][p]
        positions = [[] for _ in range(stride)]
        sums = [[0] for _ in range(stride)]
        for i in range(len(text) - len(masks) + 1):
            if all(BITS[c] & mask for c, mask in zip(text[i:i + len(masks)], masks)):
                phase = i % stride
                positions[phase].append(i)
                sums[phase].append(sums[phase][-1] + (i + 1)**2)
        return positions, sums

    answers = []
    for q in document["queries"]:
        choices, sums = index(q["pattern"], q["stride"])
        starts, prefix = choices[q["phase"]], sums[q["phase"]]
        lo = bisect_left(starts, int(q["start"]))
        hi = bisect_right(starts, int(q["stop"]) - len(document["patterns"][q["pattern"]]), lo)
        answers.append(pack(hi - lo, prefix[hi] - prefix[lo],
                            (starts[lo+r-1] if r <= hi-lo else None for r in map(int, q["ranks"]))))
    return {"answers": answers}



def repeated_mixture(document):
    catalog = document["catalog"]
    words = catalog[0]["data"], catalog[1]["data"][::-1]
    lengths = tuple(len(word) * int(catalog[2 + i]["times"]) for i, word in enumerate(words))
    unit = sum(lengths)
    pieces = list(zip(words, lengths))
    pieces.append(pieces[0])

    def local(pattern, stride, phase, bound):
        q = dict(start="0", stop=str(bound + len(pattern) - 1), stride=stride, phase=phase)
        return periodic_blocks(pieces, pattern, q)

    @lru_cache(maxsize=None)
    def entire(pattern, stride, phase):
        assert unit % stride == 0
        return local(pattern, stride, phase, unit)

    answers = []
    for q in document["queries"]:
        pattern = tuple(document["patterns"][q["pattern"]])
        stride, phase = q["stride"], q["phase"]
        count, linear, squares, pick = entire(pattern, stride, phase)

        def prefix(position):
            cycles, remaining = divmod(position, unit)
            n, first, second, _ = local(pattern, stride, phase, remaining)
            linear_shifts = unit * cycles * (cycles - 1) // 2
            square_shifts = unit**2 * cycles * (cycles - 1) * (2 * cycles - 1) // 6
            shift = cycles * unit
            return (cycles * count + n,
                    cycles * squares + 2 * linear * linear_shifts + count * square_shifts
                    + second + 2 * shift * first + n * shift**2)

        lower = int(q["start"])
        upper = max(lower, int(q["stop"]) - len(pattern) + 1)
        skipped, previous = prefix(lower)
        seen, current = prefix(upper)
        selected = []
        for rank in map(int, q["ranks"]):
            if skipped + rank > seen:
                selected.append(None)
            else:
                cycle, index = divmod(skipped + rank - 1, count)
                selected.append(cycle * unit + pick(index + 1))
        answers.append(pack(seen - skipped, current - previous, selected))
    return {"answers": answers}


def shared_head_answers(document):
    data = document["catalog"]
    word = data[0]["data"]
    first_small = next(i for i, row in enumerate(data[1:], 1) if row["op"] == "literal")
    copies = int(data[1]["times"]) if data[1]["op"] == "repeat" else 1 << (first_small - 1)
    seam = len(word) * copies
    tail = "".join(data[entry["right"]]["data"] for entry in data[first_small + 4:])
    answers = []
    for q in document["queries"]:
        start, stop = int(q["start"]), int(q["stop"])
        masks = document["patterns"][q["pattern"]]
        choices = []
        window = "".join(word[i % len(word)] if i < seam else tail[i - seam]
                         for i in range(start, stop))
        for i in range(q["phase"] + start - start % q["stride"],
                       stop - len(masks) + 1, q["stride"]):
            if i >= start and all(BITS[c] & mask for c, mask in zip(window[i-start:i-start+len(masks)], masks)):
                choices.append(i)
        answers.append(pack(len(choices), sum((s + 1)**2 for s in choices),
                            (choices[r-1] if r <= len(choices) else None for r in map(int, q["ranks"]))))
    return {"answers": answers}


def replay_answers(data):
    catalog = data["catalog"][:-2]
    seeds = [row["data"] for row in catalog[:8]]
    text = seeds[0]
    for row in catalog[8:]:
        if row["op"] == "reverse":
            text = text[::-1]
        elif row["left"] < 8:
            text = seeds[row["left"]] + text
        else:
            text += seeds[row["right"]]
    text = text[:int(data["catalog"][-2]["stop"])]
    n = len(text)
    extended = text + text[:63]
    indexes = []
    for pattern in data["patterns"]:
        rows = [([], [0], [0]) for _ in range(16)]
        for i in range(n):
            if all(BITS[c] & mask for c, mask in zip(extended[i:i+len(pattern)], pattern)):
                xs, sums, squares = rows[i % 16]
                xs.append(i)
                sums.append(sums[-1] + i+1)
                squares.append(squares[-1] + (i+1)**2)
        indexes.append(rows)
    answers = []
    for q in data["queries"]:
        places, sums, squares = indexes[q["pattern"]][q["phase"]]
        count = len(places)

        def prefix(bound):
            copies, partial = divmod(bound, n)
            k = bisect_left(places, partial)
            s = n * (copies - 1) * copies // 2
            t = n*n * (copies - 1) * copies * (2*copies - 1) // 6
            return (copies * count + k, copies * squares[-1] + 2 * sums[-1] * s
                    + count * t + squares[k] + 2 * n * copies * sums[k] + k * (n*copies)**2)

        lo, hi = int(q["start"]), int(q["stop"]) - len(data["patterns"][q["pattern"]]) + 1
        gone, prev = prefix(lo)
        remaining, end = prefix(max(lo, hi))

        def pick(rank):
            if gone + rank > remaining:
                return None
            block, offset = divmod(gone + rank - 1, count)
            return n * block + places[offset]
        answers.append(pack(remaining - gone, end - prev, (pick(r) for r in map(int, q["ranks"]))))
    return {"answers": answers}
