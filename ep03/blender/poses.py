import math
import charsys as C
from lib import mat, box
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

def walk(r):
    arms_down(r, 64); C.set_ik_fk(r, ik=False)
    C.rotate(r,'thigh_fk.L',(1,0,0),-24); C.rotate(r,'shin_fk.L',(1,0,0),8)
    C.rotate(r,'thigh_fk.R',(1,0,0),16); C.rotate(r,'shin_fk.R',(1,0,0),30); C.rotate(r,'foot_fk.R',(1,0,0),15)
    C.move(r,'torso',(0,0,-0.03))
    C.rotate(r,'upper_arm_fk.L',(1,0,0),18); C.rotate(r,'upper_arm_fk.R',(1,0,0),-18); C.rotate(r,'forearm_fk.R',(1,0,0),-25)
