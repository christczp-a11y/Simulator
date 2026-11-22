"""Build an editable EP02 cabin on the official CCSA v2j rest geometry (Blender)."""
import argparse
from pathlib import Path
import re
import sys
import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parent))
from ep02_cabin import (add_wheel, centre_fascia, collection, dashboard, door_cards, finishes, garnish,
                        interior_fittings, lower_cabin, seat_fabric, upper_cabin, wheel_spokes)
from ep02_still import glass, material, set_scene


def source_shells(source,mats):
    names=dict(zip(source["part_id"],source["part_name"]))
    shell,part=source["shell_n"],source["shell_pid"]
    xyz=source["xyz"]*.001
    coll=collection("Model | CCSA v2j shells")
    glazing={2000023,2000062,2000011,2000325,2000347,2000349,2000407,2000452}
    mats["glass"]=glass()
    mats["paint"]=material("Body | grey enamel",(.15,.16,.17),.68,.28)
    mats["steel"]=material("Body | phosphated steel",(.12,.13,.13),.53,.44)
    fabric=seat_fabric()
    counts={}
    included=re.compile("dash|steeringcolm|seat|headrest|door|pillar|trim|roof|cowl|hood|floor|window|glass|windshield|sidepanel|console|carpet|decklid|mirror|tunnel",re.I)
    for pid,name in names.items():
        if pid in (2000523,2000524) or (not included.search(name) and pid not in glazing):
            continue
        faces=shell[part==pid]
        if not len(faces):
            continue
        ids,local=np.unique(faces,return_inverse=True)
        local=local.reshape(-1,4)
        quads=local[:,2]!=local[:,3]
        polygons=local[quads].tolist()+local[~quads,:3].tolist()
        name=name.lower()
        if pid in glazing: finish="glass"
        elif pid==2000914: finish="metal"
        elif pid in (2000938,2000944): finish="rim" if pid==2000938 else "pad"
        elif "steeringcolm" in name: finish="black"
        elif pid==2000917: finish="upper"
        elif pid in (2000907,2000918): finish="edge"
        elif "dash" in name: finish="lower"
        elif pid in (2000879,2000860): finish="soft"
        elif "trim" in name: finish="lower"
        elif "roof" in name: finish="cloth" if pid!=2000103 else "paint"
        elif "seat" in name or "headrest" in name: finish="soft"
        elif "panel" in name or "door" in name or "hood" in name: finish="paint"
        else: finish="steel"
        mesh=bpy.data.meshes.new(name)
        mesh.from_pydata(xyz[ids].tolist(),[],polygons)
        mesh.update()
        mesh.polygons.foreach_set("use_smooth",np.ones(len(mesh.polygons),bool))
        mesh.set_sharp_from_angle(angle=np.deg2rad(46))
        ob=bpy.data.objects.new(f"{pid} | {name}",mesh)
        coll.objects.link(ob)
        ob["CCSA_part_id"]=int(pid)
        ob["official_shell_count"]=len(faces)
        mesh.materials.append(mats[finish])
        if pid in (2000925,2000926,2000927,2000928):
            mesh.materials.append(fabric)
            centre=-.335 if pid in (2000925,2000927) else .329
            order=np.concatenate((faces[quads],faces[~quads]))
            panel=np.abs(xyz[order,1].mean(axis=1)-centre)<.128
            mesh.polygons.foreach_set("material_index",panel.astype(np.int32))
        if pid in {2000938,2000940,2000944,2000946,2000914,2000910,2000854,2000904,2000913,
                   2000889,2000888,2000915,2000880,2000879,2000923,2000860,2000861,2000862}:
            ob.hide_render=True
            ob.hide_set(True)
        counts[int(pid)]=len(faces)
    return counts


def light(name,pos,aim,watts,size,color):
    data=bpy.data.lights.new(name,"AREA")
    data.energy=watts
    data.shape="DISK"
    data.size=size
    data.color=color
    ob=bpy.data.objects.new(name,data)
    bpy.context.scene.collection.objects.link(ob)
    ob.location=pos
    ob.rotation_euler=(Vector(aim)-ob.location).to_track_quat("-Z","Y").to_euler()


def camera(name,eye,aim,lens,sensor="HORIZONTAL"):
    data=bpy.data.cameras.new(name)
    data.sensor_fit=sensor
    data.sensor_width=36;data.sensor_height=32;data.lens=lens;data.clip_start=.012
    cam=bpy.data.objects.new(name,data)
    bpy.context.scene.collection.objects.link(cam)
    cam.location=eye
    cam.rotation_euler=(Vector(aim)-cam.location).to_track_quat("-Z","Y").to_euler()
    return cam


def prepare_editor(scene):
    groups={}
    for label in ("Production trim","Inspection cameras","Daylight and road"):
        folder=bpy.data.collections.get(label) or bpy.data.collections.new(label)
        if folder.name not in scene.collection.children:
            scene.collection.children.link(folder)
        groups[label]=folder
    for coll in list(scene.collection.children):
        if coll.name.startswith("Trim |"):
            groups["Production trim"].children.link(coll)
            scene.collection.children.unlink(coll)
    for ob in list(scene.objects):
        if ob.type in ("CAMERA","LIGHT") or (ob.type=="MESH" and ob.name.startswith(("Concrete wall panel","Ground","Test approach","Edge stripe"))):
            dest=groups["Inspection cameras" if ob.type=="CAMERA" else "Daylight and road"]
            if dest not in ob.users_collection:
                dest.objects.link(ob)
                for old in list(ob.users_collection):
                    if old!=dest:
                        old.objects.unlink(ob)
    for mat in bpy.data.materials:
        if mat.use_nodes:
            shader=mat.node_tree.nodes.get("Principled BSDF")
            if shader:
                mat.diffuse_color=shader.inputs["Base Color"].default_value
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=="VIEW_3D":
                space=area.spaces.active
                space.region_3d.view_perspective='CAMERA'
                space.overlay.show_overlays=False
                space.shading.color_type='MATERIAL'
                space.shading.show_shadows=True
    notes=bpy.data.texts.get("About this cabin") or bpy.data.texts.new("About this cabin")
    notes.clear()
    notes.write("EP02 interior modelling study\n\nCCSA at George Mason University / FHWA. 2010 sedan detailed FE model v2j (October 2016).\n"
                "CCSA source objects retain their part IDs. Production trim is editable, reconstructed rest-state geometry.\n"
                "The speedometer uses the 56 km/h run's initial speed. No crash deformation is applied in this scene.\n"
                "Select an inspection camera and render with Cycles (F12). The driver camera matches the previous framing study.\n"
                "Rebuild from the official archive with scripts/build_ep02_cabin.sh in the EP02 branch.\n")


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("source",type=Path)
    p.add_argument("output",type=Path)
    p.add_argument("--history",type=Path,required=True,help="Solver history supplying the speedometer reading")
    p.add_argument("--samples",type=int,default=24)
    p.add_argument("--width",type=int,default=1000,help="Width of the landscape overview")
    p.add_argument("--views",nargs="*",choices=["driver","overview","wheel","controls","passenger"],default=["driver","overview","wheel","controls","passenger"])
    args=p.parse_args(sys.argv[sys.argv.index("--")+1:])
    args.output.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    set_scene()
    # Identical relative pose to the existing 8 m approach benchmark.
    for ob in bpy.context.scene.objects:
        if ob.type=="MESH": ob.location.x+=8
    scene=bpy.context.scene
    scene.render.engine="CYCLES"
    scene.cycles.samples=args.samples
    scene.cycles.use_denoising=True
    scene.cycles.max_bounces=8
    scene.cycles.transparent_max_bounces=12
    scene.render.image_settings.file_format="JPEG"
    scene.render.image_settings.quality=94
    scene.render.resolution_percentage=100
    scene.view_settings.view_transform="AgX"
    scene.view_settings.look="AgX - Medium High Contrast"
    mats=finishes()
    upper_cabin(mats)
    with np.load(args.source) as source:
        if (len(source["node_id"]),len(source["part_id"]))!=(1488581,940):
            raise ValueError("Expected the detailed v2j source")
        counts=source_shells(source,mats)
        garnish(mats,source)
        door_cards(mats,source)
    speed=float(np.genfromtxt(args.history,delimiter=",",names=True,max_rows=1)["cg_speed_kmh"])
    add_wheel(mats)
    wheel_spokes(mats)
    centre_fascia(mats)
    dashboard(mats,speed)
    lower_cabin(mats)
    interior_fittings(mats)
    target=(-1.55,.1,.84)
    light("Daylight | driver window",(-2.05,1.19,1.34),target,19,.86,(.91,.95,1.0))
    light("Daylight | passenger reflection",(-2.16,-1.22,1.22),(-1.56,.32,.92),44,1.24,(1.0,.92,.81))
    light("Daylight | broad windscreen reflection",(-.67,.17,2.28),(-1.68,.1,.78),58,1.6,(.9,.96,1.0))
    eye=Vector((-2.12066,.325549,1.193691))
    driver=camera("01 | Driver — benchmark position",eye,eye+Vector((1,-.09,-.1)),19,"VERTICAL")
    overview=camera("02 | Dashboard overview",(-2.60,.024,1.24),(-1.37,.043,.813),28)
    wheel=camera("03 | Steering wheel",(-2.176,.453,1.128),(-1.553,.307,.927),45)
    controls=camera("04 | Instrument and centre stack",(-1.987,.080,1.081),(-1.347,-.013,.866),36)
    passenger=camera("05 | Passenger side detail",(-2.17,-.312,1.13),(-1.54,.198,.890),33)
    views={"driver":(driver,round(args.width*.72),round(args.width*.72*16/9)),
           "overview":(overview,args.width,round(args.width*.68)),
           "wheel":(wheel,args.width,round(args.width*.68)),
           "controls":(controls,args.width,round(args.width*.85)),
           "passenger":(passenger,args.width,round(args.width*.68))}
    scene.camera=overview
    scene.render.resolution_x,scene.render.resolution_y=views["overview"][1:]
    prepare_editor(scene)
    scene["source"]="CCSA 2010 Toyota Yaris, detailed v2j (2016-10). Geometry held at undeformed rest."
    scene["source_shells_visible"]=sum(counts.values())
    scene["source_parts_visible"]=len(counts)
    scene["speedometer_kmh"]=speed
    scene.render.filepath="//overview.jpg"
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str((args.output/"ep02-cabin.blend").resolve()),compress=True)
    for view in args.views:
        scene.camera,scene.render.resolution_x,scene.render.resolution_y=views[view]
        scene.render.filepath=str((args.output/(view+".jpg")).resolve())
        bpy.ops.render.render(write_still=True)
    print("Cabin shells:",len(counts),sum(counts.values()),"initial speed km/h:",speed)


if __name__=="__main__":
    main()
