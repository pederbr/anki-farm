"""The add-on's windows: the farm itself, plus the Almanac, Settings and
How to Play pages, each in its own Qt window hosting the web UI (web/farm.js).

Python is the single source of truth. The pages only render the state they
are sent and report what the player tried to do ("move this onto that").
Every open window is refreshed whenever anything changes.
"""

from __future__ import annotations

import json
import os
from typing import Any

from aqt import mw
from aqt.qt import QDialog, QVBoxLayout
from aqt.utils import disable_help_button, restoreGeom, saveGeom
from aqt.webview import AnkiWebView

from . import storage
from .game import rules, settings
from .game.view import catalog_json, state_json

# view -> (window title, default size)
VIEWS: dict[str, tuple[str, tuple[int, int]]] = {
    "farm": ("Anki Farm", (820, 640)),
    "almanac": ("Anki Farm – Almanac", (600, 680)),
    "settings": ("Anki Farm – Settings", (540, 500)),
    "howto": ("Anki Farm – How to Play", (640, 700)),
}

_windows: dict[str, FarmWindow] = {}


def web_base() -> str:
    return f"/_addons/{mw.addonManager.addonFromModule(__name__)}/web"


def asset_version() -> str:
    """Changes whenever a web file changes, so web views never show stale
    cached JS/CSS/sprites (appended to asset URLs as ?v=...)."""
    web_dir = os.path.join(os.path.dirname(__file__), "web")
    newest = 0.0
    for dirpath, _dirs, files in os.walk(web_dir):
        for name in files:
            newest = max(newest, os.path.getmtime(os.path.join(dirpath, name)))
    return str(int(newest))


def open_window(view: str) -> None:
    """Open (or bring to front) one of VIEWS in its own window."""
    if view not in VIEWS:
        return
    win = _windows.get(view)
    if win is None:
        win = _windows[view] = FarmWindow(view)
    win.show()
    win.raise_()
    win.activateWindow()


def open_farm() -> None:
    open_window("farm")
    # first visit: show the rules next to the farm
    if not storage.addon_config().get("seen_howto", False):
        storage.set_addon_config("seen_howto", True)
        open_window("howto")


def refresh_if_open(event: dict[str, Any] | None = None) -> None:
    for win in list(_windows.values()):
        win.push(event)


def close_if_open() -> None:
    for win in list(_windows.values()):
        win.close()


class FarmWindow(QDialog):
    def __init__(self, view: str) -> None:
        super().__init__(mw)
        self.view = view
        title, default_size = VIEWS[view]
        self.setWindowTitle(title)
        disable_help_button(self)

        self.web = AnkiWebView(parent=self, title=f"anki farm {view}")
        self.web.set_bridge_command(self._on_bridge, self)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.web)
        self.setLayout(layout)
        restoreGeom(self, self._geom_key(), default_size=default_size)

        base, v = web_base(), asset_version()
        self.web.stdHtml(
            '<div id="farm-root"></div>',
            head=(
                f'<link rel="stylesheet" href="{base}/farm.css?v={v}">'
                f'<script src="{base}/farm.js?v={v}" defer></script>'
                # versioned copies of farm.css's relative image URLs
                f"<style>.sprite{{background-image:url({base}/sprites/crops.png?v={v})}}"
                f".tile{{background-image:url({base}/sprites/soil.png?v={v})}}"
                f".tile.alt{{background-image:url({base}/sprites/soil_alt.png?v={v})}}</style>"
            ),
            context=self,
        )
        # eval() is queued until the page has loaded, so this is safe here
        self.web.eval(f"AnkiFarm.init({json.dumps(catalog_json())}, {json.dumps(view)})")
        self.push()

    def _geom_key(self) -> str:
        # the farm keeps its original key so its saved size survives
        return "anki_farm_dialog" if self.view == "farm" else f"anki_farm_{self.view}"

    # ---- Python -> JS --------------------------------------------------

    def push(self, event: dict[str, Any] | None = None) -> None:
        payload = {
            "state": state_json(storage.load()),
            "settings": settings.current(storage.addon_config()),
            "event": event,
        }
        self.web.eval(f"AnkiFarm.render({json.dumps(payload)})")

    # ---- JS -> Python --------------------------------------------------

    def _on_bridge(self, cmd: str) -> Any:
        if not cmd.startswith("farm:"):
            return None
        msg = json.loads(cmd[len("farm:") :])
        op = msg.get("op")

        if op == "setting":
            try:
                value = settings.clean(msg.get("key"), msg.get("value"))
            except ValueError as err:
                self.push({"kind": "error", "message": str(err)})
                return None
            storage.set_addon_config(msg["key"], value)
            refresh_if_open()
            return None

        state = storage.load()
        event: dict[str, Any] | None = None
        try:
            if op == "move":
                event = rules.move(state, msg["src"], msg["dst"]).to_dict()
            elif op == "plant":
                event = rules.plant_from_bag(state, msg["species"], msg["tile"]).to_dict()
            elif op == "plant_all":
                event = {"kind": "plant_all", "count": rules.plant_all(state)}
            elif op == "to_bag":
                rules.return_to_bag(state, msg["tile"])
                event = {"kind": "to_bag"}
            else:
                return None
        except (rules.GameError, KeyError) as err:
            # invalid move: just redraw the real state
            self.push({"kind": "error", "message": str(err)})
            return None
        storage.save(state)
        # the farm animates the move; other windows (Almanac) just redraw
        self.push(event)
        for win in list(_windows.values()):
            if win is not self:
                win.push()
        return None

    # ---- lifecycle -----------------------------------------------------

    def reject(self) -> None:
        saveGeom(self, self._geom_key())
        self.web.cleanup()
        if _windows.get(self.view) is self:
            del _windows[self.view]
        # the deck list shows the almanac, so redraw it with any new discoveries
        if mw.state == "deckBrowser":
            mw.deckBrowser.refresh()
        super().reject()

    def closeEvent(self, evt) -> None:
        self.reject()
        evt.accept()
