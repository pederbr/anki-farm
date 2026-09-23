"""Almanac panel on the main deck list screen."""

from __future__ import annotations

import html
from typing import Any

from . import farm_dialog, storage
from .game.catalog import ALMANAC_ORDER, MAX_TIER, RARITIES, TIER_NAMES
from .game.view import almanac_progress

MSG_PREFIX = "anki_farm:"

# The crop sheet is 16px cells; shown at 2x on the deck list.
SCALE = 2
CELL = 16 * SCALE


def _portrait_style(sheet_index: int) -> str:
    row, col = sheet_index // 2, (sheet_index % 2) * 6
    return f"background-position: -{col * CELL}px -{row * CELL}px;"


def render(deck_browser, content) -> None:
    conf = storage.addon_config()
    if not conf.get("show_almanac_on_deck_list", True):
        return
    content.stats += panel_html(conf)


def panel_html(conf: dict[str, Any]) -> str:
    state = storage.load()
    base = farm_dialog.web_base()
    found, total = almanac_progress(state)
    bag = state.bag_total()
    is_open = "" if conf.get("almanac_collapsed", False) else " open"

    cards = []
    for s in ALMANAC_ORDER:
        best = state.almanac.get(s.id, 0)
        rarity = RARITIES[s.rarity][0]
        if best:
            name = html.escape(s.name)
            title = f"{s.name} ({rarity}) — best: {TIER_NAMES[best]}"
        else:
            name = "???"
            title = f"Undiscovered ({rarity})"
        pips = "".join(
            f'<i class="{"on" if t <= best else ""}{" gold" if t == MAX_TIER else ""}"></i>'
            for t in range(1, MAX_TIER + 1)
        )
        cards.append(
            f'<div class="afarm-card r-{s.rarity}{"" if best else " unknown"}" '
            f'title="{html.escape(title)}">'
            f'<div class="afarm-portrait" style="{_portrait_style(s.sheet_index)}"></div>'
            f'<div class="afarm-name">{name}</div>'
            f'<div class="afarm-pips">{pips}</div>'
            f"</div>"
        )

    bag_text = f"{bag} seed{'s' if bag != 1 else ''} in bag"
    return f"""
<style>
@font-face {{ font-family: "AnkiFarmPixel"; src: url("{base}/fonts/kenney-pixel.ttf"); }}
#anki-farm-almanac {{
  --af-bg: #f6ecd6; --af-frame: #8a5a33; --af-ink: #3b2a1a; --af-muted: #8b7a64;
  --af-card: #fffaf0; --af-pip: #e3d5b8;
  max-width: 760px; margin: 24px auto 0; text-align: left;
  font-family: "AnkiFarmPixel", ui-monospace, monospace; color: var(--af-ink);
}}
.night-mode #anki-farm-almanac {{
  --af-bg: #2c2218; --af-frame: #a8743f; --af-ink: #f3e6cc; --af-muted: #b19f84;
  --af-card: #3a2d20; --af-pip: #5a4733;
}}
#anki-farm-almanac details {{
  background: var(--af-bg); border: 3px solid var(--af-frame); border-radius: 6px;
  box-shadow: 0 3px 0 rgba(0,0,0,.25);
}}
#anki-farm-almanac summary {{
  cursor: pointer; list-style: none; display: flex; align-items: center; gap: 12px;
  padding: 8px 12px; font-size: 22px; line-height: 1;
}}
#anki-farm-almanac summary::-webkit-details-marker {{ display: none; }}
#anki-farm-almanac summary::before {{ content: "▸"; color: var(--af-muted); }}
#anki-farm-almanac details[open] summary::before {{ content: "▾"; }}
#anki-farm-almanac .afarm-meta {{ color: var(--af-muted); font-size: 18px; }}
#anki-farm-almanac .afarm-open {{
  margin-left: auto; font: inherit; font-size: 18px; cursor: pointer;
  background: #6aa84f; color: #fff; border: 0; border-bottom: 3px solid #3f7a2c;
  border-radius: 4px; padding: 4px 10px 2px; white-space: nowrap;
}}
#anki-farm-almanac .afarm-open:active {{ transform: translateY(2px); border-bottom-width: 1px; }}
#anki-farm-almanac .afarm-bar {{ height: 6px; margin: 0 12px 10px; background: var(--af-pip); border-radius: 3px; overflow: hidden; }}
#anki-farm-almanac .afarm-bar > b {{ display: block; height: 100%; background: #e2b53c; }}
#anki-farm-almanac .afarm-grid {{
  display: grid; grid-template-columns: repeat(auto-fill, minmax(92px, 1fr));
  gap: 8px; padding: 0 12px 12px;
}}
#anki-farm-almanac .afarm-card {{
  background: var(--af-card); border-radius: 4px; padding: 6px 4px 5px;
  display: flex; flex-direction: column; align-items: center; gap: 3px;
  border-top: 3px solid var(--rc);
}}
#anki-farm-almanac .r-common {{ --rc: #9aa39a; }}
#anki-farm-almanac .r-uncommon {{ --rc: #5fae55; }}
#anki-farm-almanac .r-rare {{ --rc: #4a8fd8; }}
#anki-farm-almanac .r-epic {{ --rc: #a35ad6; }}
#anki-farm-almanac .r-legendary {{ --rc: #e2a43c; }}
#anki-farm-almanac .afarm-portrait {{
  width: {CELL}px; height: {CELL}px; image-rendering: pixelated;
  background-image: url("{base}/sprites/crops.png");
  background-size: {192 * SCALE}px {160 * SCALE}px;
}}
#anki-farm-almanac .unknown .afarm-portrait {{ filter: brightness(0); opacity: .25; }}
#anki-farm-almanac .afarm-name {{ font-size: 16px; line-height: 1; white-space: nowrap; }}
#anki-farm-almanac .unknown .afarm-name {{ color: var(--af-muted); }}
#anki-farm-almanac .afarm-pips {{ display: flex; gap: 2px; }}
#anki-farm-almanac .afarm-pips i {{ width: 8px; height: 5px; background: var(--af-pip); border-radius: 1px; }}
#anki-farm-almanac .afarm-pips i.on {{ background: #6aa84f; }}
#anki-farm-almanac .afarm-pips i.on.gold {{ background: #e2b53c; }}
</style>
<div id="anki-farm-almanac">
  <details{is_open} data-open="{str(bool(is_open)).lower()}"
    ontoggle="if (this.dataset.open !== String(this.open)) {{ this.dataset.open = this.open; pycmd('{MSG_PREFIX}almanac:' + (this.open ? 'open' : 'closed')); }}">
    <summary>
      <span>Almanac</span>
      <span class="afarm-meta">{found}/{total} discovered · {bag_text}</span>
      <button class="afarm-open" onclick="event.preventDefault(); pycmd('{MSG_PREFIX}open');">Open farm</button>
    </summary>
    <div class="afarm-bar"><b style="width: {100 * found / total:.1f}%"></b></div>
    <div class="afarm-grid">{''.join(cards)}</div>
  </details>
</div>
"""


def on_js_message(handled: tuple[bool, Any], message: str, context: Any) -> tuple[bool, Any]:
    if not message.startswith(MSG_PREFIX):
        return handled
    cmd = message[len(MSG_PREFIX) :]
    if cmd == "open":
        farm_dialog.open_farm()
    elif cmd.startswith("almanac:"):
        storage.set_addon_config("almanac_collapsed", cmd.endswith("closed"))
    return (True, None)
