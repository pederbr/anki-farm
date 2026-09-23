"""Preview the farm UI in a normal browser, without Anki.

Serves anki_farm/web/ and fakes Anki's pycmd() bridge with the real game
rules, keeping state in memory. Run:  python3 dev/preview_server.py
then open http://localhost:8777/
"""

import json
import os
import random
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "anki_farm"
sys.path.insert(0, str(ROOT))

from game import rules  # noqa: E402
from game.state import FarmState  # noqa: E402
from game.view import catalog_json, state_json  # noqa: E402

state = FarmState()
auto_plant = False


def load_deck_panel():
    """Import anki_farm.deck_panel with just enough of aqt stubbed out."""
    import types
    from unittest import mock

    fake_mw = mock.MagicMock()
    fake_mw.addonManager.addonFromModule.return_value = "anki_farm"
    fake_mw.col.get_config.side_effect = lambda key, default=None: state.to_dict()
    stubs = {
        "aqt": types.SimpleNamespace(mw=fake_mw),
        "aqt.qt": types.SimpleNamespace(QDialog=object, QVBoxLayout=object),
        "aqt.utils": mock.MagicMock(),
        "aqt.webview": mock.MagicMock(),
    }
    sys.modules.update(stubs)
    pkg = types.ModuleType("anki_farm")
    pkg.__path__ = [str(ROOT)]
    sys.modules["anki_farm"] = pkg
    import importlib

    return importlib.import_module("anki_farm.deck_panel")


DECK_PAGE = """<!doctype html><html><head><meta charset="utf-8"><style>
body { font-family: -apple-system, sans-serif; margin: 0; padding: 20px; text-align: center; }
body.night-mode { background: #2c2c2c; color: #ddd; }
.decks { margin: 0 auto; border-collapse: collapse; }
.decks td { padding: 4px 16px; }
</style><script>function pycmd(m){ document.title = m; }</script></head>
<body class="%s"><table class="decks"><tr><th>Deck</th><th>New</th><th>Due</th></tr>
<tr><td>Japanese</td><td>20</td><td>134</td></tr><tr><td>Anatomy</td><td>10</td><td>42</td></tr></table>
<p>Studied 87 cards in 23 minutes today.</p>%s</body></html>"""
revlog_id = 0

PAGE = """<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="/web/farm.css"><script src="/web/farm.js" defer></script>
<script>
async function call(msg) {
  const r = await fetch("/cmd", {method: "POST", body: msg});
  const payload = await r.json();
  if (payload) AnkiFarm.render(payload);
}
window.pycmd = (m) => { call(m); };
window.addEventListener("DOMContentLoaded", async () => {
  AnkiFarm.init(await (await fetch("/catalog")).json());
  call("dev:state");
});
</script></head><body class="%s"><div id="farm-root"></div>
<div style="position:fixed;bottom:6px;left:6px;display:flex;gap:6px;font:13px sans-serif">
<button onclick="call('dev:review')">Review a card</button>
<button onclick="call('dev:review10')">Review 10</button>
<button onclick="call('dev:undo')">Undo last review</button>
<button onclick="call('dev:showcase')">Showcase</button>
<button onclick="call('dev:reset')">Reset</button></div>
</body></html>"""


def payload(event=None):
    return {"state": state_json(state), "autoPlant": auto_plant, "event": event}


def handle(cmd: str):
    global state, auto_plant, revlog_id
    if cmd == "dev:state":
        return payload()
    if cmd in ("dev:review", "dev:review10"):
        ev = None
        for _ in range(10 if cmd.endswith("10") else 1):
            revlog_id += 1
            sp = rules.roll_species(random)
            tile = rules.grant_seed(state, sp, revlog_id=revlog_id, auto_plant=auto_plant)
            ev = {"kind": "reward", "species": sp, "tile": tile}
        return payload(ev)
    if cmd == "dev:undo":
        if state.recent_rewards:
            rules.revoke_reward(state, state.recent_rewards[-1])
        return payload()
    if cmd == "dev:showcase":
        from game.state import Plant
        state = FarmState()
        rows = [("wheat", [1, 2, 3, 4, 5]), ("tomato", [1, 2, 3, 4, 5]),
                ("strawberry", [6, 7, 6, 7, 6]), ("coffee", [3, 5, 6, 7, 7]),
                ("sunflower", [2, 4, 5, 6, 7])]
        for y, (sp, tiers) in enumerate(rows):
            for x, t in enumerate(tiers):
                state.tiles[f"{x},{y}"] = Plant(sp, t)
                state.discover(sp, t)
        state.bag = {"rose": 3, "corn": 7, "lemon": 1}
        return payload()
    if cmd == "dev:reset":
        state = FarmState()
        return payload()
    msg = json.loads(cmd[len("farm:"):])
    op = msg["op"]
    try:
        if op == "auto_plant":
            auto_plant = bool(msg["value"])
            return payload()
        if op == "move":
            return payload(rules.move(state, msg["src"], msg["dst"]).to_dict())
        if op == "plant":
            return payload(rules.plant_from_bag(state, msg["species"], msg["tile"]).to_dict())
        if op == "plant_all":
            return payload({"kind": "plant_all", "count": rules.plant_all(state)})
        if op == "to_bag":
            rules.return_to_bag(state, msg["tile"])
            return payload({"kind": "to_bag"})
    except (rules.GameError, KeyError) as err:
        return payload({"kind": "error", "message": str(err)})
    return None


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT), **kw)

    def _json(self, obj):
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/_addons/anki_farm/"):
            self.path = self.path[len("/_addons/anki_farm") :]
        if self.path.startswith("/decks"):
            panel = load_deck_panel().panel_html({})
            body = (DECK_PAGE % ("night-mode" if "night" in self.path else "", panel)).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            return self.wfile.write(body)
        if self.path.startswith("/catalog"):
            return self._json(catalog_json())
        if self.path in ("/", "/?night"):
            body = (PAGE % ("night-mode" if "night" in self.path else "")).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            return self.wfile.write(body)
        return super().do_GET()

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        self._json(handle(self.rfile.read(n).decode()))

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8777))
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
