"""
curve_editor.py — Nimbus demo with interactive easing curve editor.

Run with:
    uv run panel serve examples/curve_editor.py --show
"""

import numpy as np
import holoviews as hv
import panel as pn

import nimbus
from nimbus import TransitionPipe
from nimbus.widgets import CurveEditor

hv.extension("bokeh")
pn.extension()

nimbus.defaults.duration_ms = 400
nimbus.defaults.easing      = "ease_in_out"
nimbus.defaults.fps         = 30

# ---------------------------------------------------------------------------
# Data generators
# ---------------------------------------------------------------------------

def sine_wave() -> dict:
    x = np.linspace(0, 2 * np.pi, 300)
    return {"x": x, "y": np.sin(x)}

def square_wave() -> dict:
    x = np.linspace(0, 2 * np.pi, 300)
    return {"x": x, "y": np.where((x % (2*np.pi)) < np.pi, 1.0, -1.0).astype(float)}

def sawtooth() -> dict:
    x = np.linspace(0, 2 * np.pi, 300)
    return {"x": x, "y": (x % (2*np.pi)) / np.pi - 1.0}

def noise() -> dict:
    x = np.linspace(0, 2 * np.pi, 300)
    return {"x": x, "y": np.random.uniform(-1, 1, 300)}

SHAPES = [sine_wave, square_wave, sawtooth, noise]

# ---------------------------------------------------------------------------
# TransitionPipe + DynamicMap
# ---------------------------------------------------------------------------

pipe = TransitionPipe(data=sine_wave())

dmap = hv.DynamicMap(
    lambda data: hv.Curve(data, kdims=["x"], vdims=["y"]).opts(
        width=620, height=360,
        line_width=2.5, color="#1f77b4",
        ylim=(-1.6, 1.6), toolbar=None, tools=[], default_tools=[],
    ),
    streams=[pipe],
)

# ---------------------------------------------------------------------------
# Controls
# ---------------------------------------------------------------------------

editor = CurveEditor(pipe)

send_btn = pn.widgets.Button(name="▶  Animate", button_type="success", width=150)

_current_shape = SHAPES[0]

def on_send(event):
    global _current_shape
    choices = [s for s in SHAPES if s is not _current_shape]
    _current_shape = np.random.choice(choices)
    pipe.send(_current_shape())

send_btn.param.watch(on_send, "clicks")

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

pn.Column(
    pn.Column(
        send_btn,
        pn.Spacer(height=8),
        pn.layout.Divider(),
        pn.panel(dmap),
        margin=(10, 20),
    ),
    pn.Column(
        editor.panel,
        margin=(10, 20),
    ),
).servable()
