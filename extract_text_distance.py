#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Extract text mileage and offset distance from a DXF layer.

For every single-line TEXT entity on the configured layer, find the nearest
railway polyline and output its mileage position, distance to the line and
whether the text lies on the left or right side (with respect to mileage
direction).
"""

import csv
from pathlib import Path
from typing import Dict, List, Tuple

import ezdxf
from ezdxf.math import Vec2

# ----------------- configuration -------------------------------------------

# mapping of railway layer names to mileage offsets (metres)
RAIL_LAYERS = {
    'dl1': 56700,
    'dl2': 74900,
    'dl3': 100000,
    'dl4': 125000,
    'dl5': 156000,
    'dl6': 163300,
}

# DXF file path
DXF_FILE = 'break.dxf'

# name of the layer containing TEXT entities to extract
TEXT_LAYER = '标注'

# output CSV file
OUTPUT_CSV = 'text_distance.csv'

# densification threshold (metres)
MAX_SEG_LEN = 5.0

# geometric tolerance
TOLERANCE = 1e-6

# ---------------------------------------------------------------------------

def poly2d(entity) -> List[Vec2]:
    """Project a LWPOLYLINE/POLYLINE entity to a list of Vec2."""
    if entity.dxftype() not in ('LWPOLYLINE', 'POLYLINE'):
        raise TypeError(f'Unsupported entity type: {entity.dxftype()}')
    return [Vec2(pt[:2]) for pt in entity.get_points()]


def densify(points: List[Vec2], max_len: float = MAX_SEG_LEN) -> List[Vec2]:
    """Insert intermediate points so that no segment is longer than max_len."""
    dense: List[Vec2] = []
    for i in range(len(points) - 1):
        a, b = points[i], points[i + 1]
        dense.append(a)
        dist = a.distance(b)
        if dist > max_len:
            steps = int(dist // max_len)
            for k in range(1, steps + 1):
                t = k / (steps + 1)
                dense.append(a + (b - a) * t)
    dense.append(points[-1])
    return dense


def calc_cum_len(vecs: List[Vec2]) -> List[float]:
    """Return cumulative lengths for a polyline represented by Vec2 list."""
    cum = [0.0]
    for i in range(len(vecs) - 1):
        cum.append(cum[-1] + vecs[i].distance(vecs[i + 1]))
    return cum


def project_to_segment(pt: Vec2, a: Vec2, b: Vec2) -> Tuple[Vec2, float, float]:
    """Project point pt onto segment a-b.

    Returns (proj_point, distance, side_sign). side_sign > 0 if pt is left
    of the segment direction a->b, <0 if right, ~=0 if on the line.
    """
    ab = b - a
    if ab.magnitude < TOLERANCE:
        return a, pt.distance(a), 0.0
    t = (pt - a).dot(ab) / (ab.magnitude ** 2)
    if t < 0:
        proj = a
    elif t > 1:
        proj = b
    else:
        proj = a + ab * t
    dist = pt.distance(proj)
    sign = (ab.x * (pt.y - proj.y) - ab.y * (pt.x - proj.x))
    return proj, dist, sign


def nearest_on_rail(pt: Vec2, vecs: List[Vec2], cum: List[float]) -> Tuple[float, float, str]:
    """Return (length_along, distance, side) for the nearest point on a rail."""
    best_len = None
    best_dist = float('inf')
    best_side = 'On'

    for i in range(len(vecs) - 1):
        a, b = vecs[i], vecs[i + 1]
        proj, dist, sign = project_to_segment(pt, a, b)
        if dist < best_dist:
            best_dist = dist
            seg_len = (proj - a).magnitude
            best_len = cum[i] + seg_len
            if sign > TOLERANCE:
                best_side = 'Left'
            elif sign < -TOLERANCE:
                best_side = 'Right'
            else:
                best_side = 'On'
    return best_len, best_dist, best_side


def main():
    dxf_path = Path(DXF_FILE)
    if not dxf_path.exists():
        print(f'DXF 文件未找到: {dxf_path}')
        return

    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()

    texts = list(msp.query(f'TEXT[layer=="{TEXT_LAYER}"]'))
    if not texts:
        print(f'图层 {TEXT_LAYER} 未找到任何 TEXT。')

    rail_data: Dict[str, Tuple[List[Vec2], List[float], float]] = {}
    for layer_name, offset in RAIL_LAYERS.items():
        ents = list(msp.query(f'LWPOLYLINE[layer=="{layer_name}"]')) + \
               list(msp.query(f'POLYLINE[layer=="{layer_name}"]'))
        if not ents:
            print(f'Warning: 图层 {layer_name} 未找到折线, 已跳过')
            continue
        pts = densify(poly2d(ents[0]))
        cum = calc_cum_len(pts)
        rail_data[layer_name] = (pts, cum, offset)

    rows = []
    for txt in texts:
        ins = Vec2(txt.dxf.insert[:2])
        best = None
        for layer_name, (pts, cum, offset) in rail_data.items():
            length, dist, side = nearest_on_rail(ins, pts, cum)
            if best is None or dist < best['dist']:
                best = {
                    'Mileage_m': length + offset,
                    'Distance_m': dist,
                    'Side': side,
                    'Text': txt.dxf.text,
                }
        if best:
            rows.append(best)

    rows.sort(key=lambda r: r['Mileage_m'])

    if not rows:
        print('No text items processed.')
        return

    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['Mileage_m', 'Distance_m', 'Side', 'Text'])
        writer.writeheader()
        for r in rows:
            writer.writerow({
                'Mileage_m': round(r['Mileage_m'], 3),
                'Distance_m': round(r['Distance_m'], 3),
                'Side': r['Side'],
                'Text': r['Text'],
            })

    print(f'[OK] 已输出 {len(rows)} 条记录 → {OUTPUT_CSV}')


if __name__ == '__main__':
    main()
