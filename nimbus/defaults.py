"""
defaults.py
-----------
Module-level defaults for all TransitionPipe instances.

    import nimbus
    nimbus.defaults.duration_ms = 600
    nimbus.defaults.easing = "elastic_out"

Any TransitionPipe that does not explicitly set a param will inherit
from these defaults at send() time.
"""

from __future__ import annotations

import param


class _Defaults(param.Parameterized):
    duration_ms  = param.Integer(default=300, bounds=(1, None), doc="Default transition duration in ms.")
    easing       = param.Parameter(default="ease_in_out", doc="Default easing — string preset name or CubicSplineEasing.")
    fps          = param.Integer(default=60, bounds=(1, 120), doc="Default frames per second.")
    on_interrupt = param.ObjectSelector(
        default="from_current",
        objects=["from_current", "queue", "drop"],
        doc="Default interrupt behaviour.",
    )

    def __repr__(self) -> str:
        return (
            f"nimbus defaults("
            f"duration_ms={self.duration_ms}, "
            f"easing={self.easing!r}, "
            f"fps={self.fps}, "
            f"on_interrupt={self.on_interrupt!r})"
        )


#: Global defaults instance — mutate this to affect all TransitionPipes.
defaults = _Defaults(name="defaults")
