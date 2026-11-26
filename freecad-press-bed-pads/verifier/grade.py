#!/usr/bin/env python3
"""Grade a press-bed placement and its FreeCAD model."""

import argparse
import json
from pathlib import Path


STOCK = Path(__file__).resolve().parents[1] / "environment/data/task/stock.json"
VOLUME_TOLERANCE = 0.005  # cubic millimetres, per pad


def read_json(path):
    def check_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key {key!r}.")
            result[key] = value
        return result

    return json.loads(path.read_text(), object_pairs_hook=check_keys)


def rotate(point, turns):
    x, y = point
    return ((x, y), (-y, x), (-x, -y), (y, -x))[turns]


def check_placement(entries, stock):
    required = {
        (x, y)
        for y, row in enumerate(reversed(stock["rows"]))
        for x, cell in enumerate(row)
        if cell == "."
    }
    if not isinstance(entries, dict) or set(entries) != {pad["id"] for pad in stock["pads"]}:
        raise ValueError("Placement must contain exactly the stock pad IDs.")

    used = {}
    installed = {}
    for pad in stock["pads"]:
        name = pad["id"]
        entry = entries[name]
        if not isinstance(entry, dict) or set(entry) != {"turns", "origin"}:
            raise ValueError(f"{name}: expected turns and origin.")
        turns, origin = entry["turns"], entry["origin"]
        if type(turns) is not int or not 0 <= turns <= 3:
            raise ValueError(f"{name}: turns must be an integer from 0 to 3.")
        if not isinstance(origin, list) or len(origin) != 2 or any(type(v) is not int for v in origin):
            raise ValueError(f"{name}: origin must contain two integers.")

        def install(point):
            x, y = rotate(point, turns)
            return (x + origin[0], y + origin[1])

        cells = {install(point) for point in pad["cells"]}
        for cell in sorted(cells):
            if cell not in required:
                raise ValueError(f"{name}: cell {cell} is outside the usable bed.")
            if cell in used:
                raise ValueError(f"{name}: cell {cell} is already covered by {used[cell]}.")
            used[cell] = name
        installed[name] = (cells, install(pad["pocket"]), pad["height"])

    if missing := required - used.keys():
        raise ValueError(f"Uncovered bed cell {min(missing)}.")
    return installed


def compare_pad(name, shape, cells, pocket, height, app, part):
    if len(shape.Solids) != 1 or len(shape.Faces) != len(shape.Solids[0].Faces) or not shape.isValid():
        raise ValueError(f"{name}: expected one valid solid.")

    pocket_cut = part.makeCylinder(
        1.6, 2, app.Vector(10 * pocket[0] + 5, 10 * pocket[1] + 5, height - 2)
    )
    patches = []
    for x, y in sorted(cells):
        left = 0 if (x - 1, y) in cells else 0.25
        right = 0 if (x + 1, y) in cells else 0.25
        front = 0 if (x, y - 1) in cells else 0.25
        back = 0 if (x, y + 1) in cells else 0.25
        corner = app.Vector(10 * x + left, 10 * y + front, 0)
        prism = part.makeBox(10 - left - right, 10 - front - back, height, corner)
        patches.append(prism.cut(pocket_cut) if (x, y) == pocket else prism)

    expected_volume = sum(p.Volume for p in patches)
    if abs(shape.Volume - expected_volume) > VOLUME_TOLERANCE:
        raise ValueError(f"{name}: expected volume {expected_volume:.4f} mm³, found {shape.Volume:.4f} mm³.")

    # Patch interiors are disjoint, including those on either side of an
    # internal grid line. Their intersections with the submission can be added.
    shared_volume = sum(shape.common(patch).Volume for patch in patches)
    difference = expected_volume + shape.Volume - 2 * shared_volume
    if difference > VOLUME_TOLERANCE:
        raise ValueError(f"{name}: solid differs from the placed stock profile by {difference:.4f} mm³.")


def check_model(path, installed):
    if not path.is_file():
        raise ValueError("Missing pads.FCStd.")
    import FreeCAD as app
    import Part

    doc = app.openDocument(str(path))
    try:
        visible = {}
        for obj in doc.Objects:
            if not getattr(obj, "Visibility", True):
                continue
            shape = getattr(obj, "Shape", None)
            if shape is None or shape.isNull() or not shape.Solids:
                continue
            if obj.Label not in installed:
                raise ValueError(f"Unexpected visible solid {obj.Label!r}.")
            if obj.Label in visible:
                raise ValueError(f"Multiple visible solids labelled {obj.Label!r}.")
            visible[obj.Label] = shape
        if missing := set(installed) - visible.keys():
            raise ValueError(f"Missing visible pad {min(missing)}.")

        for name, (cells, pocket, height) in installed.items():
            compare_pad(name, visible[name], cells, pocket, height, app, Part)
    finally:
        app.closeDocument(doc.Name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--submission", type=Path, default=Path("/app"))
    parser.add_argument("--output", type=Path, default=Path("/logs/verifier"))
    args = parser.parse_args()
    stock = read_json(STOCK)
    report = {"reward": 0.0, "checks": []}
    try:
        installed = check_placement(read_json(args.submission / "placement.json"), stock)
        report["checks"].append({"id": "placement", "pass": True})
    except (ValueError, OSError) as exc:
        report["checks"].append({"id": "placement", "pass": False, "detail": str(exc)})
    else:
        try:
            check_model(args.submission / "pads.FCStd", installed)
            report["checks"].append({"id": "model", "pass": True})
            report["reward"] = 1.0
        except (ValueError, RuntimeError, OSError) as exc:
            report["checks"].append({"id": "model", "pass": False, "detail": str(exc)})

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "reward.json").write_text(json.dumps({"reward": report["reward"]}) + "\n")
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
