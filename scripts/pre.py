"""Cloud-side precompute (needs scipy): break times, per-particle fracture data, emitters."""
import sys; sys.path.insert(0, '/mnt/project-files/particle-sim/scripts')
import numpy as np, plane, recon
from scipy.spatial import cKDTree

def main(simpath, fracpath, out):
    S = recon.Sim(simpath); F = np.load(fracpath)
    T, nf = S.T, S.nf
    # link break frame
    nl = len(S.link_a); tb = np.full(nl, np.inf)
    for f in range(T):
        g = S.link_gap(f)
        new = (g > 0.025) & ~np.isfinite(tb); tb[new] = f
    print("links broken", np.isfinite(tb).mean())
    # first break per fragment
    fb = np.full(nf, np.inf)
    np.minimum.at(fb, S.link_a, tb); np.minimum.at(fb, S.link_b, tb)
    # per particle: earliest break among nearby link anchors
    rest = S.cen0[S.frag] + S.local
    tree = cKDTree(S.anchor[np.isfinite(tb)]); tbf = tb[np.isfinite(tb)]
    rng = np.random.default_rng(11)
    pt_break = np.full(len(rest), np.inf, np.float32); pt_d = np.full(len(rest), 9.0, np.float32)
    nb = tree.query_ball_point(rest, 0.13)
    for i, l in enumerate(nb):
        if l:
            l = np.array(l); d = np.linalg.norm(S.anchor[np.isfinite(tb)][l] - rest[i], axis=1)
            # nearer links matter first: effective time grows with distance (glow spreads from the crack)
            eff = tbf[l] + d * 40.0
            k = np.argmin(eff); pt_break[i] = eff[k]; pt_d[i] = d[k]
    interior = np.isin(S.part, [plane.PID[p] for p in ("fuel_L", "fuel_R")])
    shed = np.isfinite(pt_break) & (pt_d < 0.10) & (rng.random(len(rest)) < 0.45) & ~interior
    print("glow particles", np.isfinite(pt_break).mean(), "shed", shed.sum())
    fuel = np.flatnonzero(interior)
    eng = [np.flatnonzero(S.part == plane.PID[p]) for p in ("engine_L", "engine_R")]
    nozzle = np.concatenate([e[np.argsort(rest[e][:, 0] @ np.ones(1) if False else (S.cen0[S.frag[e]] + S.local[e]) @ (S.vel / np.linalg.norm(S.vel)))[:160]] for e in eng])
    # ground-impact ring events: first hard touchdown of each structural group
    gnames = [str(x) for x in F["gnames"]]; fg = F["frag_group"]
    rings = []
    for g in ("fuselage", "wing_R", "wing_L", "core_R", "core_L", "fin"):
        m = np.flatnonzero(fg == gnames.index(g))
        zmin = S.loc[:, m, 2].min(1)
        hit = np.flatnonzero(zmin < 0.25)
        if len(hit):
            f = int(hit[0]); j = m[np.argmin(S.loc[f, m, 2])]
            amp = {"fuselage": 1.0, "wing_R": 0.7, "wing_L": 0.7, "core_R": 0.9, "core_L": 0.9, "fin": 0.5}[g]
            rings.append([f, S.loc[f, j, 0], S.loc[f, j, 1], amp]); print("ring", g, rings[-1])
    np.savez_compressed(out, link_tb=tb, frag_break=fb, pt_break=pt_break, shed=shed, fuel=fuel, nozzle=nozzle,
                        rings=np.array(rings, np.float32), frag_tint=(0.6 + 0.8 * rng.random(nf)).astype(np.float32),
                        part_rgb=plane.PART_RGB, part_names=np.array(plane.PARTS))

if __name__ == "__main__":
    main(*sys.argv[1:4])
