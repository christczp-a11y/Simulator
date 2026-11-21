import os
import numpy as np

def qrot(q, v):
    """rotate vectors v (N,3) by quaternions q (N,4) (w,x,y,z)"""
    w = q[:, :1]; u = q[:, 1:]
    t = 2 * np.cross(u, v)
    return v + w * t + np.cross(u, t)

class Sim:
    def __init__(self, path):
        d = np.load(path)
        self.loc = d["loc"]; self.quat = d["quat"]; self.local = d["local"]; self.frag = d["frag"]
        self.nrm0 = d["nrm0"]; self.part = d["part"]; self.fmass = d["fmass"]; self.cen0 = d["cen0"]
        self.anchor = d["anchor"]; self.link_a = d["link_a"]; self.link_b = d["link_b"]; self.link_n = d["link_n"]
        self.vel = d["vel"]; self.T = len(self.loc); self.nf = self.loc.shape[1]
        import json; self.cfg = json.loads(str(d["cfg"]))
        # frame 1 quaternion is identity for all; hull objects were created unrotated
    def frame(self, f, normals=False):
        """f: 0-based float frame; linear blend between sim frames"""
        f = float(np.clip(f, 0, self.T - 1)); i = int(np.floor(f)); a = f - i; j = min(i + 1, self.T - 1)
        L = self.loc[i] * (1 - a) + self.loc[j] * a
        q0 = self.quat[i]; q1 = self.quat[j]
        q1 = np.where((q0 * q1).sum(1, keepdims=True) < 0, -q1, q1)
        Q = q0 * (1 - a) + q1 * a; Q /= np.linalg.norm(Q, axis=1, keepdims=True)
        p = L[self.frag] + qrot(Q[self.frag], self.local)
        if normals:
            return p, qrot(Q[self.frag], self.nrm0)
        return p
    def link_gap(self, f):
        """separation of each glue link's anchor as carried by its two fragments"""
        i = int(f)
        def carried(body):
            return self.loc[i][body] + qrot(self.quat[i][body], self.anchor - self.cen0[body])
        return np.linalg.norm(carried(self.link_a) - carried(self.link_b), axis=1)


class MSim:
    """An MPM run (mpm.py output): positions of every particle per 240 fps frame. No rigid fragments."""
    def __init__(self, simpath, mdir):
        d = np.load(simpath)
        self.part = d["part"]; self.vel = d["vel"]; self.frag = d["frag"]; self.cen0 = d["cen0"]; self.local = d["local"]
        import json
        self.meta = json.load(open(os.path.join(mdir, "meta.json"))); self.vel = np.array(self.meta["vel"], np.float32)
        self.X = np.load(os.path.join(mdir, "x.npy"), mmap_mode="r"); self.EP = np.load(os.path.join(mdir, "ep.npy"), mmap_mode="r")
        self.tfail = np.load(os.path.join(mdir, "fail.npy")); self.T = len(self.X); self.N = self.X.shape[1]; self.mdir = mdir
        self._c = {}
        # the MPM ground condition holds material about half a grid cell above z = 0: measure that and lower everything onto the ground
        self.zoff = float(np.clip(np.percentile(np.asarray(self.X[-1])[:, 2], 0.5), 0.0, 0.2))
    def fr(self, i):
        """whole frame i in RAM (small LRU cache)"""
        if i not in self._c:
            if len(self._c) > 4: self._c.pop(next(iter(self._c)))
            x = np.array(self.X[i]); x[:, 2] -= self.zoff; self._c[i] = x
        return self._c[i]
    def pos(self, idx, f):
        if f < 0: return self.fr(0)[idx] + (self.vel * (f / 240.0)).astype(np.float32)
        f = min(f, self.T - 1.001); i = int(np.floor(f)); a = np.float32(f - i)
        return self.fr(i)[idx] * (1 - a) + self.fr(i + 1)[idx] * a
    def strain(self, f):
        i = int(np.clip(round(f), 0, self.T - 1)); return np.asarray(self.EP[i]).astype(np.float32) * 0.01
