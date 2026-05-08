"""
interpolate.py
--------------
Interpolates between two data dicts at a given progress value.
progress ∈ ℝ — may exceed [0, 1] when the easing curve overshoots.
"""

from __future__ import annotations

from typing import Any, Callable

import numpy as np


Interpolator = Callable[[Any, Any, float], Any]


def _lerp_float(s, e, p):
    s, e = np.asarray(s, dtype=float), np.asarray(e, dtype=float)
    return s + (e - s) * p

def _lerp_int(s, e, p):
    return np.round(_lerp_float(s, e, p)).astype(np.asarray(s).dtype)

def _lerp_color(s, e, p):
    def to_rgb(arr):
        out = np.zeros((len(arr), 3), dtype=float)
        for i, c in enumerate(arr):
            c = str(c).lstrip("#")
            out[i] = [int(c[j:j+2], 16) for j in (0, 2, 4)]
        return out
    try:
        rs, re = to_rgb(s), to_rgb(e)
        if rs.shape != re.shape:
            return e if p >= 0.5 else s
        mixed = np.clip(np.round(rs + (re - rs) * p), 0, 255).astype(int)
        return [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in mixed]
    except Exception:
        return e if p >= 0.5 else s

def _snap(s, e, p):
    return e if p >= 0.5 else s

def _pick(col) -> Interpolator:
    arr = col if isinstance(col, np.ndarray) else np.asarray(col)
    if arr.dtype.kind in ("f", "c"):   return _lerp_float
    if arr.dtype.kind in ("i", "u"):   return _lerp_int
    if arr.dtype.kind in ("U", "O"):
        sample = arr.flat[0] if arr.size > 0 else ""
        if isinstance(sample, str) and sample.startswith("#") and len(sample) in (7, 9):
            return _lerp_color
    return _snap


def interpolate(
    start:     dict[str, Any],
    end:       dict[str, Any],
    progress:  float,
    overrides: dict[str, Interpolator] | None = None,
) -> dict[str, Any]:
    """
    Interpolate between two data dicts at the given progress value.

    Parameters
    ----------
    start, end : data dicts (same structure as hv.streams.Pipe data)
    progress   : easing output — 0 = start, 1 = end, may overshoot
    overrides  : per-key interpolator overrides
    """
    overrides = overrides or {}
    result: dict[str, Any] = {}

    for key in set(start) | set(end):
        if key not in start:
            result[key] = end[key] if progress >= 0.5 else np.zeros_like(np.asarray(end[key]))
            continue
        if key not in end:
            result[key] = np.zeros_like(np.asarray(start[key])) if progress >= 0.5 else start[key]
            continue

        s, e = start[key], end[key]
        if np.asarray(s).shape != np.asarray(e).shape:
            result[key] = _snap(s, e, progress)
            continue

        fn = overrides.get(key) or _pick(e)
        result[key] = fn(s, e, progress)

    return result


def snapshot(data: dict[str, Any]) -> dict[str, np.ndarray]:
    """Deep-copy a data dict into plain numpy arrays."""
    return {k: np.array(v) for k, v in data.items()}
