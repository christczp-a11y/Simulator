"""Cut the particle plane into rigid fragments (Voronoi in 3D per structural group),
compute masses and the glue graph between fragments. numpy/scipy only."""
import numpy as np
from scipy.spatial import cKDTree
import plane

GROUPS = {   # group -> (parts, n_fragments, mass_kg)
    "fuselage": (["nose", "cockpit", "cabin_fwd", "cabin_mid", "aft_fuse", "tailcone", "windshield", "windows"], 430, 2300),
    "wing_L": (["wing_L", "fuel_L", "navlight_L"], 150, 1500), "wing_R": (["wing_R", "fuel_R", "navlight_R"], 150, 1500),
    "winglet_L": (["winglet_L"], 6, 25), "winglet_R": (["winglet_R"], 6, 25),
    "engine_L": (["engine_L", "fan_L"], 46, 160), "engine_R": (["engine_R", "fan_R"], 46, 160),
    "core_L": (["core_L"], 3, 420), "core_R": (["core_R"], 3, 420),
    "pylon_L": (["pylon_L"], 6, 50), "pylon_R": (["pylon_R"], 6, 50),
    "fin": (["fin", "beacon"], 40, 170), "stab_L": (["stab_L"], 16, 60), "stab_R": (["stab_R"], 16, 60),
    "deltafin_L": (["deltafin_L"], 7, 20), "deltafin_R": (["deltafin_R"], 7, 20),
    "floor": (["floor"], 36, 350), "seats": (["seats"], 9, 450), "bulkhead": (["bulkhead"], 10, 150),
}
# glue strength multipliers (per point-link) between / within groups
STRENGTH = {"fuselage": 1.0, "wing_L": 2.2, "wing_R": 2.2, "winglet_L": 1.5, "winglet_R": 1.5,
            "engine_L": 1.2, "engine_R": 1.2, "core_L": 30, "core_R": 30, "pylon_L": 4, "pylon_R": 4,
            "fin": 1.6, "stab_L": 1.6, "stab_R": 1.6, "deltafin_L": 1.5, "deltafin_R": 1.5,
            "floor": 0.8, "seats": 3.0, "bulkhead": 0.8}
CROSS = 5.0   # extra multiplier for links joining two different groups (roots, mounts)


def run(pos, part, seed=3, link_r=0.058):
    rng = np.random.default_rng(seed)
    n = len(pos)
    frag = np.full(n, -1, np.int64); grp = np.full(n, -1, np.int64); pmass = np.zeros(n)
    gnames = list(GROUPS); nf = 0; frag_group = []
    for gi, g in enumerate(gnames):
        parts, k, mass = GROUPS[g]
        m = np.isin(part, [plane.PID[p] for p in parts]); idx = np.flatnonzero(m)
        grp[idx] = gi; pmass[idx] = mass / len(idx)
        P = pos[idx]
        # seed density: finer pieces where the airframe meets the ground first
        w = np.ones(len(P))
        if g == "fuselage":
            w *= 1.0 + 2.5 * np.clip((P[:, 0] - 1.0) / 6.0, 0, 1) + 1.5 * np.clip(-P[:, 2] / 0.9, 0, 1)
        if g.startswith("wing_"):
            w *= 1.0 + 1.0 * np.clip(np.abs(P[:, 1]) / 6.0, 0, 1)
        k = min(k, len(P) // 12)
        seeds = P[rng.choice(len(P), k, replace=False, p=w / w.sum())]
        if g.startswith("core"):
            seeds = P[np.argsort(P[:, 0])[np.linspace(0, len(P) - 1, k + 2).astype(int)[1:-1]]]
        lab = cKDTree(seeds).query(P)[1]
        for _ in range(1):   # one Lloyd step keeps shards irregular but not slivers
            cen = np.stack([P[lab == i].mean(0) if np.any(lab == i) else seeds[i] for i in range(k)])
            lab = cKDTree(cen).query(P)[1]
        # merge tiny cells
        cnt = np.bincount(lab, minlength=k)
        good = np.flatnonzero(cnt >= 10)
        cen = np.stack([P[lab == i].mean(0) for i in good])
        lab = cKDTree(cen).query(P)[1]
        frag[idx] = nf + lab; nf += len(good); frag_group += [gi] * len(good)
    frag_group = np.array(frag_group)
    # glue graph
    tree = cKDTree(pos)
    pairs = tree.query_pairs(link_r, output_type="ndarray")
    # cores hang inside the nacelles: wider search
    core_idx = np.flatnonzero(np.isin(grp, [gnames.index("core_L"), gnames.index("core_R")]))
    eng_idx = np.flatnonzero(np.isin(grp, [gnames.index("engine_L"), gnames.index("engine_R")]))
    d, j = cKDTree(pos[eng_idx]).query(pos[core_idx], k=3, distance_upper_bound=0.4)
    ok = np.isfinite(d)
    extra = np.stack([np.repeat(core_idx, 3)[ok.ravel()], eng_idx[np.minimum(j, len(eng_idx) - 1).ravel()[ok.ravel()]]], 1)
    pairs = np.concatenate([pairs, extra])
    fa, fb = frag[pairs[:, 0]], frag[pairs[:, 1]]
    m = fa != fb; pairs = pairs[m]; fa, fb = fa[m], fb[m]
    lo = np.minimum(fa, fb); hi = np.maximum(fa, fb)
    key = lo * nf + hi
    uk, inv, cnt = np.unique(key, return_inverse=True, return_counts=True)
    mid = 0.5 * (pos[pairs[:, 0]] + pos[pairs[:, 1]])
    anchor = np.stack([np.bincount(inv, mid[:, a], len(uk)) / cnt for a in range(3)], 1)
    la, lb = uk // nf, uk % nf
    ga, gb = frag_group[la], frag_group[lb]
    s = np.array([min(STRENGTH[gnames[a]], STRENGTH[gnames[b]]) for a, b in zip(ga, gb)])
    s = np.where(ga != gb, s * CROSS, s)
    # cross-group fragment pairs that start close together but are not glued: their hulls may
    # overlap at rest (wing through fuselage, floor edges...) -> must never collide with each other
    wide = tree.query_pairs(0.16, output_type="ndarray")
    wa, wb = frag[wide[:, 0]], frag[wide[:, 1]]
    m = (wa != wb) & (frag_group[wa] != frag_group[wb])
    wk = np.unique(np.minimum(wa[m], wb[m]) * nf + np.maximum(wa[m], wb[m]))
    wk = np.setdiff1d(wk, uk)
    return dict(nc_a=wk // nf, nc_b=wk % nf, frag=frag, grp=grp, pmass=pmass, frag_group=frag_group, gnames=np.array(gnames),
                link_a=la, link_b=lb, link_n=cnt, link_s=s, link_anchor=anchor, link_cross=(ga != gb))


if __name__ == "__main__":
    d = np.load("plane.npz")
    out = run(d["pos"].astype(float), d["part"])
    nf = out["frag"].max() + 1
    c = np.bincount(out["frag"])
    print("fragments", nf, "links", len(out["link_a"]), "pts/frag min/med/max", c.min(), int(np.median(c)), c.max())
    print("unassigned", np.sum(out["frag"] < 0))
    # connectivity check
    import scipy.sparse as sp, scipy.sparse.csgraph as cg
    A = sp.coo_matrix((np.ones(len(out["link_a"])), (out["link_a"], out["link_b"])), shape=(nf, nf))
    ncomp, lab = cg.connected_components(A, directed=False)
    print("components", ncomp, np.bincount(lab)[:10])
    if ncomp > 1:
        for cid in range(1, ncomp):
            f = np.flatnonzero(lab == cid)[:5]
            print("  island", cid, [str(out["gnames"][out["frag_group"][x]]) for x in f])
    np.savez_compressed("fracture.npz", **out)
