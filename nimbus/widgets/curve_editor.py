"""
widgets/curve_editor.py
-----------------------
Interactive spline easing curve editor.

Can be used standalone or linked directly to a TransitionPipe:

    pipe   = TransitionPipe(data=...)
    editor = CurveEditor(pipe)          # changes apply to pipe immediately

Or standalone, reading the transition manually:

    editor = CurveEditor()
    pipe.send(data, easing=editor.spline, duration_ms=editor.duration_ms)
"""

import panel as pn
import param
import holoviews as hv

from nimbus.transition import CubicSplineEasing, Easing, PRESETS
from nimbus.defaults import defaults as _defaults


_SIZE = 360
_N_SAMPLES = 256

_COL_CURVE  = "#4C9BE8"
_COL_POINT  = "#E8834C"
_COL_ANCHOR = "#888888"
_COL_SCRUB  = "#E84C4C"
_COL_GRID   = "#DDDDDD"
_COL_BG     = "#fafafa"


class CurveEditor(param.Parameterized):
    """
    Interactive easing curve editor.

    Parameters
    ----------
    pipe : TransitionPipe, optional
        If provided, the editor writes its settings directly to the pipe
        whenever the curve or sliders change.
    duration_ms : int, optional
    fps : int, optional
    on_interrupt : str, optional
    """

    duration_ms  = param.Integer(default=300, bounds=(50, 5000), step=50)
    fps          = param.Integer(default=60, bounds=(10, 120), step=5)
    on_interrupt = param.ObjectSelector(
        default="from_current", objects=["from_current", "queue", "drop"]
    )
    preview_t = param.Number(default=0.5, bounds=(0.0, 1.0), step=0.01)

    def __init__(self, pipe=None, **params):
        source = pipe if pipe is not None else _defaults
        params.setdefault("duration_ms", source.duration_ms)
        params.setdefault("fps", source.fps)
        params.setdefault("on_interrupt", source.on_interrupt)
        super().__init__(**params)

        self._pipe = pipe
        easing = pipe.easing if pipe is not None else None
        self._spline: CubicSplineEasing = (
            easing if isinstance(easing, CubicSplineEasing) else Easing.ease_in_out
        )

        interior = self._interior_data()
        self._draw_pts = hv.Points(interior, kdims=["x", "y"]).opts(
            color=_COL_POINT, size=11, line_color="white", line_width=1.5,
        )
        self._point_stream = hv.streams.PointDraw(
            source=self._draw_pts, data=interior, drag=True
        )
        self._point_stream.add_subscriber(self._on_points_changed)

        self._panel = self._build_panel()
        self.param.watch(self._push_to_pipe, ["duration_ms", "fps", "on_interrupt"])

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    @property
    def panel(self) -> pn.viewable.Viewable:
        return self._panel

    @property
    def spline(self) -> CubicSplineEasing:
        return self._spline

    def set_preset(self, name: str) -> None:
        if name not in PRESETS:
            raise KeyError(f"Unknown preset {name!r}. Options: {list(PRESETS)}")
        self._spline = PRESETS[name]
        self._point_stream.event(data=self._interior_data())

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _interior_data(self) -> dict:
        pts = self._spline.points
        interior = [p for p in pts if p[0] not in (0.0, 1.0)]
        return {"x": [p[0] for p in interior], "y": [p[1] for p in interior]}

    # ------------------------------------------------------------------
    # Pipe sync
    # ------------------------------------------------------------------

    def _push_to_pipe(self, *_) -> None:
        if self._pipe is None:
            return
        self._pipe.easing       = self._spline
        self._pipe.duration_ms  = self.duration_ms
        self._pipe.fps          = self.fps
        self._pipe.on_interrupt = self.on_interrupt

    # ------------------------------------------------------------------
    # Stream callbacks
    # ------------------------------------------------------------------

    def _on_points_changed(self, **kwargs) -> None:
        data = self._point_stream.data
        xs   = list(data.get("x", []))
        ys   = list(data.get("y", []))
        pts  = sorted(zip(xs, ys), key=lambda p: p[0])
        self._spline = CubicSplineEasing(pts)
        self._push_to_pipe()

    def _make_curve(self, data=None) -> hv.Curve:
        ts, ys = self._spline.sample(_N_SAMPLES)
        return hv.Curve({"x": ts.tolist(), "y": ys.tolist()}).opts(
            color=_COL_CURVE, line_width=2.5
        )

    def _make_scrubber(self, data=None, preview_t=0.5) -> hv.Overlay:
        v = float(self._spline(preview_t))
        crosshair = hv.Segments(
            [(0.0, v, preview_t, v), (preview_t, 0.0, preview_t, v)]
        ).opts(color=_COL_SCRUB, line_dash="dashed", alpha=0.6, line_width=1)
        dot = hv.Points({"x": [preview_t], "y": [v]}).opts(
            color=_COL_SCRUB, size=13, line_color="white", line_width=2
        )
        return crosshair * dot

    # ------------------------------------------------------------------
    # Plot
    # ------------------------------------------------------------------

    def _build_plot(self) -> hv.Overlay:
        overshoot_bg  = hv.HSpan(1.0, 1.35).opts(color="#f0f8ff", alpha=0.4, line_color=None)
        undershoot_bg = hv.HSpan(-0.35, 0.0).opts(color="#fff0f0", alpha=0.4, line_color=None)
        diagonal = hv.Curve([(0, 0), (1, 1)]).opts(
            color=_COL_GRID, line_dash="dashed", line_width=1.5
        )
        anchors = hv.Points({"x": [0.0, 1.0], "y": [0.0, 1.0]}).opts(
            color=_COL_ANCHOR, size=11, line_color="white", line_width=1.5
        )

        curve_dmap = hv.DynamicMap(self._make_curve, streams=[self._point_stream])

        params_stream = hv.streams.Params(self, ["preview_t"])
        scrubber_dmap = hv.DynamicMap(
            self._make_scrubber, streams=[self._point_stream, params_stream]
        )

        return (
            overshoot_bg * undershoot_bg * diagonal
            * curve_dmap * self._draw_pts * anchors
            * scrubber_dmap
        ).opts(
            hv.opts.Overlay(
                width=_SIZE,
                height=_SIZE,
                xlim=(-0.05, 1.05),
                ylim=(-0.35, 1.35),
                show_grid=True,
                shared_axes=False,
                xlabel="t  (time)",
                ylabel="value",
                title="Transition Curve",
                bgcolor=_COL_BG,
            )
        )

    # ------------------------------------------------------------------
    # Panel layout
    # ------------------------------------------------------------------

    def _build_panel(self) -> pn.viewable.Viewable:
        buttons: list[pn.widgets.Button] = [
            pn.widgets.Button(name=name, button_type="light", width=100, height=26)
            for name in PRESETS
        ]
        for btn in buttons:
            btn.on_click(lambda e, n=btn.name: self.set_preset(n))
        preset_btns = pn.FlexBox(*buttons, flex_wrap="wrap", gap="4px")

        scrubber  = pn.widgets.FloatSlider.from_param(self.param.preview_t, width=340)
        dur       = pn.widgets.IntSlider.from_param(self.param.duration_ms, width=340)
        fps       = pn.widgets.IntSlider.from_param(self.param.fps, width=340)
        interrupt = pn.widgets.Select.from_param(self.param.on_interrupt, width=200)

        return pn.Column(
            pn.pane.Markdown("### Transition Curve"),
            pn.pane.Markdown(
                "_Drag to move · Click to add · Backspace to remove_",
                styles={"color": "#888", "font-size": "12px"},
            ),
            pn.panel(self._build_plot()),
            pn.pane.Markdown("**Presets**"),
            preset_btns,
            pn.layout.Divider(),
            scrubber,
            pn.layout.Divider(),
            dur,
            fps,
            interrupt,
            width=400,
        )
