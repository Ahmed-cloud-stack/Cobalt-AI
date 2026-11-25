# Route the vacuum manifold insert

The insert for the vacuum leak-test fixture is built from three bonded layers. The toolmaker has already fixed the feed and pickup stations, the spots where a vertical transfer can be machined, and the stations reserved for clamps and dowels. Lay out the eighteen independent circuits and make the solid model of the bonded insert before the ports are drilled.

Use the supplied `routing.json`. A station is an integer triple `[x,y,z]` and the grid counts from zero on each axis. The file gives each circuit's feed, pickup, and the counts of station-to-station moves, vertical moves, and bends it needs for the fixture's matched flow calibration. These counts are exact. A vertical move also counts as a station-to-station move. Count a bend whenever two successive moves change direction, including turns into and out of a riser.

A move changes just one coordinate by one. For a vertical move, the lower of its two stations must appear in `risers`. A route cannot visit a blocked station or use any station twice. No two circuits can use the same station. You can leave open stations unused.

The blank is 96 × 72 × 18 mm with its lower corner at the origin. Station `[x,y,z]` is centred at `(3+6x, 3+6y, 3+6z)` mm. The channel between two stations is the square-section sweep of a 2 × 2 × 2 mm cube from one station centre to the other. This gives square corners and ends that extend 1 mm past the terminal centres. Remove the union of those sweeps from the blank. Leave out the port drillings and all other machining. Save the finished geometry as a single solid in a native FreeCAD document.

Deliver these files:

- `routes.json` maps each circuit ID to its ordered list of station triples, including feed and pickup.
- `insert.FCStd` contains the finished solid, aligned to the blank's coordinate system.

For a packaged run, find `routing.json` in `/app/data/task/` and put both deliverables directly in `/app/`.
