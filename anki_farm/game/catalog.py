"""Static game data: species, rarities and tiers.

Kept free of any Anki imports so it can be unit-tested outside Anki.
"""

from __future__ import annotations

from dataclasses import dataclass

MAX_TIER = 7

TIER_NAMES = {
    1: "Seed",
    2: "Sprout",
    3: "Seedling",
    4: "Young plant",
    5: "Mature crop",
    6: "Bountiful crop",
    7: "Golden crop",
}

# rarity id -> (display name, drop weight)
RARITIES: dict[str, tuple[str, float]] = {
    "common": ("Common", 60.0),
    "uncommon": ("Uncommon", 25.0),
    "rare": ("Rare", 11.0),
    "epic": ("Epic", 3.5),
    "legendary": ("Legendary", 0.5),
}

# Reviews of mature cards (interval >= MATURE_IVL days before the review)
# multiply the weight of every non-common rarity by this factor.
MATURE_IVL = 21
MATURE_RARITY_BOOST = 1.5

# Daily seed packet for clearing a deck: PACKET_SIZE seeds, the last one
# guaranteed PACKET_GUARANTEED_RARITY or better. A deck only pays out once a
# day, only after PACKET_MIN_REVIEWS reviews in it that day (so a tiny deck
# can't be farmed), and at most PACKETS_PER_DAY packets are given per day.
PACKET_SIZE = 5
PACKET_GUARANTEED_RARITY = "rare"
PACKET_MIN_REVIEWS = 10
PACKETS_PER_DAY = 3


@dataclass(frozen=True)
class Species:
    id: str
    name: str
    rarity: str
    # index in the josehzz "Farming Crops 16x16" spritesheet (reading order)
    sheet_index: int


SPECIES: tuple[Species, ...] = (
    Species("turnip", "Turnip", "common", 0),
    Species("rose", "Rose", "rare", 1),
    Species("cucumber", "Cucumber", "uncommon", 2),
    Species("tulip", "Tulip", "uncommon", 3),
    Species("tomato", "Tomato", "uncommon", 4),
    Species("melon", "Melon", "rare", 5),
    Species("eggplant", "Eggplant", "uncommon", 6),
    Species("lemon", "Lemon", "epic", 7),
    Species("pineapple", "Pineapple", "epic", 8),
    Species("rice", "Rice", "common", 9),
    Species("wheat", "Wheat", "common", 10),
    Species("grapes", "Grapes", "rare", 11),
    Species("strawberry", "Strawberry", "rare", 12),
    Species("cassava", "Cassava", "uncommon", 13),
    Species("potato", "Potato", "common", 14),
    Species("coffee", "Coffee", "legendary", 15),
    Species("orange", "Orange", "epic", 16),
    Species("avocado", "Avocado", "epic", 17),
    Species("corn", "Corn", "common", 18),
    Species("sunflower", "Sunflower", "rare", 19),
)

SPECIES_BY_ID: dict[str, Species] = {s.id: s for s in SPECIES}

# Display order for the almanac: by rarity, then name.
ALMANAC_ORDER: tuple[Species, ...] = tuple(
    sorted(SPECIES, key=lambda s: (list(RARITIES).index(s.rarity), s.name))
)


def species_in_rarity(rarity: str) -> list[Species]:
    return [s for s in SPECIES if s.rarity == rarity]


def seeds_for_tier(tier: int) -> int:
    """How many tier-1 seeds a plant of this tier is worth."""
    return 2 ** (tier - 1)
