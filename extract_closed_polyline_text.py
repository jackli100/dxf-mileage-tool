#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Extract four-corner polylines and text from a DXF and compute mileage.

The script loads a drawing (by default ``room_and_number.dxf``) and locates all
polylines that consist of four corner points. For every single-line ``TEXT``
entity found inside such a polyline, its insertion point is projected onto the
railway centre lines from ``break.dxf`` to determine the mileage. The polygon
vertices, text content and calculated mileage are exported to a CSV sorted by
mileage.
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

# Railway layer names and mileage offsets (metres) used in ``rail_power.py``
RAIL_LAYERS = {
    'dl1': 56700,
    'dl2': 74900,
    'dl3': 100000,
    'dl4': 125000,
    'dl5': 156000,
    'dl6': 163300,
}

MAX_SEG_LEN = 5.0
TOLERANCE = 1e-6

# ------------------------------------------------------------------------------


def iter_quad_polylines(msp):
    """Yield polylines made of four distinct vertices as lists of ``(x, y)``."""
    for e in msp.query("LWPOLYLINE"):
        pts = [(vx, vy) for vx, vy, *_ in e.get_points()]
        # drop duplicated closing vertex
        if len(pts) > 1 and Vec2(pts[0]).distance(Vec2(pts[-1])) < TOLERANCE:
            pts = pts[:-1]
        if len(pts) == 4:
            yield pts
    for e in msp.query("POLYLINE"):
        pts = [(vx, vy) for vx, vy, *_ in e.get_points()]
        if len(pts) > 1 and Vec2(pts[0]).distance(Vec2(pts[-1])) < TOLERANCE:
            pts = pts[:-1]
        if len(pts) == 4:
            yield pts


def poly2d(entity):
    """Project a LWPOLYLINE/POLYLINE to a list of ``Vec2`` points."""
    if entity.dxftype() not in ("LWPOLYLINE", "POLYLINE"):
        raise TypeError(f"Unsupported entity type: {entity.dxftype()}")
    return [Vec2(pt[:2]) for pt in entity.get_points()]


def densify(points, max_len=MAX_SEG_LEN):
    """Densify a sequence of ``Vec2`` points by inserting intermediate points."""
    dense = []
    for i in range(len(points) - 1):
        a, b = points[i], points[i + 1]
        dense.append(a)
        dist = a.distance(b)
        if dist > max_len:
            steps = int(dist // max_len)
            for k in range(1, steps):
                t = k / steps
                dense.append(a + (b - a) * t)
    dense.append(points[-1])
    return dense


def calc_cum_len(vecs):
    cum = [0.0]
    for i in range(len(vecs) - 1):
        cum.append(cum[-1] + vecs[i].distance(vecs[i + 1]))
    return cum


def calc_mileage(vecs, cum, point, offset):
    best_len, best_dist = None, float("inf")
    for i in range(len(vecs) - 1):
        a, b = vecs[i], vecs[i + 1]
        ab = b - a
        if ab.magnitude < TOLERANCE:
            continue
        proj = (point - a).dot(ab) / (ab.magnitude ** 2)
        if proj < 0:
            proj_pt = a
        elif proj > 1:
            proj_pt = b
        else:
            proj_pt = a + ab * proj
        dist = point.distance(proj_pt)
        if dist < best_dist:
            best_dist = dist
            best_len = cum[i] + (proj_pt - a).magnitude
    return None if best_len is None else best_len + offset


def load_rails(path: Path):
    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    rails = []
    for layer, offset in RAIL_LAYERS.items():
        ents = list(msp.query(f'LWPOLYLINE[layer=="{layer}"]')) + \
               list(msp.query(f'POLYLINE[layer=="{layer}"]'))
        for ent in ents:
            pts = densify(poly2d(ent))
            rails.append((pts, calc_cum_len(pts), offset))
    return rails


def mileage_from_point(pt: Vec2, rails):
    best = None
    for vecs, cum, offset in rails:
        m = calc_mileage(vecs, cum, pt, offset)
        if m is not None and (best is None or m < best):
            best = m
    return best


def poly2d(entity):
    """Project a LWPOLYLINE/POLYLINE to a list of ``Vec2`` points."""
    if entity.dxftype() not in ("LWPOLYLINE", "POLYLINE"):
        raise TypeError(f"Unsupported entity type: {entity.dxftype()}")
    return [Vec2(pt[:2]) for pt in entity.get_points()]


def densify(points, max_len=MAX_SEG_LEN):
    """Densify a sequence of ``Vec2`` points by inserting intermediate points."""
    dense = []
    for i in range(len(points) - 1):
        a, b = points[i], points[i + 1]
        dense.append(a)
        dist = a.distance(b)
        if dist > max_len:
            steps = int(dist // max_len)
            for k in range(1, steps):
                t = k / steps
                dense.append(a + (b - a) * t)
    dense.append(points[-1])
    return dense


def calc_cum_len(vecs):
    cum = [0.0]
    for i in range(len(vecs) - 1):
        cum.append(cum[-1] + vecs[i].distance(vecs[i + 1]))
    return cum


def calc_mileage(vecs, cum, point, offset):
    best_len, best_dist = None, float("inf")
    for i in range(len(vecs) - 1):
        a, b = vecs[i], vecs[i + 1]
        ab = b - a
        if ab.magnitude < TOLERANCE:
            continue
        proj = (point - a).dot(ab) / (ab.magnitude ** 2)
        if proj < 0:
            proj_pt = a
        elif proj > 1:
            proj_pt = b
        else:
            proj_pt = a + ab * proj
        dist = point.distance(proj_pt)
        if dist < best_dist:
            best_dist = dist
            best_len = cum[i] + (proj_pt - a).magnitude
    return None if best_len is None else best_len + offset


def load_rails(path: Path):
    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    rails = []
    for layer, offset in RAIL_LAYERS.items():
        ents = list(msp.query(f'LWPOLYLINE[layer=="{layer}"]')) + \
               list(msp.query(f'POLYLINE[layer=="{layer}"]'))
        for ent in ents:
            pts = densify(poly2d(ent))
            rails.append((pts, calc_cum_len(pts), offset))
    return rails


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
    polys = list(iter_quad_polylines(msp))

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
