"""Editable visible trim for the v2j sedan interior, in the original vehicle datum.

Dimensions used by the authoring helpers are mm. Each object identifies its
supporting FE part. Displays and switchgear are cosmetic studio geometry.
"""
from math import cos, sin, pi, radians
import bpy
import numpy as np
from mathutils import Matrix, Vector
from ep02_still import material


def skin(name, color, roughness, grain=0, bump_mm=0, metallic=0):
    m = material(name, color, metallic, roughness)
    tree = m.node_tree
    shader = tree.nodes.get("Principled BSDF")
    if grain:
        coord = tree.nodes.new("ShaderNodeTexCoord")
        noise = tree.nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = grain
        noise.inputs["Detail"].default_value = 2.5
        tree.links.new(coord.outputs["Object"],noise.inputs["Vector"])
        bump = tree.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = .28
        bump.inputs["Distance"].default_value = bump_mm/1000
        tree.links.new(noise.outputs["Fac"],bump.inputs["Height"])
        tree.links.new(bump.outputs[0],shader.inputs["Normal"])
        if name.startswith(("01","03","04")):
            cells=tree.nodes.new("ShaderNodeTexVoronoi")
            cells.feature="DISTANCE_TO_EDGE"
            cells.inputs["Scale"].default_value=1150 if name.startswith("03") else 1450
            tree.links.new(coord.outputs["Object"],cells.inputs["Vector"])
            grain_bump=tree.nodes.new("ShaderNodeBump")
            grain_bump.inputs["Strength"].default_value=.31
            grain_bump.inputs["Distance"].default_value=.00015
            tree.links.new(cells.outputs["Distance"],grain_bump.inputs["Height"])
            tree.links.new(bump.outputs[0],grain_bump.inputs["Normal"])
            tree.links.new(grain_bump.outputs[0],shader.inputs["Normal"])
    return m


def finishes():
    return dict(
        upper=skin("01 | charcoal grained dashboard",(.034,.037,.039),.69,1900,.14),
        lower=skin("02 | warm graphite moulding",(.075,.077,.074),.64,2400,.11),
        rim=skin("03 | steering wheel integral-skin polyurethane",(.021,.022,.021),.53,2200,.17),
        pad=skin("04 | textured horn pad",(.052,.053,.050),.67,2350,.19),
        black=skin("05 | graphite ABS",(.023,.026,.026),.38,2600,.045),
        recess=skin("06 | deep switch recess",(.009,.011,.012),.75),
        metal=skin("07 | satin silver painted trim",(.235,.247,.245),.39,2800,.022,.51),
        edge=skin("08 | anthracite painted trim",(.121,.133,.136),.34,0,0,.32),
        light=skin("09 | instrument silk-screen",(.71,.73,.68),.52),
        red=skin("10 | vermilion instrument lacquer",(.70,.055,.018),.43),
        lcd=skin("11 | polarised display",(.031,.052,.047),.28),
        cloth=skin("12 | headliner fabric",(.128,.127,.119),.91,3500,.1),
        soft=skin("13 | upper door insert",(.056,.059,.056),.78,2100,.16),
        lens=skin("14 | black instrument face",(.017,.020,.021),.47),
        seam=skin("15 | moulded witness line",(.026,.027,.026),.76),
    )


def collection(name):
    coll = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(coll)
    return coll


class Trim:
    def __init__(self, name, part, mats):
        self.coll=collection(name)
        self.part=part
        self.mats=mats

    def add(self,name,v,f,mat,smooth=False,bevel=0):
        mesh=bpy.data.meshes.new(name)
        mesh.from_pydata((np.asarray(v)*.001).tolist(),[],f)
        mesh.update()
        obj=bpy.data.objects.new(name,mesh)
        self.coll.objects.link(obj)
        obj["ep02_carrier_part"]=self.part
        obj["provenance"]="Reconstructed visible trim"
        mesh.materials.append(self.mats[mat])
        if smooth:
            mesh.polygons.foreach_set("use_smooth",np.ones(len(mesh.polygons),bool))
            mesh.set_sharp_from_angle(angle=radians(48))
        if bevel:
            mod=obj.modifiers.new("Mould edge radius","BEVEL")
            mod.width=bevel*.001
            mod.segments=3
            mod=obj.modifiers.new("Face normals","WEIGHTED_NORMAL")
            mod.keep_sharp=True
        return obj

    def line(self,name,coords,radius,mat,closed=False):
        curve=bpy.data.curves.new(name,"CURVE")
        curve.dimensions="3D"
        curve.bevel_depth=radius*.001
        curve.bevel_resolution=2
        curve.resolution_u=1
        spl=curve.splines.new("POLY")
        spl.points.add(len(coords)-1)
        for p,v in zip(spl.points,coords):
            p.co=(*(.001*np.asarray(v)),1)
        spl.use_cyclic_u=closed
        obj=bpy.data.objects.new(name,curve)
        self.coll.objects.link(obj)
        obj["ep02_carrier_part"]=self.part
        curve.materials.append(self.mats[mat])
        return obj


RIGHT=np.array([0.,-1.,0.])


class Face:
    """Plane facing the driver. u points toward the passenger, v points up."""
    def __init__(self,trim,origin,slope=0,right=RIGHT,up=None):
        self.t=trim
        self.o=np.array(origin,float)
        self.r=np.array(right,float);self.r/=np.linalg.norm(self.r)
        self.v=np.array(up if up is not None else [slope,0,1.],float)
        self.v-=np.dot(self.r,self.v)*self.r
        self.v/=np.linalg.norm(self.v)
        self.n=np.cross(self.r,self.v)

    def p(self,u,v,d=0):
        return self.o+self.r*u+self.v*v+self.n*d

    def extrusion(self,name,profile,depth,height,mat,bevel=.3):
        k=len(profile)
        pts=[self.p(u,v,d) for d in (depth,depth+height) for u,v in profile]
        faces=[tuple(range(k-1,-1,-1)),tuple(range(k,2*k))]
        faces.extend((i,(i+1)%k,(i+1)%k+k,i+k) for i in range(k))
        return self.t.add(name,pts,faces,mat,bevel=bevel)

    def box(self,name,u,v,w,h,d,thickness,mat,r=1.0,bevel=.3):
        r=min(r,w/2-.01,h/2-.01)
        points=[]
        for x,y,a in ((w/2-r,h/2-r,0),(-w/2+r,h/2-r,90),
                      (-w/2+r,-h/2+r,180),(w/2-r,-h/2+r,270)):
            for angle in np.linspace(a,a+90,6):
                points.append((u+x+r*cos(radians(angle)),v+y+r*sin(radians(angle))))
        return self.extrusion(name,points,d,thickness,mat,bevel)

    def disc(self,name,u,v,r,d,h,mat,bevel=.3,n=72):
        a=np.arange(n)*2*pi/n
        return self.extrusion(name,[(u+r*cos(t),v+r*sin(t)) for t in a],d,h,mat,bevel)

    def ring(self,name,u,v,outer,inner,d,h,mat):
        n=96
        pts=[self.p(u+r*cos(i*2*pi/n),v+r*sin(i*2*pi/n),z)
             for r,z in ((outer,d),(outer,d+h),(inner,d+h),(inner,d)) for i in range(n)]
        faces=[(j*n+i,j*n+(i+1)%n,((j+1)%4)*n+(i+1)%n,((j+1)%4)*n+i) for j in range(4) for i in range(n)]
        return self.t.add(name,pts,faces,mat,True,.32)

    def line(self,name,uv,r,mat,d=0):
        return self.t.line(name,[self.p(u,v,d) for u,v in uv],r,mat)

    def text(self,body,u,v,d,size,mat="light"):
        c=bpy.data.curves.new(body,"FONT")
        c.body=body;c.size=size*.001;c.align_x="CENTER";c.align_y="CENTER"
        c.resolution_u=6
        o=bpy.data.objects.new(body,c)
        self.t.coll.objects.link(o)
        o["ep02_carrier_part"]=self.t.part
        o.matrix_world=Matrix.Translation(Vector(self.p(u,v,d)*.001)) @ Matrix(np.stack([self.r,self.v,self.n],axis=1)).to_4x4()
        c.materials.append(self.t.mats[mat])


def add_wheel(mats):
    t=Trim("Trim | steering wheel and horn",2000938,mats)
    face=Face(t,[-1605.7,313.0,903.6],.419)
    sections,around=24,192
    def point(a,b):
        # The original rim has a 370 mm outer diameter. Thicken toward
        # its inside and back, retaining the measured outside outline.
        thumb=sum(np.exp(-((np.angle(np.exp(1j*(a-pos))))/.21)**2) for pos in (pi*.19,pi*.81))
        radial=171.5+(15.3+3.8*thumb)*cos(b)-1.6*thumb
        depth=3.0+(17.1+1.1*cos(12*a)*max(-sin(b),0))*sin(b)
        return face.p(radial*cos(a),radial*sin(a),depth)
    pts=[point(a*2*pi/around,b*2*pi/sections) for a in range(around) for b in range(sections)]
    faces=[(a*sections+b,((a+1)%around)*sections+b,((a+1)%around)*sections+(b+1)%sections,a*sections+(b+1)%sections)
           for a in range(around) for b in range(sections)]
    t.add("Padded grip | continuous moulded section",pts,faces,"rim",True)
    t.line("Inner mould parting line",[point(a*2*pi/around,2.55) for a in range(around)],.42,"seam",True)
    # The horn pad follows the three-spoke wheel. Rounded section rings form
    # its side return, part gap, shoulder and shallow dome.
    pad=Trim("Trim | horn pad",2000944,mats)
    pf=Face(pad,[-1632,313,879],.42)
    outline=[(-81,29),(-68,46),(-44,53),(-15,56),(15,56),(44,53),(68,46),(81,29),
             (84,9),(76,-7),(58,-19),(39,-28),(26,-46),(18,-57),(-18,-57),
             (-26,-46),(-39,-28),(-58,-19),(-76,-7),(-84,9)]
    outline=[(1.20*x,1.04*y) for x,y in outline[::-1]]
    for _ in range(2):
        outline=[tuple(w*np.array(p)+(1-w)*np.array(outline[(i+1)%len(outline)]))
                 for i,p in enumerate(outline) for w in (.75,.25)]
    k=len(outline)
    def shell(name,rings,mat):
        v=[pf.p(x*scale,y*scale,d) for scale,d in rings for x,y in outline]
        f=[(j*k+i,j*k+(i+1)%k,(j+1)*k+(i+1)%k,(j+1)*k+i)
           for j in range(len(rings)-1) for i in range(k)]
        f.append(tuple(range((len(rings)-1)*k,len(rings)*k)))
        return pad.add(name,v,f,mat,True)
    shell("Horn pad perimeter gap",[(1.06,-.8),(1.06,5),(1.01,7)],"recess")
    shell("Airbag cover | rounded shoulder",[(1.025,4),(1.022,7.3),(.982,11),(.89,13),(.64,14.5),(.20,15.3)],"pad")
    pf.text("SRS AIRBAG",0,-34,15.1,3.7,"edge")
    for side in (-1,1):
        u=side*65
        pf.line("Embossed horn symbol",[(u-3,9),(u-.8,9),(u+2.4,11),(u+2.4,6),(u-.8,8),(u-3,8),(u-3,9)],.28,"edge",14.5)
    # Slender moulded switch levers behind the wheel.
    stalk=Trim("Trim | column stalks",2000934,mats)
    for side,caption in ((1,"LIGHTS"),(-1,"WIPER")):
        base=np.array([-1518,313+side*48,854.])
        tip=np.array([-1540,313+side*181,890.])
        axis=tip-base;axis/=np.linalg.norm(axis)
        v=np.cross(axis,[1,0,0]);v/=np.linalg.norm(v);w=np.cross(axis,v)
        pts=[]
        profile=[(0,11),(.10,13),(.15,9),(.58,7),(.66,10),(.75,12),(.94,12),(1,9)]
        for s,r in profile:
            p=(1-s)*base+s*tip+[1.6*sin(s*pi),0,6*sin(s*pi)]
            for a in np.arange(28)*2*pi/28:pts.append(p+r*(cos(a)*v+sin(a)*w))
        f=[(28*j+i,28*j+(i+1)%28,28*(j+1)+(i+1)%28,28*(j+1)+i) for j in range(len(profile)-1) for i in range(28)]
        f.extend([tuple(range(27,-1,-1)),tuple(range(len(pts)-28,len(pts)))])
        stalk.add(caption+" | stalk and rotary grip",pts,f,"black",True,.4)
        for s in (.73,.88):
            p=(1-s)*base+s*tip+[1.6*sin(s*pi),0,6*sin(s*pi)]
            stalk.line("Switch collar",[p+12.1*(cos(a)*v+sin(a)*w) for a in np.arange(48)*2*pi/48],.52,"seam",True)
        lab=Face(stalk,[-1550,313+side*151,892],.25);lab.text(caption,0,0,1,2.5)


def vent(mats,side):
    t=Trim("Trim | "+("driver" if side>0 else "passenger")+" outboard air outlet",2000917,mats)
    face=Face(t,[-1347,side*595,920],.50)
    face.disc("Duct well",0,0,43,0,3,"recess",1)
    face.ring("Outer socket",0,0,45,39,1,4,"upper")
    face.ring("Satin register bezel",0,0,40.2,37.9,3.9,1.9,"edge")
    for i,y in enumerate(np.linspace(-29,29,7)):
        width=2*np.sqrt(36.8**2-y*y)
        face.box("Recessed louvre "+str(i+1),0,y,width,3.2,2,3.4,"black",1,.45)
    face.box("Airflow thumb tab",0,0,15.6,5.4,5.1,2.7,"edge",1.55,.5)


def dial(f,name,u,v,r,start,end,major,subdiv,labels,unit,needle=None):
    f.disc(name+" | face",u,v,r+.5,1,1.1,"lens")
    f.ring(name+" | dial perimeter",u,v,r+.9,r-.45,.9,1.35,"black")
    for i,theta in enumerate(np.linspace(start,end,major*subdiv+1)):
        big=i%subdiv==0
        a=radians(theta)
        j=r-2.2;k=j-(4.5 if big else 2.15)
        f.line(name+" | scale",[(u+j*cos(a),v+j*sin(a)),(u+k*cos(a),v+k*sin(a))],.55 if big else .26,"light",2.35)
        if big and labels:
            f.text(str(labels[i//subdiv]),u+(r-9.1)*cos(a),v+(r-9.1)*sin(a),2.38,4.1 if r>32 else 3.2)
    if unit:f.text(unit,u,v-r*.37,2.5,3.3)
    if needle is not None:
        a=radians(needle); e=np.array([cos(a),sin(a)]);n=np.array([-e[1],e[0]])
        center=np.array([u,v])
        shape=[center-e*5+n*.95,center+e*(r-6)+n*.28,center+e*(r-6)-n*.28,center-e*5-n*.95]
        f.extrusion(name+" | pointer",shape,3,.55,"red",.04)
        f.disc(name+" | needle pivot",u,v,2.5,3.3,.95,"black",.25)


def dashboard(mats,speed_kmh):
    t=Trim("Trim | central instrument binnacle",2000917,mats)
    f=Face(t,[-1233,-8,995],.13)
    outline=[(-169,-47),(-164,-20),(-141,3),(-104,29),(-62,44),(-20,49),(20,48),
             (65,41),(107,25),(141,1),(163,-22),(169,-47)]
    outline=outline[::-1]
    f.extrusion("Recessed instrument carrier",outline,-4,4,"recess",1.4)
    dial(f,"Speedometer",-8,2,43,207,-27,7,5,list(range(0,141,20)),"MPH",
         207-(207+27)*(speed_kmh/1.609344)/140)
    dial(f,"Auxiliary dial",-76,1,26,190,-10,4,4,[],"",None)
    f.box("Trip computer recess",68,-4,49,17,1,1.5,"black",2.2,.6)
    f.box("Trip computer | blank polariser",68,-4,46,14,2.25,.5,"lcd",1)
    for j in range(7):
        a=radians(194-32*j)
        f.text(str(40*j),-8+29*cos(a),2+29*sin(a),2.5,2.2,"edge")
    f.text("km/h",-8,-10,2.5,2.3,"edge")
    # The original dash contains circular outboard register faces and two
    # slim inboard apertures flanking the tapered centre console.
    for side in (1,-1):
        vent(mats,side)
        t=Trim("Trim | centre register "+str(side),2000914,mats)
        v=Face(t,[-1429,side*67-16,926],.94)
        v.box("Register frame",0,0,101,45,0,3.2,"edge",5)
        v.box("Duct cavity",0,0,96,40,3.1,1.6,"recess",3)
        for j in range(7):v.box("Vent vane",0,(j-3)*5.25,91.5,1.8,4.7,3.1,"black",.65)
        v.box("Vane slider",0,0,14,3.9,7.7,2.7,"edge",1)
    t=Trim("Trim | audio controls",2000914,mats)
    f=Face(t,[-1477,-16,864],.50)
    f.box("Audio fascia",0,0,183,66,0,4,"edge",7,1.3)
    f.box("Head unit perimeter joint",0,0,173,57,3.2,1.6,"recess",4,.6)
    f.box("Radio switch face",0,0,169,54,4.6,1.9,"black",4)
    f.box("CD slot",0,18,108,2.3,6.4,.7,"recess",.7)
    f.box("LCD bezel",0,5.8,105,15.5,6.3,1.1,"recess",2)
    f.box("Unlit radio display",0,5.8,99,11.5,7.35,.5,"lcd",1.2)
    for u,text in ((-68,"VOL"),(68,"TUNE")):
        f.disc("Encoder collar",u,2,9.6,6.5,2.5,"edge")
        f.disc("Encoder knob",u,2,8,8.5,6,"black",1.1)
        f.text(text,u,-12,6.65,2.45)
    for j in range(6):
        u=(j-2.5)*18
        f.box("Radio preset "+str(j+1),u,-13,16.5,7.2,6.4,1.65,"upper",1.3)
        f.text(str(j+1),u,-13,8.19,2.70)
    f.text("AM  ·  FM",0,-21,6.65,2.20)
    t=Trim("Trim | heater controls",2000914,mats)
    for y,z,tag in ((37,760,"FAN"),(-62,760,"TEMP"),(-12,676,"MODE")):
        cf=Face(t,[-1509 if z>700 else -1525,y,z],.19)
        cf.disc(tag+" | recess",0,0,23,0,2,"recess")
        cf.ring(tag+" | satin bezel",0,0,21.5,18.1,2,2,"metal")
        cf.disc(tag+" | fluted handwheel",0,0,17.9,2.5,10,"edge",1.3)
        for a in np.arange(28)*2*pi/28:
            cf.line("Knob grip",[(17.3*cos(a),17.3*sin(a)),(16.0*cos(a),16.0*sin(a))],.46,"edge",12)
        cf.box("Rotary finger bar",0,0,4.4,26.4,11.4,2.4,"edge",2,.6)
        cf.box("Index",0,10,1.5,4,13.6,.36,"light",.55)
        cf.text(tag,0,-28,1,3.1)
        for a in np.linspace(25,155,7):
            aa=radians(a)
            cf.line("Control detent",[(24*cos(aa),24*sin(aa)),(26.6*cos(aa),26.6*sin(aa))],.42,"light",1)


def upper_cabin(mats):
    t=Trim("Trim | headlining and visors",2000103,mats)
    # Underside follows the crown of the steel roof and covers the front
    # header stampings. The forward edge coincides with the windshield lip.
    xs=np.linspace(-3020,-1704,42);ys=np.linspace(-610,610,45)
    pts=[]
    for x in xs:
        for y in ys:
            roof=1420-0.000046*(x+2410)**2-0.000119*y*y
            pts.append([x,y,roof])
    ny=len(ys)
    f=[(i*ny+j,i*ny+j+1,(i+1)*ny+j+1,(i+1)*ny+j) for i in range(len(xs)-1) for j in range(ny-1)]
    t.add("Shaped fabric headliner",pts,f,"cloth",True)
    for side in (1,-1):
        visor=Face(t,[-1827,side*316,1364],right=RIGHT,up=[-1,0,.12])
        visor.box("Stowed sun visor",0,0,332,143,-1,12,"cloth",16,3.1)
        visor.box("Flip cover surround",0,1,137,68,11.6,1.3,"lower",6,.8)
        visor.box("Vanity mirror cover",0,1,132,63,12.6,1.3,"cloth",5,.7)
        visor.box("Pivot bracket",side*133,63,19,18,9.2,3,"lower",4)
    t=Trim("Trim | rear-view mirror",2000023,mats)
    f=Face(t,[-1598,6,1275],.13)
    f.box("Mirror housing",0,0,214,62,-9,12,"black",9,2.7)
    m=skin("Mirror | grey reflective glass",(.52,.55,.54),.075,metallic=.96)
    mats["mirror"]=m
    f.box("Reflective glass",0,0,204,52,2.5,1.6,"mirror",7,.9)
    f.box("Day-night lever",0,-32,20,6,-2,6,"black",2.5)
    f.t.line("Mirror stem",[[-1590,6,1278],[-1564,6,1300],[-1545,6,1304]],5.3,"black")


def wheel_spokes(mats):
    t=Trim("Trim | steering spoke mouldings",2000938,mats)
    f=Face(t,[-1605.7,313.,903.6],.419)
    # Sculpt each spoke as curved elliptical sections that enter the grip.
    for side in (-1,1):
        rings=[(50,-2,30,24,0),(73,0,32,25,0),(97,5,30,22,1),
               (121,12,26,18,2),(141,18,24,16,3),(158,24,23,14,3),(171,28,20,13,3)]
        v=[f.p(side*u,h+vertical*cos(a),d+deep*sin(a)) for u,h,vertical,deep,d in rings for a in np.arange(32)*2*pi/32]
        faces=[(j*32+i,j*32+(i+1)%32,(j+1)*32+(i+1)%32,(j+1)*32+i) for j in range(len(rings)-1) for i in range(32)]
        t.add("Upper spoke | "+str(side),v,faces,"rim",True)
    rings=[(-24,52,20),(-52,44,20),(-75,34,19),(-101,21,17),(-131,19,16),(-155,25,14),(-171,27,13)]
    v=[f.p(rx*cos(a),h,rz*sin(a)) for h,rx,rz in rings for a in np.arange(32)*2*pi/32]
    faces=[(j*32+i,j*32+(i+1)%32,(j+1)*32+(i+1)%32,(j+1)*32+i) for j in range(len(rings)-1) for i in range(32)]
    t.add("Lower spoke",v,faces,"rim",True)
    sh=Face(Trim("Trim | steering column shroud",2000934,mats),[-1518,313,858],.42)
    sh.box("Ignition shroud | lower half",0,0,135,98,-54,28,"black",28,5)
    sh.box("Ignition shroud | upper half",0,0,137,100,-25,22,"upper",29,6)


# Measured boundary sections of the original tapered centre moulding.
# Values are centreline elevation, front x and half width in mm.
STACK=np.array([(583,-1519,44),(595,-1521,50),(625,-1521,58),(675,-1518,74),
                (720,-1507,85),(765,-1500,95),(810,-1491,105),(850,-1476,114),
                (877,-1462,120),(900,-1446,128),(920,-1430,133),(940,-1409,141),
                (954,-1384,146),(966,-1360,147)])


def centre_fascia(mats):
    t=Trim("Trim | moulded centre fascia",2000914,mats)
    zvals=np.linspace(583,966,87)
    us=np.linspace(-1,1,51)
    def surface(u,z,offset):
        w=np.interp(z,STACK[:,0],STACK[:,2])
        x=np.interp(z,STACK[:,0],STACK[:,1])
        return [x+8.5*(abs(u)**2.1)-offset,-16-u*w,z]
    def panel(name,zrun,us,offset,mat):
        pts=[surface(u,z,offset) for z in zrun for u in us]
        n=len(us)
        faces=[(j*n+i,j*n+i+1,(j+1)*n+i+1,(j+1)*n+i) for j in range(len(zrun)-1) for i in range(n-1)]
        ob=t.add(name,pts,faces,mat,True)
        sol=ob.modifiers.new("Returned moulding edge","SOLIDIFY");sol.thickness=.0018
        return ob
    panel("Outer fascia | continuous satin pressing",zvals,us,2.5,"metal")
    for side in (-1,1):
        t.line("Outer console seam",[surface(side,z,2.5) for z in zvals],1.2,"recess")
        # The detailed FE console is a bare support. Return both cheeks to
        # the adjoining dash so the engine bay cannot show through its sides.
        pts=[]
        for z in zvals:
            x,y,_=surface(side,z,2.6)
            for u in np.linspace(0,1,17):
                # Reach under the original upper dash on both sides. Its
                # aperture extends past y=-220 mm on the passenger side.
                reach=np.interp(z,[583,690,810,930,966],[36,54,113,125,113])
                pts.append([x+50*u*u+7*u,y-side*reach*u,z-4*sin(pi*u)])
        n=17
        faces=[(j*n+i,j*n+i+1,(j+1)*n+i+1,(j+1)*n+i) for j in range(len(zvals)-1) for i in range(n-1)]
        t.add("Wrapped console side cheek",pts,faces,"upper",True)
        # Close the upper edge beneath the overhanging meter brow. Continue
        # the front profile towards the windscreen until it enters the dash.
        edge=np.array(pts[-n:])
        cap=[]
        for v in np.linspace(0,1,18):
            for i,p0 in enumerate(edge):
                u=i/(n-1)
                cap.append(p0+[153*v,-side*12*v,(14-5*u)*np.sin(v*pi/2)])
        t.add("Continuous shoulder below instrument brow",cap,
              [(j*n+i,j*n+i+1,(j+1)*n+i+1,(j+1)*n+i) for j in range(17) for i in range(n-1)],"upper",True)
    pts=[]
    for j in range(15):
        u=j/14
        for v in np.linspace(-1,1,61):
            pts.append([-1362+155*u+8*v*v,-16+v*(147+40*u),
                        966+11*np.sin(.5*pi*u)**.65-1.5*v*v])
    t.add("Meter lower shelf",pts,[(j*61+i,j*61+i+1,(j+1)*61+i+1,(j+1)*61+i) for j in range(14) for i in range(60)],"upper",True)
    panel("Heater switch panel",np.linspace(610,804,45),np.linspace(-.89,.89,35),3.7,"upper")
    # A small driver's hazard key sits between the two centre registers.
    f=Face(t,[-1438,-16,918],.85)
    f.box("Hazard key surround",0,0,16,18,0,2.1,"recess",3)
    f.box("Hazard key",0,0,13.6,15.6,1.8,1.5,"black",2.5)
    f.line("Hazard warning symbol",[(-4.3,-3),(0,4.0),(4.3,-3),(-4.3,-3)],.65,"red",3.5)


def garnish(mats,source):
    xyz=source["xyz"]
    shells,pids=source["shell_n"],source["shell_pid"]
    for side,pid in ((1,2000910),(-1,2000854)):
        trim=Trim("Trim | A-pillar garnish "+str(side),pid,mats)
        cloud=xyz[np.unique(shells[pids==pid])].astype(float)
        base=np.array([-1080,side*645,952.])
        axis=np.array([-.869,-side*.14,.475]);axis/=np.linalg.norm(axis)
        across=np.cross(axis,[0,0,1]);across/=np.linalg.norm(across)
        up=np.cross(axis,across)
        along=(cloud-base)@axis
        stations=np.linspace(*np.percentile(along,[.4,99.65]),28)
        sections=[]
        for s in stations:
            near=cloud[np.abs(along-s)<34]-base-axis*s
            v=near@across;w=near@up
            lo,hi=np.percentile(v,[3,97]);bot,top=np.percentile(w,[3,97])
            sections.append([(hi+lo)/2,(top+bot)/2,max(7,(hi-lo)/2),max(7,(top-bot)/2)])
        data=np.asarray(sections)
        for _ in range(3):data[1:-1]=.25*data[:-2]+.5*data[1:-1]+.25*data[2:]
        pts=[]
        for s,(vc,wc,rv,rw) in zip(stations,data):
            for a in np.arange(48)*2*pi/48:
                pts.append(base+s*axis+(vc+(rv+2)*cos(a))*across+(wc+(rw+1)*sin(a))*up)
        n=48;faces=[(j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i)
                    for j in range(len(stations)-1) for i in range(n)]
        faces.extend([tuple(range(n-1,-1,-1)),tuple(range(len(pts)-n,len(pts)))])
        trim.add("Smooth pillar cover",pts,faces,"lower",True)
    trim=Trim("Trim | windscreen ceramic border",2000023,mats)
    faces=shells[pids==2000023]
    edges=np.vstack([faces[:,[i,(i+1)%4]] for i in range(4)])
    edges=np.sort(edges[edges[:,0]!=edges[:,1]],axis=1)
    pairs,n=np.unique(edges,axis=0,return_counts=True)
    boundary=pairs[n==1]
    ids,index=np.unique(boundary,return_inverse=True)
    b=xyz[ids].astype(float)
    centre=xyz[np.unique(faces)].mean(0)
    direction=centre-b
    width=np.where(b[:,2]>1300,23.,14.)
    inner=b+width[:,None]*direction/np.linalg.norm(direction,axis=1)[:,None]
    verts=np.vstack((b,inner))+[-.65,0,-.9]
    index=index.reshape(-1,2)
    trim.add("Bonded glass frit band",verts,[(a,b,b+len(ids),a+len(ids)) for a,b in index],"recess",True)


def lower_cabin(mats):
    mats["carpet"]=skin("16 | charcoal needle-punched carpet",(.040,.043,.042),.96,4300,.33)
    mats["mat"]=skin("17 | ribbed floor mat",(.019,.021,.022),.87,2200,.15)
    t=Trim("Trim | carpeted footwells",2000905,mats)
    xs=np.linspace(-2510,-1330,67);ys=np.linspace(-670,670,75)
    pts=[]
    for x in xs:
        for y in ys:
            rise=174*np.clip((x+1730)/400,0,1)**1.65
            tunnel=144*np.exp(-(y/110)**4)
            sill=53*np.clip((abs(y)-540)/130,0,1)**1.65
            pts.append([x,y,268+rise+tunnel+sill])
    n=len(ys);faces=[(j*n+i,(j+1)*n+i,(j+1)*n+i+1,j*n+i+1) for j in range(len(xs)-1) for i in range(n-1)]
    t.add("One-piece floor carpet and tunnel",pts,faces,"carpet",True)
    rows=[(-1730,271),(-1650,293),(-1560,340),(-1470,432),(-1402,529),(-1380,635),(-1350,758),(-1295,857)]
    pts=[[x+12*(1-abs(y/700)),y,z+50*np.exp(-(y/116)**4)] for x,z in rows for y in ys]
    faces=[(j*n+i,j*n+i+1,(j+1)*n+i+1,(j+1)*n+i) for j in range(len(rows)-1) for i in range(n-1)]
    t.add("Continuous toe board and under-dash insulation",pts,faces,"carpet",True)
    for y,w,h,label in ((424,56,47,"Clutch"),(328,62,46,"Brake"),(220,32,76,"Accelerator")):
        pedal=Face(t,[-1583 if label!="Accelerator" else -1545,y,394],.35)
        t.line(label+" arm",[[-1438,y,568],[-1475,y,495],[-1567,y,401]],5,"black")
        pedal.box(label+" pedal",0,0,w,h,0,7,"rim",5,1.8)
        for v in np.linspace(-h*.34,h*.34,6):
            pedal.box("Pedal tread",0,v,w-8,2,7,1.3,"black",.7,.3)
    for s in (1,-1):
        y0=s*347
        f=Face(t,[-1980,y0,273],right=RIGHT,up=[1,0,0])
        f.box("Bound footwell mat",0,0,374,430,0,3.4,"mat",21,1)
        for i in range(19):
            f.box("Mat rib",0,(i-9)*17,327,3.1,2.9,1.4,"carpet",1.1,.3)
    # Manual gear lever and gaiter, on the tunnel between the front seats.
    g=Trim("Trim | manual shift lever and console",2000905,mats)
    base=Face(g,[-1871,0,419],right=RIGHT,up=[1,0,0])
    base.box("Floor console",0,0,158,335,-36,41,"lower",34,6)
    base.box("Gaiter surround",0,38,107,125,3,6,"edge",23,2)
    rings=[(48,56,9,0,38),(43,52,17,0,37),(32,43,29,4,34),(34,35,33,3,32),(24,32,47,0,25),
           (23,25,50,-1,24),(13,18,68,0,19),(10,11,78,0,17)]
    angles=np.arange(64)*2*pi/64
    pts=[base.p(cx+rx*cos(a)*(1+.06*sin(5*a)),cy+ry*sin(a)*(1+.08*cos(5*a)),h+2.3*sin(4*a)) for rx,ry,h,cx,cy in rings for a in angles]
    faces=[(j*64+i,j*64+(i+1)%64,(j+1)*64+(i+1)%64,(j+1)*64+i) for j in range(len(rings)-1) for i in range(64)]
    g.add("Gathered shift boot",pts,faces,"rim",True)
    knob=[]
    for v in np.linspace(-pi/2+.02,pi/2-.02,28):
        for a in angles:knob.append(base.p(22*cos(v)*cos(a),17+26*cos(v)*sin(a),95+27*sin(v)))
    faces=[(j*64+i,j*64+(i+1)%64,(j+1)*64+(i+1)%64,(j+1)*64+i) for j in range(27) for i in range(64)]
    g.add("Gear knob",knob,faces,"pad",True)
    base.text("1  3  5",0,22,121.1,3.5)
    base.text("2  4  R",0,14,121.1,3.5)


def interior_fittings(mats):
    for side,pid in ((1,2000880),(-1,2000861)):
        t=Trim("Trim | inner door release "+str(side),pid,mats)
        f=Face(t,[-1635,side*632,815],right=[side,0,0],up=[0,0,1])
        f.box("Handle escutcheon",0,0,120,45,0,3,"upper",11,1.3)
        f.box("Recessed finger cup",0,0,107,35,3,1.8,"recess",10,.8)
        profile=[(-39,3),(-29,9),(28,9),(41,6),(41,-1),(26,0),(-22,2),(-36,-5),(-42,-4)]
        f.extrusion("Door release | satin lever",profile[::-1],5,6.5,"metal",1.6)
        f.box("Door lock rocker",48,14,11,5,4,3,"black",1)
        f.box("Latch indicator",48,14,5,1.9,7,.5,"red",.4)
        switch=Face(t,[-1730,side*621,751],right=[side,0,0],up=[0,side,.30])
        switch.box("Window switch pod",0,0,106,38,0,4,"upper",9)
        for j in range(2 if side==1 else 1):
            switch.box("Power window rocker",22-j*32,0,24,17,4,3.4,"black",3,.75)
            switch.line("Window icon",[(16-j*32,-2),(18-j*32,3),(27-j*32,3),(27-j*32,-2),(16-j*32,-2)],.3,"light",7.6)
    t=Trim("Trim | dashboard storage",2000917,mats)
    # Narrow dust grooves on the demister grille run along the base of the glass.
    f=Face(t,[-996,0,1013],right=RIGHT,up=[1,0,.06])
    for side in (-1,1):
        for j in range(4):
            f.box("Defroster grille slot",side*315,(j-1.5)*4.2,170-5*abs(j-1.5),1.65,0,.7,"recess",.7,.15)
    # Front passenger glovebox latch on the original door, at its top lip.
    g=Face(Trim("Trim | glovebox latch",2000916,mats),[-1391,-421,747],.23)
    g.box("Latch pocket",0,0,75,18,0,2.4,"recess",4)
    g.box("Latch",0,2,61,10,2.3,3.5,"lower",3)
    t=Trim("Trim | instrument bridge and knee panel",2000905,mats)
    # Continuous dashboard substrate behind the meter opening and trim returns.
    zs=np.linspace(690,970,40);ys=np.linspace(-237,208,58)
    pts=[]
    for z in zs:
        for y in ys:
            x=np.interp(z,[690,800,890,937,970],[-1290,-1318,-1326,-1302,-1265])
            pts.append([x+.00038*(y+15)**2,y,z])
    n=len(ys)
    t.add("Instrument support valance",pts,[(j*n+i,j*n+i+1,(j+1)*n+i+1,(j+1)*n+i) for j in range(len(zs)-1) for i in range(n-1)],"upper",True)
    f=Face(t,[-1345,317,743],.22)
    f.box("Lower steering knee trim",0,0,373,160,0,8,"lower",22,4)
    # Boot at the telescopic joint prevents a sightline into the column support.
    boot=Face(t,[-1403,313,839],.42)
    for j in range(5):
        boot.box("Telescopic column gaiter pleat",0,0,135+1.1*j,78+.9*j,j*10,9,"black",24,2.3)


def seat_fabric():
    m=skin("18 | woven seat centre panel",(.12,.127,.127),.91,2900,.19)
    tree=m.node_tree
    coord=tree.nodes.new("ShaderNodeTexCoord")
    tex=tree.nodes.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value=1490
    tex.inputs["Detail"].default_value=1.7
    tree.links.new(coord.outputs["Object"],tex.inputs["Vector"])
    wave=tree.nodes.new("ShaderNodeTexWave")
    wave.wave_type="BANDS";wave.bands_direction="DIAGONAL"
    wave.inputs["Scale"].default_value=145
    tree.links.new(coord.outputs["Object"],wave.inputs["Vector"])
    mix=tree.nodes.new("ShaderNodeMath");mix.operation="MULTIPLY"
    tree.links.new(tex.outputs["Fac"],mix.inputs[0]);tree.links.new(wave.outputs["Fac"],mix.inputs[1])
    ramp=tree.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color=(.033,.039,.042,1)
    ramp.color_ramp.elements[1].color=(.12,.134,.14,1)
    tree.links.new(mix.outputs[0],ramp.inputs[0])
    tree.links.new(ramp.outputs[0],tree.nodes.get("Principled BSDF").inputs["Base Color"])
    return m


def door_cards(mats,source):
    """Loft the finished door cards on the v2j silhouette; retain realistic panel returns."""
    xyz,shells,pids=source["xyz"],source["shell_n"],source["shell_pid"]
    for side,pid in ((1,2000880),(-1,2000861)):
        t=Trim("Trim | "+("left" if side==1 else "right")+" front door card",pid,mats)
        p=xyz[np.unique(shells[pids==pid])]
        xs=np.linspace(*np.percentile(p[:,0],[.35,99.65]),79)
        envelope=[]
        for x in xs:
            near=p[np.abs(p[:,0]-x)<15]
            envelope.append(np.percentile(near[:,2],[.8,99.3]))
        bounds=np.array(envelope)
        for _ in range(3):bounds[1:-1]=.25*bounds[:-2]+.5*bounds[1:-1]+.25*bounds[2:]
        def into(x,z):
            taper=33*np.clip((abs(x+1730)-275)/205,0,1)**1.6
            return 653+taper-19*np.exp(-((z-699)/66)**2)+9*np.clip((z-835)/120,0,1)
        def pt(x,z,relief=0):
            return np.array([x,side*(into(x,z)-relief),z])
        vv=np.linspace(0,1,45)
        pts=[pt(x,lo+(hi-lo)*v) for x,(lo,hi) in zip(xs,bounds) for v in vv]
        n=len(vv)
        faces=[(j*n+i,j*n+i+1,(j+1)*n+i+1,(j+1)*n+i) for j in range(len(xs)-1) for i in range(n-1)]
        ob=t.add("Continuous door card skin",pts,faces,"lower",True)
        mod=ob.modifiers.new("Return under edges","SOLIDIFY");mod.thickness=.003
        t.line("Glass run rubber seal",[pt(x,hi-1,2.2) for x,(_,hi) in zip(xs,bounds)],3.5,"recess")
        # Soft fabric insert, with a piped shutline and taper near the release.
        run=np.linspace(-2110,-1455,60);uv=np.linspace(0,1,15)
        def edges(x):
            u=(x-run[0])/(run[-1]-run[0])
            return 734+19*u+13*u**3,877-40*u+9*sin(pi*u)
        rows=[]
        for x in run:
            lo,hi=edges(x)
            rows.extend(pt(x,lo+(hi-lo)*v,4+1.7*sin(pi*v)) for v in uv)
        n=len(uv)
        t.add("Fabric shoulder insert",rows,[(j*n+i,j*n+i+1,(j+1)*n+i+1,(j+1)*n+i) for j in range(len(run)-1) for i in range(n-1)],"soft",True)
        for k in (0,1):
            t.line("Welt at shoulder insert",[pt(x,edges(x)[k],4.2) for x in run],.9,"seam")
        # Cushion on the armrest; section radius and depth taper at both ends.
        ts=np.linspace(0,1,53);angs=np.arange(36)*2*pi/36
        pts=[]
        for u in ts:
            x=-2132+598*u
            cap=max(.08,min(1,u/.09,(1-u)/.11))**.45
            centre=pt(x,719+18*u,16*cap)
            for a in angs:
                pts.append(centre+[0,side*37*cap*cos(a),17.5*cap*sin(a)])
        n=len(angs)
        t.add("Padded armrest",pts,[(j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i)
                                   for j in range(len(ts)-1) for i in range(n)],"soft",True)
        # Recessed oval speaker grille. Perforations share one editable mesh.
        speaker=Face(t,pt(-1455,523,3),right=[side,0,0],up=[0,0,1])
        speaker.disc("Speaker grille",0,0,60,0,1.8,"lower",.9)
        speaker.ring("Speaker grille lip",0,0,60.6,58.7,1,1.0,"edge")
        dots=[];faces=[]
        for j in range(-13,14):
            for i in range(-13,14):
                u=(i+.5*(j%2))*4.8;v=j*4.16
                if u*u+v*v>55**2:continue
                a0=len(dots)
                dots.extend(speaker.p(u+1.02*cos(a),v+1.02*sin(a),1.92) for a in np.arange(6)*pi/3)
                faces.append(tuple(range(a0,a0+6)))
        t.add("Grille perforation field",dots,faces,"recess")
        # Outboard mirror with real reflective material and a door sail mount.
        t=Trim("Trim | outside mirror "+str(side),pid,mats)
        f=Face(t,[-1317,side*814,1016],right=[-.22*side,-1.,0],up=[0,0,1])
        outline=[(-82,2),(-73,-29),(-44,-40),(40,-39),(71,-27),(81,-3),(74,25),(55,37),(-49,40),(-72,31)]
        f.extrusion("Mirror casing",outline,-34,34,"black",5)
        f.extrusion("Side-view glass",[(u*.923,v*.88) for u,v in outline],.35,1.1,"mirror",1)
        t.line("Mirror base and neck",[[-1350,side*695,964],[-1338,side*730,981],[-1319,side*762,995]],12,"black")
