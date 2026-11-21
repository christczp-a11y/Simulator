"""Impact pose shared by the first-person simulation and renderer (same convention as mpm.py)."""
import numpy as np
POSE = dict(speed=95.0, path_deg=-33.0, pitch_deg=-24.0, roll_deg=14.0, yaw_deg=4.0)


def frame(P=POSE):
    r, pt, yw = (np.radians(P[k]) for k in ("roll_deg", "pitch_deg", "yaw_deg"))
    Rx = np.array([[1, 0, 0], [0, np.cos(r), -np.sin(r)], [0, np.sin(r), np.cos(r)]])
    Ry = np.array([[np.cos(-pt), 0, np.sin(-pt)], [0, 1, 0], [-np.sin(-pt), 0, np.cos(-pt)]])
    Rz = np.array([[np.cos(yw), -np.sin(yw), 0], [np.sin(yw), np.cos(yw), 0], [0, 0, 1]])
    g = np.radians(P["path_deg"])
    return Rz @ Ry @ Rx, np.array([np.cos(g), 0.0, np.sin(g)]) * P["speed"]


def place(verts, P=POSE):
    """world positions at t = 0, the instant the lowest point of the model touches the ground (z = 0) at the origin"""
    R0, vel = frame(P); w = np.asarray(verts, np.float64) @ R0.T; T0 = -w[np.argmin(w[:, 2])]
    return w + T0, R0, T0, vel
