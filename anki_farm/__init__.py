"""Anki Farm: earn seeds by reviewing, merge them into bigger crops."""

from __future__ import annotations

from aqt import gui_hooks, mw
from aqt.qt import QAction, qconnect

from . import deck_panel, farm_dialog, rewards


def _add_toolbar_link(links: list[str], toolbar) -> None:
    links.append(
        toolbar.create_link(
            "anki_farm", "Farm", farm_dialog.open_farm, tip="Open Anki Farm", id="anki_farm"
        )
    )


def _setup() -> None:
    mw.addonManager.setWebExports(__name__, r"web/.*\.(js|css|png|ttf)")

    action = QAction("Anki Farm", mw)
    qconnect(action.triggered, farm_dialog.open_farm)
    mw.form.menuTools.addAction(action)

    gui_hooks.reviewer_did_answer_card.append(rewards.on_answer)
    gui_hooks.state_did_undo.append(rewards.on_undo)
    gui_hooks.deck_browser_will_render_content.append(deck_panel.render)
    gui_hooks.webview_did_receive_js_message.append(deck_panel.on_js_message)
    gui_hooks.top_toolbar_did_init_links.append(_add_toolbar_link)
    gui_hooks.profile_will_close.append(farm_dialog.close_if_open)


_setup()
