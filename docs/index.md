# nimbus

Smooth animated data transitions for HoloViews / Panel. Drop `TransitionPipe` in place of `hv.streams.Pipe` and your plots animate between states automatically.

!!! info "Deployment modes"
    nimbus works with `panel serve` (live server) and `panel convert` (Pyodide/WASM — runs fully in the browser, no server required). Static HTML exports are not supported.

## Quick start

```python
import numpy as np
import holoviews as hv
from nimbus import TransitionPipe

hv.extension("bokeh")

x = np.linspace(0, 2 * np.pi, 300)

pipe = TransitionPipe(data={"x": x, "y": np.sin(x)})
dmap = hv.DynamicMap(lambda data: hv.Curve(data), streams=[pipe])

# Animate to new data
pipe.send({"x": x, "y": np.cos(x)})
```

---

[Installation](installation.md) | [Usage guide](usage.md) | [API reference](api/pipe.md)
