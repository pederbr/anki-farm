"""Farm state and its JSON (de)serialization.

The whole state is stored in the collection config, which syncs through
AnkiWeb and should stay small, so the representation is deliberately compact:
the seed bag is a count per species and tiles are keyed by "x,y".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .catalog import MAX_TIER, SPECIES_BY_ID

SCHEMA_VERSION = 1
START_SIZE = 5
# how many recent rewards we remember so an undo can take them back
RECENT_REWARDS_KEPT = 30
# how far back reviews synced from other devices (phones) are paid out
CATCH_UP_DAYS = 30


@dataclass
class Plant:
    species: str
    tier: int

    def to_list(self) -> list[Any]:
        return [self.species, self.tier]


@dataclass
class FarmState:
    width: int = START_SIZE
    height: int = START_SIZE
    tiles: dict[str, Plant] = field(default_factory=dict)
    bag: dict[str, int] = field(default_factory=dict)
    # species id -> highest tier ever reached
    almanac: dict[str, int] = field(default_factory=dict)
    stats: dict[str, int] = field(default_factory=dict)
    # [{"rid": revlog id, "species": str, "tile": "x,y" | None,
    #   "packet": deck id (only for seeds from a daily packet)}, ...]
    recent_rewards: list[dict[str, Any]] = field(default_factory=list)
    # {"day": scheduler day number, "decks": [deck ids that paid a packet]}
    daily: dict[str, Any] = field(default_factory=dict)
    # scheduler day -> number of reviews that have earned their seed. Used to
    # pay out reviews synced from phones, which the add-on never sees live.
    review_days: dict[int, int] = field(default_factory=dict)
    # reviews older than this revlog id (the add-on's install time) earn nothing
    start_rid: int | None = None

    # ---- helpers -------------------------------------------------------

    def in_bounds(self, key: str) -> bool:
        x, y = parse_key(key)
        return 0 <= x < self.width and 0 <= y < self.height

    def empty_tiles(self) -> list[str]:
        return [
            tile_key(x, y)
            for y in range(self.height)
            for x in range(self.width)
            if tile_key(x, y) not in self.tiles
        ]

    def bag_total(self) -> int:
        return sum(self.bag.values())

    def bump_stat(self, name: str, amount: int = 1) -> None:
        self.stats[name] = self.stats.get(name, 0) + amount

    def discover(self, species: str, tier: int) -> bool:
        """Record a tier in the almanac. Returns True if it is new."""
        if tier > self.almanac.get(species, 0):
            self.almanac[species] = tier
            return True
        return False

    # ---- serialization -------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "v": SCHEMA_VERSION,
            "w": self.width,
            "h": self.height,
            "tiles": {k: p.to_list() for k, p in self.tiles.items()},
            "bag": {k: n for k, n in self.bag.items() if n > 0},
            "almanac": dict(self.almanac),
            "stats": dict(self.stats),
            "recent": list(self.recent_rewards),
            "daily": dict(self.daily),
            "days": {str(d): n for d, n in self.review_days.items()},
            "start": self.start_rid,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> FarmState:
        if not data:
            return cls()
        data = migrate(data)
        state = cls(
            width=int(data.get("w", START_SIZE)),
            height=int(data.get("h", START_SIZE)),
        )
        for key, value in (data.get("tiles") or {}).items():
            species, tier = value
            if species in SPECIES_BY_ID and 1 <= tier <= MAX_TIER:
                state.tiles[key] = Plant(species, int(tier))
        state.bag = {
            k: int(n)
            for k, n in (data.get("bag") or {}).items()
            if k in SPECIES_BY_ID and n > 0
        }
        state.almanac = {
            k: int(t) for k, t in (data.get("almanac") or {}).items() if k in SPECIES_BY_ID
        }
        state.stats = {k: int(n) for k, n in (data.get("stats") or {}).items()}
        state.recent_rewards = list(data.get("recent") or [])[-RECENT_REWARDS_KEPT:]
        state.daily = dict(data.get("daily") or {})
        state.review_days = {int(d): int(n) for d, n in (data.get("days") or {}).items()}
        start = data.get("start")
        state.start_rid = int(start) if start is not None else None
        return state


def migrate(data: dict[str, Any]) -> dict[str, Any]:
    """Upgrade older saves to SCHEMA_VERSION. Nothing to do yet."""
    return data


def tile_key(x: int, y: int) -> str:
    return f"{x},{y}"


def parse_key(key: str) -> tuple[int, int]:
    x, y = key.split(",")
    return int(x), int(y)
