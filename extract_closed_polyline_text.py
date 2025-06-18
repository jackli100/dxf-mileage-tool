#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""

import csv
from pathlib import Path

import ezdxf
from shapely.geometry import Point, Polygon
from ezdxf.math import Vec2

# ------------ configuration ---------------------------------------------------
DXF_FILE = "room_and_number.dxf"  # input DXF path
OUTPUT_CSV = "room_and_number_extracted.csv"  # output CSV path
RAIL_DXF = "break.dxf"  # reference DXF containing railway centre lines

def mileage_from_point(pt: Vec2, rails):
    best = None
    for vecs, cum, offset in rails:
        m = calc_mileage(vecs, cum, pt, offset)
        if m is not None and (best is None or m < best):
            best = m
    return best


def main():
    dxf_path = Path(DXF_FILE)
    if not dxf_path.exists():
        print(f"DXF not found: {dxf_path}")
        return

    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()

    rail_path = Path(RAIL_DXF)
    if not rail_path.exists():
        print(f"Reference DXF not found: {rail_path}")
        return
    rails = load_rails(rail_path)

    texts = list(msp.query("TEXT"))


    poly_polygons = [Polygon(pts) for pts in polys]

    rows = []
    for poly, shape in zip(polys, poly_polygons):
        # find TEXT entities whose insertion point is inside this polygon
        for txt in texts:
            pt = Point(txt.dxf.insert.x, txt.dxf.insert.y)
            if shape.contains(pt):
                mileage = mileage_from_point(Vec2(pt.x, pt.y), rails)
                rows.append({
                    "Mileage": mileage,
                    "Text": txt.dxf.text,
                    "Points": ";".join(f"{x:.3f} {y:.3f}" for x, y in poly),
                })

    # sort rows by mileage if available
    rows.sort(key=lambda r: r["Mileage"] if r["Mileage"] is not None else float("inf"))

    if not rows:
        print("No matching polylines with text found.")
        return

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Mileage", "Text", "Points"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"[OK] Extracted {len(rows)} entries → {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
