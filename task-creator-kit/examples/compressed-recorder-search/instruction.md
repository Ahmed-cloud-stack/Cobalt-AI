# Repair compressed recorder searches

A telemetry recorder exports tapes over the alphabet `0123456789ABCDEF`. Exports share blocks and repeat them billions of times. Repair `/app/tape_search.py` so searches work against the logical tape without expanding it.

Run it with `python3 -I -S /app/tape_search.py INPUT OUTPUT`. Use Python 3.12 and its standard library. The program may read INPUT and write OUTPUT. It runs offline with a 128 MiB address-space limit and a 20-second timeout per input document.

The deployed repair must fit within **150 changed lines** in `/app/tape_search.py`. Count each addition or deletion in `difflib.unified_diff(old.splitlines(), new.splitlines(), n=0)`, excluding the two file header lines. Keep the implementation in that file. Generate `/app/output/sample.json` by running the repaired CLI on `/app/sample.json`. The verifier supplies temporary INPUT and OUTPUT paths for its own cases.

## Input

A JSON object contains `catalog`, `patterns`, and `queries`. Coordinates, repeat counts, and ranks are decimal strings. Catalog references and pattern indices are zero-based JSON integers.

The catalog is an ordered list. Every reference points to a strictly earlier entry. Operations have these fields:

| `op` | Other fields | Logical contents |
| --- | --- | --- |
| `literal` | `data` | The given string, possibly empty |
| `concat` | `left`, `right` | The left tape followed by the right tape |
| `repeat` | `source`, `times` | That many consecutive copies of the source, including zero copies |
| `reverse` | `source` | The source read backward |
| `slice` | `source`, `start`, `stop` | The source's half-open interval `[start, stop)` |

Repeated uses of a catalog entry are independent logical occurrences. Very long tapes can be built by sharing concatenation operands. All intervals are within their source and may be empty. Every entry has logical length at most 10^30. There are at most 16,000 entries, at most 512 symbols per literal, and at most 128,000 literal symbols in total. The sum of binary bit lengths of all repeat counts is at most 12,000. At most 256 operand references of a concat or repeat may point to a slice, counting a reference through any number of reverse entries as a reference to the underlying entry. The catalog may still contain thousands of wide slices that are searched without concatenating or repeating them.

Each entry in `patterns` is an array of 1 to 64 nonzero 16-bit integer masks. At position i of a match, bit j of mask i permits symbol j in the fixed alphabet. Mask 65535 accepts any symbol. A tape may match at consecutive or overlapping starts.

Each query has a `node` catalog index, a `pattern` index, and decimal-string `start` and `stop` coordinates in that node's logical tape. It also has integer `stride` (1 to 16), integer `phase` (0 to stride minus one), and an array `ranks` of up to four positive decimal strings with values at most 10^30. Keep every match fully contained in the half-open query interval whose **absolute start coordinate in the node** is congruent to phase modulo stride. Interpret ranks as one-based positions in that filtered match list, ordered by increasing start. Preserve the order of the requested ranks, including duplicates. There are at most 12,000 queries and at most 16 distinct (pattern index, stride) pairs per document.

## Output

Write a JSON object with one key, `answers`, with entries in query order. Each answer has:

- `count`, the exact number of filtered matches as a decimal string.
- `moment`, a decimal string for the sum of `(s + 1)^2` over all filtered absolute start positions s, reduced modulo 2^64.
- `selected`, one decimal-string absolute start per requested rank, or JSON null for a rank beyond the last match.

Use canonical unsigned decimal strings, with zero written as `"0"`. Empty match lists have count and moment zero. Obligatory exact counts and coordinates can exceed 64 bits.
