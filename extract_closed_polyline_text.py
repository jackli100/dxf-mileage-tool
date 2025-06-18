#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Extract closed polylines and inner text from a DXF.

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

# ------------ configuration ---------------------------------------------------
DXF_FILE = "room_and_number.dxf"  # input DXF path
OUTPUT_CSV = "room_and_number_extracted.csv"  # output CSV path

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


def main():
    dxf_path = Path(DXF_FILE)
    if not dxf_path.exists():
        print(f"DXF not found: {dxf_path}")
        return

    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()

    texts = list(msp.query("TEXT"))
    polys = list(iter_closed_polylines(msp))

    poly_polygons = [Polygon(pts) for pts in polys]

    rows = []
    for poly, shape in zip(polys, poly_polygons):
        # find TEXT entities whose insertion point is inside this polygon
        found_text = None
        mileage = None
        for txt in texts:
            # ``txt.dxf.insert`` is a ``Vec3`` instance which does not
            # support slicing like ``[:2]``. Access ``x`` and ``y``
            # components explicitly to create the Shapely point.
            pt = Point(txt.dxf.insert.x, txt.dxf.insert.y)
            if shape.contains(pt):
                found_text = txt.dxf.text
                mileage = parse_mileage(found_text)
                break
        if found_text is None:
            continue
        rows.append({
            "Mileage": mileage,
            "Text": found_text,
            "Points": ";".join(f"{x:.3f} {y:.3f}" for x, y in poly)
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
