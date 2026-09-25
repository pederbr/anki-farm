"""Build the JSON the web UI renders from."""

from __future__ import annotations

from typing import Any

from .catalog import (
    ALMANAC_ORDER,
    MATURE_IVL,
    MATURE_RARITY_BOOST,
    MAX_TIER,
    PACKET_GUARANTEED_RARITY,
    PACKET_MIN_REVIEWS,
    PACKET_SIZE,
    PACKETS_PER_DAY,
    RARITIES,
    SPECIES,
    TIER_NAMES,
)
from .state import CATCH_UP_DAYS, FarmState


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
        # numbers quoted by the How to play panel, so it never goes stale
        "rules": {
            "dropWeights": {k: w for k, (_name, w) in RARITIES.items()},
            "matureIvl": MATURE_IVL,
            "matureBoost": MATURE_RARITY_BOOST,
            "packetSize": PACKET_SIZE,
            "packetRarity": RARITIES[PACKET_GUARANTEED_RARITY][0],
            "packetMinReviews": PACKET_MIN_REVIEWS,
            "packetsPerDay": PACKETS_PER_DAY,
            "catchUpDays": CATCH_UP_DAYS,
        },
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
