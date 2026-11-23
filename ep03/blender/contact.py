import sys, math
sys.path.insert(0,'/home/claude/ep03')
import bpy
from mathutils import Vector
blend=sys.argv[-3]; frames=[int(x) for x in sys.argv[-2].split(',')]; out=sys.argv[-1]
bpy.ops.wm.open_mainfile(filepath=blend)
from lib import mat, sun, camera
sc=bpy.context.scene
sc.render.engine='CYCLES'; sc.cycles.device='CPU'; sc.cycles.samples=12; sc.cycles.use_denoising=True
sc.render.resolution_x=420; sc.render.resolution_y=560; sc.view_settings.view_transform='AgX'
w=bpy.data.worlds.new('W'); sc.world=w; w.use_nodes=True
w.node_tree.nodes['Background'].inputs['Color'].default_value=(0.93,0.925,0.91,1); w.node_tree.nodes['Background'].inputs['Strength'].default_value=0.8
sun(42,215,strength=3.0,color=(1,0.97,0.92),angle=5)
bpy.ops.mesh.primitive_plane_add(size=200); bpy.context.object.data.materials.append(mat('floor',(0.80,0.795,0.78),rough=0.8))
rig=[o for o in bpy.data.objects if o.name.endswith('_rig')][0]
cam=camera((4,0,1.2),(0,0,0.9),lens=50)
from PIL import Image
ims=[]
for f in frames:
    sc.frame_set(f); bpy.context.view_layer.update()
    hp=rig.matrix_world @ rig.pose.bones['torso'].head
    cam.location=(hp.x+4.2, hp.y, 1.1); 
    d=Vector((hp.x,hp.y,0.85))-cam.location; cam.rotation_euler=d.to_track_quat('-Z','Y').to_euler()
    sc.render.filepath=f'/tmp/claude-0/cf_{f}.png'; bpy.ops.render.render(write_still=True)
    ims.append(Image.open(sc.render.filepath).convert('RGB'))
W=Image.new('RGB',(420*len(ims),560),(255,255,255))
for i,im in enumerate(ims): W.paste(im,(i*420,0))
W.save(out); print('DONE')
