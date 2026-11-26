#!/usr/bin/env python3
"""Build the reference solid from the checked-in routing witness."""

import argparse
import json
import shutil
from pathlib import Path

import FreeCAD as App
import Part


def build(destination):
    source = Path(__file__).with_name("routes.json")
    routes = json.loads(source.read_text())
    cavities = []
    for route in routes.values():
        sweeps = []
        for start, finish in zip(route, route[1:]):
            center = [3 + 6 * min(a, b) for a, b in zip(start, finish)]
            corner = App.Vector(*(coordinate - 1 for coordinate in center))
            dimensions = [2 + 6 * abs(a - b) for a, b in zip(start, finish)]
            sweeps.append(Part.makeBox(*dimensions, corner))
        cavity = sweeps[0].multiFuse(sweeps[1:]).removeSplitter()
        cavities.append(cavity)

    blank = Part.makeBox(72, 60, 18)
    insert = blank.cut(cavities).removeSplitter()

    destination.mkdir(parents=True, exist_ok=True)
    doc = App.newDocument("VacuumInsert")
    obj = doc.addObject("Part::Feature", "Insert")
    obj.Shape = insert
    doc.recompute()
    doc.saveAs(str(destination / "insert.FCStd"))
    App.closeDocument(doc.Name)
    shutil.copyfile(source, destination / "routes.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    build(parser.parse_args().output.resolve())
