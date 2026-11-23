"""Convert OpenCourant animation files (el_ayyatA###) to compact per-frame arrays.
Usage: python export_frames.py [every_n_frames]
Needs anim_to_vtk_win64.exe (OpenCourant release). Writes out/frames.npz:
  node_id (N,) int32           radioss node ids, same order as xyz
  t (F,) float32               frame time, ms
  xyz (F,N,3) float32          deformed node coordinates, mm
  quads (E,4) int32            shell connectivity as indices into node_id (triangles repeat the 3rd)
  elem_id (E,), part_id (E,)   radioss element / part ids
  deleted (F,E) bool           element eroded (failure) at that frame
"""
import glob, os, subprocess, sys
import numpy as np

EXE = r'C:\YouTubeNeuropolis\tools\OpenCourant\exec\anim_to_vtk_win64.exe'
EVERY = int(sys.argv[1]) if len(sys.argv) > 1 else 1


def read_vtk(text):
    lines = text.split('\n'); i = 0; out = {}
    def nums(count, dtype):
        nonlocal i
        vals = []
        while len(vals) < count:
            vals.extend(lines[i].split()); i += 1
        return np.array(vals[:count], dtype=dtype)
    section = None
    while i < len(lines):
        s = lines[i].split(); i += 1
        if not s: continue
        k = s[0]
        if k == 'TIME': out['time'] = float(lines[i].split()[0]); i += 1
        elif k == 'POINTS': out['points'] = nums(int(s[1]) * 3, np.float32).reshape(-1, 3)
        elif k == 'CELLS':
            n, size = int(s[1]), int(s[2]); flat = nums(size, np.int64)
            cells = []; p = 0
            for _ in range(n):
                m = flat[p]; cells.append(flat[p + 1:p + 1 + m]); p += m + 1
            out['cells'] = cells
        elif k == 'CELL_TYPES': out['types'] = nums(int(s[1]), np.int32)
        elif k == 'POINT_DATA': section = ('p', int(s[1]))
        elif k == 'CELL_DATA': section = ('c', int(s[1]))
        elif k == 'SCALARS':
            i += 1  # LOOKUP_TABLE
            name = s[1]; dt = np.int64 if s[2] == 'int' else np.float32
            arr = nums(section[1], dt)
            if name in ('NODE_ID', 'ELEMENT_ID', 'PART_ID', 'EROSION_STATUS'): out[name] = arr
        elif k == 'VECTORS':
            arr = nums(section[1] * 3, np.float32)
            if s[1] == 'Displacement': out['disp'] = arr.reshape(-1, 3)
    return out


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    files = sorted(glob.glob(os.path.join(here, 'el_ayyatA[0-9][0-9][0-9]')))[::EVERY]
    T, X, D = [], [], []
    base = None
    for f in files:
        v = read_vtk(subprocess.run([EXE, f], capture_output=True, text=True, check=True).stdout)
        if base is None:
            shell = np.array([t in (5, 9) for t in v['types']])   # VTK triangle / quad
            sel = np.nonzero(shell)[0]
            quads = np.array([np.pad(v['cells'][c], (0, 4 - len(v['cells'][c])), mode='edge') for c in sel], np.int32)
            base = dict(node_id=v['NODE_ID'].astype(np.int32), quads=quads, sel=sel,
                        elem_id=v['ELEMENT_ID'][sel].astype(np.int32), part_id=v['PART_ID'][sel].astype(np.int16))
        T.append(v['time']); X.append(v['points'])
        D.append(v['EROSION_STATUS'][base['sel']] == 0)   # status 1 = active, 0 = eroded
        print(os.path.basename(f), v['time'], int(D[-1].sum()), 'deleted', flush=True)
    # rigid-body shells report EROSION_STATUS 0 from the start; only count elements that were active at t=0
    D = [d & ~D[0] for d in D]
    os.makedirs(os.path.join(here, 'out'), exist_ok=True)
    np.savez_compressed(os.path.join(here, 'out', 'frames.npz'), t=np.array(T, np.float32), xyz=np.stack(X),
                        deleted=np.stack(D), **{k: v for k, v in base.items() if k != 'sel'})


if __name__ == '__main__':
    main()
