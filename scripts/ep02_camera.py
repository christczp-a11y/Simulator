"""Physical-time camera for EP02. x forward, y left, z up, angles in degrees."""
from dataclasses import dataclass

import numpy as np
from scipy.signal import lsim

# All speed cases use the same phases and frequencies.
rng = np.random.default_rng(20261121)


def oscillator_bank(lo, hi, axes):
    f = rng.uniform(lo, hi, (axes, 6))
    phase = rng.uniform(0, 2*np.pi, f.shape)
    def sample(t):
        t = np.atleast_1d(t)
        return np.sin(2*np.pi*t[:,None,None]*f + phase).sum(axis=2)/f.shape[1]
    return sample


road = oscillator_bank(5, 25, 6)
sway = oscillator_bank(.5, 2, 3)
ring = oscillator_bank(30, 80, 3)


@dataclass
class Camera:
    time: np.ndarray
    travel: np.ndarray
    contact: float
    peak_time: float
    peak_g: float
    speed: float

    @classmethod
    def from_history(cls, history):
        t = history["time_s"]
        rel = history["contact_time_s"]
        g = history["seat_decel_cfc60_g"]
        tc = t[0] - rel[0]
        hit = np.flatnonzero(rel >= 0)
        peak = hit[np.argmax(g[hit])]
        grid = np.linspace(0, t[-1], round(t[-1] / .0001) + 1)
        w = 2*np.pi*6
        # x'' + 2*zeta*w*x' + w*w*x = -a_mount. Forward travel in m.
        drive = np.interp(grid,t,g)*9.80665
        _,raw,_ = lsim(([1.0], [1, 2*.4*w, w*w]), drive, grid)
        x = .35*np.tanh(raw/.35)
        return cls(grid,x,tc,t[peak],g[peak],history["cg_speed_kmh"][0])

    def offsets(self, physical_s, mode):
        t = np.atleast_1d(physical_s)
        delta = np.zeros((len(t),6))  # xyz in m, then roll/pitch/yaw in deg
        if mode == "fixed":
            return delta
        # Smoothly hand over from driving vibration to impact response.
        fade = np.clip(1-(t-self.contact)/.010,0,1)
        fade = fade*fade*(3-2*fade)
        scale = np.clip(self.speed/120,.3,1.0)
        delta = road(t)*np.array([.003,.003,.003,.15,.15,.15])*scale*fade[:,None]
        delta[:,3:] += sway(t)*.2*fade[:,None]
        travel = np.interp(t,self.time,self.travel,left=0)
        delta[:,0] += travel
        delta[:,4] += np.clip(np.rad2deg(np.arctan2(travel,.50)), -35, 35)
        phase = np.maximum(0,t-self.peak_time)
        envelope = (1-np.exp(-phase/.004))*np.exp(-phase/.04)
        delta[:,3:] += ring(t)*min(.6,.42*self.peak_g/43.5)*envelope[:,None]
        return delta
