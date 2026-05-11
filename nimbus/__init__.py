"""
nimbus (nimbus) — smooth animated data transitions for HoloViews / Panel.

Minimal usage:

    from nimbus import TransitionPipe

    pipe = TransitionPipe(data={"x": x, "y": y})
    dmap = hv.DynamicMap(make_curve, streams=[pipe])
    pipe.send(new_data)

Seed defaults before constructing pipes:

    import nimbus
    nimbus.defaults.duration_ms = 600
    nimbus.defaults.easing = "elastic_out"
"""

from nimbus.defaults import defaults
from nimbus.transition import CubicSplineEasing, Easing, PRESETS
from nimbus.stream import TransitionPipe
from nimbus.interpolate import interpolate, snapshot

__all__ = [
    # Core
    "TransitionPipe",
    # Easing
    "CubicSplineEasing",
    "Easing",
    "PRESETS",
    # Global config
    "defaults",
    # Utilities
    "interpolate",
    "snapshot",
]
