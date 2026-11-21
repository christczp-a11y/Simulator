"""Colour schemes for the aircraft lattice (numpy only). Linear RGB.
scheme "v1"      : categorical colour per part (first cut)
scheme "design"  : cold airframe / warm energy. Position-coded gradients, so a fragment's colour says where it came from.
scheme "livery"  : plausible business-jet paint job (white, navy cheatline, gold pinstripe, bare-metal leading edges).
Returns rgb (N,3), base emission (N,), edge colour (3,) shown along broken edges, edge emission."""
import numpy as np

X0 = 7.9


def _ramp(x, xs, cols):
    cols = np.asarray(cols, np.float32)
    return np.stack([np.interp(x, xs, cols[:, i]) for i in range(3)], -1).astype(np.float32)


def _mix(a, b, w):
    w = np.clip(w, 0, 1)[:, None]
    return a * (1 - w) + np.asarray(b, np.float32) * w


def colors(rest, part, pid, scheme, part_rgb_v1=None):
    n = len(rest); x, y, z = rest[:, 0], rest[:, 1], rest[:, 2]; s = X0 - x
    P = lambda *names: np.isin(part, [pid[k] for k in names])
    rgb = np.zeros((n, 3), np.float32); emit = np.full(n, 0.30, np.float32)
    if scheme == "v1":
        rgb[:] = part_rgb_v1[part]
        for k, e in (("windows", 1.2), ("windshield", 0.9), ("fan_L", 1.5), ("fan_R", 1.5), ("core_L", 1.5), ("core_R", 1.5), ("seats", 0.8), ("fuel_L", 1.0), ("fuel_R", 1.0)):
            emit[P(k)] = e
        edge = None; edge_emit = 0.0
    elif scheme == "design":
        ice, sky, azure, cobalt, indigo = (0.78, 0.94, 1.0), (0.26, 0.74, 1.0), (0.07, 0.40, 1.0), (0.05, 0.17, 0.85), (0.20, 0.09, 0.72)
        violet, lilac, rose, mint = (0.50, 0.20, 1.0), (0.80, 0.62, 1.0), (1.0, 0.16, 0.42), (0.10, 1.0, 0.62)
        amber, gold, steel = (1.0, 0.50, 0.06), (1.0, 0.72, 0.28), (0.30, 0.40, 0.58)
        fus = _ramp(s, [0, 2.5, 7.5, 12.5, 17], [ice, sky, azure, cobalt, indigo])
        m = P("nose", "cockpit", "cabin_fwd", "cabin_mid", "aft_fuse", "tailcone"); rgb[m] = fus[m]
        # wings: root picks up the fuselage blue, tip fades into the nav-light colour of that side
        ay = np.abs(y)
        for nm, tip in (("wing_L", rose), ("wing_R", mint)):
            m = P(nm); rgb[m] = _ramp(ay[m], [0.9, 3.4, 6.3], [azure, sky, tip])
        for nm, tip in (("winglet_L", rose), ("winglet_R", mint)):
            m = P(nm); rgb[m] = _ramp(z[m], [-0.4, 0.7], [tip, (1, 1, 1)]) * 0.6 + np.asarray(tip, np.float32) * 0.4
        m = P("fin"); rgb[m] = _ramp(z[m], [0.7, 2.9], [cobalt, violet])
        m = P("stab_L", "stab_R"); rgb[m] = _ramp(ay[m], [0, 2.3], [violet, lilac])
        m = P("deltafin_L", "deltafin_R"); rgb[m] = indigo
        # engines: cool steel shell, warm intake lip and tail pipe
        m = P("engine_L", "engine_R"); se = (X0 - 11.75) - x          # distance aft of the intake lip
        rgb[m] = _ramp(se[m], [0, 0.22, 0.5, 2.5, 3.0], [gold, amber, steel, steel, amber]); emit[m] = np.interp(se[m], [0, 0.22, 0.5, 2.5, 3.0], [1.4, 0.9, 0.3, 0.3, 1.0])
        m = P("pylon_L", "pylon_R"); rgb[m] = steel
        m = P("fan_L", "fan_R"); rgb[m] = gold; emit[m] = 1.6
        m = P("core_L", "core_R"); rgb[m] = amber; emit[m] = 1.4
        m = P("windows"); rgb[m] = (1.0, 0.80, 0.50); emit[m] = 1.6
        m = P("windshield"); rgb[m] = (0.55, 0.95, 1.0); emit[m] = 0.8
        m = P("seats"); rgb[m] = gold; emit[m] = 0.9
        m = P("floor"); rgb[m] = (0.16, 0.22, 0.40)
        m = P("bulkhead"); rgb[m] = (0.30, 0.42, 0.70)
        m = P("fuel_L", "fuel_R"); rgb[m] = amber; emit[m] = 0.9
        edge = np.array([0.85, 0.97, 1.0], np.float32); edge_emit = 0.9
    elif scheme == "livery":
        white, navy, gold = np.array([0.86, 0.87, 0.90], np.float32), (0.015, 0.045, 0.21), (0.90, 0.56, 0.10)
        grey, metal, dark = (0.42, 0.45, 0.50), (0.72, 0.76, 0.82), (0.03, 0.035, 0.045)
        rgb[:] = white; emit[:] = 0.24
        fz = np.interp(s, [0, 0.25, 0.7, 1.4, 2.2, 3.1, 4.0, 4.8, 11.0, 12.4, 13.8, 15.2, 16.2, 16.75, 16.9],
                       [-0.34, -0.32, -0.29, -0.24, -0.17, -0.09, -0.03, 0, 0, 0.04, 0.12, 0.24, 0.35, 0.42, 0.44])
        zl = z - fz
        m = P("nose", "cockpit", "cabin_fwd", "cabin_mid", "aft_fuse", "tailcone")
        # cheatline under the windows, sweeping up toward the fin behind the wing
        zc = -0.10 + np.clip(s - 10.2, 0, None) * 0.17 + np.clip(2.6 - s, 0, None) * -0.10
        band = m & (zl > zc - 0.14) & (zl < zc + 0.03) & (s > 1.1)
        pin = m & (zl > zc - 0.24) & (zl <= zc - 0.165) & (s > 1.1)
        belly = m & (zl < -0.62)
        rgb[belly] = grey; rgb[band] = navy; rgb[pin] = gold
        glare = m & (s > 1.25) & (s < 2.15) & (zl > 0.05) & (np.abs(y) < 0.30); rgb[glare] = dark
        m = P("windshield"); rgb[m] = (0.035, 0.06, 0.09); emit[m] = 0.55
        m = P("windows"); rgb[m] = (0.9, 0.72, 0.45); emit[m] = 0.9
        # flying surfaces: white with bare-metal leading edges
        sweep = np.tan(np.radians(13.0)); c_root, c_tip, ytip = 2.75, 1.05, 6.30; ay = np.abs(y)
        m = P("wing_L", "wing_R")
        u = ay / ytip; c = c_root + (c_tip - c_root) * u
        x_le = (X0 - 6.45) + (((X0 - 6.45) - 0.25 * c_root - sweep * ytip + 0.25 * c_tip) - (X0 - 6.45)) * u
        xc = (x_le - x) / c
        rgb[m & (xc < 0.07)] = metal; emit[m & (xc < 0.07)] = 0.4
        rgb[m & (z < -0.66 + 0.0437 * ay - 0.01) & (xc >= 0.07)] = grey
        m = P("winglet_L", "winglet_R"); rgb[m] = navy; rgb[m & (z > 0.48)] = gold
        m = P("fin"); rgb[m] = white
        dz = z - (1.55 + (x - (X0 - 15.0)) * 0.55)          # slanted colour break on the fin
        rgb[m & (dz > 0.12)] = navy; rgb[m & (dz > 0.0) & (dz <= 0.12)] = gold
        m = P("stab_L", "stab_R"); le = (X0 - 15.85) - ay * (1.2 / 2.235); rgb[m & (le - x < 0.09)] = metal
        m = P("engine_L", "engine_R"); se = (X0 - 11.75) - x
        rgb[m & (se < 0.20)] = metal; emit[m & (se < 0.20)] = 0.45
        rgb[m & (se > 1.05) & (se < 1.55)] = navy; rgb[m & (se >= 1.55) & (se < 1.67)] = gold
        rgb[m & (se > 2.62)] = (0.22, 0.20, 0.20)
        m = P("fan_L", "fan_R"); rgb[m] = (0.30, 0.32, 0.36); emit[m] = 0.35
        m = P("core_L", "core_R"); rgb[m] = (0.50, 0.42, 0.36)
        m = P("seats"); rgb[m] = (0.70, 0.50, 0.30); emit[m] = 0.5
        m = P("floor"); rgb[m] = (0.20, 0.21, 0.25)
        m = P("bulkhead"); rgb[m] = (0.50, 0.60, 0.14)
        m = P("fuel_L", "fuel_R"); rgb[m] = (0.85, 0.55, 0.10); emit[m] = 0.6
        edge = np.array([0.50, 0.66, 0.12], np.float32); edge_emit = 0.55       # zinc-chromate primer on torn edges
    else:
        raise ValueError(scheme)
    for k in ("navlight_L", "beacon"): m = P(k); rgb[m] = (1.0, 0.02, 0.02); emit[m] = 25
    m = P("navlight_R"); rgb[m] = (0.02, 1.0, 0.10); emit[m] = 25
    return rgb, emit, edge, edge_emit
