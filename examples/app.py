"""
app.py — Nimbus demo dashboard.

Run with:
    uv run panel serve app.py --show
    uv run panel serve app.py --allow-websocket-origin=*
"""

import numpy as np
import holoviews as hv
import panel as pn

import nimbus
from nimbus import TransitionPipe
from nimbus.widgets import CurveEditor

hv.extension("bokeh")
pn.extension()

# ---------------------------------------------------------------------------
# Optional: set global defaults once, affects all TransitionPipes
# ---------------------------------------------------------------------------

nimbus.defaults.duration_ms = 400
nimbus.defaults.easing      = "ease_in_out"

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

SHAPES = {"Sine": sine_wave, "Square": square_wave, "Sawtooth": sawtooth, "Noise": noise}

# ---------------------------------------------------------------------------
# TransitionPipe + DynamicMap  — the whole integration in 4 lines
# ---------------------------------------------------------------------------

pipe = TransitionPipe(data=sine_wave())

dmap = hv.DynamicMap(
    lambda data: hv.Curve(data, kdims=["x"], vdims=["y"]).opts(
        width=620, height=360,
        line_width=2.5, color="#1f77b4",
        ylim=(-1.6, 1.6), toolbar=None,
    ),
    streams=[pipe],
)

# ---------------------------------------------------------------------------
# Curve editor — linked directly to the pipe
# ---------------------------------------------------------------------------

editor = CurveEditor(pipe)

# ---------------------------------------------------------------------------
# Controls
# ---------------------------------------------------------------------------

shape_selector = pn.widgets.RadioButtonGroup(
    options=list(SHAPES), value="Sine",
    button_type="primary", width=300,
)
send_btn = pn.widgets.Button(name="▶  Animate", button_type="success", width=150)
status   = pn.pane.Markdown("_Ready_", styles={"color": "#888", "font-size": "12px"})

def on_send(event):
    data = SHAPES[shape_selector.value]()
    pipe.send(data)
    status.object = f"_Animating → **{shape_selector.value}** ({pipe.duration_ms} ms)_"

send_btn.param.watch(on_send, "clicks")

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

sidebar = pn.Column(
    pn.pane.Markdown("## nimbus"),
    pn.pane.Markdown("Smooth animated transitions for HoloViews.",
                     styles={"color": "#666", "font-size": "13px"}),
    pn.layout.Divider(),
    pn.pane.Markdown("**Target shape**"),
    shape_selector,
    pn.Spacer(height=8),
    send_btn,
    status,
    pn.layout.Divider(),
    editor.panel,
    width=420, margin=(10, 20),
)

main = pn.Column(
    pn.pane.Markdown("### Live plot"),
    pn.panel(dmap),
    margin=(10, 20),
)

pn.Row(sidebar, main).servable()
