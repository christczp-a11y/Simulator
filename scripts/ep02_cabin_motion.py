"""Transfer solved v1l shell motion to the matching editable v2j cabin in Blender."""
import bpy
import numpy as np
from mathutils import Matrix
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree


def points(mesh):
    coords = np.empty((len(mesh.vertices), 3), np.float32)
    mesh.vertices.foreach_get("co", coords.ravel())
    return coords


def tri_axes(tri):
    u = tri[:,1] - tri[:,0]
    w = np.cross(u, tri[:,2]-tri[:,0])
    ulen = np.linalg.norm(u, axis=1)
    wlen = np.linalg.norm(w, axis=1)
    u = u / np.maximum(ulen[:,None], 1e-20)
    w = w / np.maximum(wlen[:,None], 1e-20)
    return np.stack((u, np.cross(w,u), w), axis=1), wlen


def erosion_nodes():
    group = bpy.data.node_groups.new("Hide faces lost by their solver carrier", "GeometryNodeTree")
    for kind in ("INPUT", "OUTPUT"):
        group.interface.new_socket(name="Geometry", in_out=kind, socket_type="NodeSocketGeometry")
    src = group.nodes.new("NodeGroupInput")
    dest = group.nodes.new("NodeGroupOutput")
    flag = group.nodes.new("GeometryNodeInputNamedAttribute")
    flag.data_type = "BOOLEAN"
    flag.inputs["Name"].default_value = "ep02_eroded"
    delete = group.nodes.new("GeometryNodeDeleteGeometry")
    delete.domain = "FACE"
    group.links.new(src.outputs["Geometry"], delete.inputs["Geometry"])
    group.links.new(flag.outputs["Attribute"], delete.inputs["Selection"])
    group.links.new(delete.outputs["Geometry"], dest.inputs["Geometry"])
    return group


class ShellSurface:
    def __init__(self, rest, indices, cells):
        axes, area = tri_axes(rest[indices])
        valid = area > 1e-12
        self.nodes = indices[valid]
        self.cells = cells[valid]
        self.axes = axes[valid]
        self.rest = rest[self.nodes]
        nodes, local = np.unique(self.nodes, return_inverse=True)
        self.tree = BVHTree.FromPolygons(rest[nodes], local.reshape(-1,3), all_triangles=True)

    def nearest(self, coords):
        hit = [self.tree.find_nearest(v) for v in coords]
        return np.array([h[2] for h in hit], np.int32), np.array([h[0] for h in hit])

    def bind(self, coords):
        face, q = self.nearest(coords)
        tri = self.rest[face]
        edge = tri[:,1:]-tri[:,:1]
        normal = np.cross(edge[:,0], edge[:,1])
        denom = np.einsum("ij,ij->i", normal, normal)
        delta = q-tri[:,0]
        u = (np.cross(delta,edge[:,1])*normal).sum(axis=1)/denom
        v = (np.cross(edge[:,0],delta)*normal).sum(axis=1)/denom
        weights = np.stack((1-u-v,u,v),axis=1)
        offset = np.einsum("nij,nj->ni", self.axes[face], coords-q)
        return face, weights.astype(np.float32), offset.astype(np.float32)


class CabinMotion:
    def __init__(self, scene, top, first, rigid_parts):
        shells = bpy.data.collections["Model | CCSA v2j shells"]
        trim = bpy.data.collections["Production trim"]
        self.parts = {int(o["CCSA_part_id"]) for o in shells.objects}
        self.rigid_parts = rigid_parts
        rest = first["xyz"].astype(float)*.001
        quad, tri = top["quad"], top["tri"]
        faces = np.concatenate((quad[:,(0,1,2)], quad[:,(0,2,3)], tri))
        cells = np.concatenate((top["quad_cell"], top["quad_cell"], top["tri_cell"]))
        pids = top["part_id"][cells]
        self.surfaces = {}
        self.skins = {}
        self.fittings = []
        self.linings = []
        self.rest = rest
        erode = erosion_nodes()
        # The floor covering spans the left pan, right pan and tunnel.
        floor = (2000198,2000203,2000239)
        dash = (2000905,2000914,2000917)
        for pid in self.parts | {floor, (*floor,2000172), dash, 2000172}:
            selected = np.isin(pids, pid)
            if not np.any(selected):
                raise ValueError(f"Missing solved carrier {pid}")
            self.surfaces[pid] = ShellSurface(rest, faces[selected], cells[selected])

        def bind_skin(ob, pid):
            if not np.allclose(ob.matrix_world, np.eye(4)):
                raise ValueError(f"Expected car-space mesh vertices on {ob.name}")
            mesh = ob.data
            ob["ep02_motion_carrier"] = str(pid)
            surface = self.surfaces[pid]
            binding = surface.bind(points(mesh))
            centers = np.empty((len(mesh.polygons),3), np.float32)
            mesh.polygons.foreach_get("center", centers.ravel())
            closest, _ = surface.nearest(centers)
            carrier_cells = surface.cells[closest]
            flag = mesh.attributes.new("ep02_eroded", "BOOLEAN", "FACE")
            mod = ob.modifiers.new("Solver shell erosion", "NODES")
            mod.node_group = erode
            ob.modifiers.move(len(ob.modifiers)-1, 0)
            self.skins.setdefault(pid, []).append((mesh, binding, carrier_cells, flag))

        # Cloth and trim spanning separate pressed sheets have no measured
        # thickness/rotation field. Blend nodal displacements and rotate the
        # standoff with the cockpit, not a folding individual firewall facet.
        trees = {}
        def bind_lining(ob, carriers):
            surface = self.surfaces[carriers]
            if carriers not in trees:
                nodes = np.unique(surface.nodes)
                tree = KDTree(len(nodes))
                for node in nodes:
                    tree.insert(rest[node], int(node))
                tree.balance()
                trees[carriers] = tree
            coords = points(ob.data)
            near = [trees[carriers].find_n(v,16) for v in coords]
            ids = np.array([[h[1] for h in row] for row in near],dtype=np.int32)
            dist = np.array([[h[2] for h in row] for row in near])
            weights = 1/(dist**2+.015**2)
            weights /= weights.sum(axis=1)[:,None]
            offsets = coords-np.einsum("ni,nij->nj",weights,rest[ids])
            self.linings.append((ob.data,ids,weights,offsets))
            ob["ep02_motion_carrier"] = str(carriers)

        for ob in shells.objects:
            bind_skin(ob, int(ob["CCSA_part_id"]))
        # Long flexible trim follows local shells. Printed legends, needles
        # and switches share one rigid frame per fitted assembly.
        assemblies = {}
        for group in trim.children:
            pieces = list(group.objects)
            pid, = {int(ob["ep02_carrier_part"]) for ob in pieces}
            for ob in pieces:
                if ob.name.startswith("One-piece floor carpet"):
                    bind_lining(ob, floor)
                elif ob.name.startswith("Continuous toe board"):
                    bind_lining(ob, (*floor,2000172))
                elif ob.name.startswith(("Wrapped console side cheek", "Continuous shoulder below",
                                         "Meter lower shelf", "Instrument support valance")):
                    bind_lining(ob, dash)
                elif ob.type == "MESH" and (ob.name.startswith(("Bonded glass frit", "Shaped fabric headliner"))
                                            or "A-pillar garnish" in group.name):
                    bind_skin(ob, pid)
                else:
                    carrier, label = pid, group.name
                    if "manual shift" in label:
                        carrier = 2000239
                    elif "carpeted footwells" in label:
                        if ob.name.startswith(("Bound footwell mat", "Mat rib")):
                            left = np.asarray(ob.bound_box).mean(axis=0)[1] > 0
                            carrier = 2000198 if left else 2000203
                        else:
                            carrier = 2000172
                    elif pid == 2000914:
                        carrier, label = 2000914, "Centre stack subassembly"
                    ob["ep02_motion_carrier"] = int(carrier)
                    assemblies.setdefault((carrier,label), []).append(ob)
        for (pid,label), hard in assemblies.items():
            centers = [np.asarray(ob.matrix_world) @ np.r_[np.asarray(ob.bound_box).mean(axis=0), 1.] for ob in hard]
            surface = self.surfaces[pid]
            nodes = np.unique(surface.nodes)
            # Fit one rotation to nearby physical nodes. This preserves
            # legibility and the rigid relationship of small hardware.
            if pid not in (2000938,2000944):
                distance = np.linalg.norm(rest[nodes]-np.median(centers,axis=0)[:3],axis=1)
                nodes = nodes[np.argsort(distance)[:min(32,len(nodes))]]
            fit_cells, _ = surface.nearest(rest[nodes])
            ref = rest[nodes]
            rel = ref-ref.mean(axis=0)
            if np.linalg.matrix_rank(rel) < 2:
                raise ValueError(f"Underdetermined attachment for {label}")
            self.fittings.append((pid, nodes, rel, ref.mean(axis=0), surface.cells[fit_cells],
                                  [(ob, ob.matrix_world.copy(), ob.hide_render) for ob in hard]))
        # The studio still has 8 m of approach baked into the environment.
        for ob in bpy.data.collections["Daylight and road"].objects:
            if ob.type == "MESH":
                ob.location.x -= 8.
        self.mount = np.array([np.flatnonzero(top["node_id"] == n).item() for n in (5000514,5000513,5000511)])
        self.rig = [(ob,ob.matrix_world.copy()) for ob in scene.objects if ob.type == "CAMERA" or ob.type == "LIGHT" and ob.data.type == "AREA"]
        self.last_active = None
        self.pointer = bpy.data.objects.get("Speedometer | pointer")
        self.pivot = bpy.data.objects.get("Speedometer | needle pivot")
        self.initial_speed = float(scene["speedometer_kmh"])
        self.report = {"native_parts":len(self.parts), "trim_objects":len(trim.all_objects),
                       "surface_vertices":sum(len(mesh.vertices) for batch in self.skins.values() for mesh,*_ in batch),
                       "lining_vertices":sum(len(mesh.vertices) for mesh,*_ in self.linings),
                       "rigid_trim_groups":len(self.fittings)}
        if self.pointer and self.pivot:
            # The dial plane in dashboard() has +u to the passenger side.
            center = points(self.pivot.data).mean(axis=0)
            normal = np.array([-1.,0.,.13]); normal /= np.linalg.norm(normal)
            self.dial_center = Matrix.Translation(center)
            self.dial_normal = normal

    def update(self, xyz, active, speed):
        changed = active is not self.last_active
        for pid, meshes in self.skins.items():
            surface = self.surfaces[pid]
            tri = xyz[surface.nodes]
            axes, area = tri_axes(tri)
            collapsed = area < 1e-12
            axes[collapsed] = surface.axes[collapsed]
            for mesh, (face,w,offset), cells, flag in meshes:
                coords = (np.einsum("ni,nij->nj",w,tri[face]) +
                          np.einsum("ni,nij->nj",offset,axes[face]))
                mesh.vertices.foreach_set("co", np.ascontiguousarray(coords,dtype=np.float32).ravel())
                if changed and pid not in self.rigid_parts:
                    flag.data.foreach_set("value", np.ascontiguousarray(~active[cells]))
                mesh.update()
        for pid, nodes, ref, center, cells, pieces in self.fittings:
            now = xyz[nodes]
            u, _, vh = np.linalg.svd(ref.T @ (now-now.mean(axis=0)))
            sign = 1 if np.linalg.det(vh.T @ u.T)>0 else -1
            rot = vh.T @ np.diag([1,1,sign]) @ u.T
            pose = Matrix.Translation(now.mean(axis=0)-rot@center) @ Matrix(rot).to_4x4()
            gone = pid not in self.rigid_parts and not np.any(active[cells])
            for ob, basis, hidden in pieces:
                ob.matrix_world = pose @ basis
                ob.hide_render = hidden or gone
                if ob == self.pointer and self.pivot:
                    angle = np.deg2rad(-234*(speed-self.initial_speed)/1.609344/140)
                    ob.matrix_world = pose @ self.dial_center @ Matrix.Rotation(angle,4,self.dial_normal) @ self.dial_center.inverted() @ basis
        def seat_frame(positions):
            origin, fore, left = positions[self.mount]
            x = fore-origin
            x /= np.linalg.norm(x)
            z = np.cross(x, left-origin)
            z /= np.linalg.norm(z)
            matrix = Matrix(np.column_stack((x,np.cross(z,x),z))).to_4x4()
            matrix.translation = origin
            return matrix
        rig_motion = seat_frame(xyz) @ seat_frame(self.rest).inverted()
        rotation = np.asarray(rig_motion.to_3x3())
        for mesh,nodes,weights,offsets in self.linings:
            coords = np.einsum("ni,nij->nj",weights,xyz[nodes]) + offsets @ rotation.T
            mesh.vertices.foreach_set("co",np.ascontiguousarray(coords,dtype=np.float32).ravel())
            mesh.update()
        for ob, basis in self.rig:
            ob.matrix_world = rig_motion @ basis
        self.last_active = active
