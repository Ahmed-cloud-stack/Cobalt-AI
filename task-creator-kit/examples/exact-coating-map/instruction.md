# Reconstruct the exact visible coating map

Repair the deployed `/app/overlay.py` renderer for an offline plotter. It receives a JSON drawing and writes the exact visible boundaries, coverage measurements and material interfaces to a second JSON file. The current version has correctness and performance defects. Some failures only appear after earlier failures are fixed.

The deployment accepts a patch of at most **100 changed lines** in `/app/overlay.py`. Count each added or deleted line in a Python `difflib.unified_diff` with zero context, excluding the two file headers. Replacing a line counts as two. Keep the CLI in this file and use no helper files or libraries outside the Python standard library.

After repairing the renderer, use it to generate `/app/output/sample.json` and `/app/output/sample_history.json` from `/app/sample.json` and `/app/sample_history.json`, respectively. For held-out cases, the verifier supplies temporary input and output paths as CLI arguments.

Run it with `python3 -I -S /app/overlay.py INPUT OUTPUT`. Use Python 3.12 and its standard library. The program cannot launch subprocesses, access the network, or write outside OUTPUT. The verifier enforces a 256 MiB address-space limit and a 20-second per-drawing timeout.

## Input

An object with a `layers` array, in bottom-to-top order, and optional `revisions` and `probes` arrays described below. Each layer is an object with `material`, `rule` and `paths`.

- Material is an ASCII identifier matching `[a-z][a-z0-9_]*`, or JSON null for an opaque eraser. Uncovered space also has material null. Multiple layers may use the same material.
- Rule is `nonzero` or `evenodd`. A layer covers an off-boundary point when the sum of signed winding numbers of ALL its paths is nonzero or odd, respectively. The highest covering layer determines visible material, including erasers.
- A path is a vertex list, each vertex a pair of integer coordinates in [-10^9, 10^9]. Close each path implicitly. Ignore zero-length segments, including redundant closing vertices. Empty paths, repeated edges, overlaps, retracing, touching, self-crossing and opposite orientations are valid. No drawing viewport clips the result.
- There may be 16,000 nonzero input segments. For the largest cases, spatially local edge queries are sparse: a balanced spatial index can avoid comparing every pair. At most 60,000 distinct atomic segments result from splitting input edges at every point intersection and at both endpoints of every collinear overlap. Empty layers are allowed.

Use exact arithmetic throughout. Tiny nonzero regions and nearly coincident vertices are significant.

## Output

Write one JSON object with keys `materials` and `interfaces`. All rational coordinates and measurements are strings in reduced form, with a positive denominator, no leading plus or zeros, and no slash for integers. JSON object key order and whitespace are ignored.

`materials` maps each visible non-null material with positive area to an object with keys `area`, `centroid` (a pair of rationals), and `rings` (an array of vertex lists).

- An atomic edge belongs to a material's boundary exactly when that material is visible on one side and a different material is visible on the other. Direct each such edge with its material to its left.
- At the end of a directed edge, rotate **clockwise** from the ray pointing back along the incoming edge to the first outgoing directed boundary edge of that same material. This rule pairs edges even at point contacts. Follow the pairs to form closed walks; a walk may visit a vertex more than once. Serialize each walk once and omit its final repeated closing vertex.
- Remove intermediate collinear vertices where the two consecutive directed segments have the same direction, including across the closing seam, even if a different material changes across the boundary there. Preserve all direction changes and repeated visits that remain after simplification.
- Rotate every simplified vertex sequence to its lexicographically smallest cyclic rotation, comparing vertices as numeric (x,y) pairs. Keep its direction. Sort the sequences lexicographically by these numeric pairs. Outer and hole walks have opposite orientation. Area and centroid refer to the full visible region, including the subtraction of holes.

`interfaces` is a sorted array of objects with `pair` and `length`. For every unordered pair of different visible materials that share atomic edges, include one entry. Outside and eraser space are both null. Sort the two materials and then the array of pairs, with null before all strings and strings in ASCII order. Length is the total exact **Manhattan** length of their shared edges, counting each atomic edge once, including edges along holes and excluding point contacts.

For example, an `ink` layer with one nonzero path `[[0,0],[2,0],[2,1],[0,1]]` yields:

```json
{"materials":{"ink":{"area":"2","centroid":["1","1/2"],"rings":[[["0","0"],["2","0"],["2","1"],["0","1"]]]}},"interfaces":[{"pair":[null,"ink"],"length":"6"}]}
```

The provided CLI is the deployment entry point. The public sample is at `/app/sample.json`. General correctness and resource limits are evaluated on other drawings.

## Revision history

The drawing may also contain a `revisions` array. Revision 0 is the base drawing above. Entry i (counting from 1) defines revision i as a copy of its `parent` revision with exactly one layer edited. The parent is an integer in [0, i-1], and the `layer` is a zero-based index in the base `layers` array. Each entry has required keys `parent`, `layer`, and `paint`. The new paint is a material string, null (opaque eraser), or false (disabled and transparent). Reassigning a disabled layer restores its full original footprint when the new paint is a string or null. A revision never changes paths or layer order. A parent can have many children and a child does not change its parent.

When the input contains `revisions`, include a `revisions` array in the output, even if empty. Its ith entry describes revision i, starting at 1, and has `materials` and `interfaces` in the base format, with the `rings` key replaced by `ring_count`, a JSON integer giving the number of closed boundary walks for that material, with exactly the same pairing rule as revision 0. The top-level `materials` and `interfaces` still describe revision 0. Material names that are introduced solely by revisions follow the same sorting rules.

For the batch there are at most 6,000 revisions and 16 distinct material names. The static coverage stack on a side consists of all base layers with nonzero signed winding there, irrespective of the layer's rule or visible paint. Across all atomic edge sides there are at most 500,000 stack entries. For each revision, count atomic edges that have its reassigned layer in the stack on either side. The sum of these counts over all revisions is at most 300,000. For each counted edge, add the number of atomic edges incident to each of its two endpoints (including the counted edge). The sum of these endpoint counts over all revisions is at most 2,400,000. The 20-second and 256 MiB limits apply to the whole input including its history. In particular large histories include many branch points with changes in different tiles, where rerendering whole drawings independently is too slow.

## Winding-rule changes and directed boundary probes

A revision may include a `rule` key with value `nonzero` or `evenodd`. It replaces the edited layer's current winding rule in that revision. Omitting the key inherits the parent's rule. This also applies while a layer is disabled: later revisions restore its paint independently of its inherited rule. The coverage stack and work bounds above count each layer with nonzero winding before any rule or paint is applied.

The input may contain a `probes` array. Each probe has a `point` (a pair of rational strings in the output coordinate syntax) and a `heading` (a nonzero pair of integers in the input coordinate range). From that point, follow a positive infinitesimal step in the given direction. The probe selects the unique directed atomic edge whose relative interior contains that step, if one exists. The point can lie inside an edge or at an endpoint. Orientation follows the heading. At a crossing or contact the heading selects the ray, independent of the other rays. A point, direction or invisible edge that selects no boundary of a non-null material on its left has no result.

A revision may have a `queries` array of pairs of zero-based probe indices. Include a `queries` array in that revision's result exactly when its input entry has one. For each pair, report an object with keys `first`, `second`, and `same_walk`. Each of the first two keys is null when that probe has no result. Otherwise it is an object with `material` (the visible material on its left), `signed_area` (signed shoelace area of the entire closed walk, positive for an outer walk and negative for a hole), `length` (whole-walk Manhattan length), and `anchor` (the first vertex of its canonical vertex list, using a pair of rational strings). `same_walk` is true exactly when both probes select the same closed walk in the current revision, regardless of whether they select the same directed edge. The top-level output still has only the base drawing and optional revision results.

There are at most 16,000 probes and 24,000 query pairs in the entire input. Each input probe coordinate has absolute value at most 10^9 and a denominator at most 10^18. The spatial locality assumption also applies to probe point queries.

The revision example is at `/app/sample_history.json`. Its first revision has no materials or interfaces and both probe results are null because the doubled path cancels under even-odd winding. In the second revision both probes resolve to the `ink` walk with signed area `"2"`, length `"6"`, and anchor `["0","0"]`, and `same_walk` is true.
