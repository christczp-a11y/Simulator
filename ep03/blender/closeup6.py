import sys
sys.path.insert(0,'/home/claude/ep03')
import bpy
from mathutils import Vector
blend,frames,out=sys.argv[-3],[int(x) for x in sys.argv[-2].split(',')],sys.argv[-1]
bpy.ops.wm.open_mainfile(filepath=blend)
from lib import mat, sun, camera
sc=bpy.context.scene
sc.render.engine='CYCLES'; sc.cycles.device='CPU'; sc.cycles.samples=16; sc.cycles.use_denoising=True
sc.render.resolution_x=400; sc.render.resolution_y=400; sc.view_settings.view_transform='AgX'
w=bpy.data.worlds.new('W'); sc.world=w; w.use_nodes=True
w.node_tree.nodes['Background'].inputs['Color'].default_value=(0.93,0.925,0.91,1); w.node_tree.nodes['Background'].inputs['Strength'].default_value=0.8
sun(42,215,strength=3.0,color=(1,0.97,0.92),angle=5)
bpy.ops.mesh.primitive_plane_add(size=200); bpy.context.object.data.materials.append(mat('floor',(0.80,0.795,0.78),rough=0.8))
rig=[o for o in bpy.data.objects if o.name.endswith('_rig')][0]
cam=camera((4,0,1.2),(0,0,0.9),lens=50)
from PIL import Image
ims=[]
views=[('DEF-spine.001',Vector((0.9,-0.5,0.15))),('DEF-spine.001',Vector((0.0,-1.0,0.1))),('DEF-spine.001',Vector((-0.9,0.4,0.1)))]
for f in frames:
    sc.frame_set(f); bpy.context.view_layer.update()
    for bn,off in views:
        p=rig.matrix_world @ rig.pose.bones[bn].head
        cam.location=p+off; d=p-cam.location; cam.rotation_euler=d.to_track_quat('-Z','Y').to_euler()
        sc.render.filepath=f'/tmp/claude-0/cu_{f}_{bn}.png'; bpy.ops.render.render(write_still=True)
        ims.append(Image.open(sc.render.filepath).convert('RGB'))
n=len(views)
W=Image.new('RGB',(400*n,400*len(frames)),(255,255,255))
for i,im in enumerate(ims): W.paste(im,((i%n)*400,(i//n)*400))
W.save(out); print('DONE')
