# nimbus

Smooth animated data transitions for HoloViews / Panel. Drop `TransitionPipe` in place of `hv.streams.Pipe` and your plots animate between states automatically.

## Installation

Install directly from GitHub using `pip` or `uv`:

```bash
# pip
pip install git+https://github.com/lnk2past/nimbus.git

# uv
uv add git+https://github.com/lnk2past/nimbus.git
```

## Requirements

nimbus requires an active event loop and is not compatible with static HTML exports. Two deployment modes are supported:

- **`panel serve`** — standard live server deployment.
- **`panel convert` (Pyodide/WASM)** — runs fully in the browser with no server required. Panel routes `add_periodic_callback` through the browser's asyncio loop automatically.

## Overview

nimbus provides `TransitionPipe`, a replacement for `hv.streams.Pipe` that interpolates between data states over a configurable duration using an easing function. Each call to `pipe.send(new_data)` triggers an animated transition rather than an instant jump.

Key concepts:

- **`TransitionPipe`** — the core stream; wraps a HoloViews `DynamicMap` and drives frame-by-frame interpolation via Panel's periodic callback.
- **Easing** — controls the acceleration curve of a transition. Built-in presets include `linear`, `ease_in_out`, `elastic_out`, `bounce_out`, and more. Custom curves can be defined with `CubicSplineEasing`.
- **`defaults`** — a global config object (`nimbus.defaults`) for setting `duration_ms`, `easing`, `fps`, and `on_interrupt` once, affecting all pipes.
- **Interrupt policies** — when `send()` arrives during an active transition, behavior is controlled by `on_interrupt`: `"from_current"` (default), `"queue"`, or `"drop"`.

## Usage

### Minimal

```python
import numpy as np
import holoviews as hv
import nimbus
from nimbus import TransitionPipe

hv.extension("bokeh")

x = np.linspace(0, 2 * np.pi, 300)

pipe = TransitionPipe(data={"x": x, "y": np.sin(x)})
dmap = hv.DynamicMap(lambda data: hv.Curve(data), streams=[pipe])

# Animate to new data
pipe.send({"x": x, "y": np.cos(x)})
```

### Global defaults

```python
import nimbus

nimbus.defaults.duration_ms = 600
nimbus.defaults.easing = "elastic_out"
nimbus.defaults.fps = 60
nimbus.defaults.on_interrupt = "queue"
```

### Per-pipe and per-send overrides

```python
# Override at construction
pipe = TransitionPipe(data=..., duration_ms=400, easing="ease_in_out")

# Override for a single send (highest priority)
pipe.send(new_data, duration_ms=200, easing="bounce_out")
```

### Custom easing

```python
from nimbus import CubicSplineEasing

my_easing = CubicSplineEasing([(0.3, 0.0), (0.7, 1.2)])
pipe.send(new_data, easing=my_easing)
```

### Running the demo

```bash
uv run panel serve examples/app.py --show
```

## AI Disclaimer

This project used AI to provide the initial implementation, and will use it to aid in development. With that said, everything is reviewed extensively by a human!

## (Un)license

See [./UNLICENSE](./UNLICENSE)
