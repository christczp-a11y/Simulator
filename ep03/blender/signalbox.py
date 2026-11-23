"""Al-Raqqa style signal box (ENR rural type: brick ground floor, glazed operating room above, flat slab roof)
with an electric route-setting console + mimic track diagram. Origin = ground centre; track side = -X face."""
import bpy, math, random
from mathutils import Vector
from lib import *
from trains import prism, prism_z, tube, to_mesh_join

def sb_mats():
    return dict(
        brick=grime_mat('sbBrick', (0.40, 0.17, 0.10), rough=0.85, amount=0.45, scale=4, dirt=(0.20, 0.13, 0.09)),
        render=grime_mat('sbRender', (0.50, 0.45, 0.36), rough=0.9, amount=0.35, scale=6, dirt=(0.35, 0.28, 0.20), streak=False),
        conc=grime_mat('sbConc', (0.55, 0.52, 0.47), rough=0.9, amount=0.55, streak=False),
        frame=grime_mat('sbFrame', (0.75, 0.73, 0.68), rough=0.5, amount=0.4, dirt=(0.4, 0.35, 0.28), streak=False),
        glass=window_glass('sbGlass', (0.80,0.82,0.78), 0.06),
        floor=grime_mat('sbFloor', (0.36, 0.33, 0.28), rough=0.7, amount=0.4, scale=3, streak=False),
        wall=grime_mat('sbWall', (0.52, 0.50, 0.42), rough=0.9, amount=0.25, scale=6, dirt=(0.45, 0.40, 0.30), streak=False),
        panel=grime_mat('sbPanel', (0.30, 0.36, 0.34), rough=0.5, amount=0.2, streak=False),
        mimic=mat('sbMimic', (0.035, 0.04, 0.04), rough=0.85),
        wood=grime_mat('sbWood', (0.22, 0.13, 0.07), rough=0.6, amount=0.3),
        metal=grime_mat('sbMetal', (0.25, 0.25, 0.24), rough=0.5, metal=0.8, amount=0.4),
        line=mat('sbLine', (0.85, 0.85, 0.8), rough=0.8),
        red=mat('ledRed', (0.6, 0.02, 0.01), rough=0.2, emit=(1, 0.05, 0.02), estr=18),
        grn=mat('ledGrn', (0.02, 0.5, 0.1), rough=0.2, emit=(0.1, 1, 0.25), estr=14),
        yel=mat('ledYel', (0.6, 0.45, 0.02), rough=0.2, emit=(1, 0.75, 0.1), estr=14),
        off=mat('ledOff', (0.10, 0.10, 0.09), rough=0.3),
        paper=mat('paper', (0.82, 0.80, 0.72), rough=0.9),
        tea=mat('teaGlass', (0.55, 0.25, 0.08), rough=0.1, trans=0.6),
        chair=grime_mat('chairV', (0.12, 0.10, 0.08), rough=0.6, amount=0.3),
    )

def signal_box(name='SB', loc=(0, 0, 0), occupied_lights=None):
    m = sb_mats(); P = []
    W, D = 7.0, 4.2       # along track (Y) x depth (X)
    gh, uh = 3.0, 2.9     # ground floor, operating floor height
    # ground floor brick with door + small windows
    P.append(box(name + '_gf', (D, W, gh), (0, 0, gh / 2), m['brick'], bevel=0.02))
    for k in range(int(gh / 0.42)):
        P.append(box(name + f'_course{k}', (D + 0.012, W + 0.012, 0.012), (0, 0, 0.3 + k * 0.42), m['render'], bevel=0.0))
    P.append(box(name + '_door', (0.05, 1.0, 2.1), (D / 2 + 0.01, -2.0, 1.05), m['wood'], bevel=0.01))
    for y in (0.3, 2.2):
        P.append(box(name + f'_gw{y}', (0.05, 0.8, 0.9), (-D / 2 - 0.01, y, 1.8), m['mimic'], bevel=0.01))
        P.append(box(name + f'_gwb{y}', (0.07, 0.9, 0.08), (-D / 2 - 0.02, y, 1.32), m['conc'], bevel=0.0))
    # floor slab with overhang
    P.append(box(name + '_slab1', (D + 0.5, W + 0.5, 0.22), (0, 0, gh + 0.11), m['conc'], bevel=0.02))
    # operating room: corner posts, low wall, glazing all round
    z0 = gh + 0.22; wallh = 1.0
    for s in (-1, 1):
        P.append(box(name + f'_lwx{s}', (0.22, W, wallh), (s * (D / 2 - 0.11), 0, z0 + wallh / 2), m['render'], bevel=0.01))
        P.append(box(name + f'_lwy{s}', (D, 0.22, wallh), (0, s * (W / 2 - 0.11), z0 + wallh / 2), m['render'], bevel=0.01))
    gz0, gz1 = z0 + wallh, z0 + uh - 0.25
    for s in (-1, 1):
        for y in [-W / 2 + 0.11 + i * (W - 0.22) / 6 for i in range(7)]:
            P.append(box(name + f'_mx{s}{y:.1f}', (0.10, 0.09, gz1 - gz0), (s * (D / 2 - 0.11), y, (gz0 + gz1) / 2), m['frame'], bevel=0.005))
        for x in [-D / 2 + 0.11 + i * (D - 0.22) / 4 for i in range(5)]:
            P.append(box(name + f'_my{s}{x:.1f}', (0.09, 0.10, gz1 - gz0), (x, s * (W / 2 - 0.11), (gz0 + gz1) / 2), m['frame'], bevel=0.005))
        P.append(box(name + f'_gx{s}', (0.02, W - 0.3, gz1 - gz0), (s * (D / 2 - 0.11), 0, (gz0 + gz1) / 2), m['glass'], bevel=0.0))
        P.append(box(name + f'_gy{s}', (D - 0.3, 0.02, gz1 - gz0), (0, s * (W / 2 - 0.11), (gz0 + gz1) / 2), m['glass'], bevel=0.0))
        for zz in (gz0, gz1, (gz0 + gz1) / 2 + 0.25):
            P.append(box(name + f'_tx{s}{zz:.1f}', (0.12, W, 0.07), (s * (D / 2 - 0.11), 0, zz), m['frame'], bevel=0.005))
            P.append(box(name + f'_ty{s}{zz:.1f}', (D, 0.12, 0.07), (0, s * (W / 2 - 0.11), zz), m['frame'], bevel=0.005))
    P.append(box(name + '_head', (D, W, 0.25), (0, 0, gz1 + 0.125), m['render'], bevel=0.01))
    P.append(box(name + '_roof', (D + 0.8, W + 0.8, 0.2), (0, 0, z0 + uh + 0.1), m['conc'], bevel=0.02))
    P.append(box(name + '_floorI', (D - 0.44, W - 0.44, 0.03), (0, 0, z0 + 0.015), m['floor'], bevel=0.0))
    P.append(box(name + '_ceilI', (D - 0.44, W - 0.44, 0.03), (0, 0, z0 + uh - 0.03), m['wall'], bevel=0.0))
    # nameboard (no real text, just a plate) + external stair
    P.append(box(name + '_board', (0.06, 2.2, 0.45), (-D / 2 - 0.06, 0, gh + 0.55), m['line'], bevel=0.01))
    for k in range(14):
        P.append(box(name + f'_st{k}', (1.0, 0.28, 0.06), (D / 2 + 0.55, W / 2 - 0.3 - k * 0.24, 0.2 + k * 0.215), m['conc'], bevel=0.005))
    P.append(tube(name + '_srail', [(D / 2 + 1.05, W / 2 - 0.2, 1.2), (D / 2 + 1.05, W / 2 - 3.4, gh + 0.9 + 0.5)], 0.02, m['metal']))
    # console facing the track (operator looks -X through the glazing)
    cx = -D / 2 + 1.05; cz = z0
    P.append(prism(name + '_desk', [(-1.8, cz), (1.8, cz), (1.8, cz + 0.78), (-1.8, cz + 0.78)], cx - 0.35, cx + 0.35, m['panel'], 0.01))
    # mimic board at the back of the desk, leaning away from the operator; face points +X and up
    th = math.radians(-20); n = Vector((math.cos(-th), 0, math.sin(-th))); t = Vector((math.sin(th), 0, math.cos(th)))
    bc = Vector((cx - 0.28, 0, cz + 1.08))
    bd = box(name + '_board2', (0.03, 3.7, 0.60), bc, m['mimic'], bevel=0.004); bd.rotation_euler = (0, th, 0); P.append(bd)
    fr = box(name + '_boardfr', (0.05, 3.8, 0.70), bc - n * 0.02, m['panel'], bevel=0.01); fr.rotation_euler = (0, th, 0); P.append(fr)
    lines, lamps = [], []
    rnd = random.Random(4)
    def onpanel(u, v, h=0.0):   # u along track, v up the board (-0.28..0.28)
        return bc + n * (0.016 + h) + Vector((0, u, 0)) + t * v
    def seg(p, q, w=0.014):
        d = q - p; L = d.length
        o = box(name + '_ml', (0.004, L, w), (p + q) / 2, m['line'], bevel=0.0)
        o.rotation_euler = (math.atan2(d.dot(t), d.y) if False else 0, th, 0)
        # in-plane angle: rotate about board normal; build via matrix
        import mathutils
        ang = math.atan2((q - p).dot(t), (q - p).y)
        R = mathutils.Matrix.Rotation(th, 4, 'Y') @ mathutils.Matrix.Rotation(ang, 4, 'X')
        o.rotation_euler = R.to_euler(); lines.append(o)
    up, dn = 0.06, -0.08
    seg(onpanel(-1.75, up), onpanel(1.75, up)); seg(onpanel(-1.75, dn), onpanel(1.75, dn))
    for u0 in (-1.1, 0.9):   # crossovers
        seg(onpanel(u0, up), onpanel(u0 + 0.35, dn))
    seg(onpanel(-0.3, dn), onpanel(0.1, -0.2)); seg(onpanel(0.1, -0.2), onpanel(0.9, -0.2))   # loop/siding
    for i in range(16):
        u = -1.6 + i * 0.213; v = up if i % 2 == 0 else dn
        st = (occupied_lights or {}).get(i, rnd.choice(['off', 'off', 'grn', 'yel']))
        rot = (0, math.radians(70), 0)
        lamps.append(cyl(name + f'_lamp{i}', 0.022, 0.012, onpanel(u, v + 0.035, 0.004), rot=rot, m=m[st], verts=12))
    for i in range(10):   # signal-state lamps along the top edge
        lamps.append(cyl(name + f'_sig{i}', 0.011, 0.012, onpanel(-1.6 + i * 0.36, 0.21, 0.004), rot=(0, math.radians(70), 0),
                         m=m['red' if i in (3, 4) else ('grn' if i in (7,) else 'off')], verts=10))
    # route buttons row + phone + log book + tea glass
    for i in range(18):
        b = cyl(name + f'_btn{i}', 0.012, 0.02, (cx + 0.2, -1.6 + i * 0.19, cz + 0.79), m=m['off'] if i % 3 else m['red'], verts=10)
        P.append(b)
    P.append(box(name + '_phone', (0.18, 0.22, 0.08), (cx + 0.2, 1.55, cz + 0.82), m['mimic'], bevel=0.2))
    P.append(box(name + '_book', (0.30, 0.42, 0.03), (cx + 0.15, 0.9, cz + 0.795), m['paper'], bevel=0.0))
    P.append(box(name + '_bookcov', (0.31, 0.43, 0.012), (cx + 0.15, 0.9, cz + 0.783), m['wood'], bevel=0.0))
    P.append(cyl(name + '_tea', 0.03, 0.09, (cx + 0.25, -0.4, cz + 0.825), m=m['tea'], verts=16))
    # chair (empty) pulled back from desk
    ch = []
    ch.append(box(name + '_chs', (0.48, 0.48, 0.06), (cx + 0.85, 0.35, cz + 0.47), m['chair'], bevel=0.02))
    ch.append(box(name + '_chb', (0.06, 0.46, 0.5), (cx + 0.60, 0.35, cz + 0.78), m['chair'], bevel=0.02))
    for dx in (-0.2, 0.2):
        for dy in (-0.2, 0.2):
            ch.append(cyl(name + '_chl', 0.015, 0.45, (cx + 0.85 + dx, 0.35 + dy, cz + 0.22), m=m['metal'], verts=8))
    for o in ch: o.rotation_euler = (0, 0, 0); P.append(o)
    # L-return desk with two VDU monitors, keyboards, radio set; binder shelf + fan on the +Y wall
    P.append(prism(name + '_desk2', [(1.85, cz), (3.30, cz), (3.30, cz + 0.78), (1.85, cz + 0.78)], cx - 0.35, cx + 0.35, m['panel'], 0.01))
    import mathutils
    hs = mat('sbVDU', (0.06, 0.065, 0.065), rough=0.35)
    chairp = Vector((cx + 0.85, 0.35))
    for k, (yy, img) in enumerate(((2.15, 'sbscreen.png'), (2.80, 'sbscreen2.png'))):
        sc = Vector((cx - 0.12, yy, cz + 1.12))
        dv = chairp - sc.xy; rz = math.atan2(dv.y, dv.x) + math.pi / 2
        R = mathutils.Euler((math.pi / 2 - math.radians(8), 0, rz), 'XYZ')
        nrm = R.to_matrix() @ Vector((0, 0, 1))
        P.append(screen(name + f'_vdu{k}', 0.50, 0.31, sc + nrm * 0.003, R, img, strength=8.0))
        hb = box(name + f'_vduH{k}', (0.56, 0.37, 0.05), sc - nrm * 0.024, hs, bevel=0.008); hb.rotation_euler = R; P.append(hb)
        P.append(cyl(name + f'_vduS{k}', 0.025, 0.30, (sc.x - nrm.x * 0.06, sc.y - nrm.y * 0.06, cz + 0.93), m=hs, verts=10))
        P.append(box(name + f'_vduB{k}', (0.20, 0.24, 0.015), (sc.x - nrm.x * 0.06, sc.y - nrm.y * 0.06, cz + 0.787), hs, bevel=0.004))
        kb = box(name + f'_kb{k}', (0.16, 0.44, 0.022), (sc.x + nrm.x * 0.30, sc.y + nrm.y * 0.30, cz + 0.792), mat('sbKey', (0.55, 0.54, 0.50), rough=0.5), bevel=0.005)
        kb.rotation_euler = (0, math.radians(-4), rz - math.pi / 2); P.append(kb)
    # radio set (handset on hook, two knobs, small display)
    P.append(box(name + '_radio', (0.30, 0.42, 0.14), (cx + 0.05, 3.05, cz + 0.85), hs, bevel=0.01))
    P.append(box(name + '_radioD', (0.005, 0.12, 0.04), (cx + 0.201, 3.10, cz + 0.88), mat('radLCD', (0.1, 0.2, 0.08), emit=(0.35, 0.9, 0.25), estr=1.5), bevel=0.0))
    for j in range(2):
        P.append(cyl(name + f'_rk{j}', 0.018, 0.02, (cx + 0.205, 2.92 + j * 0.07, cz + 0.83), rot=(0, math.pi / 2, 0), m=m['metal'], verts=12))
    P.append(box(name + '_hand', (0.07, 0.20, 0.05), (cx + 0.05, 3.05, cz + 0.945), m['mimic'], bevel=0.3))
    P.append(tube(name + '_cord', [(cx + 0.06, 2.95, cz + 0.93), (cx + 0.22, 2.90, cz + 0.70), (cx + 0.20, 3.00, cz + 0.55), (cx + 0.18, 3.12, cz + 0.79)], 0.005, m['mimic']))
    # low open bookcase under the +Y window sill with ring binders; ceiling fan; notices on the sill wall
    yw = W / 2 - 0.22; bx0_, bx1_ = cx + 0.45, cx + 1.85; byc = yw - 0.17
    for zz in (0.0, 0.44, 0.88):
        P.append(box(name + f'_bcS{zz}', (bx1_ - bx0_, 0.34, 0.025), ((bx0_ + bx1_) / 2, byc, z0 + zz + 0.0125), m['wood'], bevel=0.003))
    for xx in (bx0_, bx1_, (bx0_ + bx1_) / 2):
        P.append(box(name + '_bcV', (0.025, 0.34, 0.90), (xx, byc, z0 + 0.45), m['wood'], bevel=0.003))
    P.append(box(name + '_bcBk', (bx1_ - bx0_, 0.01, 0.90), ((bx0_ + bx1_) / 2, yw - 0.005, z0 + 0.45), m['wood'], bevel=0.0))
    bcol = [(0.10, 0.18, 0.35), (0.45, 0.08, 0.06), (0.12, 0.30, 0.15), (0.55, 0.50, 0.40), (0.08, 0.08, 0.08)]
    rb = random.Random(9)
    for lvl in (0.025, 0.465):
        for (xa, xb2) in ((bx0_ + 0.02, (bx0_ + bx1_) / 2 - 0.02), ((bx0_ + bx1_) / 2 + 0.02, bx1_ - 0.03)):
            xb = xa
            while xb < xb2 - 0.09:
                tw = rb.uniform(0.05, 0.075); hh = rb.uniform(0.30, 0.36)
                c = rb.choice(bcol)
                bm_ = bpy.data.materials.get(f'binder{c}') or grime_mat(f'binder{c}', c, rough=0.55, amount=0.25, streak=False)
                P.append(box(name + '_bnd', (tw, 0.27, hh), (xb + tw / 2, byc + 0.02, z0 + lvl + hh / 2), bm_, bevel=0.004)); xb += tw + 0.004
    P.append(box(name + '_trayP', (0.30, 0.24, 0.05), (cx + 0.75, byc, z0 + 0.925), m['paper'], bevel=0.003))
    # ceiling fan
    fcx, fcy, ftop = cx + 1.35, 1.2, z0 + uh - 0.03
    P.append(cyl(name + '_fanRod', 0.012, 0.45, (fcx, fcy, ftop - 0.225), m=m['frame'], verts=8))
    P.append(cyl(name + '_fanHub', 0.09, 0.10, (fcx, fcy, ftop - 0.50), m=m['frame'], verts=20))
    for j in range(3):
        a_ = j * 2 * math.pi / 3 + 0.4
        bl = box(name + f'_fanBl{j}', (0.55, 0.11, 0.008), (fcx + 0.33 * math.cos(a_), fcy + 0.33 * math.sin(a_), ftop - 0.52), m['frame'], bevel=0.003)
        bl.rotation_euler = (math.radians(8), 0, a_); P.append(bl)
    for j, (dx, dz, w_, h_) in enumerate(((0.10, 0.60, 0.21, 0.30), (2.05, 0.55, 0.30, 0.21))):
        P.append(box(name + f'_note{j}', (w_, 0.004, h_), (cx + dx, yw - 0.002, z0 + dz), m['paper'], bevel=0.0))
    # wall clock + fluorescent tube + calendar on back wall
    P.append(cyl(name + '_clock', 0.16, 0.04, (D / 2 - 0.24, 1.6, z0 + 2.2), rot=(0, math.pi / 2, 0), m=m['line'], verts=24))
    P.append(box(name + '_fl', (0.06, 1.2, 0.05), (0, 0, z0 + uh - 0.08), mat('sbTube', (1, 1, 1), emit=(1, 0.98, 0.92), estr=8), bevel=0.0))
    P.append(box(name + '_cal', (0.01, 0.35, 0.5), (D / 2 - 0.23, -1.2, z0 + 1.8), m['paper'], bevel=0.0))
    P += lines + lamps
    o = to_mesh_join(P, name)
    o.location += Vector(loc)
    o['console'] = (cx, 0.0, cz)
    return o
