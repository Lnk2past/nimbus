"""
defaults.py
-----------
Module-level defaults for all TransitionPipe instances.

    import nimbus
    nimbus.defaults.duration_ms = 600
    nimbus.defaults.easing = "elastic_out"

Defaults are copied into each TransitionPipe at construction time.
"""

import param


class _Defaults(param.Parameterized):
    """Container for module-level defaults copied into each TransitionPipe at construction."""

    duration_ms = param.Integer(
        default=300, bounds=(1, None), doc="Transition duration in ms."
    )
    easing = param.Parameter(
        default="ease_in_out", doc="Easing — string preset name or CubicSplineEasing."
    )
    fps = param.Integer(default=60, bounds=(1, 120), doc="Frames per second.")
    on_interrupt = param.ObjectSelector(
        default="from_current",
        objects=["from_current", "queue", "drop"],
        doc="Interrupt behaviour.",
    )

    def __repr__(self) -> str:
        """Return a concise human-readable summary of the current defaults."""
        return (
            f"nimbus defaults("
            f"duration_ms={self.duration_ms}, "
            f"easing={self.easing!r}, "
            f"fps={self.fps}, "
            f"on_interrupt={self.on_interrupt!r})"
        )


#: Global defaults instance — mutate this to affect pipes constructed afterwards.
defaults = _Defaults(name="defaults")
