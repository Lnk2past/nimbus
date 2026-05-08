"""
transition.py
-------------
CubicSplineEasing — the easing primitive.
Easing / PRESETS  — named presets.

Transition is kept as a lightweight internal config carrier used only
inside TransitionPipe._tick(). It is not part of the public API.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Union

import numpy as np


EasingFn = Callable[[float], float]
EasingArg = Union[str, "CubicSplineEasing", EasingFn]


class CubicSplineEasing:
    """
    C2-continuous natural cubic spline easing function.

    Control points are in (x, y) space where:
      x = normalised time   ∈ [0, 1]  (monotone, enforced)
      y = normalised output ∈ ℝ       (may overshoot freely)

    Anchors (0, 0) and (1, 1) are always enforced.
    """

    def __init__(self, points: list[tuple[float, float]]):
        interior = [(x, y) for x, y in points if 0.0 < x < 1.0]
        all_pts  = [(0.0, 0.0)] + sorted(interior, key=lambda p: p[0]) + [(1.0, 1.0)]
        seen: dict[float, float] = {}
        for x, y in all_pts:
            seen[x] = y
        pts = sorted(seen.items())

        self._xs     = np.array([p[0] for p in pts], dtype=float)
        self._ys     = np.array([p[1] for p in pts], dtype=float)
        self._coeffs = _natural_cubic_coeffs(self._xs, self._ys)

    @property
    def points(self) -> list[tuple[float, float]]:
        return list(zip(self._xs.tolist(), self._ys.tolist()))

    def __call__(self, t: float) -> float:
        t   = float(np.clip(t, 0.0, 1.0))
        idx = int(np.clip(np.searchsorted(self._xs, t, side="right") - 1, 0, len(self._coeffs) - 1))
        h   = t - self._xs[idx]
        a, b, c, d = self._coeffs[idx]
        return float(a + b*h + c*h**2 + d*h**3)

    def sample(self, n: int = 256) -> tuple[np.ndarray, np.ndarray]:
        ts = np.linspace(0.0, 1.0, n)
        return ts, np.array([self(t) for t in ts])

    def with_points(self, points: list[tuple[float, float]]) -> CubicSplineEasing:
        return CubicSplineEasing(points)

    def with_point_added(self, x: float, y: float) -> CubicSplineEasing:
        return CubicSplineEasing(self.points + [(x, y)])

    def with_point_moved(self, index: int, x: float, y: float) -> CubicSplineEasing:
        pts = self.points
        if index in (0, len(pts) - 1):
            raise ValueError("Cannot move anchor points.")
        pts[index] = (x, y)
        return CubicSplineEasing(pts)

    def with_point_removed(self, index: int) -> CubicSplineEasing:
        pts = self.points
        if index in (0, len(pts) - 1):
            raise ValueError("Cannot remove anchor points.")
        pts.pop(index)
        return CubicSplineEasing(pts)

    def __repr__(self) -> str:
        return f"CubicSplineEasing(points={self.points})"


def _natural_cubic_coeffs(xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    n = len(xs)
    h = np.diff(xs)

    rhs = np.zeros(n)
    for i in range(1, n - 1):
        rhs[i] = 3.0 * ((ys[i+1] - ys[i]) / h[i] - (ys[i] - ys[i-1]) / h[i-1])

    diag  = np.ones(n) * 2.0
    upper = np.zeros(n)
    lower = np.zeros(n)
    for i in range(1, n - 1):
        upper[i] = h[i]   / (h[i-1] + h[i])
        lower[i] = h[i-1] / (h[i-1] + h[i])
    diag[0] = diag[-1] = 1.0
    lower[0] = upper[-1] = 0.0

    c, d, a, b = upper.copy().astype(float), rhs.copy().astype(float), \
                 lower.copy().astype(float), diag.copy().astype(float)
    for i in range(1, n):
        m    = a[i-1] / b[i-1]
        b[i] -= m * c[i-1]
        d[i] -= m * d[i-1]
    sigma     = np.zeros(n)
    sigma[-1] = d[-1] / b[-1]
    for i in range(n - 2, -1, -1):
        sigma[i] = (d[i] - c[i] * sigma[i+1]) / b[i]

    coeffs = np.zeros((n - 1, 4))
    for i in range(n - 1):
        hi          = h[i]
        coeffs[i,0] = ys[i]
        coeffs[i,1] = (ys[i+1] - ys[i]) / hi - hi * (2*sigma[i] + sigma[i+1]) / 3.0
        coeffs[i,2] = sigma[i]
        coeffs[i,3] = (sigma[i+1] - sigma[i]) / (3.0 * hi)
    return coeffs


# ---------------------------------------------------------------------------
# Named presets
# ---------------------------------------------------------------------------

class Easing:
    """Named preset easing curves."""
    linear      = CubicSplineEasing([(0,0), (1,1)])
    ease_in     = CubicSplineEasing([(0,0), (0.42, 0.0), (1,1)])
    ease_out    = CubicSplineEasing([(0,0), (0.58, 1.0), (1,1)])
    ease_in_out = CubicSplineEasing([(0,0), (0.42, 0.0), (0.58, 1.0), (1,1)])
    ease_out_in = CubicSplineEasing([(0,0), (0.42, 1.0), (0.58, 0.0), (1,1)])
    overshoot   = CubicSplineEasing([(0,0), (0.5, 0.9), (0.75, 1.15), (1,1)])
    anticipate  = CubicSplineEasing([(0,0), (0.2, -0.1), (0.6, 1.0), (1,1)])
    elastic_out = CubicSplineEasing([(0,0), (0.2,1.2), (0.4,0.85), (0.6,1.05), (0.8,0.97), (1,1)])
    bounce_out  = CubicSplineEasing([(0,0), (0.3,0.6), (0.5,1.0), (0.65,0.8), (0.75,1.0),
                                     (0.85,0.93), (0.92,1.0), (1,1)])


PRESETS: dict[str, CubicSplineEasing] = {
    "linear":      Easing.linear,
    "ease_in":     Easing.ease_in,
    "ease_out":    Easing.ease_out,
    "ease_in_out": Easing.ease_in_out,
    "ease_out_in": Easing.ease_out_in,
    "overshoot":   Easing.overshoot,
    "anticipate":  Easing.anticipate,
    "elastic_out": Easing.elastic_out,
    "bounce_out":  Easing.bounce_out,
}


def resolve_easing(easing: EasingArg) -> EasingFn:
    """Resolve a string preset name, CubicSplineEasing, or callable to an EasingFn."""
    if isinstance(easing, str):
        if easing not in PRESETS:
            raise ValueError(f"Unknown easing preset {easing!r}. Options: {list(PRESETS)}")
        return PRESETS[easing]
    if callable(easing):
        return easing
    raise TypeError(f"easing must be a string preset name or callable, got {type(easing)}")


# ---------------------------------------------------------------------------
# Internal config carrier — not part of public API
# ---------------------------------------------------------------------------

@dataclass
class _AnimConfig:
    """Resolved animation config for one transition. Internal use only."""
    duration_ms:  int
    easing:       EasingFn
    fps:          int
    on_interrupt: str

    @property
    def frame_interval_ms(self) -> int:
        return max(1, 1000 // self.fps)
