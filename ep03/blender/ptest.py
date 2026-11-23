import sys, math
sys.path.insert(0,'/home/claude/ep03')
import bpy
from mathutils import Vector
from lib import reset, mat, sun, camera, box
sc=reset()
import charsys as C
sc.render.resolution_x=2000; sc.render.resolution_y=1000; sc.cycles.samples=40
sc.view_settings.look='AgX - Base Contrast'
w=bpy.data.worlds.new('W'); sc.world=w; w.use_nodes=True
w.node_tree.nodes['Background'].inputs['Color'].default_value=(0.93,0.925,0.91,1); w.node_tree.nodes['Background'].inputs['Strength'].default_value=0.7
sun(42,215,strength=3.0,color=(1,0.97,0.92),angle=5)
bpy.ops.mesh.primitive_plane_add(size=60); bpy.context.object.data.materials.append(mat('floor',(0.80,0.795,0.78),rough=0.8))
SEAT=mat('seat',(0.18,0.30,0.30),rough=0.7)
def arms_down(r, ang=72):
    C.set_ik_fk(r, ik=False)
    for n in ('thigh_parent.L','thigh_parent.R'): r.pose.bones[n]['IK_FK']=0.0
    C.rotate(r,'upper_arm_fk.L',(0,1,0), ang); C.rotate(r,'upper_arm_fk.R',(0,1,0),-ang)
def stand(r):
    arms_down(r, 58); C.rotate(r,'forearm_fk.L',(1,0,0),-12); C.rotate(r,'forearm_fk.R',(1,0,0),-12)
def seated(r, x):
    arms_down(r, 68)
    hip = r.pose.bones['torso'].matrix.translation.z
    seat_h=0.46
    C.move(r,'torso',(0,0.06,-(hip-seat_h-0.07)))
    for sd,sx in (('L',1),('R',-1)):
        C.move(r,f'foot_ik.{sd}',(sx*0.02,-0.40,0))
        C.rotate(r,f'upper_arm_fk.{sd}',(1,0,0),-25)
        C.rotate(r,f'forearm_fk.{sd}',(1,0,0),-60)
    C.rotate(r,'chest',(1,0,0),-6)
    # seat geometry
    box('seat',(0.50,0.48,0.10),(x,0.10,seat_h-0.02),SEAT,bevel=0.02)
    box('back',(0.50,0.10,0.70),(x,0.38,seat_h+0.33),SEAT,bevel=0.02)
def run(r):
    arms_down(r, 66); C.set_ik_fk(r, ik=False)
    C.move(r,'torso',(0,-0.04,-0.05)); C.rotate(r,'torso',(1,0,0),-12)
    C.rotate(r,'thigh_fk.L',(1,0,0),-55); C.rotate(r,'shin_fk.L',(1,0,0),70); C.rotate(r,'foot_fk.L',(1,0,0),-10)
    C.rotate(r,'thigh_fk.R',(1,0,0),28); C.rotate(r,'shin_fk.R',(1,0,0),85); C.rotate(r,'foot_fk.R',(1,0,0),30)
    C.rotate(r,'upper_arm_fk.L',(1,0,0),40); C.rotate(r,'forearm_fk.L',(1,0,0),-75)
    C.rotate(r,'upper_arm_fk.R',(1,0,0),-45); C.rotate(r,'forearm_fk.R',(1,0,0),-85)
    C.move(r,'torso',(0,0,0.10))
def brace(r):
    # thrown backward / losing balance
    arms_down(r, 30)
    C.rotate(r,'torso',(1,0,0),14); C.move(r,'torso',(0,0.10,-0.08))
    C.move(r,'foot_ik.L',(0.05,-0.30,0.10)); C.rotate(r,'foot_ik.L',(1,0,0),-25)
    C.rotate(r,'neck',(1,0,0),-20); C.rotate(r,'head',(1,0,0),-10)
    for sd,sx in (('L',1),('R',-1)):
        C.rotate(r,f'upper_arm_fk.{sd}',(1,0,0),-35); C.rotate(r,f'forearm_fk.{sd}',(1,0,0),-35)
    C.mouth(r,'A')
people=[
 (dict(name='m1',sex='m',age='adult',height=1.76,skin='tan',hair='short',facial='moustache',top='shirt',top_col=(0.62,0.66,0.70),sleeve='short',bottom_col=(0.15,0.15,0.17)), stand),
 (dict(name='f1',sex='f',age='adult',height=1.63,skin='light',hair='none',hijab=(0.36,0.20,0.22),top='tee',top_col=(0.20,0.22,0.26),sleeve='long',bottom_col=(0.12,0.12,0.14)), 'seated'),
 (dict(name='o1',sex='m',age='old',height=1.70,build=1.15,skin='brown',hair='receding',hair_col=(0.55,0.54,0.52),facial='full',top='shirt',top_col=(0.78,0.76,0.70),sleeve='long',bottom_col=(0.28,0.25,0.21),glasses=True), 'seated'),
 (dict(name='c1',sex='m',age='child',height=1.28,skin='tan',hair='curly',top='tee',top_col=(0.55,0.15,0.12),sleeve='short',bottom='shorts',bottom_col=(0.18,0.22,0.32)), run),
 (dict(name='u1',sex='m',age='adult',height=1.80,skin='brown',hair='short',facial='stubble',top='uniform',top_col=(0.20,0.24,0.32),sleeve='long',bottom_col=(0.14,0.16,0.22),cap=(0.16,0.19,0.26)), brace),
]
xs=[-1.8,-0.9,0,0.9,1.8]
for x,(p,fn) in zip(xs,people):
    r,b=C.make_character(loc=(x,0,0),**p)
    bpy.context.view_layer.update()
    if fn=='seated': seated(r,x)
    else: fn(r)
cam=camera((1.2,-6.6,1.5),(0,0,0.8),lens=48)
sc.render.filepath='/home/claude/ep03/out/chars_v1_poses.png'
bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath='/home/claude/ep03/chars_v1p.blend')
print('DONE')
