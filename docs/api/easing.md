# Easing

## CubicSplineEasing

::: nimbus.transition.CubicSplineEasing

## Presets

`nimbus.PRESETS` is a `dict[str, CubicSplineEasing]` of all named presets.
`nimbus.Easing` mirrors these as attributes for tab-completion convenience (e.g. `Easing.elastic_out`).

| Name | Description |
|---|---|
| `linear` | Constant speed |
| `ease_in` | Accelerates |
| `ease_out` | Decelerates |
| `ease_in_out` | Accelerates then decelerates |
| `ease_out_in` | Decelerates then accelerates |
| `overshoot` | Overshoots slightly before settling |
| `anticipate` | Pulls back before moving forward |
| `elastic_out` | Spring-like oscillation at the end |
| `bounce_out` | Bounces at the end |

::: nimbus.transition.resolve_easing
