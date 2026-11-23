"""El-Ayyat rear-end collision: LS-DYNA-format keyword deck for OpenRadioss (starter reads .k).
Units: kg, mm, ms  ->  stress GPa, force kN, velocity mm/ms (= m/s), accel mm/ms^2.
Bodies
  * 2010 tail coach: deformable steel shell car body (24 m), rear end at Y=0, extends to Y=-24000.
    Side walls with window band openings, flat roof with 45-deg chamfers, floor, rear end wall with
    gangway door opening, underframe (centre sill box, sole bars, cross members every 2 m).
    Fine 50 mm mesh in the rear 10 m (crash zone), 50x100 mm further forward.
    Mass: steel shell + 30 t non-structural (interior, equipment) on the floor + 150 t on the
    front 1 m representing the rest of the stopped train (coupled, brakes applied).
  * Train 134 lead locomotive: rigid body (MAT_RIGID) built from boxes; front at Y=+150, moving -Y.
    Effective mass 200 t (loco + share of trailing train). Initial speed V_KMH (illustrative:
    real speed not published).
  * Ground: coach underframe slides on a rigid wall at Z=900 (stands in for the bogies), loco trucks
    on a rigid wall at Z=0.  Gravity on.  Automatic single-surface contact for everything.
Run:  starter -i el_ayyat.k   (OpenRadioss writes el_ayyat_0001.rad, then run the engine on it)."""
import math, json, sys
V_KMH = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0
V = V_KMH / 3.6                      # m/s == mm/ms
T_END = 450.0                        # ms
DT_OUT = 5.0                         # ms per animation frame

nodes = {}; nid_of = {}; shells = []; masses = []
def N(x, y, z, body):
    k = (body, round(x, 1), round(y, 1), round(z, 1))
    if k not in nid_of:
        nid_of[k] = len(nid_of) + 1; nodes[nid_of[k]] = (x, y, z, body)
    return nid_of[k]
def Q(pid, a, b, c, d=None): shells.append((pid, a, b, c, d if d is not None else c))

# ---------------- parts / props ----------------
PARTS = {   # pid: (title, thickness mm, mat)
    1: ('coach side skin', 2.5, 1), 2: ('coach window piers', 4.0, 1), 3: ('coach roof', 2.0, 1),
    4: ('coach floor', 3.0, 1), 5: ('coach end wall', 3.0, 1), 6: ('coach underframe sills', 8.0, 2),
    7: ('coach cross members', 5.0, 2), 8: ('coach roof chamfer', 2.5, 1),
    20: ('loco rigid', 8.0, 9),
}
# ---------------- coach geometry ----------------
HW, ZF, ZS, ZR, CH = 1450, 1200, 3600, 3900, 300      # half width, floor, side top, roof, chamfer
ZU = 900                                               # underframe bottom
def ys_coach():
    ys = [-24000 + 100 * i for i in range(0, 141)]     # -24000 .. -10000 step 100
    ys += [-10000 + 50 * i for i in range(1, 201)]     # -9950 .. 0 step 50
    return ys
YS = ys_coach()
def ring():
    """closed loop of (x,z,part) segments around the car body, 50 mm steps, start at floor left."""
    pts = []
    for x in range(-HW, HW, 50): pts.append((x, ZF, 4))                 # floor, left->right
    for z in range(ZF, ZS, 50): pts.append((HW, z, 1))                  # right side up
    for k in range(0, CH // 50): pts.append((HW - 50 * k, ZS + 50 * k, 8))  # right chamfer
    for x in range(HW - CH, -(HW - CH), -50): pts.append((x, ZR, 3))     # roof right->left
    for k in range(0, CH // 50): pts.append((-(HW - CH) - 50 * k, ZR - 50 * k, 8))
    for z in range(ZS, ZF, -50): pts.append((-HW, z, 1))                # left side down
    return pts
RING = ring()
def window_at(y, z):
    if not (2050 <= z < 2850): return False
    if y > -900 or y < -23200: return False
    u = (y + 23200) % 2000          # pitch 2000: 1300 window + 700 pier
    return u < 1300
for j in range(len(YS) - 1):
    y0, y1 = YS[j], YS[j + 1]
    for i in range(len(RING)):
        xa, za, pa = RING[i]; xb, zb, _ = RING[(i + 1) % len(RING)]
        pid = pa
        if pa == 1:
            zm = (za + zb) / 2; ym = (y0 + y1) / 2
            if window_at(ym, zm): continue
            if 2050 <= zm < 2850: pid = 2
        Q(pid, N(xa, y0, za, 'c'), N(xb, y0, zb, 'c'), N(xb, y1, zb, 'c'), N(xa, y1, za, 'c'))
    # underframe: centre sill webs x=+-250, bottom flange; sole bars x=+-1450 with inward flange
    for xw in (-250, 250, -HW, HW):
        for z in range(ZU, ZF, 50):
            Q(6, N(xw, y0, z, 'c'), N(xw, y0, z + 50, 'c'), N(xw, y1, z + 50, 'c'), N(xw, y1, z, 'c'))
    for x in range(-250, 250, 50):
        Q(6, N(x, y0, ZU, 'c'), N(x + 50, y0, ZU, 'c'), N(x + 50, y1, ZU, 'c'), N(x, y1, ZU, 'c'))
    for s in (-1, 1):
        for k in range(3):
            xa = s * (HW - 50 * k); xb = s * (HW - 50 * (k + 1))
            Q(6, N(xa, y0, ZU, 'c'), N(xb, y0, ZU, 'c'), N(xb, y1, ZU, 'c'), N(xa, y1, ZU, 'c'))
# cross members every 2 m (transverse plates between floor and underframe bottom)
for y in YS:
    if y % 2000 != 0: continue
    for x in range(-HW, HW, 50):
        for z in range(ZU, ZF, 50):
            Q(7, N(x, y, z, 'c'), N(x + 50, y, z, 'c'), N(x + 50, y, z + 50, 'c'), N(x, y, z + 50, 'c'))
# rear end wall at Y=0 with gangway door opening (|x|<450, z<3150)
def inside(x, z): return ZF <= z <= ZR and abs(x) <= HW - max(0, z - ZS) + 1e-6
for x in range(-HW, HW, 50):
    for z in range(ZF, ZR, 50):
        if abs(x + 25) < 450 and z < 3150: continue
        c = [(x, z), (x + 50, z), (x + 50, z + 50), (x, z + 50)]
        ins = [p for p in c if inside(*p)]
        if len(ins) == 4: Q(5, *[N(px, 0, pz, 'c') for px, pz in c])
        elif len(ins) == 3: Q(5, *[N(px, 0, pz, 'c') for px, pz in ins])
# ---------------- locomotive (rigid) ----------------
Y0L = 150.0
def lbox(x0, x1, y0, y1, z0, z1, h=100):
    """six faces of a box, 100 mm mesh, nodes private to the loco body"""
    def rng(a, b):
        n = max(1, int(round((b - a) / h))); return [a + (b - a) * i / n for i in range(n + 1)]
    X, Y, Z = rng(x0, x1), rng(Y0L + y0, Y0L + y1), rng(z0, z1)
    for i in range(len(X) - 1):
        for j in range(len(Y) - 1):
            for z in (z0, z1): Q(20, N(X[i], Y[j], z, 'l'), N(X[i + 1], Y[j], z, 'l'), N(X[i + 1], Y[j + 1], z, 'l'), N(X[i], Y[j + 1], z, 'l'))
    for i in range(len(X) - 1):
        for k in range(len(Z) - 1):
            for y in (Y[0], Y[-1]): Q(20, N(X[i], y, Z[k], 'l'), N(X[i + 1], y, Z[k], 'l'), N(X[i + 1], y, Z[k + 1], 'l'), N(X[i], y, Z[k + 1], 'l'))
    for j in range(len(Y) - 1):
        for k in range(len(Z) - 1):
            for x in (x0, x1): Q(20, N(x, Y[j], Z[k], 'l'), N(x, Y[j + 1], Z[k], 'l'), N(x, Y[j + 1], Z[k + 1], 'l'), N(x, Y[j], Z[k + 1], 'l'))
lbox(-1520, 1520, 0, 20000, 1300, 1550)        # deck / underframe
lbox(-1500, 1500, 250, 2900, 1550, 2700)       # short nose
lbox(-1500, 1500, 900, 4150, 1550, 4320)       # cab
lbox(-1200, 1200, 4150, 16400, 1550, 4050)     # long hood
lbox(-1450, 1450, -150, 250, 300, 1300)        # pilot / plough + coupler pocket
lbox(-1350, 1350, 2400, 6300, 0, 1300)         # front truck
lbox(-1350, 1350, 13700, 17600, 0, 1300)       # rear truck
lbox(-1100, 1100, 7000, 13000, 500, 1300)      # fuel tank
# ---------------- masses ----------------
floor_nodes = [n for n, (x, y, z, b) in nodes.items() if b == 'c' and z == ZF]
for n in floor_nodes: masses.append((n, 30000.0 / len(floor_nodes)))
front_nodes = [n for n, (x, y, z, b) in nodes.items() if b == 'c' and y <= -23000 and z <= ZF]
for n in front_nodes: masses.append((n, 150000.0 / len(front_nodes)))
# loco density from its shell area so the rigid body weighs 200 t
area = 0.0
def qarea(a, b, c, d):
    import itertools
    P = [nodes[i][:3] for i in (a, b, c, d)]
    def tri(p, q, r):
        u = [q[k] - p[k] for k in range(3)]; v = [r[k] - p[k] for k in range(3)]
        cx = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        return 0.5 * math.sqrt(sum(t * t for t in cx))
    return tri(P[0], P[1], P[2]) + (tri(P[0], P[2], P[3]) if d != c else 0)
for (pid, a, b, c, d) in shells:
    if pid == 20: area += qarea(a, b, c, d)
RHO_LOCO = 200000.0 / (area * PARTS[20][1])
# ---------------- write deck ----------------
def f10(v): return f'{v:10.4g}' if isinstance(v, float) else f'{v:10d}'
L = []
w = L.append
w('*KEYWORD'); w('*TITLE'); w('El-Ayyat rear-end collision (illustrative), units kg-mm-ms')
w('*CONTROL_TERMINATION'); w(f'{T_END:10.1f}')
w('*CONTROL_TIMESTEP'); w(f'{0.0:10.1f}{0.9:10.2f}')
w('*CONTROL_ENERGY'); w(f'{2:10d}{2:10d}{2:10d}{2:10d}')
w('*CONTROL_SHELL'); w(f'{20.0:10.1f}{1:10d}{-1:10d}{1:10d}{2:10d}{2:10d}{1:10d}')
w('*CONTROL_CONTACT'); w(f'{0.1:10.2f}{0.0:10.1f}{2:10d}{0:10d}{1:10d}{1:10d}{1:10d}{0:10d}')
w('*DATABASE_BINARY_D3PLOT'); w(f'{DT_OUT:10.2f}')
w('*DATABASE_GLSTAT'); w(f'{1.0:10.2f}')
w('*DATABASE_MATSUM'); w(f'{1.0:10.2f}')
# materials
w('*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE'); w('mild steel S235 skin')
w(f'{1:10d}{7.85e-6:10.3e}{210.0:10.1f}{0.3:10.2f}{0.235:10.3f}{0.9:10.3f}{0.28:10.3f}{0.0:10.1f}')
w(f'{0.0:10.1f}{0.0:10.1f}{0:10d}{0:10d}{0.0:10.1f}')
w(''.ljust(80)); w(''.ljust(80))
w('*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE'); w('S355 underframe')
w(f'{2:10d}{7.85e-6:10.3e}{210.0:10.1f}{0.3:10.2f}{0.355:10.3f}{1.1:10.3f}{0.25:10.3f}{0.0:10.1f}')
w(f'{0.0:10.1f}{0.0:10.1f}{0:10d}{0:10d}{0.0:10.1f}')
w(''.ljust(80)); w(''.ljust(80))
w('*MAT_RIGID_TITLE'); w('locomotive')
w(f'{9:10d}{RHO_LOCO:10.4e}{210.0:10.1f}{0.3:10.2f}{0.0:10.1f}{0.0:10.1f}{0.0:10.1f}{0.0:10.1f}')
w(f'{0.0:10.1f}{0:10d}{0:10d}'); w(''.ljust(80))
w('*HOURGLASS'); w(f'{1:10d}{4:10d}{0.05:10.3f}')
for pid, (title, t, mid) in PARTS.items():
    w('*SECTION_SHELL'); w(f'{pid:10d}{2:10d}{1.0:10.2f}{5 if mid != 9 else 2:10d}{1.0:10.2f}{0:10d}{0:10d}{1:10d}')
    w(f'{t:10.2f}{t:10.2f}{t:10.2f}{t:10.2f}')
    w('*PART'); w(title)
    w(f'{pid:10d}{pid:10d}{mid:10d}{0:10d}{1 if mid != 9 else 0:10d}{0:10d}{0:10d}{0:10d}')
w('*NODE')
for n, (x, y, z, b) in nodes.items(): w(f'{n:8d}{x:16.3f}{y:16.3f}{z:16.3f}{0:8d}{0:8d}')
w('*ELEMENT_SHELL')
for e, (pid, a, b, c, d) in enumerate(shells, 1): w(f'{e:8d}{pid:8d}{a:8d}{b:8d}{c:8d}{d:8d}')
w('*ELEMENT_MASS')
for k, (n, m) in enumerate(masses, 1): w(f'{k:8d}{n:8d}{m:16.4f}{0:8d}')
def nset(sid, ids):
    w('*SET_NODE_LIST'); w(f'{sid:10d}')
    for i in range(0, len(ids), 8): w(''.join(f'{v:10d}' for v in ids[i:i + 8]))
coach_bottom = [n for n, (x, y, z, b) in nodes.items() if b == 'c' and z <= ZU + 0.1]
loco_bottom = [n for n, (x, y, z, b) in nodes.items() if b == 'l' and z <= 0.1]
nset(1, coach_bottom); nset(2, loco_bottom)
w('*RIGIDWALL_PLANAR'); w(f'{1:10d}{0:10d}{0:10d}{0.0:10.1f}')
w(f'{0.0:10.1f}{0.0:10.1f}{float(ZU):10.1f}{0.0:10.1f}{0.0:10.1f}{float(ZU + 1000):10.1f}{0.35:10.2f}')
w('*RIGIDWALL_PLANAR'); w(f'{2:10d}{0:10d}{0:10d}{0.0:10.1f}')
w(f'{0.0:10.1f}{0.0:10.1f}{0.0:10.1f}{0.0:10.1f}{0.0:10.1f}{1000.0:10.1f}{0.05:10.2f}')
w('*CONTACT_AUTOMATIC_SINGLE_SURFACE_ID'); w(f'{1:10d}')
w(f'{0:10d}{0:10d}{5:10d}{0:10d}')
w(f'{0.3:10.2f}{0.25:10.2f}')
w(''.ljust(80))
w('*DEFINE_CURVE'); w(f'{1:10d}'); w(f'{0.0:20.4f}{1.0:20.4f}'); w(f'{1.0e6:20.4f}{1.0:20.4f}')
w('*LOAD_BODY_Z'); w(f'{1:10d}{9.81e-3:10.4e}')
w('*INITIAL_VELOCITY_GENERATION'); w(f'{20:10d}{2:10d}{0.0:10.1f}{0.0:10.1f}{-V:10.4f}{0.0:10.1f}{0:10d}')
w(f'{0.0:10.1f}{0.0:10.1f}{0.0:10.1f}{0.0:10.1f}{0.0:10.1f}{0.0:10.1f}{0:10d}{0:10d}')
w('*END')
open('el_ayyat.k', 'w').write('\n'.join(L) + '\n')
json.dump({'parts': {k: v[0] for k, v in PARTS.items()}, 'n_nodes': len(nodes), 'n_shells': len(shells),
           'v_kmh': V_KMH, 'loco_front_y': Y0L, 'units': 'kg mm ms'}, open('el_ayyat_meta.json', 'w'), indent=1)
print('nodes', len(nodes), 'shells', len(shells), 'loco rho', RHO_LOCO, 'V', V)
