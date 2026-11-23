"""Scene people: seated/standing posing + facial expressions on charsys rigs."""
import math, bpy
from mathutils import Vector
import charsys as C

def sit(r, at, facing=0.0, lean=-6, knees=0.40):
    """Seat a fresh rig so hips rest on a cushion whose top is at 'at' (x,y,z). facing: yaw deg (0 = faces -Y)."""
    r.location = (at[0], at[1] + 0.02, at[2] - 0.46 + 0.0)
    r.rotation_euler = (0, 0, math.radians(facing))
    bpy.context.view_layer.update()
    C.set_ik_fk(r, ik=False)
    for n in ('thigh_parent.L', 'thigh_parent.R'): r.pose.bones[n]['IK_FK'] = 0.0
    C.rotate(r, 'upper_arm_fk.L', (0, 1, 0), 68); C.rotate(r, 'upper_arm_fk.R', (0, 1, 0), -68)
    hip = r.pose.bones['torso'].matrix.translation.z
    C.move(r, 'torso', (0, 0.06, -(hip - 0.46 - 0.07)))
    for sd, sx in (('L', 1), ('R', -1)):
        C.move(r, f'foot_ik.{sd}', (sx * 0.03, -knees, 0))
        C.rotate(r, f'upper_arm_fk.{sd}', (1, 0, 0), -14)
        C.rotate(r, f'upper_arm_fk.{sd}', (0, 1, 0), sx * 6)
        C.rotate(r, f'forearm_fk.{sd}', (1, 0, 0), -38)
        C.rotate(r, f'forearm_fk.{sd}', (0, 0, 1), -sx * 22)
    C.rotate(r, 'chest', (1, 0, 0), lean)

def _qrot(r, n, axis, deg):
    from mathutils import Quaternion
    pb = r.pose.bones[n]; pb.rotation_mode = 'QUATERNION'
    pb.rotation_quaternion = pb.rotation_quaternion @ Quaternion(axis, math.radians(deg))
    bpy.context.view_layer.update()

def head_turn(r, yaw=0, pitch=0, roll=0):
    """yaw > 0 turns the face toward the character's left (+X when facing -Y)."""
    # Rigify head is isolated (follows torso, not neck/chest): head gets the full yaw, neck only shapes the bend
    if yaw: _qrot(r, 'neck', (0, 1, 0), yaw * 0.45); _qrot(r, 'head', (0, 1, 0), yaw)
    if pitch: _qrot(r, 'head', (1, 0, 0), -pitch)
    if roll: _qrot(r, 'head', (0, 0, 1), roll)

def chest_turn(r, yaw):
    _qrot(r, 'chest', (0, 1, 0), yaw)

def gesture(r, side='R', lift=35, fore=-35):
    C.rotate(r, f'upper_arm_fk.{side}', (1, 0, 0), -lift)
    C.rotate(r, f'forearm_fk.{side}', (1, 0, 0), fore)

def expr(r, kind='neutral', amt=1.0):
    s = r.get('H', 1.74) / 1.98 if 'H' in r.keys() else 0.88
    for sd in 'LR':
        r.pose.bones['eye.' + sd].scale = (1, 1, 1)
        r.pose.bones['brow.' + sd].location = (0, 0, 0)
    C.mouth(r, 'rest')
    if kind == 'talk':
        C.mouth(r, 'E')
    elif kind == 'talkA':
        C.mouth(r, 'A')
    elif kind == 'look':        # mild attention: brows slightly up
        for sd in 'LR': C.move(r, 'brow.' + sd, (0, 0, 0.004 * amt))
    elif kind == 'puzzled':     # one brow up, mouth closed tight
        C.move(r, 'brow.L', (0, 0, 0.008 * amt)); C.move(r, 'brow.R', (0, 0, -0.002 * amt))
        C.mouth(r, 'M')
    elif kind == 'alarm':       # eyes wide, brows high, mouth open
        for sd in 'LR':
            r.pose.bones['eye.' + sd].scale = (1.12, 1, 1 + 0.45 * amt)
            C.move(r, 'brow.' + sd, (0, 0, 0.013 * amt))
        C.mouth(r, 'O')
    elif kind == 'squint':
        for sd in 'LR':
            r.pose.bones['eye.' + sd].scale = (1, 1, 0.55)
            C.move(r, 'brow.' + sd, (0, 0, -0.004))
    bpy.context.view_layer.update()
