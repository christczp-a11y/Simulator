"""Stylised faceted low-poly human (Skin modifier) posed by simple FK.
Facing -Y. Units metres. person(...) returns a baked mesh object with zone materials."""
import bpy, bmesh, math, random
from mathutils import Vector, Matrix, Euler
from lib import mat, grime_mat, link

SKIN = [(0.42,0.26,0.16),(0.34,0.20,0.12),(0.52,0.34,0.22),(0.26,0.16,0.10)]
TOPS = [(0.07,0.09,0.13),(0.55,0.52,0.47),(0.19,0.23,0.30),(0.38,0.11,0.09),(0.72,0.70,0.64),(0.11,0.19,0.15),(0.30,0.26,0.22)]
BOTS = [(0.05,0.05,0.06),(0.20,0.18,0.16),(0.09,0.11,0.17),(0.28,0.24,0.19)]

def R(x=0,y=0,z=0): return Euler((math.radians(x),math.radians(y),math.radians(z))).to_matrix()

def fk(pose):
    """pose: dict of joint rotations (degrees). returns joint positions for 1.72m figure."""
    P = {}
    g = lambda k, d=(0,0,0): pose.get(k, d)
    root = Vector(pose.get('root', (0,0,0.98)))
    Mroot = R(*g('hips'))
    P['pelvis'] = root
    # spine chain
    Ms = Mroot @ R(*g('spine'))
    P['spine'] = P['pelvis'] + Ms @ Vector((0,0,0.20))
    Mc = Ms @ R(*g('chest'))
    P['chest'] = P['spine'] + Mc @ Vector((0,0,0.18))
    Mn = Mc @ R(*g('neck'))
    P['neck'] = P['chest'] + Mn @ Vector((0,0,0.13))
    Mh = Mn @ R(*g('head'))
    P['head'] = P['neck'] + Mh @ Vector((0,-0.01,0.10))
    P['crown'] = P['head'] + Mh @ Vector((0,0.01,0.13))
    P['nose'] = P['head'] + Mh @ Vector((0,-0.095,0.015))
    P['jaw'] = P['head'] + Mh @ Vector((0,-0.04,-0.06))
    for side, sx in (('l',1),('r',-1)):
        sh = P['chest'] + Mc @ Vector((0.17*sx, 0, 0.06))
        P[side+'_sh'] = sh
        Ma = Mc @ R(*g(side+'_arm', (0, 10*sx, 0)))
        P[side+'_el'] = sh + Ma @ Vector((0,0,-0.28))
        Mf = Ma @ R(*g(side+'_fore', (0,0,0)))
        P[side+'_wr'] = P[side+'_el'] + Mf @ Vector((0,0,-0.25))
        P[side+'_hand'] = P[side+'_wr'] + Mf @ Vector((0,0,-0.10))
        hp = P['pelvis'] + Mroot @ Vector((0.10*sx, 0, -0.04))
        P[side+'_hip'] = hp
        Mt = Mroot @ R(*g(side+'_thigh'))
        P[side+'_kn'] = hp + Mt @ Vector((0,0,-0.43))
        Ml = Mt @ R(*g(side+'_shin'))
        P[side+'_an'] = P[side+'_kn'] + Ml @ Vector((0,0,-0.43))
        Mft = Ml @ R(*g(side+'_foot'))
        P[side+'_toe'] = P[side+'_an'] + Mft @ Vector((0,-0.16,-0.05))
    return P

EDGES = [('pelvis','spine'),('spine','chest'),('chest','neck'),('neck','head'),('head','crown'),('head','nose'),('head','jaw'),
 ('chest','l_sh'),('l_sh','l_el'),('l_el','l_wr'),('l_wr','l_hand'),
 ('chest','r_sh'),('r_sh','r_el'),('r_el','r_wr'),('r_wr','r_hand'),
 ('pelvis','l_hip'),('l_hip','l_kn'),('l_kn','l_an'),('l_an','l_toe'),
 ('pelvis','r_hip'),('r_hip','r_kn'),('r_kn','r_an'),('r_an','r_toe')]
RAD = {'pelvis':(0.16,0.11),'spine':(0.145,0.10),'chest':(0.175,0.11),'neck':(0.05,0.05),'head':(0.082,0.098),'crown':(0.065,0.075),'nose':(0.016,0.02),'jaw':(0.055,0.05),
 'sh':(0.06,0.06),'el':(0.045,0.045),'wr':(0.033,0.028),'hand':(0.045,0.02),
 'hip':(0.085,0.085),'kn':(0.058,0.058),'an':(0.04,0.045),'toe':(0.045,0.035)}

SEATED = {'root':(0,0,0.47+0.02), 'l_thigh':(-88,0,-4), 'r_thigh':(-86,0,4), 'l_shin':(84,0,0), 'r_shin':(88,0,0),
          'l_foot':(0,0,0),'r_foot':(0,0,0),
          'l_arm':(-25,10,0), 'r_arm':(-25,-10,0), 'l_fore':(-60,0,0), 'r_fore':(-60,0,0)}

def person(name, pose=None, seed=0, height=1.72, width=1.0, galabeya=False, hijab=False, loc=(0,0,0), rotz=0.0):
    rnd = random.Random(seed)
    pose = dict(pose or {})
    P = fk(pose); s = height/1.72
    keys = list(P.keys())
    me = bpy.data.meshes.new(name); bm = bmesh.new(); vm = {}
    for k in keys: vm[k] = bm.verts.new(P[k]*s)
    for a,b in EDGES: bm.edges.new((vm[a], vm[b]))
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); link(o)
    sk = o.modifiers.new('skin','SKIN'); sk.branch_smoothing = 0.7
    for i,k in enumerate(keys):
        base = k.split('_')[-1] if '_' in k else k
        rx, ry = RAD.get(k, RAD.get(base, (0.05,0.05)))
        if k in ('pelvis','spine','chest'): rx*=width; ry*=width
        if galabeya and base in ('kn','an'): rx*=1.6; ry*=1.6
        me.skin_vertices[0].data[i].radius = (rx*s, ry*s)
    me.skin_vertices[0].data[keys.index('pelvis')].use_root = True
    sub = o.modifiers.new('sub','SUBSURF'); sub.levels = 1; sub.render_levels = 1
    dec = o.modifiers.new('dec','DECIMATE'); dec.ratio = 0.5
    dg = bpy.context.evaluated_depsgraph_get()
    me2 = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
    o.modifiers.clear(); o.data = me2
    skin = mat(f'skin{seed}', rnd.choice(SKIN), rough=0.5)
    top = grime_mat(f'top{seed}', rnd.choice(TOPS), rough=0.85, amount=0.2, scale=8)
    bot = grime_mat(f'bot{seed}', rnd.choice(BOTS), rough=0.85, amount=0.2, scale=8)
    hair = mat('hair', (0.018,0.014,0.012), rough=0.55)
    shoe = mat('shoe', (0.03,0.025,0.02), rough=0.45)
    for m_ in (skin, top, bot, hair, shoe): me2.materials.append(m_)
    # classify faces by nearest skeleton segment
    segs = [(a,b) for a,b in EDGES]
    def part(c):
        best=None; bd=1e9
        for a,b in segs:
            A=P[a]*s; B=P[b]*s; ab=B-A; t=max(0,min(1,(c-A).dot(ab)/max(ab.length_squared,1e-9))); d=(A+ab*t-c).length
            if d<bd: bd=d; best=(a,b,t)
        return best
    for poly in me2.polygons:
        a,b,t = part(poly.center)
        names = (a,b)
        idx = 1
        if 'head' in names or 'nose' in names or 'jaw' in names or 'neck' in names: idx = 0
        if ('head','crown') == names:
            # hair on top/back, face skin on front
            idx = 3 if (poly.center.y - P['head'].y*s) > -0.03*s or poly.center.z > P['crown'].z*s-0.02 else 0
        if b.endswith('hand') or (b.endswith('wr') and t > 0.6): idx = 0
        if any(n.endswith(('hip','kn','an')) for n in names) or a=='pelvis' and b.endswith('hip'): idx = 1 if galabeya else 2
        if b.endswith('toe') or (b.endswith('an') and t>0.85): idx = 4
        if hijab and (names in (('head','crown'),('neck','head'),('chest','neck')) ) and not (names==('head','crown') and poly.center.y < P['head'].y*s-0.05 and poly.center.z < P['crown'].z*s-0.04):
            idx = 1
        poly.material_index = idx; poly.use_smooth = False
    o.location = loc; o.rotation_euler = (0,0,rotz)
    return o
