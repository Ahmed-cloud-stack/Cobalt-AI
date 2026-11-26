# Lay out the press-bed pads

The press bed needs a new set of sacrificial pads. We have the bed drawing and one piece of each stock profile. The profiles have already been cut and each has a blind locating pocket on its finished face. Work out where they all go and send back the assembled FreeCAD model for a fit check.

Use `stock.json` for the bed and stock profiles. A dot in `rows` is a cell that needs a pad. A hash is a keep-out. The leftmost character has x = 0 and the bottom row has y = 0. Coordinates and cell corners are on a 10 mm grid. Cell [x,y] has its lower-left corner at (10x, 10y) mm.

Each stock pad is described by a list of local cell coordinates. Use every pad once. You can translate a pad by an integer number of cells and rotate it about the local origin by 0, 90, 180, or 270 degrees counterclockwise as viewed from above. The finished face stays up, so no reflections. Cover every dot exactly once and leave every keep-out open.

Model each pad as its own solid, starting at z = 0 and ending at the stock `height` in millimetres. Each occupied cell contributes a rectangular prism. Inset a side of that prism by 0.25 mm if the adjacent cell across that side is outside the same pad. Leave sides against cells of the same pad on the grid line. Join the prisms of each pad into one solid. At the centre of its transformed `pocket` cell, cut a vertical blind pocket 3.2 mm in diameter and 2 mm deep from the top face.

Save two files:

- `placement.json` maps each pad ID to an object with integer `turns` (0 through 3, in quarter turns) and `origin` (the [x,y] translation applied **after** rotation). Apply the rotation directly to the stock coordinates, without moving the rotated bounding box back to zero.
- `pads.FCStd` contains the installed pads. Each pad solid must be visible and have its pad ID as the FreeCAD object label. The document only needs the pads.

In a packaged run, read `/app/data/task/stock.json` and save both files in `/app/`.
