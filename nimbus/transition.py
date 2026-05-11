"""
transition.py
-------------
CubicSplineEasing — the easing primitive.
Easing / PRESETS  — named presets.

_AnimConfig is a lightweight internal config carrier used only
inside TransitionPipe._tick(). It is not part of the public API.
"""

from __future__ import annotations

import types
from dataclasses import dataclass
from typing import Callable

import numpy as np


EasingFn = Callable[[float], float]
EasingArg = str | EasingFn


class CubicSplineEasing:
    """
    C2-continuous natural cubic spline easing function.

    Control points are in (x, y) space where:
      x = normalised time   ∈ [0, 1]  (monotone, enforced)
      y = normalised output ∈ ℝ       (may overshoot freely)

    Anchors (0, 0) and (1, 1) are always enforced.
    """

    def __init__(self, points: list[tuple[float, float]]):
        seen = {x: y for x, y in points if 0.0 < x < 1.0}
        all_pts = [(0.0, 0.0), *sorted(seen.items()), (1.0, 1.0)]

        self._xs = np.array([p[0] for p in all_pts], dtype=float)
        self._ys = np.array([p[1] for p in all_pts], dtype=float)
        self._coeffs = _natural_cubic_coeffs(self._xs, self._ys)

    @property
    def points(self) -> list[tuple[float, float]]:
        return list(zip(self._xs.tolist(), self._ys.tolist()))

    def __call__(self, t: float) -> float:
        t = float(np.clip(t, 0.0, 1.0))
        idx = int(
            np.clip(
                np.searchsorted(self._xs, t, side="right") - 1, 0, len(self._coeffs) - 1
            )
        )
        h = t - self._xs[idx]
        a, b, c, d = self._coeffs[idx]
        return float(a + b * h + c * h**2 + d * h**3)

    def sample(self, n: int = 256) -> tuple[np.ndarray, np.ndarray]:
        ts = np.linspace(0.0, 1.0, n)
        return ts, np.vectorize(self)(ts)

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

    total = h[:-1] + h[1:]
    rhs = np.zeros(n, dtype=float)
    rhs[1:-1] = 3.0 * ((ys[2:] - ys[1:-1]) / h[1:] - (ys[1:-1] - ys[:-2]) / h[:-1])

    diag = np.full(n, 2.0, dtype=float)
    upper = np.zeros(n, dtype=float)
    lower = np.zeros(n, dtype=float)
    upper[1:-1] = h[1:] / total
    lower[1:-1] = h[:-1] / total
    diag[0] = diag[-1] = 1.0

    # Thomas algorithm — forward elimination
    for i in range(1, n):
        m = lower[i - 1] / diag[i - 1]
        diag[i] -= m * upper[i - 1]
        rhs[i] -= m * rhs[i - 1]

    # Backward substitution → second derivatives (sigma)
    sigma = np.zeros(n)
    sigma[-1] = rhs[-1] / diag[-1]
    for i in range(n - 2, -1, -1):
        sigma[i] = (rhs[i] - upper[i] * sigma[i + 1]) / diag[i]

    coeffs = np.zeros((n - 1, 4))
    coeffs[:, 0] = ys[:-1]
    coeffs[:, 1] = (ys[1:] - ys[:-1]) / h - h * (2 * sigma[:-1] + sigma[1:]) / 3.0
    coeffs[:, 2] = sigma[:-1]
    coeffs[:, 3] = (sigma[1:] - sigma[:-1]) / (3.0 * h)
    return coeffs


# ---------------------------------------------------------------------------
# Named presets — single source of truth; Easing mirrors these as attributes
# ---------------------------------------------------------------------------

PRESETS: dict[str, CubicSplineEasing] = {
    "linear": CubicSplineEasing([(0, 0), (1, 1)]),
    "ease_in": CubicSplineEasing([(0, 0), (0.42, 0.0), (1, 1)]),
    "ease_out": CubicSplineEasing([(0, 0), (0.58, 1.0), (1, 1)]),
    "ease_in_out": CubicSplineEasing([(0, 0), (0.42, 0.0), (0.58, 1.0), (1, 1)]),
    "ease_out_in": CubicSplineEasing([(0, 0), (0.42, 1.0), (0.58, 0.0), (1, 1)]),
    "overshoot": CubicSplineEasing([(0, 0), (0.5, 0.9), (0.75, 1.15), (1, 1)]),
    "anticipate": CubicSplineEasing([(0, 0), (0.2, -0.1), (0.6, 1.0), (1, 1)]),
    "elastic_out": CubicSplineEasing(
        [(0, 0), (0.2, 1.2), (0.4, 0.85), (0.6, 1.05), (0.8, 0.97), (1, 1)]
    ),
    "bounce_out": CubicSplineEasing(
        [
            (0, 0),
            (0.3, 0.6),
            (0.5, 1.0),
            (0.65, 0.8),
            (0.75, 1.0),
            (0.85, 0.93),
            (0.92, 1.0),
            (1, 1),
        ]
    ),
}

Easing = types.SimpleNamespace(**PRESETS)


def resolve_easing(easing: EasingArg) -> EasingFn:
    """Resolve a string preset name or callable to an EasingFn."""
    if isinstance(easing, str):
        if easing not in PRESETS:
            raise ValueError(
                f"Unknown easing preset {easing!r}. Options: {list(PRESETS)}"
            )
        return PRESETS[easing]
    if callable(easing):
        return easing
    raise TypeError(
        f"easing must be a string preset name or callable, got {type(easing)}"
    )


# ---------------------------------------------------------------------------
# Internal config carrier — not part of public API
# ---------------------------------------------------------------------------


@dataclass
class _AnimConfig:
    """Resolved animation config for one transition. Internal use only."""

    duration_ms: int
    easing: EasingFn
    frame_interval_ms: int
    on_interrupt: str
