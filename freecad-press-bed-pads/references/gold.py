#!/usr/bin/env python3
"""Build a FreeCAD document from the reference placement."""

import argparse
import json
import shutil
from pathlib import Path

import FreeCAD as App
import Part


ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "environment/data/task/stock.json"
PLACEMENT = Path(__file__).with_name("placement.json")


def build_stock_pad(pad):
    cells = {tuple(point) for point in pad["cells"]}
    height = pad["height"]
    faces = []
    for x, y in sorted(cells):
        x0 = 10 * x + (0 if (x - 1, y) in cells else 0.25)
        x1 = 10 * (x + 1) - (0 if (x + 1, y) in cells else 0.25)
        y0 = 10 * y + (0 if (x, y - 1) in cells else 0.25)
        y1 = 10 * (y + 1) - (0 if (x, y + 1) in cells else 0.25)
        corners = [App.Vector(a, b, 0) for a, b in [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]]
        faces.append(Part.Face(Part.makePolygon(corners + corners[:1])))

    profile = faces[0].multiFuse(faces[1:]).removeSplitter()
    solid = profile.extrude(App.Vector(0, 0, height))
    pocket_x, pocket_y = pad["pocket"]
    cutter = Part.makeCylinder(1.6, 2, App.Vector(10 * pocket_x + 5, 10 * pocket_y + 5, height - 2))
    return solid.cut(cutter).removeSplitter()


def installed_placement(entry):
    x, y = entry["origin"]
    rotation = App.Rotation(App.Vector(0, 0, 1), 90 * entry["turns"])
    # The schedule rotates cell indices. In the solid, rotate their centres
    # around the centre of stock cell (0, 0) before applying the translation.
    pivot = App.Vector(5, 5, 0)
    translation = App.Vector(10 * x, 10 * y, 0) + pivot - rotation.multVec(pivot)
    return App.Placement(translation, rotation)


def build(output):
    stock = json.loads(STOCK.read_text())
    schedule = json.loads(PLACEMENT.read_text())
    doc = App.newDocument("PressBedPads")
    for pad in stock["pads"]:
        name = pad["id"]
        entry = schedule[name]
        solid = build_stock_pad(pad)
        if len(solid.Solids) != 1 or not solid.isValid():
            raise RuntimeError(f"Invalid reference solid for {name}.")
        obj = doc.addObject("Part::Feature", name)
        obj.Shape = solid.Solids[0]
        obj.Label = name
        obj.Placement = installed_placement(entry)
    doc.recompute()
    output.mkdir(parents=True, exist_ok=True)
    doc.saveAs(str(output / "pads.FCStd"))
    App.closeDocument(doc.Name)
    shutil.copyfile(PLACEMENT, output / "placement.json")


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("output", type=Path)
    build(cli.parse_args().output.resolve())
