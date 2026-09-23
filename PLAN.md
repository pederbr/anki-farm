# Anki Farm: Design & Implementation Plan

An Anki add-on that turns reviews into a small retro, pixel-art merge game. Every card you review gives you a seed. You plant seeds on a farm grid and merge identical plants into higher tiers. Over time you expand the farm, fill in a plant almanac, and take on orders.

**Design rule:** the game must never distort studying. Rewards must not depend on which answer button you press, and the game stays out of the way while you review.

---

## 1. Core loop

```
Review a card ──► get a seed (random plant, random rarity)
      ▲                         │
      │                         ▼
 want more seeds ◄── merge 2 identical plants → next tier
                                │
                                ▼
                  max-tier crop → harvest for coins / orders
                                │
                                ▼
                  coins → expand the farm, buildings, upgrades
```

### Reward rules (anti-cheese)
| Rule | Why |
|---|---|
| Again, Hard, Good and Easy all give **1 seed** | Honest "Again" answers are never punished. "Easy" is never favoured, so the add-on can't bias your scheduling. |
| No reward if the answer took less than about 1.5 s (configurable) | Stops spam-clicking through cards. |
| Undoing a review (Ctrl+Z) takes the seed back | Keeps the numbers honest. |
| Bonus seed packet when you finish all due cards in a deck for the day | Rewards finishing, not grinding new cards. |
| Mature cards (interval ≥ 21 d) get a slightly higher rarity roll | Rewards long-term memory. You can't farm this without actually knowing the cards. |

---

## 2. Merge mechanics

- **Merge-2:** drag a plant onto an identical plant (same species and same tier) to get one plant of the next tier. This is the Merge Mansion / Travel Town style, and it gives feedback faster than merge-3.
- Seeds go into a **Seed Bag** (inventory). You plant them onto empty tiles yourself, so a full board never loses rewards.
- **Auto-plant** (config option, off by default): new seeds go straight to a random empty tile, falling back to the bag when the board is full.
- The board starts at **5×5** and can be expanded later with coins.

### Tiers (per species)
| Tier | Name | Seeds needed | Sprite idea |
|---|---|---|---|
| 1 | Seed | 1 | tiny mound |
| 2 | Sprout | 2 | two leaves |
| 3 | Seedling | 4 | small stem |
| 4 | Young plant | 8 | leafy |
| 5 | Mature crop | 16 | crop visible |
| 6 | Bountiful crop | 32 | large, sparkles |
| 7 | Golden crop ⭐ | 64 | gold palette-swap, animated |

At tier 7, one golden crop is about 64 reviews. With 100 reviews/day that's roughly one or two golden crops a day, which feels good. Tune later with real data.

### Species & rarity
The launch roster matches the 20 crops in the chosen art pack (see §4 Art):

| Rarity | Drop % | Species |
|---|---|---|
| Common | 60 | Wheat, Potato, Turnip, Rice, Corn |
| Uncommon | 25 | Tomato, Cucumber, Eggplant, Cassava, Tulip |
| Rare | 11 | Strawberry, Melon, Sunflower, Rose, Grapes |
| Epic | 3.5 | Lemon, Orange, Avocado, Pineapple |
| Legendary | 0.5 | Coffee. Later: fantasy recolours such as Moonflower (a hue-shifted Rose) and Crystal melon |

Higher rarity is worth more coins, and some plants can only be merged a limited number of times, which makes them rarer at high tiers.

---

## 3. Further progression (layered, add one at a time)

1. **Coins & harvesting.** Sell any plant: value = base × 2^(tier−1) × rarity multiplier. Tier-7 crops give a bonus.
2. **Farm expansion.** Unlock more tiles, e.g. 5×5 → 6×6 → 7×7 → 8×8 with rising costs. Fog-of-war tiles you reveal (Merge Dragons style) fit the retro feel.
3. **Almanac / collection.** A grid of every species × tier, greyed out until discovered. Completing a species' row gives a permanent perk (e.g. "+2 % chance for Tomato"). This is a strong long-term hook with almost no content cost. **It is shown on the main deck list screen** (see §4).
4. **Orders board.** NPC villagers ask for things like "2× Mature Tomato + 1× Sprout Sunflower" and pay coins, XP or special seeds. Orders refresh daily. This gives merging a purpose beyond "go up".
5. **Farmer level (XP).** Every merge and order gives XP. Levels unlock new species, buildings and cosmetics. It also provides the pacing structure.
6. **Buildings** (one-time purchases with upgrade levels):
   - **Barn:** extra storage slots off the board.
   - **Greenhouse:** increases rare+ drop chance.
   - **Compost bin:** 3 unwanted tier-1 plants become a random seed of the next rarity up.
   - **Windmill:** turns golden crops into "flour" for high-value orders.
7. **Animals.** Chickens, cows and bees produce items every *N reviews* (not real time, so they only progress while you study). Their products feed into orders.
8. **Cross-breeding.** Merge two *different* golden crops to get a hybrid species (e.g. Strawberry + Sunflower = Sunberry). This is a late-game discovery layer.
9. **Seasons.** Tied to the real calendar, each season boosts certain species. Seasonal legendaries give a reason to come back.
10. **Streak weather.** Daily study streaks bring nicer weather (sun → rainbow). Weather gives small drop bonuses. Missing a day never destroys anything; it only resets the bonus, so the game stays kind.
11. **Cosmetics.** Fences, paths, a scarecrow and farmhouse skins. Pure decoration to spend coins on once the core economy is done.

---

## 4. Technical architecture

**Target:** Anki 2.1.55+ / 23.x / 24.x / 25.x (Qt6, Python 3.9+).

> **What M1 actually built** (this differs a little from the sketch below):
> - **Layout:** flatter than planned. `__init__.py`, `rewards.py`, `storage.py`, `farm_dialog.py` and `deck_panel.py` sit at the top level, with pure logic in `game/`.
> - **Rendering:** DOM elements with CSS sprites instead of `<canvas>`. This makes drag-and-drop and hover simpler.
> - **Saving:** state is saved after every change, since it's only a few hundred bytes.
> - **Undo:** keeps the last 30 rewards and checks which of their revlog entries still exist.
> - **Answer time:** read from the revlog `time` column.

```
anki_farm/
├── __init__.py            # entry: registers hooks, menu, toolbar button
├── manifest.json
├── config.json            # user-tunable: min answer time, show toasts, etc.
├── config.md
├── game/                  # PURE PYTHON, no aqt imports → unit-testable
│   ├── catalog.py         # species, tiers, rarities, prices (data tables)
│   ├── state.py           # dataclasses + JSON (de)serialization + migrations
│   ├── rules.py           # roll_seed(), can_merge(), merge(), sell(), orders…
│   └── rng.py             # seeded RNG wrapper (deterministic tests)
├── integration/
│   ├── hooks.py           # reviewer_did_answer_card, undo handling
│   └── storage.py         # load/save via collection config
├── ui/
│   ├── farm_dialog.py     # QDialog hosting an AnkiWebView
│   └── bridge.py          # pycmd message handling JS ↔ Python
├── web/
│   ├── farm.html
│   ├── farm.js            # canvas rendering, drag-and-drop, animations
│   ├── farm.css
│   └── sprites/           # pixel-art spritesheets (PNG)
└── tests/                 # pytest for game/*
```

### Key integration points
| Concern | API |
|---|---|
| Detect a review | `aqt.gui_hooks.reviewer_did_answer_card(reviewer, card, ease)`. Use `card.time_taken()` for the minimum-time check. |
| Undo | `gui_hooks.state_did_undo` or `operation_did_execute`. Store `last_reward = {card_id, revlog_id}` and reverse it if that revlog entry disappears. |
| Persistence | `mw.col.set_config("anki_farm", state_dict)`. This **syncs through AnkiWeb**, so the farm follows you to other desktops. Include a `schema_version` for migrations. Save on dialog close and at most every N rewards, not on every card. |
| Open farm | Tools-menu action and a toolbar link via `gui_hooks.top_toolbar_did_init_links`. Optional shortcut (e.g. `F`). |
| Almanac on the deck list | `gui_hooks.deck_browser_will_render_content(deck_browser, content)`: append HTML to `content.stats`. The panel is compact: seed-bag count, coins, and the almanac grid (species rows × 7 tiers, undiscovered cells shown as silhouettes). Clicking it calls `pycmd("anki_farm:open")`, handled by `gui_hooks.webview_did_receive_js_message`, which opens the farm. The deck list redraws after each study session, so the panel is always up to date. Can be collapsed, and turned off in config. |
| Reward feedback | `aqt.utils.tooltip("🌱 +1 Tomato seed (Uncommon)")`, which is non-blocking. Optional later: a small corner badge in the reviewer via `webview_will_set_content`. |
| Serving web assets | `mw.addonManager.setWebExports(__name__, r"web/.*")`, then load the page with `/_addons/<id>/web/...` URLs. |
| JS → Python | `pycmd("merge:3,4:3,5")` handled in `webview.set_bridge_command`. Python validates everything in `rules.py` and sends the new state back with `webview.eval(...)`. |

**Python is the single source of truth.** JS only renders and sends intents like "merge A into B". This prevents desync and keeps the rules testable.

### State shape (v1)
```json
{
  "schema_version": 1,
  "board": { "w": 5, "h": 5, "tiles": { "2,3": {"species": "carrot", "tier": 3} } },
  "seed_bag": [{"species": "tomato", "tier": 1}],
  "coins": 0, "xp": 0, "level": 1,
  "almanac": { "carrot": 4 },
  "stats": { "reviews_rewarded": 0, "merges": 0 },
  "last_reward": null
}
```

### Rendering
- An HTML5 `<canvas>` with `image-rendering: pixelated` and integer scaling (32×32 sprites shown at 2× or 3×). This gives the retro look.
- Pointer events for drag-and-drop. Snap to tiles, with a merge "pop" plus a particle burst.
- **Art (chosen):**
  - **Crops:** [Farming Crops 16x16 by josehzz](https://opengameart.org/content/farming-crops-16x16). CC0, 20 crops, 5 growth stages each, plus a portrait per crop.
    - Stages 1–5 map to tiers 1–5.
    - Tier 6 is stage 5 with a sparkle overlay.
    - Tier 7 is a gold palette-swap of stage 5, done in code or pre-baked.
    - Portraits are used as almanac row icons.
  - **Tiles and farm decoration:** [Kenney Pixel Platformer Farm Expansion](https://kenney-assets.itch.io/pixel-platformer-farm-expansion). CC0, pay what you want.
  - **Why CC0 matters:** the add-on ships the PNGs to every user, which counts as redistribution. CC0 has no attribution or share-alike obligations. We'll credit the artists in `CREDITS.md` and the add-on description anyway.
  - **If we need more species:** [Pixel Farm – 26 Farm Crops by Frenchpixelle](https://frenchpixelle.itch.io/farm-crops) costs about $5 and is CC BY 4.0 (credit required). It has 4 stages per crop, and its style is close enough to mix in.
  - **Avoid** [LPC Crops](https://opengameart.org/content/lpc-crops). It is CC-BY-SA/GPL, which would force the whole add-on under a share-alike licence.
- Optional: 8-bit sounds (jsfxr) for plant, merge and harvest, with a mute toggle in the config.

---

## 5. Milestones

| # | Milestone | Scope | Done when |
|---|---|---|---|
| **M0** ✅ | Skeleton | Add-on loads, Tools menu opens an empty dialog, symlinked dev setup | Opens in Anki without errors |
| **M1** ✅ | MVP loop | Review → seed in bag (with tooltip), 5×5 board, plant from bag, merge-2, save via col config, 4 common species with placeholder coloured squares | You can play for a day of reviews |
| **M2** | Look & feel | Pixel sprites, all 7 tiers, rarity table, animations, sound, anti-cheese rules plus undo | It feels like a game |
| **M3** | Economy | Coins, selling, farm expansion, almanac | There's a reason to keep merging |
| **M4** | Goals | Orders board, farmer level/XP, first 2 buildings | Daily goals exist |
| **M5** | Depth | Animals, cross-breeding, seasons, streak weather | Long-term hooks |
| **M6** | Ship | Config UI, sync edge cases, balance pass, AnkiWeb listing, screenshots | Published |

### Dev workflow
- Symlink `anki_farm/` into `~/Library/Application Support/Anki2/addons21/anki_farm` and restart Anki to reload. Consider the "Add-on Reloader" or a debug-console `importlib.reload` for faster iteration.
- Unit-test `game/` with pytest outside Anki. Most logic lives there.
- Test in a separate Anki profile so a bug can't touch your real collection config.
- Package with `zip -r anki_farm.ankiaddon anki_farm -x '*/__pycache__/*' '*/tests/*'`.

---

## 6. Decisions
1. **Merge-2.**
2. **Seed Bag**, with an optional auto-plant setting.
3. **Almanac panel on the deck list screen.** The full farm lives in its own window.
4. **Art:** josehzz *Farming Crops 16x16* for crops and Kenney *Farm Expansion* for tiles. Both are CC0.
