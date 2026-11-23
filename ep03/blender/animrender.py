import sys
sys.path.insert(0,'/home/claude/ep03')
import bpy
from mathutils import Vector
blend,mode,out=sys.argv[-4],sys.argv[-2],sys.argv[-1]
bpy.ops.wm.open_mainfile(filepath=blend)
from lib import mat, sun, camera, box
sc=bpy.context.scene
sc.render.engine='CYCLES'; sc.cycles.device='CPU'; sc.cycles.samples=8; sc.cycles.use_denoising=True
sc.render.resolution_x=480; sc.render.resolution_y=600; sc.view_settings.view_transform='AgX'
w=bpy.data.worlds.new('W'); sc.world=w; w.use_nodes=True
w.node_tree.nodes['Background'].inputs['Color'].default_value=(0.93,0.925,0.91,1); w.node_tree.nodes['Background'].inputs['Strength'].default_value=0.8
sun(42,215,strength=3.0,color=(1,0.97,0.92),angle=5)
rig=[o for o in bpy.data.objects if o.name.endswith('_rig')][0]
ms=[o for o in bpy.data.objects if o.type=='MESH' and o.parent==rig]
SF=int(sys.argv[-3])
sc.frame_set(SF); dg=bpy.context.evaluated_depsgraph_get()
hp=rig.matrix_world@rig.pose.bones['DEF-thigh.L'].head; hr=rig.matrix_world@rig.pose.bones['DEF-thigh.R'].head; hc=(hp+hr)/2
zs=[]
for o in ms:
    e=o.evaluated_get(dg); m=e.to_mesh()
    for v in m.vertices:
        p=o.matrix_world@v.co
        if p.z>0.25 and abs(p.y-hc.y)<0.10 and abs(p.x-hc.x)<0.2: zs.append(p.z)
    e.to_mesh_clear()
seat=min(zs); print('seat top',seat)
if mode=='sit':
  C=mat('chair',(0.55,0.32,0.20),rough=0.6)
  box('seat',(0.5,0.48,0.06),(hc.x,hc.y+0.08,seat-0.03),C)
  box('back',(0.5,0.05,0.62),(hc.x,hc.y+0.33,seat+0.30),C)
  for dx in (-0.22,0.22):
    for dy in (-0.14,0.30): box('leg',(0.04,0.04,seat-0.06),(hc.x+dx,hc.y+0.08+dy*0.7,(seat-0.06)/2),C)
bpy.ops.mesh.primitive_plane_add(size=200); bpy.context.object.data.materials.append(mat('floor',(0.80,0.795,0.78),rough=0.8))
cam=camera((4,0,1.2),(0,0,0.9),lens=45)
import os
os.makedirs(out,exist_ok=True)
act=rig.animation_data.action; f1=int(act.frame_range[1])
cx=None
for f in range(1,f1+1):
    sc.frame_set(f)
    t=rig.matrix_world@rig.pose.bones['torso'].head
    if mode=='sit': c=hc
    else:
        cx=t.copy() if cx is None else cx.lerp(t,0.15); c=cx
    cam.location=(c.x+4.0, c.y-0.6, 1.0)
    d=Vector((c.x,c.y-0.1,0.75))-cam.location; cam.rotation_euler=d.to_track_quat('-Z','Y').to_euler()
    sc.render.filepath=f'{out}/{f:04d}.png'; bpy.ops.render.render(write_still=True)
print('DONE')
