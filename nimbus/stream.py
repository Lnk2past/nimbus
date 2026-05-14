"""
stream.py
---------
TransitionPipe: a drop-in replacement for hv.streams.Pipe with built-in
animated transitions.

Minimal usage — zero config required:

    pipe = TransitionPipe(data={"x": x, "y": y})
    dmap = hv.DynamicMap(make_curve, streams=[pipe])
    pipe.send(new_data)

Override at the pipe level:

    pipe = TransitionPipe(data=..., duration_ms=600, easing="elastic_out")

Override per send:

    pipe.send(new_data, duration_ms=200, easing="bounce_out")

Seed global defaults before constructing pipes:

    import nimbus
    nimbus.defaults.duration_ms = 600
    nimbus.defaults.easing = "elastic_out"

Priority: send() kwargs  >  pipe params
"""

import time
from typing import Any

import panel as pn
import holoviews as hv

from nimbus.interpolate import interpolate, snapshot, Interpolator
from nimbus.transition import EasingArg, resolve_easing, _AnimConfig
from nimbus.defaults import defaults as _defaults


class TransitionPipe(hv.streams.Pipe):
    """
    A Pipe stream with built-in animated transitions.

    Parameters
    ----------
    data : dict
        Initial data, same as hv.streams.Pipe.
    duration_ms : int, optional
        Transition duration in ms. Defaults to nimbus.defaults.duration_ms at construction.
    easing : str or CubicSplineEasing or callable, optional
        Easing function. String names resolve to PRESETS.
        Defaults to nimbus.defaults.easing at construction.
    fps : int, optional
        Frames per second. Defaults to nimbus.defaults.fps at construction.
    on_interrupt : str, optional
        'from_current' | 'queue' | 'drop'.
        Defaults to nimbus.defaults.on_interrupt at construction.
    column_overrides : dict[str, Interpolator], optional
        Per-column interpolator overrides applied to every transition.
    """

    def __init__(
        self,
        data: dict[str, Any] | None = None,
        duration_ms: int | None = None,
        easing: EasingArg | None = None,
        fps: int | None = None,
        on_interrupt: str | None = None,
        column_overrides: dict[str, Interpolator] | None = None,
        **params,
    ):
        super().__init__(data=data, **params)

        self.duration_ms = (
            duration_ms if duration_ms is not None else _defaults.duration_ms
        )
        self.easing = easing if easing is not None else _defaults.easing
        self.fps = fps if fps is not None else _defaults.fps
        self.on_interrupt = (
            on_interrupt if on_interrupt is not None else _defaults.on_interrupt
        )
        self.column_overrides = column_overrides or {}

        self._current: dict[str, Any] = snapshot(data) if data else {}
        self._cb = None  # active PeriodicCallback
        self._queued = None  # (end_data, _AnimConfig) waiting to run

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send(
        self,
        data: dict[str, Any],
        duration_ms: int | None = None,
        easing: EasingArg | None = None,
        fps: int | None = None,
        on_interrupt: str | None = None,
    ) -> None:
        """
        Animate to new data.

        Any kwargs provided here override pipe-level params for this send only.
        """
        cfg = self._resolve_config(duration_ms, easing, fps, on_interrupt)

        if self._cb is not None:
            self._handle_interrupt(data, cfg)
            return

        self._start_animation(snapshot(self._current), snapshot(data), cfg)

    def send_raw(self, data: dict[str, Any]) -> None:
        """Send immediately with no animation, cancelling any in-flight transition."""
        self._stop_animation()
        self._current = snapshot(data)
        super().send(data)

    @property
    def in_flight(self) -> bool:
        """True if a transition is currently running."""
        return self._cb is not None

    # ------------------------------------------------------------------
    # Config resolution  (send kwargs > pipe params)
    # ------------------------------------------------------------------

    def _resolve_config(
        self,
        duration_ms: int | None,
        easing: EasingArg | None,
        fps: int | None,
        on_interrupt: str | None,
    ) -> _AnimConfig:
        """Merge per-send overrides with pipe-level params into an _AnimConfig."""
        fps = fps if fps is not None else self.fps
        return _AnimConfig(
            duration_ms=duration_ms if duration_ms is not None else self.duration_ms,
            easing=resolve_easing(easing if easing is not None else self.easing),
            frame_interval_ms=max(1, 1000 // fps),
            on_interrupt=on_interrupt
            if on_interrupt is not None
            else self.on_interrupt,
        )

    # ------------------------------------------------------------------
    # Animation loop
    # ------------------------------------------------------------------

    def _start_animation(
        self,
        start: dict[str, Any],
        end: dict[str, Any],
        cfg: _AnimConfig,
    ) -> None:
        """Start the periodic animation loop from start to end data."""
        self._anim_start = start
        self._anim_end = end
        self._anim_cfg = cfg
        self._anim_t0 = time.monotonic()

        self._cb = pn.state.add_periodic_callback(
            self._tick,
            period=cfg.frame_interval_ms,
        )

    def _tick(self) -> None:
        """Advance the animation by one frame; stops and chains any queued animation when done."""
        elapsed_ms = (time.monotonic() - self._anim_t0) * 1000.0
        raw_t = min(elapsed_ms / self._anim_cfg.duration_ms, 1.0)
        progress = self._anim_cfg.easing(raw_t)

        frame = interpolate(
            self._anim_start,
            self._anim_end,
            progress,
            self.column_overrides,
        )
        self._current = frame
        super().send(frame)

        if raw_t >= 1.0:
            self._stop_animation()
            if self._queued is not None:
                end, cfg = self._queued
                self._queued = None
                self._start_animation(snapshot(self._current), end, cfg)

    def _stop_animation(self) -> None:
        """Cancel the active periodic callback."""
        if self._cb is not None:
            try:
                self._cb.stop()
            except Exception:
                pass
            self._cb = None

    def _handle_interrupt(self, new_end: dict[str, Any], cfg: _AnimConfig) -> None:
        """Apply the on_interrupt policy when send() arrives during an active animation."""
        mode = cfg.on_interrupt
        if mode == "drop":
            return  # discard the incoming animation; let the current one finish
        if mode == "queue":
            self._queued = (snapshot(new_end), cfg)
            return
        # "from_current": restart from wherever the current animation left off
        self._stop_animation()
        self._start_animation(snapshot(self._current), snapshot(new_end), cfg)
