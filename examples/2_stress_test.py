"""
stress_test.py — Nimbus stress-test dashboard.

Animates multiple large-array curves simultaneously to probe
animation smoothness under load.

Run with:
    uv run panel serve examples/stress_test.py --show
"""

import numpy as np
import holoviews as hv
import panel as pn

import nimbus
from nimbus import TransitionPipe

hv.extension("bokeh")
pn.extension()

nimbus.defaults.duration_ms = 400
nimbus.defaults.easing      = "ease_in_out"
nimbus.defaults.fps         = 30

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

N_CURVES = 4
COLORS   = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]

# ---------------------------------------------------------------------------
# Data generators
# ---------------------------------------------------------------------------

def sine(x):     return np.sin(x)
def cosine(x):   return np.cos(x)
def sawtooth(x): return (x % (2 * np.pi)) / np.pi - 1.0
def square(x):   return np.where((x % (2 * np.pi)) < np.pi, 1.0, -1.0).astype(float)
def noise(x):    return np.random.uniform(-1, 1, len(x))
def chirp(x):    return np.sin(x ** 2 / (2 * np.pi))

SHAPES = [sine, cosine, sawtooth, square, noise, chirp]

def make_data(fn, n: int) -> dict:
    x = np.linspace(0, 2 * np.pi, n)
    return {"x": x, "y": fn(x)}

# ---------------------------------------------------------------------------
# Pipes + DynamicMaps
# ---------------------------------------------------------------------------

pipes = [TransitionPipe(data=make_data(SHAPES[i], 1_000)) for i in range(N_CURVES)]

def make_dmap(pipe, color):
    return hv.DynamicMap(
        lambda data: hv.Curve(data, kdims=["x"], vdims=["y"]).opts(
            width=300, height=200,
            line_width=1.5, color=color,
            ylim=(-1.6, 1.6), toolbar=None, tools=[], default_tools=[],
        ),
        streams=[pipe],
    )

dmaps = [make_dmap(p, COLORS[i]) for i, p in enumerate(pipes)]

# ---------------------------------------------------------------------------
# Controls
# ---------------------------------------------------------------------------

n_points_slider = pn.widgets.IntSlider(
    name="Points per curve", value=1_000, start=500, end=25_000, step=500,
)
animate_btn = pn.widgets.Button(name="▶  Animate All", button_type="success", width=150)
status      = pn.pane.Markdown("_Ready_", styles={"color": "#888", "font-size": "12px"})

def on_animate(event):
    n = n_points_slider.value
    for i, pipe in enumerate(pipes):
        target = SHAPES[(i + np.random.randint(1, len(SHAPES))) % len(SHAPES)]
        pipe.send(make_data(target, n))
    status.object = f"_Animating {N_CURVES} × {n:,} points_"

animate_btn.param.watch(on_animate, "clicks")

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

pn.Column(
    pn.pane.Markdown("**Points per curve**"),
    pn.Row(n_points_slider, animate_btn),
    pn.Spacer(height=8),
    status,
    pn.layout.Divider(),
    pn.GridBox(*[pn.panel(d) for d in dmaps], ncols=2),
    margin=(10, 20),
).servable()
