"""Point-target models: one object moving at constant velocity relative to the air mass.

Path: the object starts on the reference frame's sight line (base.anchor) and moves
with ground velocity = air velocity + wind at its altitude (+ the shared wind error),
at constant horizontal velocity in the tangent plane and constant vertical speed,
staying on its altitude shell. Air velocity comes from `airspeed_kt` and `heading_deg`
(degrees true) when the model uses them; a wind drifter has none.

Variants differ only in emitter physics (size model, glare) and in which velocity
parameters they read; the hypothesis YAML picks one by name and supplies priors.
"""

from __future__ import annotations

import numpy as np

from .. import frames as F
from .base import INVALID, Prediction, anchor, object_wind, observables
from .geometry import JetState, z_on_shell


def _path(case, jet: JetState, params: dict, use_air_velocity: bool):
    a = anchor(case, jet, params)
    if a is None:
        return None
    p_ref, h_ref = a
    i = case.ref_frame
    tau = case.t - case.t[i]
    vz = params.get("vz_fpm", 0.0) * F.FT / 60.0
    if use_air_velocity:
        A = params.get("airspeed_kt", 0.0) * F.KT
        psi = np.radians(params.get("heading_deg", 0.0))
        v_air_h = np.array([A * np.sin(psi), A * np.cos(psi)])
    else:
        v_air_h = np.zeros(2)
    wind = object_wind(case, h_ref, params)
    v_h = v_air_h + wind
    xy = p_ref[:2] + np.outer(tau, v_h)
    h = h_ref + vz * tau
    if np.any(h[case.window] < 0):
        return None
    z = z_on_shell(xy, h)
    pos = np.column_stack([xy, z])
    vel = np.column_stack([np.broadcast_to(v_h, xy.shape), np.gradient(z, case.t)])
    air = np.column_stack([np.broadcast_to(v_air_h, xy.shape), np.full(len(tau), vz)])
    return pos, vel, air, wind


def _make(size_model: str, glare: bool, use_air_velocity: bool):
    def model(case, jet: JetState, params: dict, options: dict | None = None) -> Prediction:
        r = _path(case, jet, params, use_air_velocity)
        if r is None:
            return INVALID
        pos, vel, air, wind = r
        return observables(case, jet, pos, vel, air, wind, size_model, glare)
    model.size_model = size_model
    model.glare = glare
    model.use_air_velocity = use_air_velocity
    return model


# Real object moving through the air at constant velocity (generic).
point_target = _make("inverse_range", glare=False, use_air_velocity=True)
# Real object carried by the wind (no air velocity of its own; vertical speed allowed).
wind_drifter = _make("inverse_range", glare=False, use_air_velocity=False)
# Real slow mover (bird, small drone): same physics as point_target, kept as its own entry
# so the registry documents the intended speed regime; the speed limits live in the YAML priors.
slow_mover = _make("inverse_range", glare=False, use_air_velocity=True)
# Close small object: same physics again; nearness is a prior, not code.
close_object = _make("inverse_range", glare=False, use_air_velocity=True)
# A target seen through a glare: the path is the target's, the image blob is a glare whose size
# follows its brightness (not range) and whose orientation follows the pod's derotation.
glare_target = _make("brightness_sqrt", glare=True, use_air_velocity=True)
