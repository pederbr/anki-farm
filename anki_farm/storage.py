"""Load and save the farm in the collection config (syncs via AnkiWeb)."""

from __future__ import annotations

from typing import Any

from aqt import mw

from .game.state import FarmState

CONFIG_KEY = "anki_farm"


def load() -> FarmState:
    return FarmState.from_dict(mw.col.get_config(CONFIG_KEY, None))


def save(state: FarmState) -> None:
    mw.col.set_config(CONFIG_KEY, state.to_dict())


def addon_config() -> dict[str, Any]:
    """User preferences from config.json (per-device, not synced)."""
    return mw.addonManager.getConfig(__name__) or {}


def set_addon_config(key: str, value: Any) -> None:
    conf = addon_config()
    conf[key] = value
    mw.addonManager.writeConfig(__name__, conf)
