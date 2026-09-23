"""Build the JSON the web UI renders from."""

from __future__ import annotations

from typing import Any

from .catalog import ALMANAC_ORDER, MAX_TIER, RARITIES, SPECIES, TIER_NAMES
from .state import FarmState


def catalog_json() -> dict[str, Any]:
    return {
        "maxTier": MAX_TIER,
        "tierNames": TIER_NAMES,
        "rarities": {k: name for k, (name, _w) in RARITIES.items()},
        "species": {
            s.id: {"name": s.name, "rarity": s.rarity, "sheet": s.sheet_index}
            for s in SPECIES
        },
        "almanacOrder": [s.id for s in ALMANAC_ORDER],
    }


def state_json(state: FarmState) -> dict[str, Any]:
    return {
        "w": state.width,
        "h": state.height,
        "tiles": {k: p.to_list() for k, p in state.tiles.items()},
        "bag": dict(state.bag),
        "almanac": dict(state.almanac),
        "stats": dict(state.stats),
    }


def almanac_progress(state: FarmState) -> tuple[int, int]:
    """(tiers discovered, total tiers) across all species."""
    found = sum(min(t, MAX_TIER) for t in state.almanac.values())
    return found, len(SPECIES) * MAX_TIER
