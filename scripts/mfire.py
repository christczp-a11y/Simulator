"""Fire pass with Blender's own gas solver (Mantaflow), driven by the fuel particles of an MPM run.
  blender -b --factory-startup -P mfire.py -- --data <data> --mpm <mpm run> --out <fire dir> [--cell 0.4 ...]
One Mantaflow frame per OUTPUT frame of the slow-motion timeline. The domain time scale follows the timeline, so the gas
evolves in simulated seconds while the emitters move exactly as they do on screen.
Emitters: one small tetrahedron per fuel particle, following that particle; it has zero size until the particle ignites.
Writes <out>/data/fluid_data_####.vdb (density, flame, heat, velocity in metres per simulated second; index space starts at
the domain's minimum corner), <out>/meta.json and <out>/preview.png.  Blender frame = output frame + 1."""
import bpy, sys, os, json, time, argparse, struct
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fx, mview

ap = argparse.ArgumentParser()
ap.add_argument("--data", default=os.path.join(HERE, "..", "data"))
ap.add_argument("--mpm", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--n", type=int, default=450)
ap.add_argument("--end", type=int, default=449)          # last output frame to simulate
ap.add_argument("--cell", type=float, default=0.4)       # base grid cell (m)
ap.add_argument("--noise", type=int, default=0)          # wavelet up-res factor (0 = off)
ap.add_argument("--pad", type=float, default=10.0)
ap.add_argument("--padfwd", type=float, default=25.0)   # extra room ahead (+x): the fire keeps the aircraft's momentum
ap.add_argument("--top", type=float, default=22.0)
ap.add_argument("--rflash", type=float, default=1.3)     # emitter radius (m) during the flash
ap.add_argument("--rburn", type=float, default=0.5)      # emitter radius (m) while the rest of the fuel burns
ap.add_argument("--spray", type=int, default=2)          # mist blobs thrown per igniting fuel particle
ap.add_argument("--rspray", type=float, default=1.0)     # scale of the mist blob radius (0.7-1.5 m)
ap.add_argument("--blife", type=float, default=40.0)     # typical sim frames a mist blob keeps feeding fuel (after that the gas is on its own)
ap.add_argument("--vspread", type=float, default=1.0)    # scale of the random spread speed of the mist
ap.add_argument("--vup", type=float, default=1.0)        # scale of the upward bounce speed of the mist
ap.add_argument("--flash", type=float, default=30.0)     # sim frames the flash lasts
ap.add_argument("--swell", type=float, default=8.0)      # sim frames an emitter takes to swell to full size at ignition
ap.add_argument("--sdist", type=float, default=0.05)     # emission distance from the emitter surface (cells); the volume inside always emits
ap.add_argument("--fuel", type=float, default=1.0)
ap.add_argument("--dur_mul", type=float, default=1.0)    # stretch of every particle's burn time
ap.add_argument("--vfac", type=float, default=0.8)       # share of the fuel's own velocity given to the gas
ap.add_argument("--vnorm", type=float, default=0.0)      # extra velocity along emitter normals (expansion of the flash)
ap.add_argument("--beta", type=float, default=1.0)       # heat buoyancy
ap.add_argument("--alpha", type=float, default=0.3)      # smoke density buoyancy
ap.add_argument("--vort", type=float, default=0.3)
ap.add_argument("--burn", type=float, default=0.75)      # burning rate (higher = shorter flames)
ap.add_argument("--smoke", type=float, default=1.0)      # smoke made by the flame
ap.add_argument("--fvort", type=float, default=0.5)
ap.add_argument("--threads", type=int, default=0)
ap.add_argument("--views", default="")                   # output frames for the preview sheet
A = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
os.makedirs(A.out, exist_ok=True)


def log(*a):
    print("[mfire]", *a, flush=True)


t00 = time.time()
X = fx.FX(os.path.join(A.data, "sim.npz"), os.path.join(A.data, "pre.npz"), mpm=A.mpm)
tl = fx.timeline(A.n)
fuel = X.fuel; ign = np.asarray(X.fuel_ign, np.float64); dur = np.asarray(X.fuel_dur, np.float64) * A.dur_mul
ok = np.isfinite(ign)
RV = np.random.default_rng(11).uniform(0.6, 1.25, len(fuel)).astype(np.float32)        # per-particle variation of the flash size
i0 = max(1, int(np.searchsorted(tl, ign[ok].min())) - 2); i1 = min(A.end, A.n - 1)
log(f"fuel particles {len(fuel)}  ignite {int(ok.sum())}  first ignition simf {ign[ok].min():.1f}  output frames {i0}..{i1}")


def weights(i):
    """emitter radius (m) per fuel particle at output frame i. Mantaflow has no gas expansion, so the fireball's volume is
    made by the emitters themselves: each swells to the flash radius at ignition, holds it for the flash, then shrinks to a
    small steady source until its fuel is gone; 0 = not burning"""
    f = tl[i]; a = f - ign; on = ok & (a >= 0) & (a < dur)
    w = np.zeros(len(fuel), np.float32); prog = np.clip(a[on] / dur[on], 0, 1)
    late = A.rburn * (0.5 + 0.5 * (1 - prog)) * np.clip((1 - prog) / 0.1, 0, 1)
    k = np.clip((a[on] - A.flash) / 10.0, 0, 1)
    w[on] = np.minimum(a[on] / A.swell, 1.0) * (A.rflash * RV[on] * (1 - k) + late * k)
    return w


# ---- fuel spray. The MPM fuel is a liquid that mostly stays in the crushed wing, but in a real crash the tanks burst into a
# mist that keeps the aircraft's speed, bounces up off the ground and burns as it goes. Each igniting fuel particle therefore
# also throws A.spray ballistic "mist blobs" (drag + a little gravity); they are emitters too, so Mantaflow gets their fuel
# and their momentum and does the rest (roll-up, buoyancy, mixing).
rs = np.random.default_rng(23); src = np.repeat(np.flatnonzero(ok), A.spray); nb = len(src)
b_t0 = ign[src] + rs.uniform(0, 14, nb); b_life = rs.uniform(A.blife * 0.5, A.blife * 1.4, nb) * A.dur_mul; b_R = rs.uniform(0.7, 1.5, nb).astype(np.float32) * A.rspray
b_x0 = np.zeros((nb, 3), np.float32); b_v0 = np.zeros((nb, 3), np.float32); fr = np.round(b_t0).astype(int)
for f in np.unique(fr):
    m = fr == f; p, v = X.pts_vel(fuel[src[m]], float(f)); b_x0[m] = p; b_v0[m] = v
d = rs.normal(0, 1, (nb, 3)); d /= np.linalg.norm(d, axis=1, keepdims=True)
b_v0 = b_v0 * rs.uniform(0.55, 1.05, (nb, 1)) + d * rs.uniform(2, 12, (nb, 1)) * A.vspread; b_v0[:, 2] = np.abs(b_v0[:, 2]) * 0.3 + rs.uniform(3, 20, nb) * A.vup
b_x0[:, 2] = np.maximum(b_x0[:, 2], 0.3); KD = 1.8; GZ = -4.0


def blobs(i):
    """spray blob centres (nb,3) and radii (nb,) at output frame i"""
    a = tl[i] - b_t0; tau = np.clip(a, 0, None)[:, None] / fx.FPS_SIM; e = (1 - np.exp(-KD * tau)) / KD
    x = b_x0 + b_v0 * e; x[:, 2] += GZ * (tau[:, 0] / KD - e[:, 0] / KD); np.maximum(x[:, 2], 0.3, out=x[:, 2])
    r = b_R * np.clip(a / A.swell, 0, 1) * np.clip((b_life - a) / 20.0, 0, 1)
    return x.astype(np.float32), r.astype(np.float32)


lo = np.full(3, np.inf); hi = np.full(3, -np.inf)
for i in range(i0, i1 + 1, 2):
    w = weights(i)
    if (w > 0).any():
        p = X.pts(fuel[w > 0], tl[i]); lo = np.minimum(lo, p.min(0)); hi = np.maximum(hi, p.max(0))
    x, r = blobs(i)
    if (r > 0).any(): lo = np.minimum(lo, x[r > 0].min(0)); hi = np.maximum(hi, x[r > 0].max(0))
c = A.cell
lo = np.array([lo[0] - A.pad, lo[1] - A.pad, 0.0]); hi = np.array([hi[0] + A.padfwd, hi[1] + A.pad, A.top])
res = np.ceil((hi - lo) / c).astype(int); hi = lo + res * c; size = hi - lo
log("domain", lo.round(2).tolist(), hi.round(2).tolist(), "res", res.tolist(), "cells %.2fM" % (res.prod() / 1e6))

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene; sc.render.fps = 30; sc.frame_start = i0 + 1; sc.frame_end = i1 + 1
if A.threads: sc.render.threads_mode = 'FIXED'; sc.render.threads = A.threads
bpy.ops.mesh.primitive_cube_add(size=1, location=tuple((lo + hi) / 2)); dom = bpy.context.object; dom.name = "domain"; dom.scale = tuple(size)
m = dom.modifiers.new("fluid", 'FLUID'); m.fluid_type = 'DOMAIN'; ds = m.domain_settings


def setp(o, k, v):
    try: setattr(o, k, v)
    except Exception as e: log("could not set", k, "->", repr(e))


ds.domain_type = 'GAS'; ds.resolution_max = int(res.max())
for k, v in dict(alpha=A.alpha, beta=A.beta, vorticity=A.vort, burning_rate=A.burn, flame_smoke=A.smoke, flame_vorticity=A.fvort,
                 use_dissolve_smoke=False, use_adaptive_domain=False, use_adaptive_timesteps=True,
                 use_collision_border_bottom=True, use_collision_border_top=False, use_collision_border_front=False,
                 use_collision_border_back=False, use_collision_border_left=False, use_collision_border_right=False,
                 cache_type='REPLAY', cache_data_format='OPENVDB', cache_directory=A.out, cache_frame_start=i0 + 1, cache_frame_end=i1 + 1,
                 openvdb_cache_compress_type='BLOSC', openvdb_data_depth='16').items():
    setp(ds, k, v)
if A.noise > 0:
    setp(ds, "use_noise", True); setp(ds, "noise_scale", A.noise); setp(ds, "noise_strength", 1.0)

# emitter: 4 vertices per fuel particle
# emitter shape: one octahedron (6 vertices, 8 outward-facing triangles) per fuel particle / mist blob
T4 = np.array([[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]], np.float32); NV = len(T4)
nf = len(fuel) + nb; base = (np.arange(nf) * NV)[:, None]; tris = []
for sx in (0, 1):
    for sy in (0, 1):
        for sz in (0, 1):
            t = (sx, 2 + sy, 4 + sz); tris.append(t if (sx + sy + sz) % 2 == 0 else (t[0], t[2], t[1]))
faces = np.concatenate([base + np.array(t)[None] for t in tris]).tolist()
# every emitter gets its own random orientation and proportions, so the fire never shows a regular emitter shape
rr = np.random.default_rng(31); Q = rr.normal(0, 1, (nf, 4)); Q /= np.linalg.norm(Q, axis=1, keepdims=True); qw, qx, qy, qz = Q.T
ROT = np.stack([np.stack([1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy - qz * qw), 2 * (qx * qz + qy * qw)], 1),
                np.stack([2 * (qx * qy + qz * qw), 1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz - qx * qw)], 1),
                np.stack([2 * (qx * qz - qy * qw), 2 * (qy * qz + qx * qw), 1 - 2 * (qx * qx + qy * qy)], 1)], 1)
SHAPE = np.einsum("nij,nvj->nvi", ROT, T4[None] * rr.uniform(0.55, 1.45, (nf, 1, 3))).astype(np.float32)


def verts(i):
    x, r = blobs(i)
    cen = np.concatenate([X.pts(fuel, tl[i]), x]); rad = np.concatenate([weights(i), r])
    return (cen[:, None, :] + SHAPE * rad[:, None, None]).reshape(-1, 3).astype(np.float32)


# Mantaflow only inherits emitter velocity from motion the dependency graph itself evaluates (edits made from Python each
# frame reset its memory of the previous positions), so the whole emitter animation goes into a point-cache file that a
# Mesh Cache modifier plays back; the time scale is keyframed for the same reason (setting it mid-run resets the bake).
pc2 = os.path.join(A.out, "emitter.pc2"); ns = i1 - i0 + 2
with open(pc2, "wb") as fh:
    fh.write(b"POINTCACHE2\0" + struct.pack("<iiffi", 1, nf * NV, float(i0), 1.0, ns))
    for i in range(i0 - 1, i1 + 1): fh.write(verts(i).tobytes())
me = bpy.data.meshes.new("fuel"); me.from_pydata(verts(i0 - 1).tolist(), [], faces); me.update()
em = bpy.data.objects.new("fuel", me); sc.collection.objects.link(em)
mc = em.modifiers.new("cache", 'MESH_CACHE')
for k, v in dict(cache_format='PC2', filepath=pc2, time_mode='FRAME', play_mode='SCENE', frame_start=float(i0), frame_scale=1.0, interpolation='LINEAR',
                 deform_mode='OVERWRITE', forward_axis='POS_Y', up_axis='POS_Z', factor=1.0).items():
    setp(mc, k, v)
fm = em.modifiers.new("fluid", 'FLUID'); fm.fluid_type = 'FLOW'; fs = fm.flow_settings
for k, v in dict(flow_type='FIRE', flow_behavior='INFLOW', fuel_amount=A.fuel, use_initial_velocity=True, velocity_factor=A.vfac,
                 velocity_normal=A.vnorm, surface_distance=A.sdist, volume_density=1.0, subframes=0, use_absolute=True).items():
    setp(fs, k, v)
for i in range(i0, i1 + 1):
    ds.time_scale = float(max((tl[i] - tl[i - 1]) / fx.FPS_SIM * sc.render.fps, 1e-4)); ds.keyframe_insert("time_scale", frame=i + 1)
log("emitter cache %.0f MB, time scale keyed, set-up %.0f s" % (os.path.getsize(pc2) / 1e6, time.time() - t00))

def save_meta():
    json.dump(dict(lo=lo.tolist(), cell=c, res=res.tolist(), i0=int(i0), i1=int(i1), n=A.n, args=vars(A), stats=stats, mpm=os.path.abspath(A.mpm)),
              open(os.path.join(A.out, "meta.json"), "w"), indent=1)


views = [int(v) for v in A.views.split(",")] if A.views else list(np.linspace(i0 + 8, i1, 6).astype(int))
tiles = []; stats = []
for i in range(i0, i1 + 1):
    t1 = time.time()
    sc.frame_set(i + 1)
    if i == i0 + 1: save_meta()                       # early, so stills can be rendered while the run is still going
    if i in views or i % 10 == 0 or i == i1:
        dg = bpy.context.evaluated_depsgraph_get(); dse = dom.evaluated_get(dg).modifiers["fluid"].domain_settings
        r = tuple(dse.domain_resolution); n = r[0] * r[1] * r[2]
        try:
            fl = np.array(dse.flame_grid, np.float32); de = np.array(dse.density_grid, np.float32)
            k = int(round((len(fl) / n) ** (1 / 3))); cc = c / k           # with noise on these are the fine grids
            if len(fl) != n * k ** 3 or len(de) != len(fl): raise RuntimeError(f"grid sizes {len(fl)} {len(de)} vs {n}")
            fl = fl.reshape(r[2] * k, r[1] * k, r[0] * k); de = de.reshape(r[2] * k, r[1] * k, r[0] * k)
            zz = np.flatnonzero(fl.max((1, 2)) > 0.05)
            s = dict(i=i, simf=round(float(tl[i]), 1), ts=round(float(dse.time_scale), 4), burning=int((weights(i) > 0).sum()), blobs=int((blobs(i)[1] > 0).sum()), flame_m3=round(float((fl > 0.05).sum() * cc ** 3), 1),
                     flame_top=float((zz.max() + 1) * cc) if len(zz) else 0.0, smoke_m3=round(float((de > 0.05).sum() * cc ** 3), 1),
                     vmax=round(float(np.abs(np.array(dse.velocity_grid, np.float32)).max()), 2), sec=round(time.time() - t1, 2), total=round(time.time() - t00))
            stats.append(s); log(json.dumps(s))
            if i in views:
                def tile(ax):
                    F = fl.max(ax); D = np.clip(de.max(ax), 0, 1)
                    img = D[..., None] * np.array([0.35, 0.35, 0.4], np.float32) + np.clip(F, 0, 1)[..., None] * np.array([1.0, 0.45, 0.08], np.float32) + np.clip(F - 0.6, 0, 1)[..., None] * 1.5
                    return np.clip(img[::-1], 0, 1)
                side = tile(1); top = tile(0); gap = np.full((2, side.shape[1], 3), 0.3, np.float32)
                tiles.append(np.concatenate([side, gap, top, gap], 0))
        except Exception as e:
            log("grid read failed at", i, repr(e))

save_meta()
if tiles:
    sheet = np.concatenate(tiles, 0); k = max(1, int(np.ceil(700 / sheet.shape[1])))
    sheet = np.repeat(np.repeat(sheet, k, 0), k, 1)
    mview.png(os.path.join(A.out, "preview.png"), (sheet * 255).astype(np.uint8))
log("done in %.0f s" % (time.time() - t00))
