# Usage

## Minimal setup

```python
import numpy as np
import holoviews as hv
from nimbus import TransitionPipe

hv.extension("bokeh")

x = np.linspace(0, 2 * np.pi, 300)

pipe = TransitionPipe(data={"x": x, "y": np.sin(x)})
dmap = hv.DynamicMap(lambda data: hv.Curve(data), streams=[pipe])

pipe.send({"x": x, "y": np.cos(x)})
```

## Global defaults

Set defaults once before constructing any pipes; all pipes pick them up at construction time.

```python
import nimbus

nimbus.defaults.duration_ms = 600     # ms
nimbus.defaults.easing = "elastic_out"
nimbus.defaults.fps = 60
nimbus.defaults.on_interrupt = "queue"
```

## Per-pipe configuration

Override defaults for a specific pipe at construction:

```python
from nimbus import TransitionPipe

pipe = TransitionPipe(
    data={"x": x, "y": y},
    duration_ms=400,
    easing="ease_in_out",
    fps=30,
    on_interrupt="from_current",
)
```

## Per-send overrides

Override for a single transition (highest priority — beats pipe params and global defaults):

```python
pipe.send(new_data, duration_ms=200, easing="bounce_out")
```

## Easing presets

Built-in named presets usable as strings:

| Name | Description |
|------|-------------|
| `linear` | Constant speed |
| `ease_in` | Accelerates |
| `ease_out` | Decelerates |
| `ease_in_out` | Accelerates then decelerates |
| `ease_out_in` | Decelerates then accelerates |
| `overshoot` | Overshoots slightly before settling |
| `anticipate` | Pulls back before moving forward |
| `elastic_out` | Spring-like oscillation at the end |
| `bounce_out` | Bounces at the end |

## Custom easing

Define your own curve with `CubicSplineEasing`. Control points are `(time, value)` pairs in `[0, 1]`; the anchors `(0, 0)` and `(1, 1)` are always enforced.

```python
from nimbus import CubicSplineEasing

my_easing = CubicSplineEasing([(0.3, 0.0), (0.7, 1.2)])
pipe.send(new_data, easing=my_easing)
```

## Interrupt policies

When `send()` is called while a transition is already running, `on_interrupt` controls what happens:

| Value | Behaviour |
|-------|-----------|
| `"from_current"` | Cancel current transition and start the new one from the current frame (default) |
| `"queue"` | Finish the current transition, then run the new one |
| `"drop"` | Discard the incoming call; let the current transition finish |

## Skipping animation

Use `send_raw()` to update data instantly with no transition:

```python
pipe.send_raw(new_data)
```

## Running the demo

```bash
# Live server
uv run panel serve examples/app.py --show

# Static Pyodide build (no server required at runtime)
uv build
uv run panel convert examples/app.py \
  --to pyodide \
  --out ./dist-web/ \
  --requirements dist/nimbus-0.1.0-py3-none-any.whl holoviews param
python -m http.server 8765 --directory dist-web/
```
