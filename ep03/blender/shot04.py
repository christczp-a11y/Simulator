"""Shot 4: El-Ayyat platform, 134 pulling out; 2-3 people walking (CMU 02_01 retarget) + one seated."""
import sys, math, random
sys.path.insert(0,'/home/claude/ep03')
import bpy
from mathutils import Vector, Matrix
from lib import *
PREV = '--final' not in sys.argv
sc = reset(); sc.render.fps = 30
import addon_utils; addon_utils.enable('rigify', default_set=True)
import world, charsys as C, people as PP, retarget as RT
world.lighting(exposure=-1.5)
G = 300.0
world.build(y_min=150, y_max=520, quality=0.6 if PREV else 1.0, gap134=G, hole=(255, 368))
rnd = random.Random(4)
PZ = 0.55                                   # platform top (rail top = 0)
conc = grime_mat('platConc', (0.50, 0.47, 0.42), rough=0.9, amount=0.45, scale=3, streak=False)
edge = mat('platEdge', (0.75, 0.62, 0.10), rough=0.7)
render_ = grime_mat('stRender', (0.66, 0.58, 0.45), rough=0.9, amount=0.5, scale=2, dirt=(0.35, 0.28, 0.2), streak=False)
dark = grime_mat('stDark', (0.12, 0.11, 0.10), rough=0.6, amount=0.3, streak=False)
green = grime_mat('stGreen', (0.10, 0.22, 0.18), rough=0.6, amount=0.35, streak=False)
Y0, Y1 = 262.0, 360.0
box('plat', (5.8, Y1 - Y0, PZ + 0.62), (1.75 + 2.9, (Y0 + Y1) / 2, (PZ - 0.62) / 2), conc, bevel=0.02)
box('platEdge', (0.45, Y1 - Y0, 0.012), (1.75 + 0.225, (Y0 + Y1) / 2, PZ + 0.006), edge, bevel=0.0)
for y in range(int(Y0) + 2, int(Y1), 1):   # slab joints
    box(f'pj{y}', (5.6, 0.012, 0.004), (4.7, y + 0.5, PZ + 0.002), dark, bevel=0.0)
# ---- canopy: steel columns, cantilever trusses, purlins, corrugated sheet, fascia + gutter, lights
import bmesh
from trains import tube
def sign_plane(name, w, h, loc, rot, img, rough=0.55):
    o = screen(name, w, h, loc, rot, img, strength=0.0)
    m = bpy.data.materials.get('sgn_' + img)
    if not m:
        m = bpy.data.materials.new('sgn_' + img); m.use_nodes = True; N = m.node_tree.nodes
        tx = N.new('ShaderNodeTexImage'); tx.image = bpy.data.images.load('/home/claude/ep03/assets/tex/' + img)
        bs = N['Principled BSDF']; bs.inputs['Roughness'].default_value = rough
        m.node_tree.links.new(tx.outputs['Color'], bs.inputs['Base Color'])
    o.data.materials[0] = m
    return o
sheet = grime_mat('roofSheet', (0.47, 0.47, 0.45), rough=0.42, metal=0.75, amount=0.55, scale=2, dirt=(0.28, 0.22, 0.16), streak=False)
cy0, cy1 = Y0 + 4, Y1 - 4
XF, XR = 2.25, 6.55                         # front (track side) / rear edge
ZF, ZR = PZ + 3.28, PZ + 3.50               # sheet falls toward the track gutter
def zroof(x): return ZF + (ZR - ZF) * (x - XF) / (XR - XF)
# corrugated sheet: profile along Y, straight along X
bm = bmesh.new(); pitch = 0.076; ny = int((cy1 - cy0) / (pitch / 2)) + 1
rowF, rowR = [], []
for i in range(ny):
    y = cy0 + i * pitch / 2; dz = 0.018 if i % 2 else -0.018
    rowF.append(bm.verts.new((XF - 0.05, y, zroof(XF - 0.05) + dz))); rowR.append(bm.verts.new((XR, y, zroof(XR) + dz)))
for i in range(ny - 1): bm.faces.new((rowF[i], rowF[i + 1], rowR[i + 1], rowR[i]))
me = bpy.data.meshes.new('canopySheet'); bm.to_mesh(me); bm.free()
for p in me.polygons: p.use_smooth = True
ob = bpy.data.objects.new('canopySheet', me); link(ob); me.materials.append(sheet)
ob.modifiers.new('sol', 'SOLIDIFY').thickness = 0.004
for k, xp in enumerate((2.45, 3.5, 4.6, 5.7, 6.4)):          # purlins (Z sections)
    box(f'purl{k}', (0.05, cy1 - cy0, 0.11), (xp, (cy0 + cy1) / 2, zroof(xp) - 0.08), green, bevel=0.004)
box('fascia', (0.03, cy1 - cy0 + 0.1, 0.32), (XF - 0.07, (cy0 + cy1) / 2, ZF - 0.08), green, bevel=0.005)
for i in range(int((cy1 - cy0) / 0.32)):                      # scalloped valance teeth
    yv = cy0 + 0.16 + i * 0.32
    box(f'val{i}', (0.025, 0.20, 0.10), (XF - 0.07, yv, ZF - 0.27), green, bevel=0.04)
gut = cyl('gutter', 0.07, cy1 - cy0, (XF - 0.13, (cy0 + cy1) / 2, ZF + 0.02), rot=(math.pi / 2, 0, 0),
          m=grime_mat('gutM', (0.35, 0.36, 0.35), rough=0.4, metal=0.8, amount=0.6, streak=False), verts=16)
lampM = mat('canLamp', (1, 1, 1), emit=(1, 0.96, 0.88), estr=4)
for y in range(int(Y0) + 8, int(Y1) - 6, 7):
    cyl(f'col{y}', 0.10, ZR - 0.15 - PZ, (5.2, y, PZ + (ZR - 0.15 - PZ) / 2), m=green, verts=14)
    cyl(f'colB{y}', 0.16, 0.25, (5.2, y, PZ + 0.125), m=green, verts=14)            # base collar
    box(f'colP{y}', (0.36, 0.36, 0.02), (5.2, y, PZ + 0.01), dark, bevel=0.003)       # base plate
    cyl(f'dp{y}', 0.035, ZR - PZ - 0.3, (5.33, y + 0.13, PZ + (ZR - PZ - 0.3) / 2), m=bpy.data.materials['gutM'], verts=10)
    # cantilever truss: top chord under the roof, bottom chord rising from the column, zig-zag web
    tb = lambda x: zroof(x) - 0.16
    bb = lambda x: PZ + 2.70 + (tb(XF + 0.1) - 0.06 - PZ - 2.70) * (5.2 - x) / (5.2 - XF - 0.1) if x <= 5.2 else PZ + 2.70 + (x - 5.2) * 0.35
    tube(f'trT{y}', [(XR - 0.05, y, tb(XR - 0.05)), (XF + 0.05, y, tb(XF + 0.05))], 0.045, green)
    tube(f'trB{y}', [(6.3, y, bb(6.3)), (5.2, y, bb(5.2)), (XF + 0.1, y, tb(XF + 0.1) - 0.06)], 0.035, green)
    xs = [6.3, 5.2, 4.55, 3.9, 3.25, 2.6]
    for j in range(len(xs) - 1):
        xa, xb_ = xs[j], xs[j + 1]
        p0 = (xa, y, bb(xa)) if j % 2 == 0 else (xa, y, tb(xa))
        p1 = (xb_, y, tb(xb_)) if j % 2 == 0 else (xb_, y, bb(xb_))
        tube(f'trW{y}{j}', [p0, p1], 0.022, green)
    # twin fluorescent fitting between trusses
    box(f'lfit{y}', (0.14, 1.25, 0.06), (3.6, y + 3.5, zroof(3.6) - 0.20), dark, bevel=0.01)
    box(f'ltube{y}', (0.08, 1.15, 0.02), (3.6, y + 3.5, zroof(3.6) - 0.235), lampM, bevel=0.0)
    cyl(f'bin{y}', 0.22, 0.75, (5.55, y + 1.0, PZ + 0.375), m=grime_mat('binM', (0.12, 0.25, 0.20), rough=0.5, metal=0.3, amount=0.5, streak=False), verts=18)
    cyl(f'binL{y}', 0.235, 0.05, (5.55, y + 1.0, PZ + 0.77), m=dark, verts=18)
# hanging platform sign + station name boards
for y in (293.5, 328.5):
    tube(f'shR{y}', [(3.6, y - 0.6, zroof(3.6) - 0.15), (3.6, y - 0.6, PZ + 2.75)], 0.008, dark)
    tube(f'shL{y}', [(3.6, y + 0.6, zroof(3.6) - 0.15), (3.6, y + 0.6, PZ + 2.75)], 0.008, dark)
    for sgn in (1, -1):
        sign_plane(f'plat{y}{sgn}', 1.5, 0.45, (3.6 + sgn * 0.016, y, PZ + 2.55), (math.pi / 2, 0, sgn * math.pi / 2), 'sign_plat.png')
    box(f'platS{y}', (0.03, 1.56, 0.50), (3.6, y, PZ + 2.55), dark, bevel=0.004)
# station building behind the platform
bx0 = 8.6
box('stBld', (5.0, 30, 5.35), (bx0 + 2.5, 312, PZ + 2.1 - 0.575), render_, bevel=0.03)
box('stCorn', (5.3, 30.3, 0.25), (bx0 + 2.5, 312, PZ + 4.25), render_, bevel=0.02)
for k in range(8):
    y = 299 + k * 3.6
    box(f'stWin{k}', (0.08, 1.2, 1.6 if k % 3 else 2.4), (bx0 - 0.02, y, PZ + (1.5 if k % 3 else 1.2)), dark, bevel=0.01)
    box(f'stSh{k}', (0.10, 1.3, 0.10), (bx0 - 0.04, y, PZ + (2.35 if k % 3 else 2.45)), render_, bevel=0.0)
sign_plane('nameplate', 3.2, 0.80, (bx0 - 0.075, 312, PZ + 3.35), (math.pi / 2, 0, -math.pi / 2), 'sign_station.png')
box('nameplateFr', (0.06, 3.3, 0.90), (bx0 - 0.03, 312, PZ + 3.35), dark, bevel=0.01)
for k, y in enumerate((286, 304, 322)):    # benches
    box(f'bs{k}', (0.45, 1.8, 0.05), (6.6, y, PZ + 0.45), grime_mat('benchW', (0.30, 0.20, 0.12), rough=0.7, amount=0.3), bevel=0.01)
    box(f'bb{k}', (0.05, 1.8, 0.40), (6.85, y, PZ + 0.72), bpy.data.materials['benchW'], bevel=0.01)
    for dy in (-0.8, 0.8): box(f'bl{k}{dy}', (0.40, 0.05, 0.45), (6.65, y + dy, PZ + 0.22), dark, bevel=0.0)
# --- people
cast = [
  ('w1', dict(sex='m',age='adult',height=1.75,skin='brown',hair='short',facial='moustache',top='galabeya',top_col=(0.55,0.50,0.42),bottom='none'), (4.4, 278.5), 180, 3),
  ('w2', dict(sex='f',age='adult',height=1.63,skin='tan',hair='none',hijab=(0.14,0.10,0.12),top='tee',top_col=(0.26,0.18,0.20),sleeve='long',bottom_col=(0.09,0.09,0.10)), (3.3, 289.0), 0, 11),
  ('w3', dict(sex='m',age='adult',height=1.78,skin='tan',hair='side',facial='stubble',top='shirt',top_col=(0.68,0.70,0.72),sleeve='rolled',bottom_col=(0.16,0.16,0.20)), (5.3, 295.0), 175, 19),
]
F = 40
for name, P, (x, y), heading, off in cast:
    r, b = C.make_character(name=name, loc=(0, 0, 0), **P)
    bpy.context.view_layer.update()
    last = RT.retarget(r, '/home/claude/ep03/mocap/02_01.bvh', step=4, frame_offset=1 - off)
    RT.fix_feet(r, 1, last); RT.ground(r, 1, last)
    sc.frame_set(F)
    t = r.matrix_world @ r.pose.bones['torso'].head
    fw = (r.matrix_world @ r.pose.bones['torso'].head)
    sc.frame_set(F + 6); fw = (r.matrix_world @ r.pose.bones['torso'].head) - fw; sc.frame_set(F)
    cur = math.atan2(fw.x, -fw.y)          # current walking heading, 0 = toward -Y
    r.rotation_euler.z = math.radians(heading) - cur
    bpy.context.view_layer.update()
    t = r.matrix_world @ r.pose.bones['torso'].head
    r.location += Vector((x - t.x, y - t.y, PZ))
seat, _ = C.make_character(name='s1', sex='m', age='old', height=1.68, build=1.1, skin='brown', hair='receding', hair_col=(0.6,0.6,0.58), facial='full', top='galabeya', top_col=(0.30,0.32,0.36), bottom='none')
bpy.context.view_layer.update()
PP.sit(seat, (6.55, 286.0, PZ + 0.48), facing=-90)
PP.head_turn(seat, yaw=-35, pitch=-4); PP.expr(seat, 'look')
import poses as PO
for nm, P_, (x, y), face, look in [
    ('st1', dict(sex='f', age='adult', height=1.60, build=1.15, skin='tan', hair='none', hijab=(0.05, 0.05, 0.06), top='galabeya', top_col=(0.06, 0.06, 0.07), bottom='none'), (5.75, 309.5), -100, 20),
    ('st2', dict(sex='m', age='adult', height=1.72, skin='brown', hair='short', top='tee', top_col=(0.62, 0.60, 0.55), sleeve='short', bottom_col=(0.20, 0.25, 0.35)), (4.9, 317.0), -75, -10),
    ('st3', dict(sex='m', age='adult', height=1.70, build=1.2, skin='brown', hair='receding', facial='moustache', top='shirt', top_col=(0.40, 0.42, 0.33), sleeve='long', bottom_col=(0.13, 0.12, 0.11)), (6.2, 324.0), -95, 0),
]:
    rr, _ = C.make_character(name=nm, **P_); PO.stand(rr)
    rr.rotation_euler.z = math.radians(face); rr.location = (x, y, PZ)
    PP.head_turn(rr, yaw=look, pitch=-3); PP.expr(rr, 'look')
lug = [grime_mat('lugA', (0.10, 0.12, 0.16), rough=0.5, amount=0.3, streak=False), grime_mat('lugB', (0.45, 0.32, 0.18), rough=0.8, amount=0.4, streak=False),
       grime_mat('lugC', (0.55, 0.50, 0.44), rough=0.95, amount=0.4, streak=False)]
box('case1', (0.25, 0.45, 0.62), (6.35, 288.3, PZ + 0.31), lug[0], bevel=0.04)
cyl('caseH', 0.012, 0.25, (6.35, 288.3, PZ + 0.72), m=dark, verts=8)
box('bag1', (0.30, 0.50, 0.28), (6.2, 309.0, PZ + 0.14), lug[1], bevel=0.08)
o = cyl('sack', 0.26, 0.55, (5.95, 323.6, PZ + 0.26), m=lug[2], verts=16, bevel=0.08); o.rotation_euler = (0.12, 0.05, 0)
box('box1', (0.40, 0.35, 0.30), (6.6, 324.6, PZ + 0.15), grime_mat('cardb', (0.50, 0.38, 0.24), rough=0.9, amount=0.3, streak=False), bevel=0.005)
sc.frame_set(F)
cam = camera((6.3, 270.5, PZ + 1.55), (2.4, 300.0, PZ + 1.75), lens=32)
cam.data.dof.use_dof = True; cam.data.dof.focus_distance = 10; cam.data.dof.aperture_fstop = 5.6
sc.render.resolution_percentage = 50 if PREV else 100; sc.cycles.samples = 48 if PREV else 160
sc.render.filepath = '/home/claude/ep03/out/s04' + ('_prev' if PREV else '') + '.png'
bpy.ops.wm.save_as_mainfile(filepath='/home/claude/ep03/s04.blend')
bpy.ops.render.render(write_still=True)
