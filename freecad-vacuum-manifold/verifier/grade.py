#!/usr/bin/env python3
"""Check the route schedule and the submitted FreeCAD solid."""

import argparse
import json
from pathlib import Path


HANDOUT = Path(__file__).resolve().parents[1] / "environment/data/task/routing.json"
VOLUME_TOL = 0.01
LENGTH_TOL = 0.00001


def read_json(path):
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    return json.loads(path.read_text(), object_pairs_hook=unique_keys)


def check_routes(schedule, spec):
    if not isinstance(schedule, dict) or set(schedule) != {d["id"] for d in spec["ducts"]}:
        raise ValueError("The route file must contain exactly the circuit IDs in the handout.")

    used = {tuple(point): "blocked station" for point in spec["blocked"]}
    risers = {tuple(point) for point in spec["risers"]}
    for duct in spec["ducts"]:
        name = duct["id"]
        route = schedule[name]
        if not isinstance(route, list) or len(route) != duct["steps"] + 1:
            raise ValueError(f"{name}: expected {duct['steps']} moves.")
        if route[0] != duct["feed"] or route[-1] != duct["pickup"]:
            raise ValueError(f"{name}: feed or pickup does not match the handout.")
        vertical_moves = 0
        bends = 0
        last_move = None
        for index, station in enumerate(route):
            if not isinstance(station, list) or len(station) != 3 or any(
                type(value) is not int or not 0 <= value < limit
                for value, limit in zip(station, spec["grid"])
            ):
                raise ValueError(f"{name}: invalid station at route position {index}.")
            point = tuple(station)
            if point in used:
                raise ValueError(f"{name}: station {station} already used ({used[point]}).")
            used[point] = name
            if not index:
                continue
            previous = route[index - 1]
            move = tuple(b - a for a, b in zip(previous, point))
            if sum(map(abs, move)) != 1:
                raise ValueError(f"{name}: illegal move from {previous} to {station}.")
            if last_move is not None and move != last_move:
                bends += 1
            last_move = move
            if move[2]:
                vertical_moves += 1
                x, y, z = point
                if (x, y, min(z, previous[2])) not in risers:
                    raise ValueError(f"{name}: no riser between {previous} and {station}.")
        if vertical_moves != duct["risers"]:
            raise ValueError(f"{name}: expected {duct['risers']} vertical moves, found {vertical_moves}.")
        if "bends" in duct and bends != duct["bends"]:
            raise ValueError(f"{name}: expected {duct['bends']} bends, found {bends}.")


def check_solid(path, schedule, grid):
    import FreeCAD as app
    import Part

    if not path.is_file():
        raise ValueError("Missing insert.FCStd.")
    doc = app.openDocument(str(path))
    try:
        shapes = []
        for obj in doc.Objects:
            shape = getattr(obj, "Shape", None)
            if getattr(obj, "Visibility", True) and shape and not shape.isNull() and shape.Solids:
                shapes.append(shape)
        if len(shapes) != 1 or len(shapes[0].Solids) != 1:
            raise ValueError("Expected one visible solid.")
        shape = shapes[0]
        if not shape.isValid() or len(shape.Faces) != len(shape.Solids[0].Faces):
            raise ValueError("The visible shape must be a valid solid.")

        size = [6 * count for count in grid]
        bounds = shape.BoundBox
        measured = (bounds.XMin, bounds.YMin, bounds.ZMin, bounds.XMax, bounds.YMax, bounds.ZMax)
        if any(abs(value - expected) > LENGTH_TOL for value, expected in zip(measured, [0, 0, 0, *size])):
            raise ValueError("The solid does not have the specified outer bounds.")

        # A station cube contributes 8 mm³. Each move contributes another
        # 16 mm³ between cubes. Valid station-disjoint paths cannot overlap.
        void_volume = sum(8 * len(route) + 16 * (len(route) - 1) for route in schedule.values())
        expected = size[0] * size[1] * size[2] - void_volume
        if abs(shape.Volume - expected) > VOLUME_TOL:
            raise ValueError(f"Material volume {shape.Volume:.4f} mm³, expected {expected} mm³.")

        # The bounds and volume rule out extra machining once the scheduled
        # voids have all been checked. Cutters from different routes are disjoint.
        for name, route in schedule.items():
            boxes = []
            for first, second in zip(route, route[1:]):
                lower = app.Vector(*(2 + 6 * min(a, b) for a, b in zip(first, second)))
                span = [2 + 6 * abs(a - b) for a, b in zip(first, second)]
                boxes.append(Part.makeBox(*span, lower))
            cavity = boxes[0].multiFuse(boxes[1:])
            overlap = shape.common(cavity).Volume
            if overlap > VOLUME_TOL:
                raise ValueError(f"{name}: {overlap:.4f} mm³ of material in the scheduled void.")
    finally:
        app.closeDocument(doc.Name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--submission", type=Path, default=Path("/app"))
    parser.add_argument("--output", type=Path, default=Path("/logs/verifier"))
    args = parser.parse_args()
    spec = read_json(HANDOUT)
    report = {"reward": 0.0, "checks": []}
    try:
        schedule = read_json(args.submission / "routes.json")
        check_routes(schedule, spec)
        report["checks"].append({"id": "routing", "pass": True})
    except (ValueError, OSError) as exc:
        report["checks"].append({"id": "routing", "pass": False, "detail": str(exc)})
    else:
        try:
            check_solid(args.submission / "insert.FCStd", schedule, spec["grid"])
            report["checks"].append({"id": "solid", "pass": True})
            report["reward"] = 1.0
        except (ValueError, RuntimeError, OSError) as exc:
            report["checks"].append({"id": "solid", "pass": False, "detail": str(exc)})

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "reward.json").write_text(json.dumps({"reward": report["reward"]}) + "\n")
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
