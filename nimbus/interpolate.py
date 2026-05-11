"""
interpolate.py
--------------
Interpolates between two data dicts at a given progress value.
progress ∈ ℝ — may exceed [0, 1] when the easing curve overshoots.
"""

from typing import Any, Callable

import numpy as np


Interpolator = Callable[[Any, Any, float], Any]


def interpolate(
    start: dict[str, Any],
    end: dict[str, Any],
    progress: float,
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

    for key in start.keys() | end.keys():
        if key not in start:
            result[key] = (
                end[key] if progress >= 0.5 else np.zeros_like(np.asarray(end[key]))
            )
            continue
        if key not in end:
            result[key] = (
                np.zeros_like(np.asarray(start[key])) if progress >= 0.5 else start[key]
            )
            continue

        s, e = start[key], end[key]
        s_arr, e_arr = np.asarray(s), np.asarray(e)

        if s_arr.shape != e_arr.shape:
            result[key] = e if progress >= 0.5 else s
            continue

        if key in overrides:
            result[key] = overrides[key](s, e, progress)
        elif np.issubdtype(s_arr.dtype, np.number):
            s_f, e_f = s_arr.astype(float), e_arr.astype(float)
            result[key] = s_f + (e_f - s_f) * progress
        else:
            result[key] = e if progress >= 0.5 else s

    return result


def snapshot(data: dict[str, Any]) -> dict[str, np.ndarray]:
    """Deep-copy a data dict into plain numpy arrays."""
    return {k: np.array(v) for k, v in data.items()}
