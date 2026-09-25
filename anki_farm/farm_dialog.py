"""The farm window: a Qt dialog hosting the web UI in web/farm.js.

Python is the single source of truth. The page only renders the state it is
sent and reports what the player tried to do ("move this onto that").
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
from .game import rules
from .game.view import catalog_json, state_json

GEOM_KEY = "anki_farm_dialog"

_dialog: FarmDialog | None = None


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


def open_farm() -> None:
    global _dialog
    if _dialog is None:
        _dialog = FarmDialog()
    _dialog.show()
    _dialog.raise_()
    _dialog.activateWindow()


def refresh_if_open(event: dict[str, Any] | None = None) -> None:
    if _dialog is not None:
        _dialog.push(event)


def close_if_open() -> None:
    if _dialog is not None:
        _dialog.close()


class FarmDialog(QDialog):
    def __init__(self) -> None:
        super().__init__(mw)
        self.setWindowTitle("Anki Farm")
        disable_help_button(self)

        self.web = AnkiWebView(parent=self, title="anki farm")
        self.web.set_bridge_command(self._on_bridge, self)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.web)
        self.setLayout(layout)
        restoreGeom(self, GEOM_KEY, default_size=(820, 640))

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
        self.web.eval(f"AnkiFarm.init({json.dumps(catalog_json())})")
        self.push()

    # ---- Python -> JS --------------------------------------------------

    def push(self, event: dict[str, Any] | None = None) -> None:
        conf = storage.addon_config()
        payload = {
            "state": state_json(storage.load()),
            "autoPlant": bool(conf.get("auto_plant", False)),
            "sound": bool(conf.get("sound", True)),
            "event": event,
        }
        self.web.eval(f"AnkiFarm.render({json.dumps(payload)})")

    # ---- JS -> Python --------------------------------------------------

    def _on_bridge(self, cmd: str) -> Any:
        if not cmd.startswith("farm:"):
            return None
        msg = json.loads(cmd[len("farm:") :])
        op = msg.get("op")

        if op in ("auto_plant", "sound"):
            storage.set_addon_config(op, bool(msg.get("value")))
            self.push()
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
        self.push(event)
        return None

    # ---- lifecycle -----------------------------------------------------

    def reject(self) -> None:
        global _dialog
        saveGeom(self, GEOM_KEY)
        self.web.cleanup()
        _dialog = None
        # the deck list shows the almanac, so redraw it with any new discoveries
        if mw.state == "deckBrowser":
            mw.deckBrowser.refresh()
        super().reject()

    def closeEvent(self, evt) -> None:
        self.reject()
        evt.accept()
