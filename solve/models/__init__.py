"""Registry of physical models for M3 scoring.

Each entry maps (case, jet state, parameters, options) to a base.Prediction holding
every predicted observable. Hypotheses (solve/hypotheses/*.yaml) name a model by its
registry key; nothing in solve/ looks at a hypothesis's id or label.
"""

from __future__ import annotations

from .point import close_object, glare_target, point_target, slow_mover, wind_drifter
from .spline import spline_path

MODELS = {
    "point_target": point_target,
    "wind_drifter": wind_drifter,
    "slow_mover": slow_mover,
    "close_object": close_object,
    "glare_target": glare_target,
    "spline_path": spline_path,
}


def get(name: str):
    try:
        return MODELS[name]
    except KeyError as e:
        raise KeyError(f"unknown model {name!r}; registry: {sorted(MODELS)}") from e
