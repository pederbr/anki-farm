"""Game rules. Every change to FarmState goes through here.

Functions raise GameError for moves that aren't allowed; the UI simply
re-renders the current state when that happens.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from .catalog import (
    MATURE_RARITY_BOOST,
    MAX_TIER,
    PACKET_GUARANTEED_RARITY,
    PACKET_SIZE,
    PACKETS_PER_DAY,
    RARITIES,
    SPECIES_BY_ID,
    species_in_rarity,
)
from .state import CATCH_UP_DAYS, RECENT_REWARDS_KEPT, FarmState, Plant


class GameError(Exception):
    pass


@dataclass
class MoveResult:
    kind: str  # "move" | "swap" | "merge" | "plant"
    tile: str
    new_discovery: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "tile": self.tile, "new": self.new_discovery}


# ---- rewards -----------------------------------------------------------


def earns_seed(*, ease: int, review_type: int, ivl: int, time_ms: int, min_ms: float) -> bool:
    """Does this review-log entry earn a seed? Only answers that *complete*
    a card do: afterwards it sits in the review queue (a passed review, or a
    card graduating from learning). The revlog's ivl is the new interval:
    positive = days, negative = seconds for a (re)learning step.

    Used for live rewards and for catching up on phone reviews, so the two
    always agree on what counts.
    """
    real_answer = ease > 0 and 0 <= review_type <= 3  # not a manual reschedule
    return real_answer and ivl > 0 and time_ms >= min_ms


def roll_rarity(
    rng: random.Random, mature: bool = False, min_rarity: str | None = None
) -> str:
    order = list(RARITIES)
    allowed = order[order.index(min_rarity) :] if min_rarity else order
    weights = []
    for rarity in allowed:
        weight = RARITIES[rarity][1]
        if mature and rarity != "common":
            weight *= MATURE_RARITY_BOOST
        weights.append(weight)
    return rng.choices(allowed, weights=weights)[0]


def roll_species(
    rng: random.Random, mature: bool = False, min_rarity: str | None = None
) -> str:
    rarity = roll_rarity(rng, mature, min_rarity)
    return rng.choice(species_in_rarity(rarity)).id


def grant_seed(
    state: FarmState,
    species: str,
    *,
    revlog_id: int | None = None,
    auto_plant: bool = False,
    rng: random.Random | None = None,
    packet_deck: int | None = None,
    review_day: int | None = None,
) -> str | None:
    """Give the player one seed. Returns the tile it was planted on, or None
    if it went into the bag. Pass review_day when the seed pays for a review,
    so catch_up() knows that review has been rewarded."""
    _check_species(species)
    tile = None
    empty = state.empty_tiles()
    if auto_plant and empty:
        tile = (rng or random).choice(empty)
        state.tiles[tile] = Plant(species, 1)
    else:
        state.bag[species] = state.bag.get(species, 0) + 1
    state.discover(species, 1)
    state.bump_stat("seeds_earned")
    if review_day is not None:
        state.review_days[review_day] = state.review_days.get(review_day, 0) + 1
    if revlog_id is not None:
        reward: dict[str, Any] = {"rid": revlog_id, "species": species, "tile": tile}
        if packet_deck is not None:
            reward["packet"] = packet_deck
        if review_day is not None:
            reward["day"] = review_day
        state.recent_rewards.append(reward)
        del state.recent_rewards[:-RECENT_REWARDS_KEPT]
    return tile


def claim_packet(
    state: FarmState,
    *,
    day: int,
    deck_id: int,
    revlog_id: int | None = None,
    auto_plant: bool = False,
    rng: random.Random | None = None,
) -> list[str] | None:
    """Give the daily seed packet for clearing a deck, unless this deck has
    already paid out today or the daily limit is reached. Returns the seeds."""
    rng = rng or random
    if state.daily.get("day") != day:
        state.daily = {"day": day, "decks": []}
    claimed = state.daily["decks"]
    if deck_id in claimed or len(claimed) >= PACKETS_PER_DAY:
        return None
    seeds = [roll_species(rng) for _ in range(PACKET_SIZE - 1)]
    seeds.append(roll_species(rng, min_rarity=PACKET_GUARANTEED_RARITY))
    for species in seeds:
        grant_seed(
            state,
            species,
            revlog_id=revlog_id,
            auto_plant=auto_plant,
            rng=rng,
            packet_deck=deck_id,
        )
    claimed.append(deck_id)
    state.bump_stat("packets")
    return seeds


def revoke_reward(state: FarmState, reward: dict[str, Any]) -> bool:
    """Take back a seed after its review was undone. Best effort: if the seed
    has already been merged away there is nothing left to take."""
    species = reward["species"]
    tile = reward.get("tile")
    removed = False
    if tile and state.tiles.get(tile) == Plant(species, 1):
        del state.tiles[tile]
        removed = True
    elif state.bag.get(species, 0) > 0:
        state.bag[species] -= 1
        if not state.bag[species]:
            del state.bag[species]
        removed = True
    else:
        for key, plant in list(state.tiles.items()):
            if plant == Plant(species, 1):
                del state.tiles[key]
                removed = True
                break
    if removed:
        state.bump_stat("seeds_earned", -1)
    if reward in state.recent_rewards:
        state.recent_rewards.remove(reward)
    day = reward.get("day")
    if day is not None and state.review_days.get(day, 0) > 0:
        state.review_days[day] -= 1
    # undoing the review that cleared a deck makes its packet claimable again
    deck = reward.get("packet")
    claimed = state.daily.get("decks", [])
    if deck is not None and deck in claimed:
        claimed.remove(deck)
        state.bump_stat("packets", -1)
    return removed


def ensure_started(state: FarmState, now_rid: int) -> None:
    """Remember when the add-on started paying out, so reviews from before
    it was installed don't flood the bag on first sync."""
    if state.start_rid is None:
        state.start_rid = now_rid


def catch_up(
    state: FarmState,
    reviews: list[tuple[int, int, bool]],
    *,
    today: int,
    auto_plant: bool = False,
    rng: random.Random | None = None,
) -> list[str]:
    """Pay out reviews the add-on didn't see live (done on a phone, then
    synced). `reviews` is every eligible review of the last CATCH_UP_DAYS
    days as (revlog id, scheduler day, was mature). For each day, anything
    beyond the number already rewarded earns a seed. Returns the seeds."""
    rng = rng or random
    by_day: dict[int, list[bool]] = {}
    for rid, day, mature in sorted(reviews):
        if state.start_rid is not None and rid < state.start_rid:
            continue
        by_day.setdefault(day, []).append(mature)
    seeds = []
    for day, matures in sorted(by_day.items()):
        done = state.review_days.get(day, 0)
        for mature in matures[done:]:
            species = roll_species(rng, mature=mature)
            grant_seed(state, species, auto_plant=auto_plant, rng=rng, review_day=day)
            seeds.append(species)
    for day in [d for d in state.review_days if d <= today - CATCH_UP_DAYS]:
        del state.review_days[day]
    return seeds


# ---- player actions ----------------------------------------------------


def plant_from_bag(state: FarmState, species: str, tile: str) -> MoveResult:
    _check_tile(state, tile)
    if state.bag.get(species, 0) <= 0:
        raise GameError(f"no {species} seeds in the bag")
    target = state.tiles.get(tile)
    seed = Plant(species, 1)
    if target is None:
        _take_from_bag(state, species)
        state.tiles[tile] = seed
        return MoveResult("plant", tile)
    if target == seed:
        # dropping a seed on an identical seed merges straight away
        _take_from_bag(state, species)
        return _merge_into(state, tile, target)
    raise GameError("tile is occupied")


def plant_all(state: FarmState, rng: random.Random | None = None) -> int:
    """Fill empty tiles from the bag, rarest species first. Returns count."""
    rng = rng or random
    empty = state.empty_tiles()
    rng.shuffle(empty)
    rarity_rank = {r: i for i, r in enumerate(RARITIES)}
    order = sorted(
        state.bag, key=lambda s: -rarity_rank[SPECIES_BY_ID[s].rarity]
    )
    planted = 0
    for species in order:
        while state.bag.get(species, 0) > 0 and empty:
            _take_from_bag(state, species)
            state.tiles[empty.pop()] = Plant(species, 1)
            planted += 1
    return planted


def move(state: FarmState, src: str, dst: str) -> MoveResult:
    """Drag a plant from src to dst: move, merge, or swap."""
    _check_tile(state, src)
    _check_tile(state, dst)
    if src == dst:
        raise GameError("same tile")
    plant = state.tiles.get(src)
    if plant is None:
        raise GameError("nothing to move")
    target = state.tiles.get(dst)
    if target is None:
        state.tiles[dst] = state.tiles.pop(src)
        return MoveResult("move", dst)
    if can_merge(plant, target):
        del state.tiles[src]
        return _merge_into(state, dst, target)
    state.tiles[src], state.tiles[dst] = target, plant
    return MoveResult("swap", dst)


def can_merge(a: Plant, b: Plant) -> bool:
    return a == b and a.tier < MAX_TIER


def return_to_bag(state: FarmState, tile: str) -> None:
    """Pick a seed back up off the board (only tier-1 plants)."""
    _check_tile(state, tile)
    plant = state.tiles.get(tile)
    if plant is None or plant.tier != 1:
        raise GameError("only seeds can go back in the bag")
    del state.tiles[tile]
    state.bag[plant.species] = state.bag.get(plant.species, 0) + 1


# ---- internals ---------------------------------------------------------


def _merge_into(state: FarmState, tile: str, target: Plant) -> MoveResult:
    merged = Plant(target.species, target.tier + 1)
    state.tiles[tile] = merged
    state.bump_stat("merges")
    new = state.discover(merged.species, merged.tier)
    if merged.tier == MAX_TIER:
        state.bump_stat("golden_crops")
    return MoveResult("merge", tile, new_discovery=new)


def _take_from_bag(state: FarmState, species: str) -> None:
    state.bag[species] -= 1
    if not state.bag[species]:
        del state.bag[species]


def _check_species(species: str) -> None:
    if species not in SPECIES_BY_ID:
        raise GameError(f"unknown species {species!r}")


def _check_tile(state: FarmState, key: str) -> None:
    try:
        ok = state.in_bounds(key)
    except (ValueError, AttributeError):
        ok = False
    if not ok:
        raise GameError(f"bad tile {key!r}")
