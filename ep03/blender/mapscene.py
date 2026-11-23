"""Shots 3 & 10: paper-white relief map of the Nile valley south of Cairo (schematic, not to survey accuracy).
Brand palette only: paper #F4F3F0, ink #0E0E0E, tick grey #8A8A8A, signal red #D7261E (one element: train 134).
Units: 1 BU = 1 km. North = +Y. Rail on the west bank."""
import sys, math, random
sys.path.insert(0, '/home/claude/ep03')
import bpy, bmesh
from mathutils import Vector
from lib import *
from trains import tube

def srgb(h):
    h = h.lstrip('#'); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c)
PAPER, INK, GREY, RED = srgb('F4F3F0'), srgb('0E0E0E'), srgb('8A8A8A'), srgb('D7261E')

def nile_x(y):   # river centreline (km), gentle meanders
    return 3.2 + 1.1 * math.sin(y * 0.11) + 0.5 * math.sin(y * 0.29 + 1.0)
def rail_x(y):
    return nile_x(y) - 4.2 - 0.6 * math.sin(y * 0.07 + 0.5)

STATIONS = [('cairo', 46.0), ('el-ayyat', 0.0), ('kafr ammar', -6.5), ('al-raqqa', -12.0)]   # schematic order southbound
CRASH_Y = -9.0

def ribbon(name, fx, y0, y1, w, z, m, n=240):
    me = bpy.data.meshes.new(name); bm = bmesh.new(); prev = None
    for i in range(n + 1):
        y = y0 + (y1 - y0) * i / n; x = fx(y)
        a = bm.verts.new((x - w / 2, y, z)); b = bm.verts.new((x + w / 2, y, z))
        if prev: bm.faces.new((prev[0], prev[1], b, a))
        prev = (a, b)
    bm.to_mesh(me); bm.free(); o = bpy.data.objects.new(name, me); link(o); me.materials.append(m); return o

def text(s, loc, size, m, align='LEFT', rot=0.0, extrude=0.0):
    cu = bpy.data.curves.new('t', 'FONT'); cu.body = s; cu.size = size; cu.align_x = align; cu.extrude = extrude
    f = '/home/claude/ep03/assets/fonts/InterDisplay-Bold.otf'
    try:
        import os
        for cand in (f, '/home/claude/ep03/assets/fonts/Inter-Bold.otf', '/home/claude/ep03/assets/fonts/InterDisplay-Bold.ttf'):
            if os.path.exists(cand): cu.font = bpy.data.fonts.load(cand); break
    except Exception: pass
    o = bpy.data.objects.new('t', cu); o.location = loc; o.rotation_euler = (0, 0, rot); link(o); cu.materials.append(m); return o

def _bm_obj(name, bm, m, smooth=False):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    if smooth:
        for p in me.polygons: p.use_smooth = True
    o = bpy.data.objects.new(name, me); link(o); me.materials.append(m); return o

def _add_box(bm, c, size, rz=0.0):
    r = bmesh.ops.create_cube(bm, size=1.0)
    vs = r['verts']
    for v in vs:
        x, y, z = v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]
        cs, sn = math.cos(rz), math.sin(rz)
        v.co = Vector((c[0] + x * cs - y * sn, c[1] + x * sn + y * cs, c[2] + z))

def rail_dir(y):
    d = (rail_x(y + 0.05) - rail_x(y - 0.05)) / 0.1
    return math.atan2(-d, 1.0)     # rotation about Z so local +Y follows the rail

def mini_train(name, y_front, cars, body, band, facing=-1, z0=-0.40):
    """Schematic model train sitting on the rail. facing=-1: nose points south (-Y); cars trail behind."""
    L, gap, W, H = 0.62, 0.07, 0.30, 0.26
    objs = []
    for i in range(cars):
        yc = y_front - facing * (L / 2 + i * (L + gap))
        x = rail_x(yc); rz = rail_dir(yc)
        o = box(f'{name}_car{i}', (W, L, H), (x, yc, z0 + H / 2 + 0.03), body, bevel=0.05, segs=4); o.rotation_euler.z = rz
        objs.append(o)
        for s in (-1, 1):   # window band
            bdx = s * (W / 2 + 0.004)
            bb = box(f'{name}_band{i}{s}', (0.006, L * 0.84, 0.06), (x + bdx * math.cos(rz), yc + bdx * math.sin(rz), z0 + H * 0.68 + 0.03), band, bevel=0.0)
            bb.rotation_euler.z = rz
        if i == 0:          # sloped nose
            nose = box(f'{name}_nose', (W * 0.96, 0.10, H * 0.62), (x, yc + facing * (L / 2 + 0.035), z0 + H * 0.31 + 0.03), body, bevel=0.04)
            nose.rotation_euler = (facing * math.radians(-28), 0, rz)
    return objs

def label_card(name, s, at, height, ink, paper, accent=None, w=None):
    """Upright paper tag on a pin, text in Inter Bold; faces the camera roughly (south-west)."""
    w = w or 0.42 * len(s) + 0.5
    rz = math.radians(-24)
    card = box(name + '_card', (w, 0.06, 0.78), (at[0], at[1], at[2] + height), paper, bevel=0.03)
    card.rotation_euler = (0, 0, rz)
    fr = box(name + '_edge', (w + 0.06, 0.05, 0.84), (at[0], at[1] + 0.006, at[2] + height), accent or ink, bevel=0.035)
    fr.rotation_euler = (0, 0, rz)
    t = text(s, (0, 0, 0), 0.52, accent or ink, align='CENTER', extrude=0.012)
    t.data.align_y = 'CENTER'; t.name = name + '_txt'
    nrm = Vector((math.sin(rz) * 1, -math.cos(rz), 0))
    t.location = Vector((at[0], at[1], at[2] + height)) + nrm * 0.035
    t.rotation_euler = (math.pi / 2, 0, rz)
    tube(name + '_pin', [(at[0], at[1], at[2]), (at[0], at[1], at[2] + height - 0.40)], 0.018, ink)
    return card

def build(y134=8.0, y2010=CRASH_Y, show_gap=False):
    rnd = random.Random(7)
    paper = mat('mPaper', PAPER, rough=0.85)
    paper2 = mat('mPaper2', tuple(c * 0.93 for c in PAPER), rough=0.85)
    paper3 = mat('mPaper3', tuple(c * 0.89 for c in PAPER), rough=0.85)
    ink = mat('mInk', INK, rough=0.5)
    grey = mat('mGrey', GREY, rough=0.7)
    lgrey = mat('mLGrey', srgb('C9CBCD'), rough=0.7)
    red = mat('mRed', RED, rough=0.35, coat=0.4)
    redD = mat('mRedD', tuple(c * 0.45 for c in RED), rough=0.4)
    water = mat('mWater', tuple(c * 0.72 for c in GREY), rough=0.18, coat=0.5)
    box('table', (80, 140, 0.4), (0, 0, -0.6), paper2, bevel=0.0)
    # desert plateaus: five thin contour sheets on each side
    for side in (-1, 1):
        for k in range(5):
            edge = lambda y: (nile_x(y) + side * (8.2 + 1.05 * k + 0.7 * math.sin(y * 0.17 + k * 0.8) + 0.35 * math.sin(y * 0.43 + k)))
            ys = [-40 + i * 0.5 for i in range(241)]
            if side > 0: poly = [(edge(y), y) for y in ys] + [(40, 80), (40, -40)]
            else: poly = [(-40, -40), (-40, 80)] + [(edge(y), y) for y in reversed(ys)]
            bm = bmesh.new(); top = -0.4 + 0.10 * (k + 1)
            vs = [bm.verts.new((x, y, top)) for x, y in poly]
            f = bm.faces.new(vs); bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            r = bmesh.ops.extrude_face_region(bm, geom=[f])
            for v in [e for e in r['geom'] if isinstance(e, bmesh.types.BMVert)]: v.co.z -= 0.10
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            _bm_obj('ter', bm, paper)
    # Nile: recessed channel with a lighter bank line either side
    ribbon('nile', nile_x, -40, 80, 0.95, -0.398, water)
    for s in (-1, 1):
        ribbon('bank', lambda y, s=s: nile_x(y) + s * 0.53, -40, 80, 0.10, -0.396, lgrey)
    # irrigation canal + road parallel to the line (schematic)
    ribbon('canal', lambda y: rail_x(y) - 1.6 - 0.3 * math.sin(y * 0.2), -40, 80, 0.12, -0.397, water)
    ribbon('road', lambda y: rail_x(y) + 0.75, -40, 80, 0.09, -0.397, lgrey)
    # field parcels on the valley floor (west of the Nile, east of the desert edge), slightly embossed
    bmF = bmesh.new(); bmF2 = bmesh.new()
    for yy in [ -32 + i * 0.85 for i in range(76)]:
        x0 = nile_x(yy) - 7.8; x1 = nile_x(yy) - 0.75
        x = x0 + rnd.uniform(0, 0.4)
        while x < x1:
            wx = rnd.uniform(0.35, 1.1)
            xc = x + wx / 2
            near = min(abs(xc - rail_x(yy)), abs(xc - rail_x(yy) - 0.75), abs(xc - (rail_x(yy) - 1.6)))
            if near > 0.32 and x + wx < x1:
                _add_box(rnd.choice([bmF, bmF2]), (xc, yy + 0.42, -0.398 + 0.006), (wx - 0.07, 0.78, 0.012))
            x += wx
    # east bank too
        x0 = nile_x(yy) + 0.75; x1 = nile_x(yy) + 7.5; x = x0
        while x < x1:
            wx = rnd.uniform(0.4, 1.2)
            if x + wx < x1: _add_box(rnd.choice([bmF, bmF2]), (x + wx / 2, yy + 0.42, -0.392), (wx - 0.07, 0.78, 0.012))
            x += wx
    _bm_obj('fields', bmF, paper); _bm_obj('fields2', bmF2, paper3)
    # villages: clusters of tiny blocks beside each station
    bmV = bmesh.new()
    for nm, y in STATIONS:
        cx = rail_x(y) + 4.9
        for j in range(rnd.randint(28, 45)):
            a = rnd.uniform(0, 6.28); r = abs(rnd.gauss(0, 0.55))
            h = rnd.uniform(0.04, 0.12)
            _add_box(bmV, (cx + r * math.cos(a), y + r * math.sin(a) * 1.4, -0.39 + h / 2), (rnd.uniform(0.07, 0.15), rnd.uniform(0.07, 0.15), h), rz=rail_dir(y))
    _bm_obj('villages', bmV, paper)
    # railway: ink band with paper ties (classic map symbol)
    ribbon('rail', rail_x, -40, 80, 0.12, -0.375, ink)
    bmT = bmesh.new()
    for i in range(0, 1200):
        y = -40 + i * 0.1
        if i % 2: _add_box(bmT, (rail_x(y), y, -0.367), (0.07, 0.05, 0.004), rz=rail_dir(y))
    _bm_obj('railTies', bmT, paper)
    # stations: paper disc with ink ring on the line + lower-case label
    for nm, y in STATIONS:
        x = rail_x(y)
        cyl('stRing', 0.22, 0.05, (x, y, -0.35), m=ink, verts=32)
        cyl('stDot', 0.15, 0.06, (x, y, -0.345), m=paper, verts=32)
        text(nm, (x + 0.45, y - 0.22, -0.37), 0.55, ink if nm == 'el-ayyat' else grey, align='LEFT', extrude=0.012)
    # trains (schematic models)
    mini_train('t2010', y2010 - 2.71, 4, ink, mat('mInkBand', tuple(c * 0.55 for c in PAPER), rough=0.5), facing=-1)
    mini_train('t134', y134, 4, red, redD, facing=-1)
    label_card('L2010', '2010', (rail_x(y2010 - 1.6) + 0.9, y2010 - 1.6, -0.36), 1.25, ink, paper)
    label_card('L134', '134', (rail_x(y134 + 1.2) + 0.9, y134 + 1.2, -0.36), 1.25, ink, paper, accent=red)
    if show_gap:
        g0, g1 = y2010 + 0.25, y134 - 0.25
        ribbon('gap', lambda y: rail_x(y) - 0.55, g0, g1, 0.045, -0.36, red, n=600)
        for yy in (g0, g1):
            box('gapT', (0.30, 0.045, 0.02), (rail_x(yy) - 0.55, yy, -0.355), red, bevel=0.0)
    # scale bar + north arrow (lower-left of the frame, on the table)
    sx, sy = rail_x(-20) - 6.0, -20.0
    for k in range(2):
        box('sb', (1.0, 0.12, 0.02), (sx + 0.5 + k, sy, -0.37), ink if k == 0 else paper, bevel=0.0)
    box('sbO', (2.04, 0.16, 0.015), (sx + 1.0, sy, -0.375), ink, bevel=0.0)
    text('0', (sx, sy - 0.55, -0.37), 0.32, grey, align='CENTER', extrude=0.005)
    text('2 km', (sx + 2.0, sy - 0.55, -0.37), 0.32, grey, align='CENTER', extrude=0.005)
    me = bpy.data.meshes.new('north'); bm = bmesh.new()
    nx, ny = sx + 3.4, sy - 0.2
    v = [bm.verts.new(p) for p in ((nx, ny + 0.8, -0.36), (nx - 0.25, ny - 0.3, -0.36), (nx, ny - 0.1, -0.36), (nx + 0.25, ny - 0.3, -0.36))]
    bm.faces.new(v); bm.to_mesh(me); bm.free(); o = bpy.data.objects.new('north', me); link(o); me.materials.append(ink)
    text('n', (nx, ny + 0.95, -0.37), 0.34, ink, align='CENTER', extrude=0.005)

def scene(view='s3', y134=8.0):
    sc = reset(); sc.render.resolution_x, sc.render.resolution_y = 1080, 1920
    w = bpy.data.worlds.new('W'); sc.world = w; w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (*PAPER, 1); w.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.6
    sun(28, 290, strength=3.6, color=(1, 0.97, 0.93), angle=4)
    sc.view_settings.look = 'AgX - Base Contrast'; sc.view_settings.exposure = -0.2
    build(y134=y134, show_gap=(view == 's10'))
    if view == 's3':
        cam = camera((-9, -26, 22), (0.5, -4, 0), lens=50)
    else:
        mid = (CRASH_Y + y134) / 2
        cam = camera((rail_x(mid) - 4, mid - 13, 15), (rail_x(mid) + 0.8, mid, 0), lens=45)
    cam.data.dof.use_dof = True; cam.data.dof.focus_distance = (Vector(cam.location) - Vector((rail_x(CRASH_Y), CRASH_Y, 0))).length
    cam.data.dof.aperture_fstop = 2.0
    return sc

if __name__ == '__main__':
    view = sys.argv[sys.argv.index('--view') + 1] if '--view' in sys.argv else 's3'
    prev = '--final' not in sys.argv
    sc = scene(view, y134=(8.0 if view == 's3' else -4.0))
    sc.render.resolution_percentage = 50 if prev else 100; sc.cycles.samples = 48 if prev else 160
    sc.render.filepath = f'/home/claude/ep03/out/{view}_map' + ('_prev' if prev else '') + '.png'
    bpy.ops.render.render(write_still=True)
