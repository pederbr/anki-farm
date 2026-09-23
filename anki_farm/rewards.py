"""Turn reviews into seeds, and take them back when a review is undone."""

from __future__ import annotations

import random

from anki.cards import Card
from anki.utils import ids2str
from aqt import mw
from aqt.utils import tooltip

from . import farm_dialog, storage
from .game import rules
from .game.catalog import MATURE_IVL, PACKET_MIN_REVIEWS, RARITIES, SPECIES_BY_ID


def on_answer(reviewer, card: Card, ease: int) -> None:
    # Every answer button gives the same reward, so the game never nudges
    # you towards pressing Easy.
    row = mw.col.db.first(
        "select id, time, lastIvl from revlog where cid = ? order by id desc limit 1",
        card.id,
    )
    if not row:
        return
    revlog_id, time_ms, last_ivl = row
    conf = storage.addon_config()
    if time_ms < float(conf.get("min_answer_seconds", 1.5)) * 1000:
        return

    auto_plant = bool(conf.get("auto_plant", False))
    species = rules.roll_species(random, mature=last_ivl >= MATURE_IVL)
    state = storage.load()
    tile = rules.grant_seed(state, species, revlog_id=revlog_id, auto_plant=auto_plant)

    packet = None
    if _deck_cleared():
        deck_id = mw.col.decks.get_current_id()
        if _reviews_today(deck_id) >= PACKET_MIN_REVIEWS:
            packet = rules.claim_packet(
                state,
                day=mw.col.sched.today,
                deck_id=deck_id,
                revlog_id=revlog_id,
                auto_plant=auto_plant,
            )
    storage.save(state)

    if conf.get("show_tooltips", True):
        s = SPECIES_BY_ID[species]
        where = "planted" if tile else "added to bag"
        rarity = RARITIES[s.rarity][0]
        msg = f"🌱 {s.name} seed ({rarity}) — {where}"
        if packet:
            names = ", ".join(SPECIES_BY_ID[p].name for p in packet)
            msg += f"<br>🎁 Deck cleared! Seed packet: {names}"
        tooltip(msg, period=3000 if packet else 1500)
    if packet:
        farm_dialog.refresh_if_open({"kind": "packet", "species": packet})
    else:
        farm_dialog.refresh_if_open({"kind": "reward", "species": species, "tile": tile})


def _deck_cleared() -> bool:
    """Nothing left to study in the current deck right now."""
    return sum(mw.col.sched.counts()) == 0


def _reviews_today(deck_id: int) -> int:
    day_start_ms = (mw.col.sched.day_cutoff - 86400) * 1000
    dids = ids2str(mw.col.decks.deck_and_child_ids(deck_id))
    return mw.col.db.scalar(
        f"select count() from revlog where id > ? and cid in "
        f"(select id from cards where did in {dids})",
        day_start_ms,
    )


def on_undo(_changes) -> None:
    if not mw.col:
        return
    state = storage.load()
    if not state.recent_rewards:
        return
    ids = [r["rid"] for r in state.recent_rewards]
    still_there = set(mw.col.db.list(f"select id from revlog where id in {ids2str(ids)}"))
    undone = [r for r in state.recent_rewards if r["rid"] not in still_there]
    if not undone:
        return
    for reward in undone:
        rules.revoke_reward(state, reward)
    storage.save(state)
    if storage.addon_config().get("show_tooltips", True):
        tooltip("↩︎ Review undone — seed returned", period=1500)
    farm_dialog.refresh_if_open()
