"""User settings shown in the farm's Settings panel.

They live in the add-on config (per device, not synced). The panel can only
change keys listed here, and values are coerced/clamped before saving.
"""

from __future__ import annotations

from typing import Any

# key -> (default, kind, extra)
SETTINGS: dict[str, tuple[Any, str, dict[str, float]]] = {
    "auto_plant": (False, "bool", {}),
    "sound": (True, "bool", {}),
    "show_tooltips": (True, "bool", {}),
    "show_almanac_on_deck_list": (True, "bool", {}),
    "min_answer_seconds": (1.5, "number", {"min": 0.0, "max": 10.0}),
}


def current(conf: dict[str, Any]) -> dict[str, Any]:
    """Every setting with its current value (defaults filled in)."""
    return {key: clean(key, conf.get(key, default)) for key, (default, _k, _x) in SETTINGS.items()}


def clean(key: str, value: Any) -> Any:
    """Validate one setting. Raises ValueError for unknown keys or bad values."""
    if key not in SETTINGS:
        raise ValueError(f"unknown setting {key!r}")
    default, kind, extra = SETTINGS[key]
    if kind == "bool":
        if not isinstance(value, bool):
            raise ValueError(f"{key} must be true or false")
        return value
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{key} must be a number") from None
    if number != number:  # NaN
        raise ValueError(f"{key} must be a number")
    return round(min(max(number, extra["min"]), extra["max"]), 1)
