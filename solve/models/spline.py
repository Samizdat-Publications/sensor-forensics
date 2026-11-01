"""Spline-path model: an object whose motion is free, at a given reference range.

The path is the anchor point (base.anchor) plus a smooth displacement D(t) in east,
north and height, a natural cubic spline through K knots spread evenly over the
scored window, shifted so D(t_ref) = 0. Its 3K knot values are free parameters
(counted in the complexity penalty like any other, per the design). Air velocity is
the ground velocity minus the modeled wind at the object's height.
"""

from __future__ import annotations

import numpy as np
from scipy.interpolate import CubicSpline

from .base import INVALID, Prediction, anchor, observables
from .geometry import JetState, z_on_shell


def spline_path(case, jet: JetState, params: dict, options: dict | None = None) -> Prediction:
    k = int((options or {}).get("knots", 4))
    a = anchor(case, jet, params)
    if a is None:
        return INVALID
    p_ref, h_ref = a
    w = case.window
    tk = np.linspace(case.t[w[0]], case.t[w[-1]], k)
    d = np.array([[params[f"knot_{ax}_{j}"] for ax in ("e", "n", "u")] for j in range(k)])
    cs = CubicSpline(tk, d, bc_type="natural", axis=0)
    t = case.t
    D = cs(t) - cs(t[case.ref_frame])
    xy = p_ref[:2] + D[:, :2]
    h = h_ref + D[:, 2]
    if np.any(h[w] < 0):
        return INVALID
    z = z_on_shell(xy, h)
    pos = np.column_stack([xy, z])
    dv = cs(t, 1)
    vel = np.column_stack([dv[:, :2], np.gradient(z, t)])
    wind = case.env.wind_enu(h)
    wind_mean = wind[w].mean(axis=0)
    air = np.column_stack([dv[:, :2] - wind, dv[:, 2]])
    return observables(case, jet, pos, vel, air, wind_mean, "inverse_range", False)


spline_path.size_model = "inverse_range"
spline_path.glare = False
spline_path.use_air_velocity = False
