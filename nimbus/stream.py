"""
stream.py
---------
TransitionPipe: a drop-in replacement for hv.streams.Pipe with built-in
animated transitions.

Minimal usage — zero config required:

    pipe = TransitionPipe(data={"x": x, "y": y})
    dmap = hv.DynamicMap(make_curve, streams=[pipe])
    pipe.send(new_data)   # animated with global defaults

Override at the pipe level:

    pipe = TransitionPipe(data=..., duration_ms=600, easing="elastic_out")

Override per send:

    pipe.send(new_data, duration_ms=200, easing="bounce_out")

Change global defaults:

    import nimbus
    nimbus.defaults.duration_ms = 600
    nimbus.defaults.easing = "elastic_out"

Priority: send() kwargs  >  pipe params  >  nimbus.defaults
"""

import time
from typing import Any

import numpy as np
import panel as pn
import param
import holoviews as hv

from nimbus.interpolate import interpolate, snapshot, Interpolator
from nimbus.transition import EasingArg, resolve_easing, _AnimConfig
from nimbus.defaults import defaults as _defaults

_UNSET = object()   # sentinel for "user did not provide this param"


class TransitionPipe(hv.streams.Pipe):
    """
    A Pipe stream with built-in animated transitions.

    Parameters
    ----------
    data : dict
        Initial data, same as hv.streams.Pipe.
    duration_ms : int, optional
        Transition duration in ms. Falls back to nimbus.defaults.
    easing : str or CubicSplineEasing or callable, optional
        Easing function. String names resolve to PRESETS.
        Falls back to nimbus.defaults.
    fps : int, optional
        Frames per second. Falls back to nimbus.defaults.
    on_interrupt : str, optional
        'from_current' | 'queue' | 'drop'.
        Falls back to nimbus.defaults.
    column_overrides : dict[str, Interpolator], optional
        Per-column interpolator overrides applied to every transition.
    """

    def __init__(
        self,
        data:             dict[str, Any] | None = None,
        duration_ms:      int | None = None,
        easing:           EasingArg | None = None,
        fps:              int | None = None,
        on_interrupt:     str | None = None,
        column_overrides: dict[str, Interpolator] | None = None,
        **params,
    ):
        super().__init__(data=data, **params)

        # None means "inherit from defaults at send() time"
        self._duration_ms  = duration_ms
        self._easing       = easing
        self._fps          = fps
        self._on_interrupt = on_interrupt
        self.column_overrides = column_overrides or {}

        self._current: dict[str, Any] = snapshot(data) if data else {}
        self._cb      = None   # active PeriodicCallback
        self._queued  = None   # (end_data, _AnimConfig) waiting to run

    # ------------------------------------------------------------------
    # Param-style properties — read/write, fall back to defaults
    # ------------------------------------------------------------------

    @property
    def duration_ms(self) -> int:
        return self._duration_ms if self._duration_ms is not None else _defaults.duration_ms

    @duration_ms.setter
    def duration_ms(self, v: int) -> None:
        self._duration_ms = v

    @property
    def easing(self) -> EasingArg:
        return self._easing if self._easing is not None else _defaults.easing

    @easing.setter
    def easing(self, v: EasingArg) -> None:
        self._easing = v

    @property
    def fps(self) -> int:
        return self._fps if self._fps is not None else _defaults.fps

    @fps.setter
    def fps(self, v: int) -> None:
        self._fps = v

    @property
    def on_interrupt(self) -> str:
        return self._on_interrupt if self._on_interrupt is not None else _defaults.on_interrupt

    @on_interrupt.setter
    def on_interrupt(self, v: str) -> None:
        self._on_interrupt = v

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send(
        self,
        data:         dict[str, Any],
        duration_ms:  int | None = None,
        easing:       EasingArg | None = None,
        fps:          int | None = None,
        on_interrupt: str | None = None,
    ) -> None:
        """
        Animate to new data.

        Any kwargs provided here override pipe-level params for this
        send only. Omitted kwargs fall through to pipe params, then
        to nimbus.defaults.

        Parameters
        ----------
        data         : target data state
        duration_ms  : one-off duration override
        easing       : one-off easing override (string or callable)
        fps          : one-off fps override
        on_interrupt : one-off interrupt mode override
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
    # Config resolution  (send kwargs > pipe props > global defaults)
    # ------------------------------------------------------------------

    def _resolve_config(
        self,
        duration_ms:  int | None,
        easing:       EasingArg | None,
        fps:          int | None,
        on_interrupt: str | None,
    ) -> _AnimConfig:
        return _AnimConfig(
            duration_ms  = duration_ms  if duration_ms  is not None else self.duration_ms,
            easing       = resolve_easing(easing if easing is not None else self.easing),
            fps          = fps          if fps          is not None else self.fps,
            on_interrupt = on_interrupt if on_interrupt is not None else self.on_interrupt,
        )

    # ------------------------------------------------------------------
    # Animation loop
    # ------------------------------------------------------------------

    def _start_animation(
        self,
        start: dict[str, Any],
        end:   dict[str, Any],
        cfg:   _AnimConfig,
    ) -> None:
        self._anim_start = start
        self._anim_end   = end
        self._anim_cfg   = cfg
        self._anim_t0    = time.monotonic()

        self._cb = pn.state.add_periodic_callback(
            self._tick,
            period=cfg.frame_interval_ms,
        )

    def _tick(self) -> None:
        elapsed_ms = (time.monotonic() - self._anim_t0) * 1000.0
        raw_t      = min(elapsed_ms / self._anim_cfg.duration_ms, 1.0)
        progress   = self._anim_cfg.easing(raw_t)

        frame = interpolate(
            self._anim_start,
            self._anim_end,
            progress,
            self.column_overrides or None,
        )
        self._current = frame
        super().send(frame)

        if raw_t >= 1.0:
            self._stop_animation()
            if self._queued is not None:
                end, cfg     = self._queued
                self._queued = None
                self._start_animation(snapshot(self._current), end, cfg)

    def _stop_animation(self) -> None:
        if self._cb is not None:
            try:
                self._cb.stop()
            except Exception:
                pass
            self._cb = None

    def _handle_interrupt(self, new_end: dict[str, Any], cfg: _AnimConfig) -> None:
        mode = cfg.on_interrupt
        if mode in ("from_current", "drop"):
            self._stop_animation()
            self._start_animation(snapshot(self._current), snapshot(new_end), cfg)
        elif mode == "queue":
            self._queued = (snapshot(new_end), cfg)
