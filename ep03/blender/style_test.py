import sys, math
sys.path.insert(0,'/home/claude/ep03')
import bpy
from lib import *
sc=reset(); sc.render.resolution_x=1600; sc.render.resolution_y=900; sc.cycles.samples=48
sc.view_settings.look='AgX - Base Contrast'
w=bpy.data.worlds.new('W'); sc.world=w; w.use_nodes=True
w.node_tree.nodes['Background'].inputs['Color'].default_value=(0.93,0.925,0.91,1); w.node_tree.nodes['Background'].inputs['Strength'].default_value=0.6
sun(40,210,strength=3.0,color=(1,0.97,0.92),angle=4)
bpy.ops.mesh.primitive_plane_add(size=60); fl=bpy.context.object; fl.data.materials.append(mat('floor',(0.80,0.795,0.78),rough=0.8))
def imp(path,x,rz=0):
    before=set(bpy.data.objects); bpy.ops.import_scene.gltf(filepath=path)
    new=[o for o in bpy.data.objects if o not in before]
    roots=[o for o in new if o.parent is None]
    for r in roots: r.location.x+=x; r.rotation_euler.z+=rz
    # stop animation: set frame 0 rest
    for o in new:
        if o.animation_data: o.animation_data.action=None
    return [o for o in new if o.type=='MESH']
def muted(meshes,sat=0.35,val=0.85):
    for o in meshes:
        for s in o.material_slots:
            m=s.material.copy(); s.material=m; nt=m.node_tree; b=[n for n in nt.nodes if n.type=='BSDF_PRINCIPLED'][0]
            lk=b.inputs['Base Color'].links
            if lk:
                hsv=nt.nodes.new('ShaderNodeHueSaturation'); hsv.inputs['Saturation'].default_value=sat; hsv.inputs['Value'].default_value=val
                nt.links.new(lk[0].from_socket,hsv.inputs['Color']); nt.links.new(hsv.outputs['Color'],b.inputs['Base Color'])
            b.inputs['Roughness'].default_value=0.75
            if 'Metallic' in b.inputs: b.inputs['Metallic'].default_value=0
def clay(meshes,col):
    m=mat('clay'+str(col),col,rough=0.7)
    for o in meshes:
        for s in o.material_slots: s.material=m
# row: original, muted, clay
X=[-2.4,-1.6,-0.4,0.4,1.6,2.4]
a=imp('assets/Michelle.glb',X[0]); b=imp('assets/Soldier.glb',X[1],math.pi)
c=imp('assets/Michelle.glb',X[2]); d=imp('assets/Soldier.glb',X[3],math.pi); muted(c); muted(d)
e=imp('assets/Michelle.glb',X[4]); f=imp('assets/Soldier.glb',X[5],math.pi); clay(e,(0.78,0.775,0.76)); clay(f,(0.30,0.30,0.30))
cam=camera((0,-7.5,1.3),(0,0,0.9),lens=50)
sc.render.filepath='/home/claude/ep03/out/style_test.png'
bpy.ops.render.render(write_still=True); print('DONE')
