import sys
sys.path.insert(0,'/home/claude/ep03')
import bpy
from mathutils import Vector
bpy.ops.wm.open_mainfile(filepath='/home/claude/ep03/gal_test.blend')
from lib import camera
sc=bpy.context.scene; sc.cycles.samples=16; sc.render.resolution_x=480; sc.render.resolution_y=720; sc.render.resolution_percentage=100
from PIL import Image
r1=bpy.data.objects['g1_rig']; r2=bpy.data.objects['g2_rig']
shots=[(10,r1,(3.2,0,1.0)),(30,r1,(2.2,-2.4,1.0)),(50,r1,(0,-3.4,1.0)),(250,r2,(2.0,-2.6,1.1)),(250,r2,(3.0,0.3,1.0))]
ims=[]
for f,r,off in shots:
    sc.frame_set(f); bpy.context.view_layer.update()
    hp=r.matrix_world@r.pose.bones['torso'].head
    tgt=Vector((hp.x,hp.y,0.85))
    cam=camera(tuple(tgt+Vector(off)-Vector((0,0,0.85-off[2]))),tuple(tgt),lens=40,name=f'c{f}')
    cam.location=tgt+Vector((off[0],off[1],0)); cam.location.z=off[2]
    d=tgt-cam.location; cam.rotation_euler=d.to_track_quat('-Z','Y').to_euler()
    sc.camera=cam; sc.render.filepath=f'/tmp/claude-0/g_{f}_{len(ims)}.png'; bpy.ops.render.render(write_still=True)
    ims.append(Image.open(sc.render.filepath).convert('RGB'))
W=Image.new('RGB',(480*len(ims),720),(255,255,255))
for i,im in enumerate(ims): W.paste(im,(i*480,0))
W.save('/home/claude/ep03/out/galabeya_v1.png'); print('DONE')
