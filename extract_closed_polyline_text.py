#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Extract closed polylines and inner text from a DXF.

Reads a DXF file (by default ``room_and_number.dxf``) and finds all closed
polylines that contain a single-line TEXT entity. The mileage value is parsed
from the text and the polyline points are exported together with the text into
CSV sorted by mileage.
"""

import csv
import re
from pathlib import Path

import ezdxf
from shapely.geometry import Point, Polygon
from ezdxf.math import Vec2

# ------------ configuration ---------------------------------------------------
DXF_FILE = "room_and_number.dxf"  # input DXF path
OUTPUT_CSV = "room_and_number_extracted.csv"  # output CSV path
RAIL_DXF = "break.dxf"  # reference DXF containing railway centre lines

# ------------------------------------------------------------------------------

def parse_mileage(text: str):
    """Parse mileage from a string.

    Accepts typical forms like ``K123+456`` or ``123+456`` as well as plain
    numbers. Returns ``float`` or ``None`` if the text does not contain a
    numeric value.
    """
    s = text.strip()

    m = re.search(r"[Kk]?(\d+)\+(\d+)", s)
    if m:
        km = int(m.group(1))
        m_val = int(m.group(2))
        return km * 1000 + m_val

    m = re.search(r"(\d+(?:\.\d+)?)", s)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None

def iter_closed_polylines(msp):
    """Yield closed LWPOLYLINE or POLYLINE entities as lists of (x, y)."""
    for e in msp.query("LWPOLYLINE"):
        if e.closed or e.is_closed:  # ezdxf LWPOLYLINE
            yield [(vx, vy) for vx, vy, *_ in e.get_points()]
    for e in msp.query("POLYLINE"):
        if e.is_closed:
            yield [(vx, vy) for vx, vy, *_ in e.get_points()]

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
    polys = list(iter_closed_polylines(msp))

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