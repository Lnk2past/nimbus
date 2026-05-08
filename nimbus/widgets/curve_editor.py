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

from __future__ import annotations

import numpy as np
import panel as pn
import param

from bokeh.models import ColumnDataSource, CustomJS
from bokeh.plotting import figure
from bokeh.events import Press, PressUp, MouseMove, DoubleTap

from nimbus.transition import CubicSplineEasing, Easing, PRESETS
from nimbus.defaults import defaults as _defaults


_SIZE      = 360
_N_SAMPLES = 256
_HIT_R     = 0.045

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
    on_interrupt = param.ObjectSelector(default="from_current", objects=["from_current", "queue", "drop"])

    def __init__(self, pipe=None, **params):
        # Seed from pipe if provided, else from global defaults
        source = pipe if pipe is not None else _defaults
        params.setdefault("duration_ms",  getattr(source, "duration_ms",  _defaults.duration_ms))
        params.setdefault("fps",          getattr(source, "fps",          _defaults.fps))
        params.setdefault("on_interrupt", getattr(source, "on_interrupt", _defaults.on_interrupt))
        super().__init__(**params)

        self._pipe = pipe
        self._spline: CubicSplineEasing = self._initial_spline(pipe)

        self._src_curve  = ColumnDataSource({"x": [], "y": []})
        self._src_points = ColumnDataSource({"x": [], "y": [], "color": []})
        self._src_scrub  = ColumnDataSource({"x": [0.5], "y": [0.5]})
        self._src_cross  = ColumnDataSource({"hx": [0., .5], "hy": [.5, .5],
                                              "vx": [.5, .5], "vy": [0., .5]})
        self._src_events = ColumnDataSource({"xs": [[0.]], "ys": [[0.]]})
        self._src_events.on_change("data", self._on_js_event)

        self._fig   = self._build_figure()
        self._panel = self._build_panel()

        self._refresh()
        # Watch own params → push to pipe
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
        self._refresh()
        self._push_to_pipe()

    # ------------------------------------------------------------------
    # Pipe sync
    # ------------------------------------------------------------------

    def _initial_spline(self, pipe) -> CubicSplineEasing:
        if pipe is not None:
            easing = getattr(pipe, "easing", None)
            if isinstance(easing, CubicSplineEasing):
                return easing
        return Easing.ease_in_out

    def _push_to_pipe(self, *_) -> None:
        """Write current editor state to the linked pipe (if any)."""
        if self._pipe is None:
            return
        self._pipe.easing       = self._spline
        self._pipe.duration_ms  = self.duration_ms
        self._pipe.fps          = self.fps
        self._pipe.on_interrupt = self.on_interrupt

    # ------------------------------------------------------------------
    # Figure
    # ------------------------------------------------------------------

    def _build_figure(self) -> figure:
        fig = figure(
            width=_SIZE, height=_SIZE,
            x_range=(-0.05, 1.05), y_range=(-0.35, 1.35),
            toolbar_location=None,
            title="Transition Curve",
            background_fill_color=_COL_BG,
            border_fill_color=_COL_BG,
        )
        fig.grid.grid_line_color = _COL_GRID
        fig.grid.grid_line_dash  = [4, 4]
        fig.xaxis.axis_label     = "t  (time)"
        fig.yaxis.axis_label     = "value"

        fig.quad(left=0, right=1, top=1.35, bottom=1.0,
                 fill_color="#f0f8ff", fill_alpha=0.4, line_color=None)
        fig.quad(left=0, right=1, top=0.0,  bottom=-0.35,
                 fill_color="#fff0f0", fill_alpha=0.4, line_color=None)
        fig.line([0, 1], [0, 1], color=_COL_GRID, line_dash=[6, 3], line_width=1.5)

        fig.line("hx", "hy", source=self._src_cross,
                 color=_COL_SCRUB, line_dash=[3, 3], alpha=0.6, line_width=1)
        fig.line("vx", "vy", source=self._src_cross,
                 color=_COL_SCRUB, line_dash=[3, 3], alpha=0.6, line_width=1)

        fig.line("x", "y",   source=self._src_curve,
                 color=_COL_CURVE, line_width=2.5)
        fig.scatter("x", "y", source=self._src_points, size=11,
                    color="color", line_color="white", line_width=1.5)
        fig.scatter("x", "y", source=self._src_scrub,  size=13,
                    color=_COL_SCRUB, line_color="white", line_width=2)

        self._attach_js(fig)
        return fig

    def _attach_js(self, fig: figure) -> None:
        pts    = self._src_points
        events = self._src_events
        drag   = ColumnDataSource({"on": [False], "idx": [-1]})

        press_cb = CustomJS(args=dict(pts=pts, drag=drag, ev=events, hit_r=_HIT_R), code="""
            const x = cb_obj.x, y = cb_obj.y;
            const xs = pts.data['x'], ys = pts.data['y'];
            let hit = -1;
            for (let i = 0; i < xs.length; i++) {
                const dx = xs[i]-x, dy = ys[i]-y;
                if (Math.sqrt(dx*dx+dy*dy) < hit_r) { hit = i; break; }
            }
            if (hit >= 0) {
                drag.data = {on:[true], idx:[hit]};
            } else {
                drag.data = {on:[false], idx:[-1]};
                const nx = [...xs, x], ny = [...ys, y];
                pts.data = {x:nx, y:ny, color:[...pts.data['color'], '#E8834C']};
                ev.data  = {xs:[nx], ys:[ny]};
            }
            drag.change.emit();
        """)

        move_cb = CustomJS(args=dict(pts=pts, drag=drag, ev=events), code="""
            if (!drag.data['on'][0]) return;
            const idx = drag.data['idx'][0];
            const xs = [...pts.data['x']], ys = [...pts.data['y']];
            const n = xs.length;
            if (idx === 0)     { xs[0]   = 0; ys[0]   = Math.max(-0.3, Math.min(1.3, cb_obj.y)); }
            else if (idx===n-1){ xs[n-1] = 1; ys[n-1] = Math.max(-0.3, Math.min(1.3, cb_obj.y)); }
            else {
                xs[idx] = Math.max(xs[idx-1]+0.01, Math.min(xs[idx+1]-0.01, cb_obj.x));
                ys[idx] = Math.max(-0.3, Math.min(1.3, cb_obj.y));
            }
            pts.data = {x:xs, y:ys, color:pts.data['color']};
            ev.data  = {xs:[xs], ys:[ys]};
        """)

        pressup_cb = CustomJS(args=dict(drag=drag), code="""
            drag.data = {on:[false], idx:[-1]};
        """)

        dblclick_cb = CustomJS(args=dict(pts=pts, drag=drag, ev=events, hit_r=_HIT_R), code="""
            const x = cb_obj.x, y = cb_obj.y;
            const xs = pts.data['x'], ys = pts.data['y'];
            for (let i = 0; i < xs.length; i++) {
                const dx = xs[i]-x, dy = ys[i]-y;
                if (Math.sqrt(dx*dx+dy*dy) < hit_r) {
                    if (i === 0 || i === xs.length-1) return;
                    pts.data = {
                        x:     xs.filter((_,j) => j!==i),
                        y:     ys.filter((_,j) => j!==i),
                        color: pts.data['color'].filter((_,j) => j!==i),
                    };
                    ev.data = {xs:[pts.data['x']], ys:[pts.data['y']]};
                    return;
                }
            }
        """)

        fig.js_on_event(Press,     press_cb)
        fig.js_on_event(MouseMove, move_cb)
        fig.js_on_event(PressUp,   pressup_cb)
        fig.js_on_event(DoubleTap, dblclick_cb)

    def _on_js_event(self, attr, old, new) -> None:
        xs  = list(new["xs"][0])
        ys  = list(new["ys"][0])
        pts = sorted(zip(xs, ys), key=lambda p: p[0])
        if not pts:
            pts = [(0.0, 0.0), (1.0, 1.0)]
        pts[0]  = (0.0, pts[0][1])
        pts[-1] = (1.0, pts[-1][1])
        self._spline = CubicSplineEasing(pts)
        self._refresh_curve()
        self._push_to_pipe()

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def _refresh(self) -> None:
        self._refresh_curve()
        pts = self._spline.points
        self._src_points.data = {
            "x":     [p[0] for p in pts],
            "y":     [p[1] for p in pts],
            "color": [_COL_ANCHOR if p[0] in (0.0, 1.0) else _COL_POINT for p in pts],
        }

    def _refresh_curve(self) -> None:
        ts, ys = self._spline.sample(_N_SAMPLES)
        self._src_curve.data = {"x": ts.tolist(), "y": ys.tolist()}

    def _update_scrubber(self, t: float) -> None:
        v = self._spline(t)
        self._src_scrub.data = {"x": [t], "y": [v]}
        self._src_cross.data = {
            "hx": [0.0, t], "hy": [v, v],
            "vx": [t, t],   "vy": [0.0, v],
        }

    # ------------------------------------------------------------------
    # Panel layout
    # ------------------------------------------------------------------

    def _build_panel(self) -> pn.viewable.Viewable:
        preset_btns = pn.FlexBox(
            *[
                pn.widgets.Button(name=name, button_type="light", width=100, height=26)
                for name in PRESETS
            ],
            flex_wrap="wrap", gap="4px",
        )
        for btn in preset_btns:
            btn.on_click(lambda e, n=btn.name: self.set_preset(n))

        scrubber = pn.widgets.FloatSlider(
            name="Preview t", start=0.0, end=1.0, step=0.01, value=0.5, width=340,
        )
        scrubber.param.watch(lambda e: self._update_scrubber(e.new), "value")
        self._update_scrubber(0.5)

        dur = pn.widgets.IntSlider.from_param(self.param.duration_ms, width=340)
        fps = pn.widgets.IntSlider.from_param(self.param.fps,         width=340)
        interrupt = pn.widgets.Select.from_param(self.param.on_interrupt, width=200)

        return pn.Column(
            pn.pane.Markdown("### Transition Curve"),
            pn.pane.Markdown(
                "_Press+drag to move · Tap to add · Double-tap to remove_",
                styles={"color": "#888", "font-size": "12px"},
            ),
            pn.pane.Bokeh(self._fig),
            pn.pane.Markdown("**Presets**"),
            preset_btns,
            pn.layout.Divider(),
            scrubber,
            pn.layout.Divider(),
            dur, fps, interrupt,
            width=400,
        )
