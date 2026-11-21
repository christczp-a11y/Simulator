"""Read the legacy ASCII .vtk files that OpenRadioss' anim_to_vtk writes, pack a run into one npz.

  python vtk_seq.py <folder with *.vtk> <out.npz>

Pure Python + numpy (runs in Blender's Python, which has no vtk / scipy). Keeps points per frame,
the cell connectivity of the first frame, and every per-cell / per-node scalar it finds (erosion
status, plastic strain, part id ... whatever the solver wrote). Only tested on a synthetic file so
far (2026-11-20).
"""
import glob
import os
import re
import sys
import numpy as np

NPTS = {1: 1, 3: 2, 5: 3, 9: 4, 10: 4, 12: 8, 13: 6, 14: 5}  # vtk cell type -> node count


def read_vtk(path):
    tok = open(path, 'r', errors='replace').read().split('\n')
    i, out, mode, n = 0, dict(point={}, cell={}), None, 0

    def take(count, start, dtype):
        vals, j = [], start
        while len(vals) < count and j < len(tok):
            vals.extend(tok[j].split())
            j += 1
        return np.array(vals[:count], dtype), j

    while i < len(tok):
        w = tok[i].split()
        i += 1
        if not w:
            continue
        k = w[0].upper()
        if k == 'POINTS':
            a, i = take(int(w[1]) * 3, i, np.float64)
            out['points'] = a.reshape(-1, 3)
        elif k == 'CELLS':
            a, i = take(int(w[2]), i, np.int64)
            out['cells_flat'], out['ncell'] = a, int(w[1])
        elif k == 'CELL_TYPES':
            out['cell_types'], i = take(int(w[1]), i, np.int64)
        elif k in ('POINT_DATA', 'CELL_DATA'):
            mode, n = ('point' if k == 'POINT_DATA' else 'cell'), int(w[1])
        elif k == 'SCALARS' and mode:
            comp = int(w[3]) if len(w) > 3 else 1
            if i < len(tok) and tok[i].upper().startswith('LOOKUP_TABLE'):
                i += 1
            a, i = take(n * comp, i, np.float64)
            out[mode][w[1]] = a.reshape(n, comp).squeeze()
        elif k in ('VECTORS', 'NORMALS') and mode:
            a, i = take(n * 3, i, np.float64)
            out[mode][w[1]] = a.reshape(n, 3)
        elif k == 'TENSORS' and mode:
            a, i = take(n * 9, i, np.float64)
            out[mode][w[1]] = a.reshape(n, 9)
        elif k == 'FIELD' and mode:
            for _ in range(int(w[2])):
                h = tok[i].split()
                i += 1
                a, i = take(int(h[1]) * int(h[2]), i, np.float64)
                out[mode][h[0]] = a.reshape(int(h[2]), int(h[1])).squeeze()
    return out


def faces(v):
    """Quads / triangles (and the outer faces are NOT extracted for solids) as index lists per cell type."""
    flat, types = v['cells_flat'], v['cell_types']
    cnt = np.array([NPTS.get(int(t), 0) for t in types])
    if (cnt == 0).any():
        cnt, p = [], 0
        for _ in types:
            cnt.append(int(flat[p]))
            p += cnt[-1] + 1
        cnt = np.array(cnt)
    start = np.concatenate([[0], np.cumsum(cnt + 1)[:-1]]) + 1
    quad = np.stack([flat[start[types == 9] + j] for j in range(4)], 1) if (types == 9).any() else np.zeros((0, 4), np.int64)
    tri = np.stack([flat[start[types == 5] + j] for j in range(3)], 1) if (types == 5).any() else np.zeros((0, 3), np.int64)
    return quad, tri, np.where(types == 9)[0], np.where(types == 5)[0]


def pack(folder, out):
    files = sorted(glob.glob(os.path.join(folder, '*.vtk')), key=lambda p: [int(x) if x.isdigit() else x for x in re.split(r'(\d+)', os.path.basename(p))])
    first = read_vtk(files[0])
    quad, tri, qi, ti = faces(first)
    pts, cell, point = [], {k: [] for k in first['cell']}, {k: [] for k in first['point'] if first['point'][k].ndim == 1}
    for f in files:
        v = read_vtk(f)
        if len(v['points']) != len(first['points']):
            raise SystemExit('point count changes between frames in %s: needs per-frame topology handling' % f)
        pts.append(v['points'].astype(np.float32))
        for k in cell:
            cell[k].append(np.asarray(v['cell'].get(k, first['cell'][k]), np.float32))
        for k in point:
            point[k].append(np.asarray(v['point'].get(k, first['point'][k]), np.float32))
    d = dict(points=np.stack(pts), quad=quad, tri=tri, quad_cell=qi, tri_cell=ti, cell_types=first['cell_types'])
    d.update({'cell_' + re.sub(r'\W', '_', k): np.stack(a) for k, a in cell.items()})
    d.update({'point_' + re.sub(r'\W', '_', k): np.stack(a) for k, a in point.items()})
    np.savez_compressed(out, **d)
    print('frames %d  points %d  quads %d  tris %d' % (len(pts), pts[0].shape[0], len(quad), len(tri)))
    print('cell data:', sorted(cell), ' point data:', sorted(point))


if __name__ == '__main__':
    pack(sys.argv[1], sys.argv[2])
