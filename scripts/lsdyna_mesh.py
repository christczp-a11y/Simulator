"""Read an LS-DYNA keyword deck (CCSA / NHTSA vehicle models) into numpy arrays.

  python lsdyna_mesh.py <main.k> <out.npz>      # writes mesh + part table, prints a summary

Pure Python + numpy (runs in Blender's Python). Handles *INCLUDE, fixed-width and comma-separated
cards, *KEYWORD LONG=Y. Reads *NODE, *ELEMENT_SHELL[_THICKNESS|_BETA], *ELEMENT_SOLID (1- or 2-card),
*PART (first data card only), *SECTION_SHELL (thickness), and the keyword name + density of each *MAT_.
Only tested on synthetic decks so far (2026-11-20); check the printed summary against the model's
published counts before trusting it.
"""
import os
import sys
import numpy as np


def _lines(path, seen=None, base=None):
    seen = seen if seen is not None else set()
    base = base or os.path.dirname(os.path.abspath(path))
    p = path if os.path.isabs(path) else os.path.join(base, path)
    if not os.path.exists(p):
        alt = os.path.join(base, os.path.basename(path))
        if not os.path.exists(alt):
            print('  missing include:', path)
            return
        p = alt
    if p in seen:
        return
    seen.add(p)
    with open(p, 'r', errors='replace') as f:
        inc = False
        for raw in f:
            s = raw.rstrip('\r\n')
            if not s or s[0] == '$':
                continue
            if s[0] == '*':
                inc = s.upper().startswith('*INCLUDE') and 'TRANSFORM' not in s.upper() and 'PATH' not in s.upper()
                if not inc:
                    yield s
                continue
            if inc:
                yield from _lines(s.strip(), seen, base)
                continue
            yield s


def _fields(s, widths):
    if ',' in s:
        out = [x.strip() for x in s.split(',')]
    else:
        out, i = [], 0
        for w in widths:
            out.append(s[i:i + w].strip())
            i += w
    return out + [''] * (len(widths) - len(out))


def _f(x, d=0.0):
    try:
        return float(x)
    except ValueError:
        try:  # fortran style 1.0-5 / 7.89-09
            m = x[1:].replace('-', 'e-').replace('+', 'e+') if len(x) > 1 else x
            return float(x[0] + m)
        except ValueError:
            return d


def _i(x, d=0):
    try:
        return int(x)
    except ValueError:
        try:
            return int(float(x))
        except ValueError:
            return d


def read(path):
    nid, xyz, shells, solids = [], [], [], []
    parts, sect, mats = {}, {}, {}
    kw, card, long_all, pend = '', 0, False, None
    for s in _lines(path):
        if s[0] == '*':
            u = s.upper().split()[0]
            if u == '*KEYWORD':
                long_all = 'LONG=Y' in s.upper().replace(' ', '')
            kw, card, pend = u, (-1 if u.rstrip('+').endswith('_TITLE') else 0), None
            continue
        lng = long_all or kw.endswith('+')
        k = kw.rstrip('+')
        m = 2 if lng else 1
        card += 1
        if card == 0:  # title card of a *..._TITLE keyword
            continue
        if k == '*NODE':
            a = _fields(s, [8 * m if not lng else 20, 16 if not lng else 20, 16 if not lng else 20, 16 if not lng else 20])
            nid.append(_i(a[0]))
            xyz.append((_f(a[1]), _f(a[2]), _f(a[3])))
        elif k.startswith('*ELEMENT_SHELL'):
            two = ('THICKNESS' in k or 'BETA' in k or 'MCID' in k or 'OFFSET' in k)
            if two and card % 2 == 0:
                continue
            a = _fields(s, [8 * m] * 10)
            n = [_i(v) for v in a[2:6]]
            if n[3] == 0:
                n[3] = n[2]
            shells.append((_i(a[0]), _i(a[1]), *n))
        elif k.startswith('*ELEMENT_SOLID'):
            a = _fields(s, [8 * m] * 10)
            vals = [_i(v) for v in a if v != '']
            if pend is None and len(vals) >= 10:
                solids.append(tuple(vals[:10]))
            elif pend is None:
                pend = vals[:2]
            else:
                n = (vals + [0] * 8)[:8]
                solids.append((pend[0], pend[1], *n))
                pend = None
        elif k.startswith('*PART') and not k.startswith('*PART_COMPOSITE'):
            if pend is None:
                pend = s.strip()
            elif pend != '':
                a = _fields(s, [10 * m] * 8)
                if _i(a[0]):
                    parts[_i(a[0])] = dict(name=pend, secid=_i(a[1]), mid=_i(a[2]))
                pend = ''  # ignore optional extra cards (_INERTIA, _CONTACT) until next keyword
        elif k.startswith('*SECTION_SHELL'):
            a = _fields(s, [10 * m] * 8)
            if card % 2 == 1:
                pend = _i(a[0])
            elif pend is not None:
                sect[pend] = _f(a[0])
        elif k.startswith('*MAT_') and card == 1:
            a = _fields(s, [10 * m] * 8)
            if _i(a[0]):
                mats[_i(a[0])] = (k[5:], _f(a[1]))
    nid = np.array(nid, np.int64)
    xyz = np.array(xyz, np.float64).reshape(-1, 3)
    order = np.argsort(nid)
    look = lambda ids: order[np.searchsorted(nid[order], ids)]
    sh = np.array(shells, np.int64).reshape(-1, 6)
    so = np.array(solids, np.int64).reshape(-1, 10)
    pid = np.array(sorted(parts), np.int64)
    out = dict(node_id=nid, xyz=xyz,
               shell_id=sh[:, 0], shell_pid=sh[:, 1], shell_n=look(sh[:, 2:]) if len(sh) else sh[:, 2:],
               solid_id=so[:, 0], solid_pid=so[:, 1], solid_n=look(so[:, 2:]) if len(so) else so[:, 2:],
               part_id=pid, part_name=np.array([parts[p]['name'] for p in pid]),
               part_thick=np.array([sect.get(parts[p]['secid'], 0.0) for p in pid]),
               part_mat=np.array([mats.get(parts[p]['mid'], ('', 0.0))[0] for p in pid]),
               part_rho=np.array([mats.get(parts[p]['mid'], ('', 0.0))[1] for p in pid]))
    return out


def summary(d):
    x = d['xyz']
    print('nodes %d  shells %d  solids %d  parts %d' % (len(x), len(d['shell_id']), len(d['solid_id']), len(d['part_id'])))
    if len(x):
        print('bbox min', x.min(0).round(1), 'max', x.max(0).round(1), 'size', (x.max(0) - x.min(0)).round(1))
    rho = d['part_rho'][d['part_rho'] > 0]
    if len(rho):
        r = float(np.median(rho))
        unit = 'tonne/mm^3 (mm, s, tonne, N)' if r < 1e-7 else 'kg/mm^3 (mm, ms, kg, kN)' if r < 1e-4 else 'kg/m^3 (SI)' if r > 100 else 'unknown'
        print('median density %.3g -> units look like %s' % (r, unit))
    cnt = np.bincount(np.searchsorted(d['part_id'], d['shell_pid']), minlength=len(d['part_id'])) if len(d['part_id']) and len(d['shell_pid']) else []
    for j in np.argsort(cnt)[::-1][:12] if len(cnt) else []:
        print('  part %-8d %-40s shells %-7d t=%.2f %s' % (d['part_id'][j], d['part_name'][j][:40], cnt[j], d['part_thick'][j], d['part_mat'][j]))


if __name__ == '__main__':
    d = read(sys.argv[1])
    summary(d)
    if len(sys.argv) > 2:
        np.savez_compressed(sys.argv[2], **d)
        print('wrote', sys.argv[2])
